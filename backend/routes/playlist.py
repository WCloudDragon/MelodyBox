from flask import Blueprint, request, jsonify, current_app
import os

playlist_bp = Blueprint('playlist', __name__, url_prefix='/api/playlists')


@playlist_bp.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        return '', 200


def get_db():
    """获取数据库连接"""
    return current_app.get_db()


def row_to_playlist_song(row):
    """将 sqlite3.Row 转换为前端期望的歌曲格式"""
    cover = row['cover_url'] or ''
    if cover and not cover.startswith('http'):
        cover = f"http://127.0.0.1:5000/api/music/cover?path={cover}"
    return {
        'id': row['id'],
        'path': row['file_path'],
        'title': row['title'] or os.path.basename(row['file_path']),
        'artist': row['artist'] or '未知艺术家',
        'album': row['album'] or '未知专辑',
        'cover': cover or None,
        'duration': row['duration'] or 0,
        'url': None,
    }


# ==================== 歌单 CRUD ====================

@playlist_bp.route('')
def list_playlists():
    """获取当前用户的所有歌单（默认 user_id=1）"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            SELECT p.*, COUNT(ps.id) as track_count
            FROM playlists p
            LEFT JOIN playlist_song ps ON p.id = ps.playlist_id
            WHERE p.user_id = 1
            GROUP BY p.id
            ORDER BY p.created_at DESC
        ''')
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        playlists = [{
            'id': r['id'],
            'name': r['name'],
            'description': r['description'],
            'cover_url': r['cover_url'],
            'is_public': bool(r['is_public']),
            'track_count': r['track_count'],
            'created_at': r['created_at'],
            'updated_at': r['updated_at'],
        } for r in rows]

        return jsonify(playlists)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@playlist_bp.route('', methods=['POST'])
def create_playlist():
    """创建新歌单"""
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': '歌单名称不能为空'}), 400

    description = data.get('description', '').strip()

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            'INSERT INTO playlists (user_id, name, description) VALUES (?, ?, ?)',
            (1, name, description)
        )
        playlist_id = cursor.lastrowid
        db.commit()

        # 返回创建的歌单
        cursor.execute('SELECT * FROM playlists WHERE id = ?', (playlist_id,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        return jsonify({
            'id': row['id'],
            'name': row['name'],
            'description': row['description'],
            'cover_url': row['cover_url'],
            'is_public': bool(row['is_public']),
            'track_count': 0,
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@playlist_bp.route('/<int:id>', methods=['DELETE'])
def delete_playlist(id):
    """删除歌单（级联删除关联歌曲）"""
    try:
        db = get_db()
        cursor = db.cursor()

        # 检查歌单是否存在
        cursor.execute('SELECT id FROM playlists WHERE id = ? AND user_id = 1', (id,))
        if not cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'error': '歌单不存在'}), 404

        # 先删除关联的歌曲记录
        cursor.execute('DELETE FROM playlist_song WHERE playlist_id = ?', (id,))
        # 再删除歌单本身
        cursor.execute('DELETE FROM playlists WHERE id = ?', (id,))
        db.commit()
        cursor.close()
        db.close()

        return jsonify({'message': '删除成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@playlist_bp.route('/<int:id>', methods=['PUT'])
def update_playlist(id):
    """更新歌单名称/描述"""
    data = request.get_json(silent=True) or {}
    name = data.get('name', None)
    description = data.get('description', None)

    # 允许清空描述，但 name 如果传了就不能为空
    if name is not None:
        name = name.strip()
        if not name:
            return jsonify({'error': '歌单名称不能为空'}), 400

    if name is None and description is None:
        return jsonify({'error': '请提供要更新的字段（name 或 description）'}), 400

    if description is not None:
        description = description.strip()

    try:
        db = get_db()
        cursor = db.cursor()

        # 检查歌单是否存在
        cursor.execute('SELECT id FROM playlists WHERE id = ? AND user_id = 1', (id,))
        if not cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'error': '歌单不存在'}), 404

        # 动态构建更新语句
        fields = []
        params = []
        if name is not None:
            fields.append('name = ?')
            params.append(name)
        if description is not None:
            fields.append('description = ?')
            params.append(description)
        fields.append("updated_at = datetime('now','localtime')")
        params.append(id)

        cursor.execute(
            f"UPDATE playlists SET {', '.join(fields)} WHERE id = ?",
            params
        )
        db.commit()

        # 返回更新后的歌单（含歌曲计数）
        cursor.execute('SELECT * FROM playlists WHERE id = ?', (id,))
        row = cursor.fetchone()
        cursor.execute('SELECT COUNT(*) as track_count FROM playlist_song WHERE playlist_id = ?', (id,))
        track_count = cursor.fetchone()['track_count']

        cursor.close()
        db.close()

        return jsonify({
            'id': row['id'],
            'name': row['name'],
            'description': row['description'],
            'cover_url': row['cover_url'],
            'is_public': bool(row['is_public']),
            'track_count': track_count,
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 歌单内歌曲管理 ====================

@playlist_bp.route('/<int:id>/songs')
def get_playlist_songs(id):
    """获取歌单中的歌曲列表"""
    try:
        db = get_db()
        cursor = db.cursor()

        # 检查歌单是否存在
        cursor.execute('SELECT id FROM playlists WHERE id = ? AND user_id = 1', (id,))
        if not cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'error': '歌单不存在'}), 404

        cursor.execute('''
            SELECT s.*
            FROM playlist_song ps
            JOIN songs s ON ps.song_id = s.id
            WHERE ps.playlist_id = ?
            ORDER BY ps.added_at ASC
        ''', (id,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        songs = [row_to_playlist_song(r) for r in rows]
        return jsonify(songs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@playlist_bp.route('/<int:id>/songs', methods=['POST'])
def add_song_to_playlist(id):
    """添加歌曲到歌单（支持 song_id 或 song_path）"""
    data = request.get_json(silent=True) or {}
    song_id = data.get('song_id')
    song_path = data.get('song_path')

    if not song_id and not song_path:
        return jsonify({'error': '缺少 song_id 或 song_path'}), 400

    try:
        db = get_db()
        cursor = db.cursor()

        # 检查歌单是否存在
        cursor.execute('SELECT id, cover_url FROM playlists WHERE id = ? AND user_id = 1', (id,))
        playlist = cursor.fetchone()
        if not playlist:
            cursor.close()
            db.close()
            return jsonify({'error': '歌单不存在'}), 404

        # 通过 song_path 查 song_id
        if song_path and not song_id:
            cursor.execute('SELECT id, cover_url FROM songs WHERE file_path = ?', (song_path,))
            song = cursor.fetchone()
            if song:
                song_id = song['id']
            else:
                song = None
        else:
            cursor.execute('SELECT id, cover_url FROM songs WHERE id = ?', (song_id,))
            song = cursor.fetchone()

        if not song:
            cursor.close()
            db.close()
            return jsonify({'error': '歌曲不存在'}), 404

        # INSERT OR IGNORE 避免重复添加
        cursor.execute(
            'INSERT OR IGNORE INTO playlist_song (playlist_id, song_id) VALUES (?, ?)',
            (id, song_id)
        )
        db.commit()

        # 如果歌单封面为空，设置为第一首添加歌曲的封面
        if not playlist['cover_url'] and song['cover_url']:
            cursor.execute(
                "UPDATE playlists SET cover_url = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                (song['cover_url'], id)
            )
            db.commit()

        cursor.close()
        db.close()

        return jsonify({'message': '添加成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@playlist_bp.route('/<int:id>/songs/by-path', methods=['DELETE'])
def remove_song_from_playlist_by_path(id):
    """通过文件路径从歌单移除歌曲"""
    song_path = request.args.get('path', '')
    if not song_path:
        return jsonify({'error': '缺少 path 参数'}), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id FROM songs WHERE file_path = ?', (song_path,))
        song = cursor.fetchone()
        if not song:
            cursor.close(); db.close()
            return jsonify({'error': '歌曲不存在'}), 404

        cursor.execute(
            'DELETE FROM playlist_song WHERE playlist_id = ? AND song_id = ?',
            (id, song['id'])
        )
        # 更新歌单 updated_at
        cursor.execute(
            "UPDATE playlists SET updated_at = datetime('now','localtime') WHERE id = ?",
            (id,)
        )
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'message': '移除成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@playlist_bp.route('/<int:id>/songs/<int:song_id>', methods=['DELETE'])
def remove_song_from_playlist(id, song_id):
    """从歌单中移除歌曲"""
    try:
        db = get_db()
        cursor = db.cursor()

        # 检查歌单是否存在
        cursor.execute('SELECT id FROM playlists WHERE id = ? AND user_id = 1', (id,))
        if not cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'error': '歌单不存在'}), 404

        cursor.execute(
            'DELETE FROM playlist_song WHERE playlist_id = ? AND song_id = ?',
            (id, song_id)
        )
        db.commit()
        cursor.close()
        db.close()

        return jsonify({'message': '移除成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
