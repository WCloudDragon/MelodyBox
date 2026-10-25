from flask import Blueprint, request, jsonify, current_app
import logging
import os
import threading
import traceback
from functools import wraps
from routes.auth import token_required

folders_bp = Blueprint('folders', __name__, url_prefix='/api/folders')

logger = logging.getLogger('melodybox.scan')

# 扫描进度（全局，单用户桌面应用无需加锁）
_scan_progress = {'current': 0, 'total': 0, 'path': '', 'scanning': False,
                  'inserted': 0, 'updated': 0, 'deleted': 0, 'errors': 0,
                  'queued': 0, 'batch_index': 0, 'batch_total': 0}

# 扫描队列：同一时刻只允许一个扫描线程，多个目录按顺序处理。
# 并发扫描会互相覆盖同一份全局进度，导致前端进度跳变/提前完成/统计错乱。
_scan_queue = []
_scan_lock = threading.Lock()
_scan_thread = None
# 本次扫描会话（批量时跨目录）的累计统计，用于结束时的汇总文案
_scan_totals = {'inserted': 0, 'updated': 0, 'deleted': 0, 'errors': 0}


@folders_bp.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        return '', 200


def get_db():
    return current_app.get_db()


def _admin_required(f):
    """管理员权限装饰器（需配合 token_required 使用）"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if getattr(request, 'user_role', None) != 'admin':
            return jsonify({'error': '仅管理员可操作'}), 403
        return f(*args, **kwargs)
    return decorated


def _list_drive_roots():
    """Windows 下列出盘符根目录；非 Windows 返回 ['/']"""
    if os.name != 'nt':
        return [os.path.abspath(os.sep)]
    roots = []
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        root = f'{letter}:\\'
        if os.path.exists(root):
            roots.append(root)
    return roots


@folders_bp.route('/browse')
@token_required
@_admin_required
def browse_directory():
    """
    服务器目录浏览（B/S 管理端选目录用，仅管理员）。

    GET /api/folders/browse?path=D:\\Music
    返回该目录下的子目录列表；path 为空时返回盘符根目录。
    """
    path = (request.args.get('path') or '').strip()

    if not path:
        roots = _list_drive_roots()
        return jsonify({
            'path': '',
            'parent': None,
            'exists': True,
            'is_dir': True,
            'subdirs': roots,
            'error': None,
        })

    if not os.path.isabs(path):
        return jsonify({'error': '必须是绝对路径'}), 400
    if not os.path.exists(path):
        return jsonify({'error': '路径不存在'}), 404
    if not os.path.isdir(path):
        return jsonify({'error': '不是文件夹'}), 400

    try:
        subdirs = sorted([
            os.path.join(path, name)
            for name in os.listdir(path)
            if os.path.isdir(os.path.join(path, name))
        ], key=lambda p: p.lower())
    except (PermissionError, OSError):
        subdirs = []

    parent = os.path.dirname(os.path.abspath(path))
    # 盘符根目录的上级仍是自己
    if parent == path:
        parent = None

    return jsonify({
        'path': path,
        'parent': parent,
        'exists': True,
        'is_dir': True,
        'subdirs': subdirs,
        'error': None,
    })


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
    """获取当前扫描进度（queued/batch_* 用于批量重扫的队列与批次展示）"""
    return jsonify({
        'scanning': _scan_progress['scanning'],
        'current': _scan_progress['current'],
        'total': _scan_progress['total'],
        'path': os.path.basename(_scan_progress['path']) if _scan_progress['path'] else '',
        'inserted': _scan_progress.get('inserted', 0),
        'updated': _scan_progress.get('updated', 0),
        'deleted': _scan_progress.get('deleted', 0),
        'errors': _scan_progress.get('errors', 0),
        'queued': _scan_progress.get('queued', 0),
        'batch_index': _scan_progress.get('batch_index', 0),
        'batch_total': _scan_progress.get('batch_total', 0),
    })


def _enqueue_scan(dir_path, flask_app, batch_index=0, batch_total=1):
    """把扫描任务加入队列，由单一工作线程顺序处理。

    并发扫描会互相覆盖同一份全局进度（前端表现为进度跳变、提前完成、
    统计错乱），因此同一时刻只允许一个扫描在跑，其余目录排队等待。
    """
    global _scan_thread
    with _scan_lock:
        # 空闲状态下开始新一批扫描：清空上一轮的累计统计
        if not _scan_queue and not _scan_progress['scanning']:
            _scan_totals.update({'inserted': 0, 'updated': 0, 'deleted': 0, 'errors': 0})
        _scan_queue.append({
            'path': dir_path,
            'app': flask_app,
            'batch_index': batch_index,
            'batch_total': batch_total,
        })
        _scan_progress['queued'] = len(_scan_queue)
        if _scan_thread is None or not _scan_thread.is_alive():
            _scan_thread = threading.Thread(target=_scan_worker, daemon=True)
            _scan_thread.start()


def _scan_worker():
    """顺序消费扫描队列；队列空时退出，并按设置触发向量自动补齐。"""
    global _scan_progress, _scan_thread
    from services.scanner import scan_and_store

    last_app = None
    while True:
        with _scan_lock:
            if not _scan_queue:
                _scan_progress['scanning'] = False
                _scan_progress['queued'] = 0
                break
            item = _scan_queue.pop(0)
            queued = len(_scan_queue)

        dir_path = item['path']
        flask_app = item['app']
        last_app = flask_app
        logger.info('扫描开始: %s', dir_path)
        _scan_progress = {'current': 0, 'total': 0, 'path': '', 'scanning': True,
                          'inserted': 0, 'updated': 0, 'deleted': 0, 'errors': 0,
                          'queued': queued,
                          'batch_index': item.get('batch_index', 0),
                          'batch_total': item.get('batch_total', 1)}

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
                    # 累计到本次扫描会话（批量重扫时多个目录合并统计）
                    for k in ('inserted', 'updated', 'deleted', 'errors'):
                        _scan_totals[k] += result.get(k, 0) or 0
                        _scan_progress[k] = _scan_totals[k]
                    logger.info('扫描完成: %s 新增=%s 更新=%s 删除=%s 解析失败=%s',
                                dir_path, result.get('inserted', 0),
                                result.get('updated', 0), result.get('deleted', 0),
                                result.get('errors', 0))
        except Exception:
            logger.error('扫描异常: %s\n%s', dir_path, traceback.format_exc())
        finally:
            # 队列还有任务时保持 scanning=True，前端看到的是一次连续扫描
            with _scan_lock:
                has_more = bool(_scan_queue)
                remaining = len(_scan_queue)
            if not has_more:
                _scan_progress['scanning'] = False
            _scan_progress['queued'] = remaining

    # 队列已清空：注销线程登记；退出瞬间若又有新任务，补启一个工作线程避免队列卡住
    with _scan_lock:
        _scan_thread = None
        queued = len(_scan_queue)
    if queued:
        with _scan_lock:
            if _scan_thread is None:
                _scan_thread = threading.Thread(target=_scan_worker, daemon=True)
                _scan_thread.start()
        return

    # 整批扫描结束：按「自动生成向量」开关为新增/变更曲目补齐向量
    if last_app is not None:
        try:
            from routes.ai import auto_generate_embeddings
            auto_generate_embeddings(last_app)
        except Exception:
            logger.warning('自动向量生成触发失败\n%s', traceback.format_exc())


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

        # 异步扫描：加入队列由工作线程顺序处理，前端轮询进度
        # 必须捕获 app 实例，因为 current_app 在线程中不可用
        flask_app = current_app._get_current_object()
        _enqueue_scan(path, flask_app)

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

        # 删除该目录下所有歌曲：统一删除内核（保留足迹模式）——歌单关联按
        # 指纹暂存（含元数据快照，重导自动恢复）、播放数据置孤儿待重连、
        # 清理关联表与向量、失效推荐缓存
        cursor.execute(
            "SELECT id FROM songs WHERE REPLACE(file_path, '\\', '/') LIKE ?",
            (norm + '/%',))
        song_ids = [r[0] for r in cursor.fetchall()]
        from services.scanner import delete_songs_from_db
        delete_songs_from_db(cursor, song_ids, preserve_footprints=True)

        cursor.execute('DELETE FROM scan_directories WHERE id = ?', (id,))

        # 清理空的艺术家和专辑
        cursor.execute('DELETE FROM artists WHERE id NOT IN (SELECT DISTINCT artist_id FROM song_artist)')
        cursor.execute('DELETE FROM albums WHERE id NOT IN (SELECT DISTINCT album_id FROM song_album)')

        # 清理没有歌曲的歌单（playlist_song 已通过外键级联清除）；
        # 有孤儿暂存的歌单保留——重扫后歌曲按指纹恢复回歌单
        cursor.execute('''
            DELETE FROM playlists
            WHERE id NOT IN (SELECT DISTINCT playlist_id FROM playlist_song)
              AND id NOT IN (SELECT DISTINCT playlist_id FROM orphaned_playlist_songs)
        ''')

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


@folders_bp.route('/rescan-all', methods=['POST'])
def rescan_all_folders():
    """重新扫描全部已添加的文件夹（按添加顺序入队，由工作线程串行执行）"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT path FROM scan_directories ORDER BY added_at ASC, id ASC')
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        paths = [r['path'] for r in rows if r['path']]
        if not paths:
            return jsonify({'error': '没有已添加的文件夹'}), 400

        flask_app = current_app._get_current_object()
        total = len(paths)
        for i, p in enumerate(paths, start=1):
            _enqueue_scan(p, flask_app, batch_index=i, batch_total=total)

        return jsonify({'success': True, 'queued': total, 'total': total})
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

        # 异步扫描：加入队列由工作线程顺序处理
        flask_app = current_app._get_current_object()
        _enqueue_scan(row['path'], flask_app)

        return jsonify({'success': True, 'message': '开始重新扫描...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
