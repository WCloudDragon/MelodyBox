"""
行为事件服务（重构版新增）

统一落库用户行为（play / complete / skip / like / dislike），
并触发异步画像刷新。events 表是画像的唯一数据源；
老用户首次刷新时由 profile 服务从 play_history 回填。
"""
import threading

_PROFILE_REFRESH_MIN_INTERVAL = 30  # 秒：两次画像刷新之间的最小间隔
_profile_refresh_state = {'last_ts': 0.0, 'running': False}
_refresh_lock = threading.Lock()


def record_event(db, user_id=1, song_id=None, fingerprint=None,
                 event_type='play', duration_ratio=None):
    """写入一条行为事件（调用方负责 commit）。"""
    cursor = db.cursor()
    cursor.execute(
        '''INSERT INTO events (user_id, song_id, fingerprint, event_type,
                              duration_ratio, ts)
           VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))''',
        (user_id, song_id, fingerprint or '', event_type, duration_ratio)
    )
    cursor.close()


def refresh_profile_async(app, user_id=1):
    """
    后台线程刷新用户画像（不阻塞请求，节流版）。

    策略：
    - 距上次刷新不足 30 秒 → 跳过（事件已先落库，数据不丢，最终一致）；
    - 已有刷新在跑 → 跳过（避免线程堆积与 DB 写竞争）。
    """
    import time

    now = time.time()
    with _refresh_lock:
        if _profile_refresh_state['running']:
            return
        if now - _profile_refresh_state['last_ts'] < _PROFILE_REFRESH_MIN_INTERVAL:
            return
        _profile_refresh_state['running'] = True

    def _run():
        try:
            with app.app_context():
                db = app.get_db()
                try:
                    from services.profile import refresh_profile
                    refresh_profile(db, user_id)
                finally:
                    db.close()
        except Exception:
            pass
        finally:
            with _refresh_lock:
                _profile_refresh_state['running'] = False
                _profile_refresh_state['last_ts'] = time.time()

    threading.Thread(target=_run, daemon=True).start()
