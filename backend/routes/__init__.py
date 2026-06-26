from flask import Blueprint, request, jsonify, current_app, send_file
import os
import sqlite3
import threading
from PIL import Image

music_bp = Blueprint('music', __name__, url_prefix='/api/music')


@music_bp.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        return '', 200


def get_db():
    """获取数据库连接"""
    return current_app.get_db()


def row_to_song(row):
    """将 sqlite3.Row 转换为前端期望的格式"""
    return {
        'path': row['file_path'],
        'name': os.path.basename(row['file_path']),
        'title': row['title'] or os.path.splitext(os.path.basename(row['file_path']))[0],
        'artist': row['artist'] or '未知艺术家',
        'album': row['album'] or '未知专辑',
        'year': row['year'] or None,
        'genre': row['genre'] or '未知',
        'duration': row['duration'] or 0,
        'bitrate': row['bitrate'] or 0,
        'sampleRate': row['sample_rate'] or 0,
        'bitDepth': row['bit_depth'] or 0,
        'quality': row['quality'] or '',
        'cover': row['cover_url'] or None,
        'lyrics': row['lyrics'] or '',
        'url': None,  # 由前端协议层填充
        'file_size': row['file_size'],
        'disc_number': row['disc_number'],
        'track_number': row['track_number'],
    }


# ==================== 歌曲列表 ====================

@music_bp.route('/songs')
def get_songs():
    """分页获取歌曲列表，支持搜索、排序、筛选"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 50, type=int)
    search = request.args.get('search', '').strip()
    sort_key = request.args.get('sort_key', 'title')
    sort_order = request.args.get('sort_order', 'asc')
    genre = request.args.get('genre', '').strip()
    artist = request.args.get('artist', '').strip()

    if page_size > current_app.config['MAX_PAGE_SIZE']:
        page_size = current_app.config['MAX_PAGE_SIZE']
    offset = (page - 1) * page_size

    # 允许排序的字段映射（防注入）
    sort_whitelist = {
        'title': 'title',
        'artist': 'artist',
        'album': 'album',
        'duration': 'duration',
        'year': 'year',
        'genre': 'genre',
    }
    sort_col = sort_whitelist.get(sort_key, 'title')
    sort_dir = 'DESC' if sort_order == 'desc' else 'ASC'

    where_clauses = []
    params = []

    if search:
        where_clauses.append('(title LIKE ? OR artist LIKE ? OR album LIKE ?)')
        like_val = f'%{search}%'
        params.extend([like_val, like_val, like_val])

    if genre:
        where_clauses.append('genre = ?')
        params.append(genre)

    if artist:
        where_clauses.append('artist = ?')
        params.append(artist)

    where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'

    try:
        db = get_db()
        cursor = db.cursor()

        # 总数
        cursor.execute(f'SELECT COUNT(*) as total FROM songs WHERE {where_sql}', params)
        total = cursor.fetchone()['total']

        # 分页数据
        cursor.execute(
            f'SELECT * FROM songs WHERE {where_sql} ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?',
            params + [page_size, offset]
        )
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        songs = [row_to_song(r) for r in rows]

        return jsonify({
            'songs': songs,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@music_bp.route('/songs/<int:song_id>')
def get_song(song_id):
    """获取单首歌曲"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM songs WHERE id = ?', (song_id,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        if not row:
            return jsonify({'error': '歌曲不存在'}), 404

        return jsonify(row_to_song(row))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@music_bp.route('/songs/by-path')
def get_song_by_path():
    """根据文件路径获取歌曲"""
    file_path = request.args.get('path', '')
    if not file_path:
        return jsonify({'error': '缺少 path 参数'}), 400
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM songs WHERE file_path = ?', (file_path,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        if not row:
            return jsonify({'error': '歌曲不存在'}), 404

        return jsonify(row_to_song(row))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 专辑 / 艺术家 / 流派 ====================

