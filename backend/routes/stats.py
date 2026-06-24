"""
MelodyBox 播放统计路由

提供歌曲播放记录的采集、查询和统计功能。
- play_stats 表通过 fingerprint 关联歌曲，确保歌曲从库中删除后统计不丢失
- play_history 表记录每次播放事件的完整时间线
"""
import hashlib
from flask import Blueprint, request, jsonify, current_app
from routes.auth import token_required, get_user_id_from_token

stats_bp = Blueprint('stats', __name__, url_prefix='/api/stats')


@stats_bp.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        return '', 200


def get_db():
    """获取数据库连接"""
    return current_app.get_db()


def make_fingerprint(title, artist, album):
    """
    根据歌曲元数据生成指纹。

    指纹 = md5("title|artist|album")，用于跨扫描周期的播放统计关联。
    当歌曲从库中删除后重新导入时，fingerprint 确保播放计数不丢失。
    """
    raw = f"{title}|{artist}|{album}".strip().lower()
    return hashlib.md5(raw.encode()).hexdigest()


# ==================== 录制播放事件 ====================

@stats_bp.route('/play', methods=['POST'])
def record_play():
    """
    录制一次播放事件。

    请求体 (JSON):
        {
            "file_path": "D:/music/song.mp3",   // 歌曲文件路径，用于匹配 songs 表获取 song_id
            "title": "Song Title",              // 必填
            "artist": "Artist Name",
            "album": "Album Name"
        }

    响应:
        { "success": true, "play_count": 5 }

    逻辑:
        1. 生成 fingerprint = md5(title|artist|album)
        2. 通过 file_path 在 songs 表中查找 song_id
        3. UPSERT play_stats：匹配 fingerprint，若存在则 play_count+1，否则 INSERT
        4. INSERT play_history 新纪录
    """
    try:
        data = request.get_json(force=True)

        title = (data.get('title', '') or '').strip()
        artist = (data.get('artist', '') or '').strip()
        album = (data.get('album', '') or '').strip()
        file_path = (data.get('file_path', '') or '').strip()

        if not title:
            return jsonify({'error': 'title 为必填字段'}), 400

        fingerprint = make_fingerprint(title, artist, album)

        db = get_db()
        cursor = db.cursor()

        # 通过 file_path 查找 song_id
        song_id = None
        if file_path:
            cursor.execute('SELECT id FROM songs WHERE file_path = ?', (file_path,))
            row = cursor.fetchone()
            if row:
                song_id = row['id']

        # UPSERT: 检查 fingerprint 是否已存在
        cursor.execute(
            'SELECT id, play_count FROM play_stats WHERE fingerprint = ?',
            (fingerprint,)
        )
        existing = cursor.fetchone()

        if existing:
            new_count = existing['play_count'] + 1
            cursor.execute(
                '''UPDATE play_stats
                   SET play_count = ?,
                       last_played = datetime('now', 'localtime'),
                       song_id = COALESCE(?, song_id)
                   WHERE fingerprint = ?''',
                (new_count, song_id, fingerprint)
            )
        else:
            new_count = 1
            cursor.execute(
                '''INSERT INTO play_stats (song_id, fingerprint, play_count, last_played)
                   VALUES (?, ?, 1, datetime('now', 'localtime'))''',
                (song_id, fingerprint)
            )

        # 插入播放历史
        cursor.execute(
            '''INSERT INTO play_history (song_id, fingerprint, played_at)
               VALUES (?, ?, datetime('now', 'localtime'))''',
            (song_id, fingerprint)
        )

        db.commit()
        cursor.close()
        db.close()

        return jsonify({'success': True, 'play_count': new_count})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 热门歌曲 ====================

@stats_bp.route('/top')
def get_top():
    """
    获取播放次数最多的歌曲。

    查询参数:
        limit (int, 默认 20, 最大 100): 返回条数

    响应:
        [{
            "song_id": 1,
            "title": "...",
            "artist": "...",
            "album": "...",
            "cover_url": "...",
            "file_path": "...",
            "fingerprint": "abc123...",
            "play_count": 42,
            "last_played": "2025-01-01 12:00:00"
        }, ...]

    说明:
        - LEFT JOIN 确保已删除歌曲的统计记录仍然返回（song_id 为 NULL）
        - 此时 title/artist 等字段从 fingerprint 无法还原，返回空字符串
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        if limit < 1:
            limit = 20
        if limit > current_app.config.get('MAX_PAGE_SIZE', 100):
            limit = current_app.config.get('MAX_PAGE_SIZE', 100)

        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            SELECT
                ps.song_id,
                s.title,
                s.artist,
                s.album,
                s.cover_url,
                s.file_path,
                ps.fingerprint,
                ps.play_count,
                ps.last_played
            FROM play_stats ps
            LEFT JOIN songs s ON ps.song_id = s.id
            ORDER BY ps.play_count DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        results = []
        for row in rows:
            results.append({
                'song_id': row['song_id'],
                'title': row['title'] or '',
                'artist': row['artist'] or '',
                'album': row['album'] or '',
                'cover_url': row['cover_url'] or '',
                'file_path': row['file_path'] or '',
                'fingerprint': row['fingerprint'],
                'play_count': row['play_count'],
                'last_played': row['last_played'],
            })

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 最近播放 ====================

@stats_bp.route('/recent')
def get_recent():
    """
    获取最近播放的歌曲。

    查询参数:
        limit (int, 默认 20, 最大 100): 返回条数

    响应:
        [{
            "song_id": 1,
            "title": "...",
            "artist": "...",
            "album": "...",
            "cover_url": "...",
            "file_path": "...",
            "played_at": "2025-01-01 12:00:00"
        }, ...]

    说明:
        - 按 fingerprint 去重，每个指纹只返回最近一次播放记录
        - 确保反复播放同一首歌不会刷屏
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        if limit < 1:
            limit = 20
        if limit > current_app.config.get('MAX_PAGE_SIZE', 100):
            limit = current_app.config.get('MAX_PAGE_SIZE', 100)

        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            SELECT
                ph.song_id,
                s.title,
                s.artist,
                s.album,
                s.cover_url,
                s.file_path,
                MAX(ph.played_at) AS played_at,
                ph.fingerprint
            FROM play_history ph
            LEFT JOIN songs s ON ph.song_id = s.id
            GROUP BY ph.fingerprint
            ORDER BY played_at DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        results = []
        for row in rows:
            results.append({
                'song_id': row['song_id'],
                'title': row['title'] or '',
                'artist': row['artist'] or '',
                'album': row['album'] or '',
                'cover_url': row['cover_url'] or '',
                'file_path': row['file_path'] or '',
                'played_at': row['played_at'],
            })

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 总播放统计 ====================

@stats_bp.route('/total')
def get_total():
    """
    获取全库总播放次数。

    响应:
        { "total_plays": 12345 }
    """
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT COALESCE(SUM(play_count), 0) AS total_plays FROM play_stats')
        row = cursor.fetchone()
        cursor.close()
        db.close()

        return jsonify({'total_plays': row['total_plays']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
