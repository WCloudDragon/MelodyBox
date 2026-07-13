"""云端曲库路由 — 管理员 CRUD + 音频流（含网络延迟模拟）"""
from flask import Blueprint, request, jsonify, current_app, Response
import os
import re
import sqlite3
import random
import time
import threading

from routes.auth import token_required

cloud_bp = Blueprint('cloud', __name__, url_prefix='/api/cloud')


# OPTIONS preflight 由 Flask-CORS 全局处理，不需要 blueprint 级别拦截


def get_db():
    return current_app.get_db()


def _admin_required(f):
    """管理员权限装饰器（需配合 token_required 使用）"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.user_role != 'admin':
            return jsonify({'error': '仅管理员可操作'}), 403
        return f(*args, **kwargs)
    return decorated


# ========== 延迟模拟 ==========

# 网络模式配置：(名称, 最小延迟s, 最大延迟s, 是否分段)
NETWORK_MODES = {
    'off':     ('关闭延迟', 0, 0, False),
    '4g':      ('4G 网络', 0.3, 0.8, True),
    '3g':      ('3G 网络', 1.0, 3.0, True),
    'slow':    ('弱网环境', 2.0, 5.0, True),
}

_current_mode = '4g'


def simulate_delay():
    """根据当前网络模式模拟延迟"""
    _, mn, mx, _ = NETWORK_MODES.get(_current_mode, NETWORK_MODES['4g'])
    if mn <= 0 and mx <= 0:
        return
    delay = random.uniform(mn, mx)
    time.sleep(delay)


def stream_cloud_audio(file_path, start=0, end=None, is_range=False):
    """分段流式发送音频文件，模拟真实网络传输
    start/end: 支持 HTTP Range 请求的字节范围（end 为 inclusive）
    is_range:  是否为 Range 请求（seek），跳过初始连接延迟
    """
    _, mn, mx, chunked = NETWORK_MODES.get(_current_mode, NETWORK_MODES['4g'])

    if not os.path.exists(file_path):
        yield b''
        return

    file_size = os.path.getsize(file_path)
    if end is None:
        end = file_size - 1
    byte_count = end - start + 1

    # 初始连接延迟（Range/seek 请求跳过，因连接已建立）
    if not is_range and (mn > 0 or mx > 0):
        time.sleep(random.uniform(min(0.2, mn), min(0.5, mx)))

    try:
        with open(file_path, 'rb') as f:
            f.seek(start)
            remaining = byte_count
            chunk_size = 65536  # 64KB
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                if chunked:
                    time.sleep(random.uniform(max(0.01, mn / 50), max(0.05, mx / 50)))
                yield chunk
    except GeneratorExit:
        pass
    except Exception as e:
        pass


# ========== 歌曲 CRUD ==========

@cloud_bp.route('/songs', methods=['GET'])
@token_required
def get_cloud_songs():
    """获取云端曲库歌曲列表（管理后台用，含下架歌曲 + 覆盖元数据）"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            SELECT cs.*,
                   COALESCE(cm.title, cs.title) AS meta_title,
                   COALESCE(cm.artist, cs.artist) AS meta_artist,
                   COALESCE(cm.album, cs.album) AS meta_album,
                   COALESCE(cm.genre, cs.genre) AS meta_genre,
                   cm.cover_url AS meta_cover_url,
                   cm.lyrics AS meta_lyrics,
                   cm.updated_at AS meta_updated_at,
                   CASE WHEN cm.cloud_song_id IS NOT NULL THEN 1 ELSE 0 END AS has_custom_meta
            FROM cloud_songs cs
            LEFT JOIN cloud_metadata cm ON cm.cloud_song_id = cs.id
            ORDER BY cs.created_at DESC
        ''')
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        songs = [{
            'id': r['id'],
            'title': r['meta_title'] or '未知歌曲',
            'artist': r['meta_artist'] or '未知艺术家',
            'album': r['meta_album'] or '未知专辑',
            'file_path': r['file_path'],
            'cover': r['meta_cover_url'] or r['cover_url'] or None,
            'year': r['year'] or None,
            'genre': r['meta_genre'] or '未知',
            'duration': r['duration'] or 0,
            'file_size': r['file_size'] or 0,
            'lang': r['lang'] or '',
            'status': r['status'] or 'online',
            'created_at': r['created_at'],
            'source': 'cloud',
            # 原始 mutagen 值（用于编辑弹窗回显）
            'original_title': r['title'],
            'original_artist': r['artist'],
            'original_album': r['album'],
            'original_genre': r['genre'],
            'original_cover_url': r['cover_url'],
            # 自定义元数据（管理员覆盖的值）
            'custom_title': r['title'] if r['has_custom_meta'] else None,
            'custom_artist': r['artist'] if r['has_custom_meta'] else None,
            'custom_album': r['album'] if r['has_custom_meta'] else None,
            'custom_genre': r['genre'] if r['has_custom_meta'] else None,
            'custom_cover_url': r['meta_cover_url'],
            'custom_lyrics': r['meta_lyrics'],
            'has_custom_meta': bool(r['has_custom_meta']),
        } for r in rows]

        return jsonify({'songs': songs, 'total': len(songs)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@cloud_bp.route('/songs', methods=['POST'])
@token_required
@_admin_required
def add_cloud_songs():
    """管理员添加云端歌曲（支持批量文件路径）"""
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400

    file_paths = data.get('file_paths', [])
    if not file_paths:
        return jsonify({'error': '请提供 file_paths 列表'}), 400

    import mutagen
    import hashlib

    # 封面提取（复用 scanner 逻辑）
    from services.scanner import extract_cover, extract_lyrics, pre_generate_thumbs_batch

    db = get_db()
    cursor = db.cursor()
    added = 0
    skipped = 0
    errors = []
    cover_paths_to_thumb = []  # 收集需要生成缩略图的封面路径

    # 展开文件夹路径——将目录中的音频文件提取为文件列表
    AUDIO_EXTS = {'.mp3', '.flac', '.wav', '.ogg', '.aac', '.m4a', '.wma', '.opus'}
    expanded_paths = []
    for fp in file_paths:
        if os.path.isdir(fp):
            found = 0
            for root, dirs, files in os.walk(fp):
                for f in files:
                    if os.path.splitext(f)[1].lower() in AUDIO_EXTS:
                        expanded_paths.append(os.path.join(root, f))
                        found += 1
            if found == 0:
                errors.append(f'文件夹中未发现音频文件: {fp}')
        elif os.path.isfile(fp):
            expanded_paths.append(fp)
        else:
            errors.append(f'路径不存在: {fp}')
    file_paths = expanded_paths

    for fp in file_paths:

        try:
            af = mutagen.File(fp, easy=True)
            if not af:
                errors.append(f'无法解析音频: {fp}')
                continue

            title = af.get('title', [os.path.splitext(os.path.basename(fp))[0]])[0]
            artist = af.get('artist', [''])[0]
            album = af.get('album', [''])[0]
            genre = af.get('genre', [''])[0]
            year = 0
            try: year = int(af.get('date', ['0'])[0][:4])
            except: pass

            info = mutagen.File(fp)
            duration = info.info.length if hasattr(info, 'info') else 0
            bitrate = getattr(info.info, 'bitrate', 0) if hasattr(info, 'info') else 0
            sample_rate = getattr(info.info, 'sample_rate', 0) if hasattr(info, 'info') else 0
            file_size = os.path.getsize(fp)

            # 指纹
            fp_str = f"{title}|{artist}|{album}"
            fingerprint = hashlib.md5(fp_str.encode()).hexdigest()

            # 提取封面 + 歌词
            cover_url = ''
            lyrics = ''
            try:
                full_mf = mutagen.File(fp)
                if full_mf:
                    cover_url = extract_cover(full_mf, fp)
                    lyrics = extract_lyrics(full_mf, fp)
                    if cover_url:
                        cover_paths_to_thumb.append(cover_url)
                    else:
                        pass
                    if lyrics:
                        pass
            except Exception as ex:
                pass

            # 检查重复
            cursor.execute('SELECT id FROM cloud_songs WHERE fingerprint = ? OR file_path = ?',
                           (fingerprint, fp))
            if cursor.fetchone():
                skipped += 1
                continue

            cursor.execute('''
                INSERT INTO cloud_songs (title, artist, album, file_path, cover_url, lyrics, genre, year,
                    duration, bitrate, sample_rate, file_size, fingerprint)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (title, artist, album, fp, cover_url, lyrics, genre, year,
                  duration, bitrate, sample_rate, file_size, fingerprint))
            added += 1
        except Exception as e:
            errors.append(f'{os.path.basename(fp)}: {str(e)}')

    # 批量生成缩略图
    if cover_paths_to_thumb:
        pre_generate_thumbs_batch(cover_paths_to_thumb)

    db.commit()
    cursor.close()
    db.close()

    return jsonify({
        'success': True,
        'added': added,
        'skipped': skipped,
        'errors': errors,
        'message': f'成功添加 {added} 首歌曲' + (f'，{skipped} 首已存在' if skipped else '')
    })