@music_bp.route('/albums')
def get_albums():
    """获取所有专辑"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            SELECT a.id, a.title as name, a.cover_url as cover, a.year, a.genre,
                   COUNT(sa.song_id) as track_count
            FROM albums a
            JOIN song_album sa ON a.id = sa.album_id
            GROUP BY a.id
            ORDER BY a.title ASC
        ''')
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        albums = [{
            'id': r['id'],
            'name': r['name'],
            'cover': r['cover'],
            'year': r['year'],
            'genre': r['genre'] or '',
            'track_count': r['track_count']
        } for r in rows]

        return jsonify(albums)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@music_bp.route('/artists')
def get_artists():
    """获取所有艺术家"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            SELECT a.id, a.name, a.image_url, COUNT(sa.song_id) as track_count
            FROM artists a
            JOIN song_artist sa ON a.id = sa.artist_id
            GROUP BY a.id
            ORDER BY a.name ASC
        ''')
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        artists = [{
            'id': r['id'],
            'name': r['name'],
            'image_url': r['image_url'] or None,
            'track_count': r['track_count']
        } for r in rows]

        return jsonify(artists)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@music_bp.route('/genres')
def get_genres():
    """获取所有流派"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            SELECT genre, COUNT(*) as track_count
            FROM songs
            WHERE genre != '' AND genre IS NOT NULL
            GROUP BY genre
            ORDER BY genre ASC
        ''')
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        return jsonify([r['genre'] for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 扫描 ====================

@music_bp.route('/scan', methods=['POST'])
def scan_music():
    """扫描目录并入库，同时同步到 scan_directories 表"""
    from services.scanner import scan_and_store

    data = request.get_json(force=True)
    dirs = data.get('directories', [])

    if not dirs:
        return jsonify({'error': '请提供目录列表'}), 400

    try:
        db = get_db()
        result = scan_and_store(db, dirs)

        # 同步到 scan_directories 表（文件夹管理功能）
        cursor = db.cursor()
        for d in dirs:
            try:
                cursor.execute('INSERT OR IGNORE INTO scan_directories (path) VALUES (?)', (d,))
            except Exception:
                pass
        db.commit()
        cursor.close()
        db.close()

        result['directories'] = dirs
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@music_bp.route('/scan-status')
def scan_status():
    """获取当前库统计信息"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT COUNT(*) as total FROM songs')
        total = cursor.fetchone()['total']

        cursor.execute('SELECT COUNT(*) as album_count FROM albums')
        album_count = cursor.fetchone()['album_count']

        cursor.execute('SELECT COUNT(*) as artist_count FROM artists')
        artist_count = cursor.fetchone()['artist_count']

        cursor.execute('SELECT COALESCE(SUM(duration), 0) as total_duration FROM songs')
        total_duration = cursor.fetchone()['total_duration']

        cursor.close()
        db.close()

        return jsonify({
            'total': total,
            'album_count': album_count,
            'artist_count': artist_count,
            'total_duration': total_duration
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 封面 ====================

@music_bp.route('/cover')
def serve_cover():
    """提供封面图片，支持 ?thumb=N 生成缩略图（宽高上限 N×N）"""
    path = request.args.get('path', '')
    if not path or not os.path.exists(path):
        return '', 404

    # 安全校验：只允许在封面缓存目录内
    cover_dir = current_app.config['COVER_DIR']
    if not os.path.realpath(path).startswith(os.path.realpath(cover_dir)):
        return '', 403

    thumb = request.args.get('thumb', type=int)
    if not thumb or thumb <= 0:
        resp = send_file(path)
        resp.cache_control.max_age = 86400
        resp.cache_control.public = True
        return resp

    # 缩略图缓存目录：%TEMP%/melodybox-thumbs/{N}/
    thumb_dir = os.path.join(os.path.dirname(cover_dir), 'melodybox-thumbs', str(thumb))
    os.makedirs(thumb_dir, exist_ok=True)
    thumb_path = os.path.join(thumb_dir, os.path.basename(path))

    # 缩略图已存在，直接返回（不可变，缓存一年）
    if os.path.exists(thumb_path):
        resp = send_file(thumb_path)
        resp.cache_control.max_age = 31536000
        resp.cache_control.public = True
        resp.cache_control.immutable = True
        return resp

    # 首次请求：先返回原图（不阻塞加载），后台线程生成缩略图供下次使用
    print(f'[cover:thumb] async generating {thumb}px for {os.path.basename(path)}')
    def _generate():
        tmp = thumb_path + '.tmp'
        try:
            img = Image.open(path)
            img.thumbnail((thumb, thumb), Image.LANCZOS)
            fmt = img.format or 'JPEG'
            img.save(tmp, format=fmt, quality=85)
            os.replace(tmp, thumb_path)
            print(f'[cover:thumb] saved {thumb}px: {os.path.getsize(thumb_path)} bytes')
        except Exception as e:
            print(f'[cover:thumb] ERROR: {e}')
            if os.path.exists(tmp):
                os.remove(tmp)
    threading.Thread(target=_generate, daemon=True).start()
    resp = send_file(path)
    resp.cache_control.max_age = 86400
    resp.cache_control.public = True
    return resp

