import os
import hashlib
import logging
import re
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger('melodybox.scan')


def _get_cover_dir():
    """封面缓存目录：%LOCALAPPDATA%/melodybox/covers/"""
    base = os.environ.get('LOCALAPPDATA',
                          os.path.join(os.path.expanduser('~'), 'AppData', 'Local'))
    return os.path.join(base, 'melodybox', 'covers')


def _get_thumbs_dir():
    """缩略图缓存目录：%LOCALAPPDATA%/melodybox/thumbs/"""
    base = os.environ.get('LOCALAPPDATA',
                          os.path.join(os.path.expanduser('~'), 'AppData', 'Local'))
    return os.path.join(base, 'melodybox', 'thumbs')


# 重型第三方库（mutagen / langdetect）改为函数内延迟导入，
# 避免 Flask 启动时连带加载，加快开发与打包启动速度。

AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.ogg', '.aac', '.m4a', '.wma', '.ape'}

# 缩略图生成进度（全局，供 API 轮询）
_thumb_progress = {'scanning': False, 'current': 0, 'total': 0, 'path': ''}
# 串行化缩略图批次：本地扫描与云端上传可能同时触发，共用一份进度必须互斥
_thumb_lock = threading.Lock()


def _ensure_tables(db_conn):
    """确保 artists、albums、song_artist、song_album、play_stats 等表存在"""
    cursor = db_conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            image_url TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            cover_url TEXT DEFAULT '',
            year INTEGER DEFAULT 0,
            genre TEXT DEFAULT '',
            UNIQUE(title, year)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS song_artist (
            song_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            role TEXT DEFAULT 'main',
            PRIMARY KEY (song_id, artist_id),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS song_album (
            song_id INTEGER NOT NULL,
            album_id INTEGER NOT NULL,
            PRIMARY KEY (song_id, album_id),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_song_artist_artist ON song_artist(artist_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_song_album_album ON song_album(album_id)')

    # 确保 songs 表有 fingerprint 列
    try:
        cursor.execute('ALTER TABLE songs ADD COLUMN fingerprint TEXT DEFAULT ""')
    except Exception:
        pass

    # 确保 play_stats 表存在（用于播放统计）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS play_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER,
            fingerprint TEXT DEFAULT '',
            play_count INTEGER DEFAULT 0,
            last_played TEXT DEFAULT '',
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE SET NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_play_stats_fingerprint ON play_stats(fingerprint)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_play_stats_song_id ON play_stats(song_id)')

    # 歌单/收藏关联的指纹孤儿暂存表：移除文件夹/删除歌曲时把歌单关联
    # 暂存于此（song 级联删除后 song_id 无从恢复），文件重新扫描入库时
    # 按指纹重连，使歌单/收藏内容在移除-重加文件夹后保持完整。
    # 元数据快照列用于歌单页展示"文件缺失"的灰色失效条目。
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orphaned_playlist_songs (
            playlist_id INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(playlist_id, fingerprint)
        )
    ''')
    for col, decl in (('file_path', 'TEXT DEFAULT ""'), ('title', 'TEXT DEFAULT ""'),
                      ('artist', 'TEXT DEFAULT ""'), ('album', 'TEXT DEFAULT ""'),
                      ('cover_url', 'TEXT DEFAULT ""'), ('duration', 'INTEGER DEFAULT 0')):
        try:
            cursor.execute(f'ALTER TABLE orphaned_playlist_songs ADD COLUMN {col} {decl}')
        except Exception:
            pass  # 列已存在

    db_conn.commit()
    cursor.close()


def scan_directory(dir_path):
    """递归扫描目录，返回所有音频文件路径列表"""
    results = []
    try:
        for entry in os.scandir(dir_path):
            if entry.is_dir(follow_symlinks=False):
                results.extend(scan_directory(entry.path))
            elif entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in AUDIO_EXTENSIONS:
                    results.append(entry.path)
    except (PermissionError, OSError):
        pass
    return results


def extract_cover(mutagen_file, file_path=''):
    """提取内嵌封面保存到缓存目录，返回缓存路径。

    以封面"内容哈希"命名（旧实现用 md5(音频文件路径)：路径不变则封面文件
    永不更新，音频内嵌封面更新会被旧缓存吃掉）。内容哈希下封面内容变化
    → 文件名变化 → 数据库 cover_url 更新 → 缩略图按新名补齐 → 前端
    thumb:// 的 immutable 缓存（URL 含文件名）自然失效，实现封面更新后的
    精准替换；同一张封面图被多首歌引用时也自动去重。
    file_path 参数保留以兼容云端上传调用点，已不参与命名。
    """
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.id3 import APIC

    cover_dir = _get_cover_dir()
    os.makedirs(cover_dir, exist_ok=True)
    picture_data = None
    ext = '.jpg'

    try:
        if isinstance(mutagen_file, MP3):
            for tag in mutagen_file.tags.values():
                if isinstance(tag, APIC):
                    picture_data = tag.data
                    ext_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}
                    ext = ext_map.get(tag.mime, '.jpg')
                    break
        elif isinstance(mutagen_file, FLAC):
            if mutagen_file.pictures:
                pic = mutagen_file.pictures[0]
                picture_data = pic.data
                ext_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}
                ext = ext_map.get(pic.mime, '.jpg')
        else:
            if hasattr(mutagen_file, 'tags') and mutagen_file.tags:
                for tag in mutagen_file.tags.values():
                    if hasattr(tag, 'data') and hasattr(tag, 'mime'):
                        picture_data = tag.data
                        ext_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}
                        ext = ext_map.get(tag.mime, '.jpg')
                        break
    except Exception:
        pass

    if not picture_data:
        return ''

    cover_hash = hashlib.md5(picture_data).hexdigest()
    cover_path = os.path.join(cover_dir, f'{cover_hash}{ext}')
    if not os.path.exists(cover_path):
        try:
            with open(cover_path, 'wb') as f:
                f.write(picture_data)
        except Exception:
            return ''

    return cover_path


_THUMB_SIZES = [72, 80, 200, 280, 292, 332]


def filter_pending_covers(cover_paths):
    """筛出还缺缩略图的封面。

    放在扫描线程里同步执行，这样扫描一结束就能给前端准确的总数：
    没有待生成项时直接归零，避免前端把"空批次"误当成"正在生成"。
    """
    if not cover_paths:
        return []
    thumbs_base = _get_thumbs_dir()
    pending = []
    for cover_path in cover_paths:
        basename = os.path.basename(cover_path)
        try:
            need = any(not os.path.exists(os.path.join(thumbs_base, str(s), basename))
                       for s in _THUMB_SIZES)
        except Exception:
            need = True
        if need:
            pending.append(cover_path)
    return pending


def pre_generate_thumbs_batch(cover_paths, max_workers=4, pre_filtered=False):
    """批量预生成缩略图（线程池并行），扫描完成后调用。

    - 先筛出真正缺少尺寸的封面：全部已存在时不产生进度（避免"空转进度条"）
    - 用 _thumb_lock 串行化整批任务，进度只对应唯一在跑的一批
    - pre_filtered=True 表示调用方已筛过，避免重复 stat
    """
    global _thumb_progress
    if not cover_paths:
        _thumb_progress = {'scanning': False, 'current': 0, 'total': 0, 'path': ''}
        return

    with _thumb_lock:
        try:
            thumbs_base = _get_thumbs_dir()
            sizes = _THUMB_SIZES

            pending = list(cover_paths) if pre_filtered else filter_pending_covers(cover_paths)

            if not pending:
                _thumb_progress = {'scanning': False, 'current': 0, 'total': 0, 'path': ''}
                return

            total = len(pending)
            done = [0]
            lock = threading.Lock()
            # 本批次独占的进度对象：即使其它线程重置全局变量，也不会把数字写串
            progress = {'scanning': True, 'current': 0, 'total': total, 'path': ''}
            _thumb_progress = progress

            def _generate_one(cover_path):
                basename = os.path.basename(cover_path)
                try:
                    with lock:
                        progress['path'] = basename
                    from PIL import Image
                    with Image.open(cover_path) as img:
                        for size in sizes:
                            thumb_dir = os.path.join(thumbs_base, str(size))
                            os.makedirs(thumb_dir, exist_ok=True)
                            thumb_path = os.path.join(thumb_dir, basename)
                            if os.path.exists(thumb_path):
                                continue
                            tmp = thumb_path + '.tmp'
                            thumb = img.copy()
                            thumb.thumbnail((size, size), Image.LANCZOS)
                            fmt = img.format or 'JPEG'
                            thumb.save(tmp, format=fmt, quality=82)
                            os.replace(tmp, thumb_path)
                except Exception:
                    pass
                finally:
                    with lock:
                        done[0] += 1
                        progress['current'] = done[0]

            try:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    list(executor.map(_generate_one, pending))
            finally:
                progress['scanning'] = False
        except Exception:
            # 任何异常都要把进度归位，否则前端会永远停在"正在生成缩略图"
            _thumb_progress = {'scanning': False, 'current': 0, 'total': 0, 'path': ''}
            raise


def detect_language(title, lyrics, artist=''):
    """
    检测歌曲语言。
    优先用歌词检测（文本更长更准确），歌词不足时用标题+艺术家。
    纯音乐占位文本（"纯音乐，请欣赏"）会被跳过，直接用标题+艺术家判定。
    带字符集启发式规则：含假名→日语，含谚文→韩语，克服 langdetect 短文本误判。
    返回 ISO 639-1 语言代码（zh/ja/en/ko/de/ru/...），失败返回 ''。
    """
    try:
        from langdetect import detect as _ld_detect, DetectorFactory
        DetectorFactory.seed = 0
    except Exception:
        return ''

    lyrics = (lyrics or '').strip()

    # 纯音乐占位文本：固定格式 "纯音乐,请欣赏" / "纯音乐，请欣赏"
    _INSTRUMENTAL_PLACEHOLDERS = ['纯音乐,请欣赏', '纯音乐，请欣赏', '纯音乐 请欣赏']
    if any(p in lyrics for p in _INSTRUMENTAL_PLACEHOLDERS):
        return 'inst'

    # 优先用歌词（取前 800 字符足够判断语言）
    text = lyrics[:800]
    # 剥离 LRC 时间戳 [mm:ss.xx] 和元数据标签（如 [ti:]、[ar:]）
    text = re.sub(r'\[\d{2}:\d{2}[.\d]*\]', '', text)
    text = re.sub(r'\[\w{2}:[^\]]*\]', '', text)
    text = text.strip()
    if len(text) < 15:
        text = f"{title} {artist}".strip()

    if len(text) < 5:
        return ''

    # 字符集启发式：仅短文本时覆盖 langdetect（长文本 langdetect 更可靠）
    # 含少量外文字符的歌词（如作曲者名含谚文）不应误判
    SHORT_TEXT_THRESHOLD = 30
    if len(text) < SHORT_TEXT_THRESHOLD:
        # 日语假名：平假名 U+3040-309F，片假名 U+30A0-30FF
        has_kana = any('\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' for c in text)
        if has_kana:
            return 'ja'

        # 韩语谚文：U+AC00-D7AF（音节），U+1100-11FF（字母）
        has_hangul = any('\uac00' <= c <= '\ud7af' or '\u1100' <= c <= '\u11ff' for c in text)
        if has_hangul:
            return 'ko'

    # 大量 CJK 汉字 + 无假名/谚文 → 必为中文（langdetect 对文学化中文有误判）
    # 使用比例制：CJK 占比 > 50% 且无假名无谚文 → 中文
    # 日文虽大量用汉字，但必混假名；韩文虽用汉字，但必混谚文
    cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    has_kana_any = any('\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' for c in text)
    has_hangul_any = any('\uac00' <= c <= '\ud7af' or '\u1100' <= c <= '\u11ff' for c in text)
    if cjk_count >= 20 and not has_kana_any and not has_hangul_any:
        non_space = len([c for c in text if not c.isspace()])
        if non_space > 0 and cjk_count / non_space >= 0.5:
            return 'zh-cn'

    try:
        lang = _ld_detect(text)
        # langdetect 对短/纯 CJK 文本经常误判为 ko（如纯音乐日文标题）
        # 韩语必有谚文，无谚文 + langdetect=ko → 假阳性，根据假名修正
        if lang == 'ko' and not has_hangul_any and cjk_count > 0:
            return 'ja' if has_kana_any else 'zh-cn'
        return lang
    except Exception:
        return ''


def clean_lyrics(text):
    """清洗歌词中的转义字符：\n \r \xa0 \t 等还原为实际字符"""
    if not text:
        return ''
    text = text.replace('\\n', '\n').replace('\\r', '\n').replace('\\r\\n', '\n')
    text = text.replace('\\xa0', ' ').replace('\\t', '\t')
    text = text.replace("\\'", "'").replace('\\"', '"')

    # 解码字面量 \uXXXX（如 \u3000 \u2005）为真实 Unicode 字符
    text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)

    # 剥离外层包裹：["..."]、['...']、'...' 等
    t = text.strip()
    if t.startswith('["') and t.endswith('"]'):
        t = t[2:-2]
    elif t.startswith("['") and t.endswith("']"):
        t = t[2:-2]
    elif t.startswith("'") and t.endswith("'"):
        t = t[1:-1]
    elif t.startswith('"') and t.endswith('"'):
        t = t[1:-1]

    # 去除 BOM 头等不可见控制字符（保留换行和制表符）
    cleaned = []
    for ch in t:
        cp = ord(ch)
        if cp < 0x20 and cp not in (0x09, 0x0a, 0x0d):
            continue  # 丢弃其他控制字符
        if cp == 0xa0:
            cleaned.append(' ')   # \xa0 → 普通空格
        elif cp == 0x0d:
            cleaned.append('\n')  # \r → 换行
        elif cp in (0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a):
            cleaned.append(' ')   # 各种 Unicode 空格 → 普通空格
        elif cp == 0x202f:
            cleaned.append(' ')   # 窄不换行空格
        elif cp == 0x205f:
            cleaned.append(' ')   # 中等数学空格
        elif cp == 0x3000:
            cleaned.append(' ')   # 全角空格 → 普通空格
        else:
            cleaned.append(ch)
    return ''.join(cleaned)


def extract_lyrics(mutagen_file, file_path):
    """提取歌词"""
    from mutagen.flac import FLAC
    from mutagen.mp3 import MP3

    lyrics = ''

    try:
        if isinstance(mutagen_file, FLAC):
            lyrics = mutagen_file.get('LYRICS', '') or ''
        elif isinstance(mutagen_file, MP3):
            from mutagen.id3 import USLT
            for tag in mutagen_file.tags.values():
                if isinstance(tag, USLT):
                    lyrics = tag.text
                    break
            if not lyrics:
                for tag in mutagen_file.tags.values():
                    if hasattr(tag, 'desc') and tag.desc == 'LYRICS':
                        lyrics = tag.text
                        break
        else:
            for key in ('LYRICS', 'Unsynchronized lyric', 'lyrics', 'Lyrics'):
                if key in mutagen_file:
                    lyrics = mutagen_file[key][0] if isinstance(mutagen_file[key], list) else str(mutagen_file[key])
                    break
    except Exception:
        pass

    if not lyrics and isinstance(mutagen_file, FLAC):
        try:
            lyrics = mutagen_file.get('LYRICS', '') or ''
        except Exception:
            pass

    raw = str(lyrics) if lyrics else ''
    return clean_lyrics(raw)


def parse_number_from_tag(tag, default=0):
    """从 tag 字符串中提取数值，如 '5/12' → 5, '05' → 5"""
    if not tag:
        return default
    tag = str(tag).strip()
    if '/' in tag:
        tag = tag.split('/')[0]
    try:
        return int(tag)
    except ValueError:
        return default


def parse_metadata(file_path):
    """解析单个文件的元数据，返回包含 fingerprint 字段的字典"""
    from mutagen import File as MutagenFile

    result = {
        'title': '',
        'artist': '',
        'album': '',
        'cover_url': '',
        'lyrics': '',
        'year': 0,
        'genre': '',
        'duration': 0,
        'bitrate': 0,
        'sample_rate': 0,
        'bit_depth': 0,
        'quality': '',
        'file_size': 0,
        'file_mtime': 0,
        'disc_number': 0,
        'track_number': 0,
        'fingerprint': '',
        'lang': ''
    }

    try:
        stat = os.stat(file_path)
        result['file_size'] = stat.st_size
        result['file_mtime'] = stat.st_mtime
    except Exception:
        pass

    try:
        audio = MutagenFile(file_path, easy=True)
        if audio is None:
            raise ValueError('Unsupported format')

        result['duration'] = int(audio.info.length) if audio.info and hasattr(audio.info, 'length') else 0
        result['bitrate'] = int(audio.info.bitrate) if audio.info and hasattr(audio.info, 'bitrate') else 0
        result['sample_rate'] = int(audio.info.sample_rate) if audio.info and hasattr(audio.info, 'sample_rate') else 0
        result['bit_depth'] = int(audio.info.bits_per_sample) if audio.info and hasattr(audio.info, 'bits_per_sample') else 0

        if audio.tags:
            result['title'] = str(audio.get('title', [''])[0])
            artist_list = audio.get('artist', [])
            result['artist'] = ' / '.join(str(a) for a in artist_list) if artist_list else ''
            result['album'] = str(audio.get('album', [''])[0])
            result['genre'] = str(audio.get('genre', [''])[0])
            try:
                result['year'] = int(str(audio.get('date', ['0'])[0])[:4])
            except (ValueError, IndexError):
                result['year'] = 0

            result['track_number'] = parse_number_from_tag(audio.get('tracknumber', [None])[0])
            result['disc_number'] = parse_number_from_tag(audio.get('discnumber', [None])[0])

        # 音质标签判定
        ext = os.path.splitext(file_path)[1].lower()
        lossy_formats = {'.mp3', '.aac', '.m4a', '.ogg', '.wma'}
        if ext in lossy_formats:
            result['quality'] = 'HQ'
        else:
            bd = result['bit_depth']
            sr = result['sample_rate']
            if bd >= 24 and sr >= 96000:
                result['quality'] = 'Hi-Res'
            elif bd > 16 or sr > 44100:
                result['quality'] = 'CD+'
            else:
                result['quality'] = 'CD'

        full_audio = MutagenFile(file_path)
        if full_audio:
            result['cover_url'] = extract_cover(full_audio, file_path)
            result['lyrics'] = extract_lyrics(full_audio, file_path)

    except Exception as e:
        pass

    # 计算指纹：md5(title|artist|album) — 与 stats.make_fingerprint 保持一致
    fp_str = f"{result['title']}|{result['artist']}|{result['album']}".strip().lower()
    result['fingerprint'] = hashlib.md5(fp_str.encode()).hexdigest()

    # 检测语言
    result['lang'] = detect_language(result['title'], result['lyrics'], result['artist'])

    return result


def _upsert_artist(cursor, artist_name):
    """INSERT OR IGNORE 单个艺术家，返回 artist_id"""
    name = artist_name.strip()
    if not name:
        return None
    cursor.execute('INSERT OR IGNORE INTO artists (name) VALUES (?)', (name,))
    cursor.execute('SELECT id FROM artists WHERE name = ?', (name,))
    row = cursor.fetchone()
    return row['id'] if row else None


def _upsert_album(cursor, album_name, cover_url, year, genre):
    """INSERT OR IGNORE 专辑，返回 album_id；已存在时封面跟随最新内嵌封面刷新"""
    name = album_name.strip()
    if not name:
        return None
    cursor.execute(
        'INSERT OR IGNORE INTO albums (title, cover_url, year, genre) VALUES (?, ?, ?, ?)',
        (name, cover_url, year, genre)
    )
    cursor.execute('SELECT id, cover_url FROM albums WHERE title = ? AND year = ?', (name, year))
    row = cursor.fetchone()
    if row is None:
        return None
    # 内容哈希命名下歌曲封面更新 → 专辑封面同步刷新（旧行为是 INSERT OR
    # IGNORE 后永不更新，专辑页会一直停留在旧封面）
    if cover_url and row['cover_url'] != cover_url:
        cursor.execute('UPDATE albums SET cover_url = ? WHERE id = ?', (cover_url, row['id']))
    return row['id']


def _handle_song_relations(cursor, song_id, meta):
    """处理歌曲的艺术家和专辑关联关系"""
    # ---- 艺术家 ----
    artist_str = meta.get('artist', '')
    if artist_str:
        artist_names = [a.strip() for a in artist_str.split('/') if a.strip()]
        for a_name in artist_names:
            artist_id = _upsert_artist(cursor, a_name)
            if artist_id is not None:
                cursor.execute(
                    'INSERT OR IGNORE INTO song_artist (song_id, artist_id, role) VALUES (?, ?, ?)',
                    (song_id, artist_id, 'main')
                )

    # ---- 专辑 ----
    album_name = meta.get('album', '')
    if album_name:
        album_id = _upsert_album(
            cursor, album_name,
            meta.get('cover_url', ''),
            meta.get('year', 0),
            meta.get('genre', '')
        )
        if album_id is not None:
            cursor.execute(
                'INSERT OR IGNORE INTO song_album (song_id, album_id) VALUES (?, ?)',
                (song_id, album_id)
            )


def _reconnect_orphaned_play_stats(cursor, song_id, fingerprint):
    """将指纹匹配的孤立 play_stats 记录重新关联到新插入的歌曲"""
    if not fingerprint:
        return
    cursor.execute(
        'UPDATE play_stats SET song_id = ? WHERE song_id IS NULL AND fingerprint = ?',
        (song_id, fingerprint)
    )


def _reconnect_orphaned_play_history(cursor, song_id, fingerprint):
    """将指纹匹配的孤立 play_history 记录重新关联到新插入的歌曲"""
    if not fingerprint:
        return
    cursor.execute(
        'UPDATE play_history SET song_id = ? WHERE song_id IS NULL AND fingerprint = ?',
        (song_id, fingerprint)
    )


def _reconnect_orphaned_playlist_songs(cursor, song_id, fingerprint):
    """将指纹匹配的孤儿暂存歌单/收藏关联恢复到新插入的歌曲。

    移除文件夹或扫描删除歌曲时，歌单关联（playlist_song，外键 CASCADE）会随之
    消失；删除前先把 (playlist_id, fingerprint) 暂存到 orphaned_playlist_songs，
    此处按指纹恢复。恢复时过滤已删除的歌单，恢复后清掉对应暂存行。
    """
    if not fingerprint:
        return
    cursor.execute('''
        SELECT op.playlist_id
        FROM orphaned_playlist_songs op
        JOIN playlists p ON p.id = op.playlist_id
        WHERE op.fingerprint = ?
    ''', (fingerprint,))
    rows = cursor.fetchall()
    if not rows:
        cursor.execute('DELETE FROM orphaned_playlist_songs WHERE fingerprint = ?', (fingerprint,))
        return
    for r in rows:
        cursor.execute(
            'INSERT OR IGNORE INTO playlist_song (playlist_id, song_id) VALUES (?, ?)',
            (r['playlist_id'], song_id)
        )
    cursor.execute('DELETE FROM orphaned_playlist_songs WHERE fingerprint = ?', (fingerprint,))


def _stage_orphan_playlist_links(cursor, song_ids):
    """删除歌曲前，把它们的歌单/收藏关联按指纹暂存到 orphaned_playlist_songs。

    同时快照歌曲元数据（file_path/title/artist/album/cover_url/duration），
    供歌单页展示"文件缺失"的灰色失效条目。UPSERT 保证旧暂存行的元数据
    也能在再次删除时补全。
    """
    if not song_ids:
        return
    placeholders = ','.join(['?'] * len(song_ids))
    cursor.execute(f'''
        INSERT INTO orphaned_playlist_songs
            (playlist_id, fingerprint, file_path, title, artist, album, cover_url, duration)
        SELECT ps.playlist_id, s.fingerprint, s.file_path, s.title, s.artist,
               s.album, s.cover_url, s.duration
        FROM playlist_song ps
        JOIN songs s ON s.id = ps.song_id
        WHERE ps.song_id IN ({placeholders}) AND s.fingerprint != ''
        ON CONFLICT(playlist_id, fingerprint) DO UPDATE SET
            file_path = COALESCE(excluded.file_path, file_path),
            title = COALESCE(excluded.title, title),
            artist = COALESCE(excluded.artist, artist),
            album = COALESCE(excluded.album, album),
            cover_url = COALESCE(excluded.cover_url, cover_url),
            duration = COALESCE(excluded.duration, duration)
    ''', song_ids)


def delete_songs_from_db(cursor, song_ids, preserve_footprints=True):
    """从音乐库删除歌曲的公共内核（不删除源文件），返回删除的歌曲数。

    所有删除入口（单曲/批量移除、移除文件夹、扫描清理消失文件）统一走
    此函数，保证附属数据处理行为一致。

    preserve_footprints=True（保留歌曲足迹）：
      - 歌单/收藏关联按指纹暂存（含元数据快照），重导同指纹歌曲自动恢复；
      - play_stats / play_history 的 song_id 置 NULL（保留指纹），重导自动重连。
    preserve_footprints=False（不留足迹）：
      - 歌单关联随外键级联直接删除，不暂存；
      - play_stats / play_history 真删，且这些指纹的历史孤儿行一并删除
        （同一首歌此前被删过一次留下的待重连数据也彻底清除）。
    两种模式共同：清理 song_artist / song_album / song_vectors(local)，
    并失效推荐/搜索的向量内存缓存。
    """
    if not song_ids:
        return 0
    placeholders = ','.join(['?'] * len(song_ids))

    if preserve_footprints:
        _stage_orphan_playlist_links(cursor, song_ids)
    # else: 不暂存，playlist_song 由外键 ON DELETE CASCADE 直接删除

    cursor.execute(
        f'SELECT DISTINCT fingerprint FROM songs WHERE id IN ({placeholders}) AND fingerprint != ""',
        song_ids)
    fingerprints = [r[0] for r in cursor.fetchall()]

    cursor.execute(f'DELETE FROM song_artist WHERE song_id IN ({placeholders})', song_ids)
    cursor.execute(f'DELETE FROM song_album WHERE song_id IN ({placeholders})', song_ids)
    cursor.execute(
        f"DELETE FROM song_vectors WHERE song_id IN ({placeholders}) AND source = 'local'",
        song_ids)

    if preserve_footprints:
        cursor.execute(
            f'UPDATE play_stats SET song_id = NULL WHERE song_id IN ({placeholders})', song_ids)
        cursor.execute(
            f'UPDATE play_history SET song_id = NULL WHERE song_id IN ({placeholders})', song_ids)
    else:
        cursor.execute(f'DELETE FROM play_stats WHERE song_id IN ({placeholders})', song_ids)
        cursor.execute(f'DELETE FROM play_history WHERE song_id IN ({placeholders})', song_ids)
        if fingerprints:
            fp_ph = ','.join(['?'] * len(fingerprints))
            # 无痕：连此前删除留下的待重连孤儿行一起清掉
            cursor.execute(
                f'DELETE FROM play_stats WHERE song_id IS NULL AND fingerprint IN ({fp_ph})',
                fingerprints)
            cursor.execute(
                f'DELETE FROM play_history WHERE song_id IS NULL AND fingerprint IN ({fp_ph})',
                fingerprints)

    cursor.execute(f'DELETE FROM songs WHERE id IN ({placeholders})', song_ids)

    try:
        from services.recommender import invalidate_embedding_cache
        invalidate_embedding_cache()
    except Exception:
        pass
    return len(song_ids)


def scan_and_store(db_conn, dir_paths, progress_callback=None):
    """扫描目录并存储到 SQLite 数据库，同时填充 artists/albums/song_artist/song_album 表"""
    # 重置缩略图进度：仅当没有批次正在生成时清空，避免覆盖正在跑的进度
    global _thumb_progress
    if _thumb_lock.acquire(blocking=False):
        try:
            _thumb_progress = {'scanning': False, 'current': 0, 'total': 0, 'path': ''}
        finally:
            _thumb_lock.release()

    # 确保相关表存在
    _ensure_tables(db_conn)

    # 收集所有音频文件
    all_files = []
    for dir_path in dir_paths:
        if os.path.exists(dir_path):
            all_files.extend(scan_directory(dir_path))

    total = len(all_files)
    inserted = 0
    updated = 0
    errors = 0

    cursor = db_conn.cursor()

    # 收集新封面路径，扫描完成后批量生成缩略图
    new_cover_paths = []

    # 加载已有文件记录（用于增量扫描）
    cursor.execute('SELECT file_path, file_mtime FROM songs')
    existing = {row['file_path']: row['file_mtime'] for row in cursor.fetchall()}

    for i, file_path in enumerate(all_files):
        if progress_callback:
            progress_callback(i + 1, total, file_path)

        # ---- 增量：mtime 未变则跳过 ----
        current_mtime = None
        try:
            current_mtime = os.stat(file_path).st_mtime
        except Exception:
            pass

        if file_path in existing and existing[file_path] == current_mtime:
            continue

        # ---- 解析元数据 ----
        meta = parse_metadata(file_path)
        if not meta['title']:
            meta['title'] = os.path.splitext(os.path.basename(file_path))[0]

        is_new = file_path not in existing

        # 收集需检查缩略图的封面：新歌与更新歌统一收集。
        # 内容哈希命名下封面更新 → 新文件名 → 缩略图必然缺失 → 本批会重建；
        # 未变化的歌其缩略图已齐全，pre_generate_thumbs_batch 内部会跳过。
        if meta['cover_url']:
            new_cover_paths.append(meta['cover_url'])

        try:
            if is_new:
                cursor.execute('''
                    INSERT INTO songs (title, artist, album, cover_url, lyrics, year, genre,
                        duration, bitrate, sample_rate, bit_depth, quality,
                        file_size, file_mtime, file_path,
                        disc_number, track_number, fingerprint, lang)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    meta['title'], meta['artist'], meta['album'], meta['cover_url'],
                    meta['lyrics'], meta['year'], meta['genre'], meta['duration'],
                    meta['bitrate'], meta['sample_rate'], meta['bit_depth'], meta['quality'],
                    meta['file_size'], meta['file_mtime'],
                    file_path,
                    meta['disc_number'], meta['track_number'],
                    meta['fingerprint'], meta['lang']
                ))
                song_id = cursor.lastrowid
                inserted += 1
            else:
                # 更新已有歌曲（含 fingerprint、lang），清空旧的 embedding 以便重新生成
                cursor.execute('''
                    UPDATE songs SET title=?, artist=?, album=?, cover_url=?,
                        lyrics=?, year=?, genre=?, duration=?, bitrate=?,
                        sample_rate=?, bit_depth=?, quality=?,
                        file_size=?, file_mtime=?,
                        disc_number=?, track_number=?, fingerprint=?, lang=?,
                        embedding = NULL,
                        audio_embedding = NULL,
                        updated_at=datetime('now','localtime')
                    WHERE file_path=?
                ''', (
                    meta['title'], meta['artist'], meta['album'], meta['cover_url'],
                    meta['lyrics'], meta['year'], meta['genre'], meta['duration'],
                    meta['bitrate'], meta['sample_rate'], meta['bit_depth'], meta['quality'],
                    meta['file_size'], meta['file_mtime'],
                    meta['disc_number'], meta['track_number'],
                    meta['fingerprint'], meta['lang'],
                    file_path
                ))
                # 获取 song_id
                cursor.execute('SELECT id FROM songs WHERE file_path = ?', (file_path,))
                row = cursor.fetchone()
                song_id = row['id'] if row else None
                updated += 1

                # 重构版：清掉向量行，使其按新元数据重新生成
                if song_id is not None:
                    cursor.execute(
                        "DELETE FROM song_vectors WHERE song_id = ? AND source = 'local'",
                        (song_id,)
                    )

                # 更新时先清除旧的关联关系再重建
                if song_id is not None:
                    cursor.execute('DELETE FROM song_artist WHERE song_id = ?', (song_id,))
                    cursor.execute('DELETE FROM song_album WHERE song_id = ?', (song_id,))

            # ---- 建立艺术家和专辑的关联 ----
            if song_id is not None:
                _handle_song_relations(cursor, song_id, meta)

                # ---- 新插入的歌曲：重连孤立的 play_stats / play_history / 歌单关联 ----
                if is_new:
                    _reconnect_orphaned_play_stats(cursor, song_id, meta['fingerprint'])
                    _reconnect_orphaned_play_history(cursor, song_id, meta['fingerprint'])
                    _reconnect_orphaned_playlist_songs(cursor, song_id, meta['fingerprint'])

        except Exception as e:
            errors += 1
            logger.warning('解析失败: %s (%s)', file_path, e)

        # 每完成一首有变更的歌曲立即提交，避免整个扫描期间长期占用数据库写锁
        # （否则扫描过程中播放/跳过等统计上报会因写锁等待超时返回 500）
        db_conn.commit()

    db_conn.commit()

    # ---- 更新艺术家封面：取该艺术家下第一张有封面的歌曲封面 ----
    cursor.execute('''
        UPDATE artists SET image_url = (
            SELECT s.cover_url FROM songs s
            JOIN song_artist sa ON s.id = sa.song_id
            WHERE sa.artist_id = artists.id AND s.cover_url != ''
            LIMIT 1
        )
    ''')
    db_conn.commit()

    # ---- 清除已删除文件的记录（仅限被扫描的目录内） ----
    dir_likes = ' OR '.join(['file_path LIKE ?'] * len(dir_paths))
    cursor.execute(f'SELECT id, file_path FROM songs WHERE {dir_likes}',
                   [f'{d}%' for d in dir_paths])
    db_paths_in_scope = {row['file_path']: row['id'] for row in cursor.fetchall()}

    deleted_file_paths = set(db_paths_in_scope.keys()) - set(all_files)
    deleted_count = len(deleted_file_paths)

    if deleted_file_paths:
        deleted_song_ids = [db_paths_in_scope[fp] for fp in deleted_file_paths
                            if db_paths_in_scope.get(fp) is not None]

        if deleted_song_ids:
            # 统一删除内核（保留足迹模式）：暂存歌单关联、置空播放数据，
            # 清理关联表与向量、失效推荐缓存
            delete_songs_from_db(cursor, deleted_song_ids, preserve_footprints=True)

        # 删除歌曲记录
        placeholders = ','.join(['?'] * len(deleted_file_paths))
        cursor.execute(f'DELETE FROM songs WHERE file_path IN ({placeholders})',
                       list(deleted_file_paths))
        db_conn.commit()

    # 异步批量生成缩略图（后台线程，不阻塞扫描完成通知）
    # 先同步筛出真正需要生成的封面：扫描一结束时前端就能拿到准确结果，
    # 没有待生成项时立即归零，避免前端一直停在"正在生成缩略图"
    pending_covers = filter_pending_covers(new_cover_paths)
    if pending_covers:
        _thumb_progress = {'scanning': True, 'current': 0, 'total': len(pending_covers), 'path': ''}
        threading.Thread(
            target=pre_generate_thumbs_batch,
            args=(pending_covers,),
            kwargs={'pre_filtered': True},
            daemon=True,
        ).start()
    else:
        _thumb_progress = {'scanning': False, 'current': 0, 'total': 0, 'path': ''}

    # ---- 孤儿封面/缩略图 GC ----
    # 内容哈希命名下封面更新后旧文件不再被任何歌曲/专辑引用，删除它们防止
    # 缓存目录无限膨胀。仅按 songs + albums 的 cover_url 判定引用；跳过
    # .tmp（缩略图批次可能正在写）。缩略图批次写入的都是被引用的文件名，
    # 与 GC 的删除集合不相交，先后顺序无影响。
    _gc_orphan_covers(cursor, keep_tmp=True)

    cursor.close()

    return {
        'total': total,
        'inserted': inserted,
        'updated': updated,
        'deleted': deleted_count,
        'errors': errors
    }


def _gc_orphan_covers(cursor, keep_tmp=False):
    """删除 covers/ 与 thumbs/ 中不被 songs.cover_url / albums.cover_url 引用的文件。

    cursor 须来自已提交全部写事务的连接（扫描末尾调用）。返回删除的文件数，
    出错返回 -1。
    """
    removed = 0
    try:
        cursor.execute(
            "SELECT DISTINCT cover_url FROM songs WHERE cover_url != '' "
            "UNION SELECT DISTINCT cover_url FROM albums WHERE cover_url != ''"
        )
        keep = {os.path.basename(row['cover_url']) for row in cursor.fetchall()}
        # 云端歌曲封面与本地共用同一缓存目录，必须纳入引用集合
        try:
            cursor.execute(
                "SELECT DISTINCT cover_url FROM cloud_songs WHERE cover_url != ''")
            keep |= {os.path.basename(row['cover_url']) for row in cursor.fetchall()}
        except Exception:
            pass  # 老库无 cloud_songs 表时跳过该来源
        # 失效歌单条目的封面快照同样被引用（歌单页"文件缺失"灰行要显示封面）
        try:
            cursor.execute(
                "SELECT DISTINCT cover_url FROM orphaned_playlist_songs WHERE cover_url != ''")
            keep |= {os.path.basename(row['cover_url']) for row in cursor.fetchall()}
        except Exception:
            pass

        cover_dir = _get_cover_dir()
        if os.path.isdir(cover_dir):
            for name in os.listdir(cover_dir):
                if name in keep or (keep_tmp and name.endswith('.tmp')):
                    continue
                try:
                    os.remove(os.path.join(cover_dir, name))
                    removed += 1
                except Exception:
                    pass

        thumbs_base = _get_thumbs_dir()
        if os.path.isdir(thumbs_base):
            for size in os.listdir(thumbs_base):
                size_dir = os.path.join(thumbs_base, size)
                if not os.path.isdir(size_dir):
                    continue
                for name in os.listdir(size_dir):
                    if name in keep or (keep_tmp and name.endswith('.tmp')):
                        continue
                    try:
                        os.remove(os.path.join(size_dir, name))
                        removed += 1
                    except Exception:
                        pass
        if removed:
            logger.info('封面GC: 清理孤儿文件 %d 个', removed)
        return removed
    except Exception:
        logger.error('封面GC异常:\n%s', traceback.format_exc())
        return -1
