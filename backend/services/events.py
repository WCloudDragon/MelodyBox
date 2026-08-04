"""
行为事件服务（重构版新增）

统一落库用户行为（play / complete / skip / like / dislike），
并触发异步画像刷新。events 表是画像的唯一数据源；
老用户首次刷新时由 profile 服务从 play_history 回填。
"""
import threading


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
    """后台线程刷新用户画像（不阻塞请求）。"""
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

    threading.Thread(target=_run, daemon=True).start()
