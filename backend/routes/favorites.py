# -*- coding: utf-8 -*-
"""
收藏（我的收藏）接口：
    GET    /api/favorites            收藏歌曲列表（本地 + 云端）
    POST   /api/favorites            { song_id, source } 添加收藏
    DELETE /api/favorites/<source>/<int:song_id>  取消收藏
"""
from flask import Blueprint, request, jsonify, current_app
from routes.auth import token_required

fav_bp = Blueprint('favorites', __name__, url_prefix='/api/favorites')


def get_db():
    return current_app.get_db()


# 收藏列表返回字段（与音乐库 track 对齐：path 即 file_path，source 区分本地/云端）
_LOCAL_COLS = 'id, title, artist, album, file_path, cover_url, duration, genre, year'


@fav_bp.route('', methods=['GET'])
@token_required
def list_favorites():
    """获取当前用户收藏的歌曲列表（按收藏时间倒序）"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'SELECT source, song_id, created_at FROM favorites '
        'WHERE user_id = ? ORDER BY id DESC',
        (request.user_id,)
    )
    rows = cursor.fetchall()
    local_ids = [r['song_id'] for r in rows if r['source'] == 'local']
    cloud_ids = [r['song_id'] for r in rows if r['source'] == 'cloud']

    songs = []
    if local_ids:
        ph = ','.join('?' * len(local_ids))
        cursor.execute(
            f'SELECT {_LOCAL_COLS} FROM songs WHERE id IN ({ph})',
            local_ids
        )
        for r in cursor.fetchall():
            d = dict(r)
            d['source'] = 'local'
            d['path'] = d.pop('file_path')
            d['duration'] = d.get('duration') or 0
            songs.append(d)
    if cloud_ids:
        ph = ','.join('?' * len(cloud_ids))
        try:
            cursor.execute(
                f'''SELECT cs.id,
                           COALESCE(cm.title, cs.title) AS title,
                           COALESCE(cm.artist, cs.artist) AS artist,
                           COALESCE(cm.album, cs.album) AS album,
                           COALESCE(cm.cover_url, cs.cover_url) AS cover_url,
                           cs.file_path, cs.duration
                    FROM cloud_songs cs
                    LEFT JOIN cloud_metadata cm ON cm.cloud_song_id = cs.id
                    WHERE cs.id IN ({ph})''',
                cloud_ids
            )
            for r in cursor.fetchall():
                d = dict(r)
                d['source'] = 'cloud'
                d['path'] = d.pop('file_path')
                d['duration'] = d.get('duration') or 0
                d['genre'] = d.get('genre') or ''
                d['year'] = d.get('year') or 0
                songs.append(d)
        except Exception:
            pass

    cursor.close()
    db.close()
    return jsonify({'songs': songs})


@fav_bp.route('', methods=['POST'])
@token_required
def add_favorite():
    """添加收藏（幂等：重复收藏自动忽略）"""
    data = request.get_json(force=True, silent=True) or {}
    song_id = data.get('song_id')
    source = data.get('source') or 'local'
    if not song_id:
        return jsonify({'error': '缺少 song_id'}), 400
    if source not in ('local', 'cloud'):
        return jsonify({'error': '无效的 source'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO favorites (user_id, source, song_id) VALUES (?, ?, ?)',
        (request.user_id, source, int(song_id))
    )
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'success': True, 'favorited': True})


@fav_bp.route('/<source>/<int:song_id>', methods=['DELETE'])
@token_required
def remove_favorite(source, song_id):
    """取消收藏"""
    if source not in ('local', 'cloud'):
        return jsonify({'error': '无效的 source'}), 400
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'DELETE FROM favorites WHERE user_id = ? AND source = ? AND song_id = ?',
        (request.user_id, source, song_id)
    )
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'success': True, 'favorited': False})