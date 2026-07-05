import os
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.id3 import ID3, APIC
from mutagen.flac import Picture

# langdetect 可选依赖，缺失时检测返回空字符串
try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
    _LANGDETECT_OK = True
except ImportError:
    _LANGDETECT_OK = False
    print('[scanner] 警告: langdetect 未安装，语言检测将跳过。pip install langdetect')

AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.ogg', '.aac', '.m4a', '.wma', '.ape'}

# 缩略图生成进度（全局，供 API 轮询）
_thumb_progress = {'scanning': False, 'current': 0, 'total': 0, 'path': ''}


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


def extract_cover(mutagen_file, file_path):
    """提取封面图片保存到临时目录，返回路径"""
    cover_dir = os.path.join(os.environ.get('TEMP', '/tmp'), 'melodybox-covers')
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

    file_hash = hashlib.md5(file_path.encode()).hexdigest()
    cover_path = os.path.join(cover_dir, f'{file_hash}{ext}')
    if not os.path.exists(cover_path):
        try:
            with open(cover_path, 'wb') as f:
                f.write(picture_data)
        except Exception:
            return ''

    return cover_path


def pre_generate_thumbs_batch(cover_paths, max_workers=4):
    """批量预生成缩略图（线程池并行），扫描完成后调用"""
    global _thumb_progress
    if not cover_paths:
        _thumb_progress['scanning'] = False
        return

    from threading import Lock
    cover_dir = os.environ.get('TEMP', '/tmp')
    sizes = [72, 80, 200, 280, 292, 332]
    total = len(cover_paths)
    done = [0]
    lock = Lock()
    _thumb_progress = {'scanning': True, 'current': 0, 'total': total, 'path': ''}

    def _generate_one(cover_path):
        basename = os.path.basename(cover_path)
        try:
            with lock:
                _thumb_progress['path'] = basename
            from PIL import Image
            img = Image.open(cover_path)
            for size in sizes:
                thumb_dir = os.path.join(cover_dir, 'melodybox-thumbs', str(size))
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
                _thumb_progress['current'] = done[0]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(_generate_one, cover_paths))

    _thumb_progress['scanning'] = False


def detect_language(title, lyrics, artist=''):
    """
    检测歌曲语言。
    优先用歌词检测（文本更长更准确），歌词不足时用标题+艺术家。
    纯音乐占位文本（"纯音乐，请欣赏"）会被跳过，直接用标题+艺术家判定。
    带字符集启发式规则：含假名→日语，含谚文→韩语，克服 langdetect 短文本误判。
    返回 ISO 639-1 语言代码（zh/ja/en/ko/de/ru/...），失败返回 ''。
    """
    if not _LANGDETECT_OK:
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
        lang = detect(text)
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
        print(f'[scanner] 解析失败: {file_path} - {e}')

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
    """INSERT OR IGNORE 专辑，返回 album_id"""
    name = album_name.strip()
    if not name:
        return None
    cursor.execute(
        'INSERT OR IGNORE INTO albums (title, cover_url, year, genre) VALUES (?, ?, ?, ?)',
        (name, cover_url, year, genre)
    )
    cursor.execute('SELECT id FROM albums WHERE title = ? AND year = ?', (name, year))
    row = cursor.fetchone()
    return row['id'] if row else None


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


def scan_and_store(db_conn, dir_paths, progress_callback=None):
    """扫描目录并存储到 SQLite 数据库，同时填充 artists/albums/song_artist/song_album 表"""
    # 重置缩略图进度（避免上次扫描的残留数据影响本次）
    global _thumb_progress
    _thumb_progress = {'scanning': False, 'current': 0, 'total': 0, 'path': ''}

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

        # 收集新封面
        if is_new and meta['cover_url']:
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

                # 更新时先清除旧的关联关系再重建
                if song_id is not None:
                    cursor.execute('DELETE FROM song_artist WHERE song_id = ?', (song_id,))
                    cursor.execute('DELETE FROM song_album WHERE song_id = ?', (song_id,))

            # ---- 建立艺术家和专辑的关联 ----
            if song_id is not None:
                _handle_song_relations(cursor, song_id, meta)

                # ---- 新插入的歌曲：重连孤立的 play_stats / play_history 记录 ----
                if is_new:
                    _reconnect_orphaned_play_stats(cursor, song_id, meta['fingerprint'])
                    _reconnect_orphaned_play_history(cursor, song_id, meta['fingerprint'])

        except Exception as e:
            print(f'[scanner] DB错误: {file_path} - {e}')
            errors += 1

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
            # 清理关联表
            placeholders_ids = ','.join(['?'] * len(deleted_song_ids))
            cursor.execute(f'DELETE FROM song_artist WHERE song_id IN ({placeholders_ids})',
                           deleted_song_ids)
            cursor.execute(f'DELETE FROM song_album WHERE song_id IN ({placeholders_ids})',
                           deleted_song_ids)
            # 将 play_stats 中的记录置为孤儿（song_id 置 NULL，保留 fingerprint 以便后续重连）
            cursor.execute(f'UPDATE play_stats SET song_id = NULL WHERE song_id IN ({placeholders_ids})',
                           deleted_song_ids)

        # 删除歌曲记录
        placeholders = ','.join(['?'] * len(deleted_file_paths))
        cursor.execute(f'DELETE FROM songs WHERE file_path IN ({placeholders})',
                       list(deleted_file_paths))
        db_conn.commit()

    cursor.close()

    # 异步批量生成缩略图（后台线程，不阻塞扫描完成通知）
    if new_cover_paths:
        import threading
        paths_copy = list(new_cover_paths)
        threading.Thread(target=pre_generate_thumbs_batch, args=(paths_copy,), daemon=True).start()

    return {
        'total': total,
        'inserted': inserted,
        'updated': updated,
        'deleted': deleted_count,
        'errors': errors
    }
