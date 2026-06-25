from flask import Blueprint, request, jsonify, current_app
import os
import threading
import traceback

folders_bp = Blueprint('folders', __name__, url_prefix='/api/folders')

# 扫描进度（全局，单用户桌面应用无需加锁）
_scan_progress = {'current': 0, 'total': 0, 'path': '', 'scanning': False,
                  'inserted': 0, 'updated': 0, 'deleted': 0}


@folders_bp.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        return '', 200


def get_db():
    return current_app.get_db()


def _dir_stats(db, dir_path):
    """统计某目录下的歌曲数量与总时长"""
    cursor = db.cursor()
    norm = dir_path.replace('\\', '/')
    # 统一用 / 比较，兼容 Windows 路径
    cursor.execute(
        "SELECT COUNT(*) as cnt, COALESCE(SUM(duration), 0) as dur FROM songs WHERE REPLACE(file_path, '\\', '/') LIKE ?",
        (norm + '/%',)
    )
    row = cursor.fetchone()
    cursor.close()
    return {'track_count': row['cnt'], 'total_duration': row['dur']}


# ==================== CRUD ====================

@folders_bp.route('/scan-progress')
def scan_progress():
    """获取当前扫描进度"""
    return jsonify({
        'scanning': _scan_progress['scanning'],
        'current': _scan_progress['current'],
        'total': _scan_progress['total'],
        'path': os.path.basename(_scan_progress['path']) if _scan_progress['path'] else '',
        'inserted': _scan_progress.get('inserted', 0),
        'updated': _scan_progress.get('updated', 0),
        'deleted': _scan_progress.get('deleted', 0),
    })


@folders_bp.route('/thumb-progress')
def thumb_progress():
    """获取当前缩略图生成进度"""
    from services.scanner import _thumb_progress
    return jsonify({
        'scanning': _thumb_progress['scanning'],
        'current': _thumb_progress['current'],
        'total': _thumb_progress['total'],
        'path': _thumb_progress['path']
    })