@cloud_bp.route('/songs/<int:song_id>', methods=['DELETE'])
@token_required
@_admin_required
def remove_cloud_song(song_id):
    """管理员删除云端歌曲"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id FROM cloud_songs WHERE id = ?', (song_id,))
        if not cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'error': '歌曲不存在'}), 404

        cursor.execute('DELETE FROM cloud_songs WHERE id = ?', (song_id,))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'success': True, 'message': '已从云端曲库移除'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== 元数据编辑 ==========

@cloud_bp.route('/songs/<int:song_id>/metadata', methods=['PUT'])
@token_required
@_admin_required
def update_cloud_metadata(song_id):
    """管理员修改云端歌曲元数据（逐字段覆盖，NULL=恢复 mutagen 默认值）"""
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400

    allowed_fields = ['title', 'artist', 'album', 'genre', 'cover_url', 'lyrics']
    updates = {k: data[k] for k in allowed_fields if k in data}
    if not updates:
        return jsonify({'error': '未提供有效字段'}), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id FROM cloud_songs WHERE id = ?', (song_id,))
        if not cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'error': '歌曲不存在'}), 404

        # INSERT OR REPLACE 逐字段覆盖
        # NULL 值 = 恢复默认（删除该行对应列）
        has_non_null = any(v is not None and v != '' for v in updates.values())
        if has_non_null:
            columns = ', '.join(updates.keys())
            placeholders = ', '.join([f':{k}' for k in updates.keys()])
            upsert_sql = f'''
                INSERT INTO cloud_metadata (cloud_song_id, {columns}, updated_at)
                VALUES (:cloud_song_id, {placeholders}, datetime('now','localtime'))
                ON CONFLICT(cloud_song_id) DO UPDATE SET
                {', '.join([f'{k} = excluded.{k}' for k in updates.keys()])},
                updated_at = excluded.updated_at
            '''
            cursor.execute(upsert_sql, {'cloud_song_id': song_id, **updates})
        else:
            # 所有字段都为空 → 删除覆盖行，恢复默认
            cursor.execute('DELETE FROM cloud_metadata WHERE cloud_song_id = ?', (song_id,))

        db.commit()
        cursor.close()
        db.close()
        return jsonify({'success': True, 'message': '元数据已更新'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== 上下架管理 ==========

@cloud_bp.route('/songs/<int:song_id>/status', methods=['PUT'])
@token_required
@_admin_required
def toggle_cloud_song_status(song_id):
    """管理员切换歌曲上下架状态"""
    data = request.get_json(force=True, silent=True) or {}
    new_status = data.get('status', '')
    if new_status not in ('online', 'offline'):
        return jsonify({'error': '状态仅可为 online 或 offline'}), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('UPDATE cloud_songs SET status = ? WHERE id = ?', (new_status, song_id))
        if cursor.rowcount == 0:
            cursor.close()
            db.close()
            return jsonify({'error': '歌曲不存在'}), 404
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'success': True, 'status': new_status, 'message': f'已{"上架" if new_status == "online" else "下架"}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== 音频流 ==========

@cloud_bp.route('/stream', methods=['GET', 'OPTIONS'])
def cloud_stream():
    """云端歌曲音频流（含网络延迟模拟 + HTTP Range 支持）"""
    # OPTIONS 预检：返回必要 CORS 头（配合 crossOrigin='anonymous' 的 Audio 元素）
    if request.method == 'OPTIONS':
        resp = jsonify({'ok': True})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Range, Content-Type'
        resp.headers['Access-Control-Max-Age'] = '86400'
        return resp

    file_path = request.args.get('path', '')
    if not file_path or not os.path.isfile(file_path):
        return jsonify({'error': f'文件不存在: {file_path}'}), 404

    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        '.mp3': 'audio/mpeg', '.flac': 'audio/flac', '.wav': 'audio/wav',
        '.ogg': 'audio/ogg', '.m4a': 'audio/mp4', '.aac': 'audio/aac',
        '.wma': 'audio/x-ms-wma',
    }
    mime = mime_map.get(ext, 'application/octet-stream')
    file_size = os.path.getsize(file_path)

    # 处理 HTTP Range 请求（浏览器拖动进度条时触发）
    range_header = request.headers.get('Range', '')
    if range_header:
        match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            start = int(match.group(1))
            end_str = match.group(2)
            end = int(end_str) if end_str else file_size - 1
            content_length = end - start + 1

            resp = Response(
                stream_cloud_audio(file_path, start=start, end=end, is_range=True),
                status=206,
                mimetype=mime,
                headers={
                    'Content-Range': f'bytes {start}-{end}/{file_size}',
                    'Content-Length': str(content_length),
                    'Accept-Ranges': 'bytes',
                    'Access-Control-Allow-Origin': '*',
                    'Cache-Control': 'no-cache',
                }
            )
            return resp

    # 完整下载（首次播放或没有 Range 头时）
    return Response(
        stream_cloud_audio(file_path),
        mimetype=mime,
        headers={
            'Content-Length': str(file_size),
            'Accept-Ranges': 'bytes',
            'Access-Control-Allow-Origin': '*',
            'Cache-Control': 'no-cache',
        }
    )


# ========== 网络模式切换 ==========

@cloud_bp.route('/network-mode', methods=['GET'])
@token_required
def get_network_mode():
    return jsonify({
        'mode': _current_mode,
        'label': NETWORK_MODES[_current_mode][0],
        'modes': [{'key': k, 'label': v[0]} for k, v in NETWORK_MODES.items()]
    })


@cloud_bp.route('/network-mode', methods=['PUT'])
@token_required
@_admin_required
def set_network_mode():
    global _current_mode
    data = request.get_json(force=True, silent=True) or {}
    mode = data.get('mode', '')
    if mode not in NETWORK_MODES:
        return jsonify({'error': f'无效模式，可选: {list(NETWORK_MODES.keys())}'}), 400
    _current_mode = mode
    return jsonify({'success': True, 'mode': mode, 'label': NETWORK_MODES[mode][0]})