@folders_bp.route('')
def list_folders():
    """列出所有已导入的文件夹，附带歌曲统计。如果表为空但 songs 有数据，自动推导并迁移"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, path, added_at FROM scan_directories ORDER BY added_at DESC')
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        # 如果 scan_directories 为空但 songs 表有数据，自动从 songs 推导文件夹
        if not rows:
            _migrate_from_songs()

        # 刷新
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, path, added_at FROM scan_directories ORDER BY added_at DESC')
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        folders = []
        for r in rows:
            stats = _dir_stats(get_db(), r['path'])
            folders.append({
                'id': r['id'],
                'path': r['path'],
                'addedAt': r['added_at'],
                'trackCount': stats['track_count'],
                'totalDuration': stats['total_duration'],
            })
        return jsonify(folders)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _migrate_from_songs():
    """从 songs 表的已有数据中自动推导并插入顶层目录到 scan_directories"""
    db = get_db()
    cursor = db.cursor()

    # 获取所有歌曲的目录
    cursor.execute("SELECT DISTINCT file_path FROM songs")
    paths = [row['file_path'] for row in cursor.fetchall()]
    cursor.close()
    db.close()

    if not paths:
        return

    # 去重后按深度排序（路径越浅越靠前，越浅越可能是根目录）
    dirs = set()
    for p in paths:
        d = os.path.dirname(p)
        if d:
            dirs.add(d)

    sorted_dirs = sorted(dirs, key=lambda x: x.count(os.sep))

    # 贪心：从浅到深，选出一组互不包含的顶层目录
    roots = []
    for d in sorted_dirs:
        # 检查是否已被已有根目录覆盖
        covered = False
        for r in roots:
            if d.replace('\\', '/').startswith(r.replace('\\', '/') + '/'):
                covered = True
                break
        if not covered:
            roots.append(d)

    # 进一步收紧：如果某根目录下只有它本身和一个子目录，取更上一级
    # 实际上直接插入即可
    db = get_db()
    cursor = db.cursor()
    for r in roots:
        try:
            cursor.execute('INSERT OR IGNORE INTO scan_directories (path) VALUES (?)', (r,))
        except Exception:
            pass
    db.commit()
    cursor.close()
    db.close()


@folders_bp.route('', methods=['POST'])
def add_folder():
    """添加一个文件夹并立即扫描入库"""
    global _scan_progress
    data = request.get_json(silent=True) or {}
    path = (data.get('path') or '').strip()

    if not path:
        return jsonify({'error': '请提供文件夹路径'}), 400
    if not os.path.isdir(path):
        return jsonify({'error': '文件夹不存在或无法访问'}), 400

    try:
        db = get_db()
        cursor = db.cursor()

        # 检查是否已添加
        cursor.execute('SELECT id FROM scan_directories WHERE path = ?', (path,))
        if cursor.fetchone():
            cursor.close(); db.close()
            return jsonify({'error': '该文件夹已添加'}), 409

        cursor.execute('INSERT INTO scan_directories (path) VALUES (?)', (path,))
        db.commit()
        cursor.close()
        db.close()

        # 异步扫描：后台线程，前端轮询进度
        # 必须捕获 app 实例，因为 current_app 在线程中不可用
        flask_app = current_app._get_current_object()

        def _scan_async(dir_path):
            global _scan_progress
            from services.scanner import scan_and_store
            _scan_progress = {'current': 0, 'total': 0, 'path': '', 'scanning': True,
                              'inserted': 0, 'updated': 0, 'deleted': 0}

            def _cb(current, total, file_path):
                _scan_progress['current'] = current
                _scan_progress['total'] = total
                _scan_progress['path'] = file_path

            try:
                with flask_app.app_context():
                    db2 = get_db()
                    result = scan_and_store(db2, [dir_path], progress_callback=_cb)
                    db2.close()
                    if result:
                        _scan_progress['inserted'] = result.get('inserted', 0)
                        _scan_progress['updated'] = result.get('updated', 0)
                        _scan_progress['deleted'] = result.get('deleted', 0)
            except Exception as e:
                traceback.print_exc()
            finally:
                _scan_progress['scanning'] = False

        threading.Thread(target=_scan_async, args=(path,), daemon=True).start()

        return jsonify({'success': True, 'message': '开始扫描...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@folders_bp.route('/<int:id>', methods=['DELETE'])
def remove_folder(id):
    """移除文件夹及其下的所有歌曲记录"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT path FROM scan_directories WHERE id = ?', (id,))
        row = cursor.fetchone()
        if not row:
            cursor.close(); db.close()
            return jsonify({'error': '文件夹不存在'}), 404

        dir_path = row['path']
        norm = dir_path.replace('\\', '/')

        # 删除该目录下所有歌曲（外键级联会清理 song_artist/song_album/playlist_song）
        cursor.execute("DELETE FROM songs WHERE REPLACE(file_path, '\\', '/') LIKE ?", (norm + '/%',))
        # 清理 play_stats 中对应 fingerprint 的记录（已是孤儿 song_id=NULL 的保留）
        cursor.execute('DELETE FROM scan_directories WHERE id = ?', (id,))

        # 清理空的艺术家和专辑
        cursor.execute('DELETE FROM artists WHERE id NOT IN (SELECT DISTINCT artist_id FROM song_artist)')
        cursor.execute('DELETE FROM albums WHERE id NOT IN (SELECT DISTINCT album_id FROM song_album)')

        # 清理没有歌曲的歌单（playlist_song 已通过外键级联清除）
        cursor.execute('DELETE FROM playlists WHERE id NOT IN (SELECT DISTINCT playlist_id FROM playlist_song)')

        db.commit()

        cursor.execute('SELECT COUNT(*) as remaining FROM songs')
        remaining = cursor.fetchone()['remaining']
        cursor.close()
        db.close()

        all_dirs = [r['path'] for r in get_db().cursor().execute('SELECT path FROM scan_directories').fetchall()]

        return jsonify({
            'success': True,
            'message': f'已移除文件夹，剩余 {remaining} 首歌曲',
            'deletedCount': remaining,
            'allScanDirs': all_dirs
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@folders_bp.route('/<int:id>/rescan', methods=['POST'])
def rescan_folder(id):
    """重新扫描指定文件夹"""
    global _scan_progress
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT path FROM scan_directories WHERE id = ?', (id,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        if not row:
            cursor.close()
            db.close()
            return jsonify({'error': '文件夹不存在'}), 404

        # 异步扫描
        flask_app = current_app._get_current_object()

        def _rescan_async(dir_path):
            global _scan_progress
            from services.scanner import scan_and_store
            _scan_progress = {'current': 0, 'total': 0, 'path': '', 'scanning': True,
                              'inserted': 0, 'updated': 0, 'deleted': 0}

            def _cb(current, total, file_path):
                _scan_progress['current'] = current
                _scan_progress['total'] = total
                _scan_progress['path'] = file_path

            try:
                with flask_app.app_context():
                    db2 = get_db()
                    result = scan_and_store(db2, [dir_path], progress_callback=_cb)
                    db2.close()
                    if result:
                        _scan_progress['inserted'] = result.get('inserted', 0)
                        _scan_progress['updated'] = result.get('updated', 0)
                        _scan_progress['deleted'] = result.get('deleted', 0)
            except Exception as e:
                traceback.print_exc()
            finally:
                _scan_progress['scanning'] = False

        path = row['path']
        threading.Thread(target=_rescan_async, args=(path,), daemon=True).start()

        return jsonify({'success': True, 'message': '开始重新扫描...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
