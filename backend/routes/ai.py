"""
MelodyBox AI 推荐路由（重构版）

提供：
- Embedding 生成 / 状态（写入独立 song_vectors 表，带版本号）
- 统一推荐接口（画像驱动 + 服务端缓存）
- 首页推荐卡片封面预览
- 情绪分数预计算刷新
- 模型缓存目录管理
"""
from flask import Blueprint, request, jsonify, current_app
import threading
import time
import hashlib
import sys
from collections import deque

from utils.cache import cache
from config.recommend_config import (
    TEXT_VECTOR_VERSION,
    AUDIO_VECTOR_VERSION,
    RECOMMEND_CACHE_TTL,
)

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# embedding 生成状态（模块级标志，供前端轮询）
_generating_text_embeddings = False
_generating_audio_embeddings = False
_audio_total = 0
_audio_done_count = 0
_text_total = 0
_text_done_count = 0
_text_use_gpu = False
# 音频 embedding 完成信号（用于 CPU→GPU 切换）
_audio_embedding_done = threading.Event()
# 向量生成任务互斥：手动触发与扫描后自动触发共用，避免两个任务并行写同一批行
_generation_running = False
_generation_guard = threading.Lock()

# ETA 采样：由 status 轮询驱动，按最近窗口的完成速率估算剩余时间
_ETA_WINDOW_SEC = 12.0
_eta_state = {
    'text': {'samples': deque(maxlen=24), 'phase': '', 'eta': None, 'rate': 0.0},
    'audio': {'samples': deque(maxlen=24), 'phase': '', 'eta': None, 'rate': 0.0},
}


def _update_eta(key, done, total, active, phase):
    """更新某一类任务的剩余时间估算。

    只在完成数真正变化时重新采样和计算；进度不变的轮询直接沿用上一次结果。
    阶段切换（CPU→GPU）或任务重置时清空样本，避免用旧速率估算新阶段。
    """
    state = _eta_state[key]
    if not active:
        state['samples'].clear()
        state['phase'] = ''
        state['eta'] = None
        state['rate'] = 0.0
        return

    now = time.monotonic()
    samples = state['samples']
    if phase != state['phase']:
        samples.clear()
        state['phase'] = phase
        state['eta'] = None
        state['rate'] = 0.0
    # 计数回退说明换了新任务/被重置，丢弃旧样本
    if samples and done < samples[-1][1]:
        samples.clear()
        state['eta'] = None
        state['rate'] = 0.0
    # 进度没有变化：不采样、不重算，保持上一次的预计时间
    if samples and done == samples[-1][1]:
        return
    samples.append((now, done))
    while len(samples) > 2 and now - samples[0][0] > _ETA_WINDOW_SEC:
        samples.popleft()

    rate = 0.0
    if len(samples) >= 2:
        dt = samples[-1][0] - samples[0][0]
        delta = samples[-1][1] - samples[0][1]
        if dt >= 1.0 and delta > 0:
            rate = delta / dt
    state['rate'] = rate

    remaining = max(0, (total or 0) - (done or 0))
    if remaining <= 0:
        state['eta'] = 0
    elif rate > 0:
        state['eta'] = remaining / rate
    else:
        state['eta'] = None


def _get_default_model_dir():
    """返回默认模型缓存目录（%APPDATA%/melodybox/models/）"""
    from config.config import Config
    return Config.resolve_model_dir()


@ai_bp.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        return '', 200


def get_db():
    return current_app.get_db()


# ==================== 待处理歌曲查询（向量表版） ====================

def _pending_songs(db, audio=False):
    """查询尚未生成（当前版本）文本/音频向量的歌曲，返回 list[dict]。"""
    col = 'audio_vec' if audio else 'text_vec'
    vcol = 'audio_version' if audio else 'text_version'
    version = AUDIO_VECTOR_VERSION if audio else TEXT_VECTOR_VERSION
    exists_sql = (
        f'SELECT 1 FROM song_vectors v '
        f'WHERE v.song_id = s.id AND v.source = \'local\' '
        f'AND v.{col} IS NOT NULL AND v.{vcol} = ?'
    )
    cursor = db.cursor()
    cursor.execute(
        f'SELECT id, title, artist, genre, year, lyrics, lang, "local" AS source '
        f'FROM songs s WHERE NOT EXISTS ({exists_sql})',
        (version,)
    )
    rows = [dict(r) for r in cursor.fetchall()]
    cloud_exists = exists_sql.replace("v.source = 'local'", "v.source = 'cloud'")
    cursor.execute(
        f'SELECT id, title, artist, genre, year, lyrics, lang, "cloud" AS source '
        f'FROM cloud_songs s WHERE NOT EXISTS ({cloud_exists})',
        (version,)
    )
    rows.extend([dict(r) for r in cursor.fetchall()])
    cursor.close()
    return rows


# ==================== Embedding 状态 ====================

@ai_bp.route('/embedding/status')
def embedding_status():
    """获取全库 embedding 生成状态（前端轮询）。"""
    try:
        from services.embedding import is_available

        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT COUNT(*) as total FROM songs')
        local_total = cursor.fetchone()['total']
        cursor.execute('SELECT COUNT(*) as total FROM cloud_songs')
        cloud_total = cursor.fetchone()['total']
        total = local_total + cloud_total

        cursor.execute(
            'SELECT COUNT(*) as done FROM song_vectors '
            'WHERE text_vec IS NOT NULL AND text_version = ?',
            (TEXT_VECTOR_VERSION,)
        )
        done = cursor.fetchone()['done']

        cursor.execute(
            '''SELECT s.lang, COUNT(*) as cnt FROM songs s
               WHERE s.lang != "" AND EXISTS (
                   SELECT 1 FROM song_vectors v
                   WHERE v.song_id = s.id AND v.source = 'local'
                     AND v.text_vec IS NOT NULL AND v.text_version = ?
               )
               GROUP BY s.lang ORDER BY cnt DESC''',
            (TEXT_VECTOR_VERSION,)
        )
        langs = [row['lang'] for row in cursor.fetchall()]

        cursor.execute('SELECT COUNT(*) as cnt FROM song_mood_scores')
        mood_scores_ready = cursor.fetchone()['cnt'] > 0

        cursor.execute(
            'SELECT COUNT(*) as done FROM song_vectors '
            'WHERE audio_vec IS NOT NULL AND audio_version = ?',
            (AUDIO_VECTOR_VERSION,)
        )
        audio_done_db = cursor.fetchone()['done']
        cursor.close()
        db.close()

        audio_processing = _generating_audio_embeddings
        text_processing = _generating_text_embeddings
        # 处理中显示"本次任务"的进度；空闲时显示全库进度。
        # 不能把数据库已有数与本轮计数相加：数据库每批 commit 后已有数也在涨，会重复计数
        if audio_processing:
            audio_done_view = min(_audio_done_count, _audio_total)
            audio_total_view = _audio_total
        else:
            audio_done_view = audio_done_db
            audio_total_view = total
        if text_processing:
            text_done_view = min(_text_done_count, _text_total)
            text_total_view = _text_total
        else:
            text_done_view = done
            text_total_view = total
        audio_available = False
        try:
            from services.embedding import is_audio_available
            audio_available = is_audio_available()
        except Exception:
            pass

        e5_download = {'status': 'completed', 'percent': 100}
        mert_download = {'status': 'completed', 'percent': 100}
        try:
            from services.embedding import get_download_progress, get_mert_download_progress
            e5_download = get_download_progress()
            mert_download = get_mert_download_progress()
        except Exception:
            pass

        provider = 'cpu'
        generating = False
        try:
            from services.embedding import get_active_provider, get_generation_active
            provider = get_active_provider()
            generating = get_generation_active()
        except Exception:
            pass

        # 更新两类任务的剩余时间（由轮询驱动；阶段切换时自动重新采样）
        _update_eta(
            'text', text_done_view, text_total_view, text_processing,
            'gpu' if _text_use_gpu else 'cpu',
        )
        _update_eta('audio', audio_done_view, audio_total_view, audio_processing, 'encoding')
        text_eta = _eta_state['text']['eta']
        audio_eta = _eta_state['audio']['eta']

        return jsonify({
            'total': total,
            'done': done,
            'text_done': text_done_view,
            'text_total': text_total_view,
            'pending': total - done,
            'ready': done > 0,
            'st_available': is_available(),
            'provider': provider,
            'langs': langs,
            'mood_scores_ready': mood_scores_ready,
            'audio_done': audio_done_view,
            'audio_total': audio_total_view,
            'audio_available': audio_available,
            'audio_processing': audio_processing,
            'text_processing': text_processing,
            'text_provider': 'GPU' if _text_use_gpu and text_processing else ('CPU' if text_processing else 'idle'),
            'text_eta_sec': None if text_eta is None else round(text_eta, 1),
            'audio_eta_sec': None if audio_eta is None else round(audio_eta, 1),
            'generating': generating,
            'e5_download': e5_download,
            'mert_download': mert_download,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== Embedding 生成 ====================

def _upsert_vector(cursor, song_id, source, blob, audio=False):
    """写入（或更新）song_vectors 行。"""
    if audio:
        cursor.execute(
            '''INSERT INTO song_vectors (song_id, source, audio_vec, audio_version, updated_at)
               VALUES (?, ?, ?, ?, datetime('now','localtime'))
               ON CONFLICT(song_id, source) DO UPDATE SET
                 audio_vec = excluded.audio_vec,
                 audio_version = excluded.audio_version,
                 updated_at = datetime('now','localtime')''',
            (song_id, source, blob, AUDIO_VECTOR_VERSION)
        )
    else:
        cursor.execute(
            '''INSERT INTO song_vectors (song_id, source, text_vec, text_version, updated_at)
               VALUES (?, ?, ?, ?, datetime('now','localtime'))
               ON CONFLICT(song_id, source) DO UPDATE SET
                 text_vec = excluded.text_vec,
                 text_version = excluded.text_version,
                 updated_at = datetime('now','localtime')''',
            (song_id, source, blob, TEXT_VECTOR_VERSION)
        )


def _run_generation(flask_app, pending_songs, audio_pending, include_audio=True):
    """
    并行生成文本（CPU 起步，音频完成后切 GPU）与音频向量。
    全部完成后：失效向量缓存 → 异步刷新情绪分数 → 异步刷新用户画像。
    include_audio=False 时只补文本向量（扫描后自动触发用，避免静默下载音频模型）。
    返回是否成功启动（已有任务在跑时返回 False）。
    """
    global _generating_text_embeddings, _generating_audio_embeddings
    global _text_use_gpu, _audio_total, _audio_done_count, _generation_running

    with _generation_guard:
        if _generation_running:
            return False
        _generation_running = True

    from services.embedding import (
        set_generation_active, wait_for_e5_download, wait_for_mert_download,
        encode_songs_batch, encode_audio_batch,
        embedding_to_blob,
    )

    set_generation_active(True)
    _audio_embedding_done.clear()

    def _start_e5_download():
        from services.embedding import _get_model
        try:
            _get_model()
        except Exception:
            pass

    def _start_mert_download():
        from services.embedding import _get_audio_model
        try:
            _get_audio_model()
        except Exception:
            pass

    # 没有音频待处理项时不下载 MERT，并立即允许文本走 GPU
    has_audio = include_audio and bool(audio_pending)
    if not has_audio:
        _audio_embedding_done.set()

    threading.Thread(target=_start_e5_download, daemon=True).start()
    if has_audio:
        threading.Thread(target=_start_mert_download, daemon=True).start()

    def _text_worker():
        global _generating_text_embeddings, _text_use_gpu, _text_done_count, _text_total
        wait_for_e5_download(timeout=600)
        from services.embedding import _get_model
        if _get_model() is None:
            return
        _text_total = len(pending_songs)
        _text_done_count = 0
        # 有音频任务时先用 CPU（把 GPU 让给音频），音频完成后切 GPU；
        # 没有音频任务时直接走 GPU。
        use_cpu = not _audio_embedding_done.is_set()
        switched = not use_cpu
        _text_use_gpu = not use_cpu
        _generating_text_embeddings = True
        try:
            with flask_app.app_context():
                db = get_db()
                cursor = db.cursor()
                try:
                    total = len(pending_songs)
                    for offset in range(0, total, 5):
                        if use_cpu and not switched and _audio_embedding_done.is_set():
                            use_cpu = False
                            switched = True
                            _text_use_gpu = True
                            from services.embedding import _get_model as _gm
                            _gm()
                        batch = pending_songs[offset:offset + 5]
                        embeddings = encode_songs_batch(
                            batch,
                            progress_callback=lambda cur, _tot, base=offset: setattr(
                                sys.modules[__name__], '_text_done_count', base + cur
                            ),
                            use_cpu=use_cpu
                        )
                        for song, emb in zip(batch, embeddings):
                            _upsert_vector(
                                cursor, song['id'], song.get('source', 'local'),
                                embedding_to_blob(emb), audio=False
                            )
                        db.commit()
                except Exception:
                    db.rollback()
                finally:
                    cursor.close()
                    db.close()
        finally:
            _generating_text_embeddings = False

    def _audio_worker():
        global _generating_audio_embeddings, _audio_total, _audio_done_count
        wait_for_mert_download(timeout=600)
        _audio_total = len(audio_pending)
        _audio_done_count = 0
        _generating_audio_embeddings = True
        try:
            with flask_app.app_context():
                if not audio_pending:
                    _audio_embedding_done.set()
                    return
                db = get_db()
                cursor = db.cursor()
                # 分块编码并在每块后立即提交：中断后重启只需重算最后一块，
                # 否则整批编码结束才写库，中途退出会导致音频向量全部白算。
                checkpoint = 32
                try:
                    for start in range(0, len(audio_pending), checkpoint):
                        chunk = audio_pending[start:start + checkpoint]
                        source_map = {sid: src for sid, _fp, src in chunk}
                        results = encode_audio_batch(
                            [(sid, fp) for sid, fp, _src in chunk],
                            batch_size=8,
                            progress_callback=lambda cur, _tot, base=start: setattr(
                                sys.modules[__name__], '_audio_done_count',
                                min(base + cur, _audio_total)
                            ),
                        )
                        for song_id, emb in results:
                            if emb is None:
                                continue
                            _upsert_vector(
                                cursor, song_id, source_map.get(song_id, 'local'),
                                emb.astype('float32').tobytes(), audio=True
                            )
                        db.commit()
                        _audio_done_count = min(start + len(chunk), _audio_total)
                except Exception:
                    db.rollback()
                    import traceback
                    traceback.print_exc()
                finally:
                    cursor.close()
                    db.close()
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            _generating_audio_embeddings = False
            _audio_embedding_done.set()

    def _finalize():
        global _generation_running
        t1 = threading.Thread(target=_text_worker, daemon=True)
        t1.start()
        t2 = None
        if has_audio:
            t2 = threading.Thread(target=_audio_worker, daemon=True)
            t2.start()
        t1.join()
        if t2 is not None:
            t2.join()

        # 向量已变更：先失效缓存，让情绪分数/画像读到新向量
        try:
            from services.recommender import invalidate_embedding_cache
            invalidate_embedding_cache()
        except Exception:
            pass

        # 情绪分数必须在模型释放前计算：它需要 encode_text，
        # 若放在卸载之后会重新加载 E5 并长期常驻。算完再统一释放。
        try:
            with flask_app.app_context():
                from services.recommender import compute_all_mood_scores
                db = get_db()
                try:
                    compute_all_mood_scores(db)
                finally:
                    db.close()
        except Exception:
            pass
        finally:
            try:
                from services.embedding import unload_models
                unload_models()
            except Exception:
                pass
            # 情绪分数与模型释放都完成，才认为整个生成流程结束
            set_generation_active(False)
            with _generation_guard:
                _generation_running = False

        # 画像只用库里的向量，不需要模型，异步执行
        def _profile():
            try:
                with flask_app.app_context():
                    from services.profile import refresh_profile
                    from services.vectors import VectorStore
                    db = get_db()
                    refresh_profile(db, user_id=1, vectors=VectorStore.load(db))
                    db.close()
            except Exception:
                pass

        threading.Thread(target=_profile, daemon=True).start()

    threading.Thread(target=_finalize, daemon=True).start()
    return True


@ai_bp.route('/embedding/generate', methods=['POST'])
def generate_embeddings():
    """为尚未生成向量（当前版本）的歌曲批量生成。异步执行，前端轮询状态。"""
    from services.embedding import is_available
    if not is_available():
        return jsonify({
            'error': 'fastembed 未安装。请在终端运行: pip install fastembed'
        }), 503

    try:
        db = get_db()
        pending_songs = _pending_songs(db, audio=False)
        audio_pending = _pending_audio(db)
        db.close()

        if not pending_songs and not audio_pending:
            return jsonify({'success': True, 'message': '所有歌曲的向量已生成'})

        if _generation_running:
            return jsonify({'success': False, 'message': '向量生成任务进行中，请稍候'}), 409

        flask_app = current_app._get_current_object()
        if not _run_generation(flask_app, pending_songs, audio_pending):
            return jsonify({'success': False, 'message': '向量生成任务进行中，请稍候'}), 409

        return jsonify({
            'success': True,
            'message': f'开始生成 {len(pending_songs)} 首歌曲的文本向量、{len(audio_pending)} 首音频向量...'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _pending_audio(db):
    """查询尚未生成（当前版本）音频向量的歌曲，返回 [(id, file_path, source)]。"""
    cursor = db.cursor()
    cursor.execute(
        '''SELECT s.id, s.file_path, 'local' AS source FROM songs s
           WHERE NOT EXISTS (
               SELECT 1 FROM song_vectors v
               WHERE v.song_id = s.id AND v.source = 'local'
                 AND v.audio_vec IS NOT NULL AND v.audio_version = ?
           )''',
        (AUDIO_VECTOR_VERSION,)
    )
    rows = [(r['id'], r['file_path'], r['source']) for r in cursor.fetchall()]
    cursor.execute(
        '''SELECT s.id, s.file_path, 'cloud' AS source FROM cloud_songs s
           WHERE NOT EXISTS (
               SELECT 1 FROM song_vectors v
               WHERE v.song_id = s.id AND v.source = 'cloud'
                 AND v.audio_vec IS NOT NULL AND v.audio_version = ?
           )''',
        (AUDIO_VECTOR_VERSION,)
    )
    rows.extend([(r['id'], r['file_path'], r['source']) for r in cursor.fetchall()])
    cursor.close()
    return rows


def auto_generate_embeddings(flask_app):
    """扫描队列清空后：若开启「自动生成向量」，为新增/变更曲目补齐向量。

    - 仅在 fastembed 可用且文本模型已缓存时触发（避免静默下载 2.2GB 模型）
    - 音频模型已就绪时一并补齐音频向量，否则只做文本向量
    - 与手动生成共用互斥标志，已有任务在跑时直接跳过
    """
    try:
        from services.embedding import is_available, is_text_model_cached, is_mert_downloaded
        if not is_available() or not is_text_model_cached():
            return
        if _generation_running:
            return
        with flask_app.app_context():
            db = get_db()
            cursor = db.cursor()
            try:
                cursor.execute('SELECT auto_generate_vectors FROM settings WHERE user_id = 1')
                row = cursor.fetchone()
            except Exception:
                row = None
            enabled = bool(row['auto_generate_vectors']) if row else False
            if not enabled:
                cursor.close()
                db.close()
                return
            pending_songs = _pending_songs(db, audio=False)
            include_audio = is_mert_downloaded()
            audio_pending = _pending_audio(db) if include_audio else []
            cursor.close()
            db.close()
        if not pending_songs and not audio_pending:
            return
        _run_generation(flask_app, pending_songs, audio_pending, include_audio=include_audio)
    except Exception:
        pass


# ==================== 推荐接口（画像驱动 + 服务端缓存） ====================

def _fetch_recommendations(mode='comprehensive', limit=20, lang=None, mood=None,
                           song_id=None, cache_ttl=RECOMMEND_CACHE_TTL, user_id=1):
    """
    走统一推荐引擎获取结果（含服务端缓存 + 封面 URL 处理）。
    供 /recommend 与 /recommend/previews 共用，保证卡片封面与列表榜首一致。

    缓存 key 含：模式参数 + 用户画像版本 + 向量代次。
    画像刷新 / 向量变更后自动失效。
    """
    from services.recommender import recommend as do_recommend
    from services.profile import get_profile
    from services.vectors import get_generation as get_vector_generation

    db = get_db()
    try:
        profile = get_profile(db, user_id)
        cache_mode = 'mood' if mode == 'weather' else mode
        # 批次时间因子：每日推荐按日期轮换（0 点换一批、当天稳定）；
        # 其余类别按半小时槽轮换（每个整点/半点换一批、槽内稳定）
        now = time.localtime()
        if cache_mode == 'comprehensive':
            time_part = time.strftime('%Y-%m-%d', now)
        else:
            half = '00' if now.tm_min < 30 else '30'
            time_part = time.strftime(f'%Y-%m-%d-%H-{half}', now)
        cache_key = (
            f"rec:{cache_mode}:{time_part}:{lang or ''}:{mood or ''}:{song_id or ''}:{limit}:"
            f"u{user_id}:p{profile.get('version') or 0}:v{get_vector_generation()}"
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, cache_key, True

        # 确定性种子：同一缓存周期内结果一致
        seed = int(hashlib.md5(cache_key.encode()).hexdigest()[:8], 16)
        results = do_recommend(
            db, user_id=user_id, mode=mode, limit=limit, seed=seed,
            lang=lang, mood=mood, song_id=song_id,
        )

        for r in results:
            cover = r.get('cover_url', '')
            if cover and not cover.startswith('http'):
                r['cover_url'] = f"http://127.0.0.1:5000/api/music/cover?path={cover}"

        cache.set(cache_key, results, ttl=cache_ttl)
        return results, cache_key, False
    finally:
        db.close()


@ai_bp.route('/recommend')
def get_recommendations():
    """
    获取 AI 推荐歌曲。

    查询参数:
        mode  (str, 默认 comprehensive): comprehensive | language | mood |
                                         similar | hidden_gem | weather
        lang / mood / song_id / limit / seed
    """
    try:
        from services.embedding import is_available
        if not is_available():
            return jsonify({
                'error': 'fastembed 未安装。请在终端运行: pip install fastembed'
            }), 503

        limit = request.args.get('limit', 20, type=int)
        if limit < 1:
            limit = 20
        if limit > 50:
            limit = 50

        mode = request.args.get('mode', 'comprehensive', type=str)
        lang = request.args.get('lang', type=str)
        mood = request.args.get('mood', type=str)
        song_id = request.args.get('song_id', type=int)

        results, _key, _hit = _fetch_recommendations(
            mode=mode, limit=limit, lang=lang, mood=mood, song_id=song_id,
        )
        return jsonify(results)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 推荐预览（首页卡片封面） ====================

@ai_bp.route('/recommend/previews')
def get_recommend_previews():
    """
    为首页推荐卡片返回每个类别的代表性歌曲封面。

    两道防线：
    1. 推荐引擎优先 — 取推荐结果第一首带封面的歌；
    2. DB fallback 保底 — 直接查库取一首带封面的歌。

    返回 { daily, hidden_gem, moods: { sad, energetic, ... } }
    """
    try:
        from services.embedding import is_available
        st_available = is_available()

        def _first_cover(results):
            for r in results:
                cover = r.get('cover_url') or ''
                if cover:
                    return {'title': r.get('title', ''), 'artist': r.get('artist', ''), 'cover': cover}
            return None

        def _pick_cover_fallback(db, category, mood_key=None):
            cursor = db.cursor()
            if category == 'hidden_gem':
                order_by = 'COALESCE(ps.play_count, 0) ASC'
            else:
                order_by = 'ps.play_count DESC'

            if mood_key and category == 'mood':
                cursor.execute('''
                    SELECT s.title, s.artist, s.cover_url
                    FROM song_mood_scores sms
                    JOIN songs s ON sms.song_id = s.id
                    WHERE s.cover_url IS NOT NULL AND s.cover_url != ''
                      AND sms.mood = ? AND sms.score > 0.3
                      AND EXISTS (
                          SELECT 1 FROM song_vectors v
                          WHERE v.song_id = s.id AND v.source = 'local'
                            AND v.text_vec IS NOT NULL AND v.text_version = ?
                      )
                    ORDER BY sms.score DESC LIMIT 1
                ''', (mood_key, TEXT_VECTOR_VERSION))
                row = cursor.fetchone()
                if not row:
                    cursor.execute('''
                        SELECT s.title, s.artist, s.cover_url
                        FROM songs s
                        LEFT JOIN play_stats ps ON s.fingerprint = ps.fingerprint
                        WHERE s.cover_url IS NOT NULL AND s.cover_url != ''
                          AND EXISTS (
                              SELECT 1 FROM song_vectors v
                              WHERE v.song_id = s.id AND v.source = 'local'
                                AND v.text_vec IS NOT NULL
                          )
                        ORDER BY ps.play_count DESC LIMIT 1
                    ''')
                    row = cursor.fetchone()
            else:
                cursor.execute(f'''
                    SELECT s.title, s.artist, s.cover_url
                    FROM songs s
                    LEFT JOIN play_stats ps ON s.fingerprint = ps.fingerprint
                    WHERE s.cover_url IS NOT NULL AND s.cover_url != ''
                      AND EXISTS (
                          SELECT 1 FROM song_vectors v
                          WHERE v.song_id = s.id AND v.source = 'local'
                            AND v.text_vec IS NOT NULL
                      )
                    ORDER BY {order_by} LIMIT 1
                ''')
                row = cursor.fetchone()
                if not row:
                    cursor.execute('''
                        SELECT title, artist, cover_url
                        FROM cloud_songs
                        WHERE cover_url IS NOT NULL AND cover_url != ''
                          AND EXISTS (
                              SELECT 1 FROM song_vectors v
                              WHERE v.song_id = cloud_songs.id AND v.source = 'cloud'
                                AND v.text_vec IS NOT NULL
                          )
                        LIMIT 1
                    ''')
                    row = cursor.fetchone()

            cursor.close()
            if row:
                cover = row['cover_url']
                if cover and not cover.startswith('http'):
                    cover = f"http://127.0.0.1:5000/api/music/cover?path={cover}"
                return {'title': row['title'], 'artist': row['artist'], 'cover': cover}
            return None

        # 同一张封面只给一张卡使用：曲库较小时避免 10 张卡重复同一首歌
        used_covers = set()

        def _get_card_cover(mode, mood_key=None):
            pick = None
            if st_available:
                try:
                    res, _k, _h = _fetch_recommendations(
                        mode=mode, limit=20, mood=mood_key,
                    )
                    pick = _first_cover(res)
                except Exception:
                    pick = None
            if not pick:
                try:
                    db = get_db()
                    pick = _pick_cover_fallback(db, mode, mood_key)
                    db.close()
                except Exception:
                    pick = None
            if not pick or not pick.get('cover'):
                return pick
            cover = pick['cover']
            if cover in used_covers:
                return None
            used_covers.add(cover)
            return pick

        result = {
            'daily': _get_card_cover('comprehensive'),
            'hidden_gem': _get_card_cover('hidden_gem'),
        }
        result['moods'] = {}
        for mood_key in ('sad', 'energetic', 'calm', 'upbeat', 'fresh', 'romantic', 'inspire'):
            result['moods'][mood_key] = _get_card_cover('mood', mood_key=mood_key)

        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 情绪分数刷新 ====================

@ai_bp.route('/mood-scores/refresh', methods=['POST'])
def refresh_mood_scores():
    """为已有向量的歌曲刷新情绪分数（异步，完成后情绪推荐免模型查询）。"""
    from services.embedding import is_available
    if not is_available():
        return jsonify({
            'error': 'fastembed 未安装。请在终端运行: pip install fastembed'
        }), 503

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            'SELECT COUNT(*) as cnt FROM song_vectors '
            'WHERE text_vec IS NOT NULL AND text_version = ?',
            (TEXT_VECTOR_VERSION,)
        )
        count = cursor.fetchone()['cnt']
        cursor.close()
        db.close()

        if count == 0:
            return jsonify({'success': True, 'message': '没有已生成向量的歌曲'})

        flask_app = current_app._get_current_object()

        def _refresh_async():
            with flask_app.app_context():
                try:
                    from services.recommender import compute_all_mood_scores
                    mood_db = get_db()
                    compute_all_mood_scores(mood_db)
                    mood_db.close()
                except Exception:
                    pass

        threading.Thread(target=_refresh_async, daemon=True).start()
        return jsonify({
            'success': True,
            'message': f'开始为 {count} 首歌曲计算情绪分数...'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 模型路径配置 ====================

@ai_bp.route('/model-download/progress', methods=['GET'])
def get_model_download_progress():
    """获取模型下载进度（前端轮询）。"""
    from services.embedding import get_download_progress
    return jsonify(get_download_progress())


@ai_bp.route('/model-dir', methods=['GET'])
def get_model_dir():
    """获取 AI 模型缓存目录配置。"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('INSERT OR IGNORE INTO ai_api_config (user_id) VALUES (1)')
        cursor.execute('SELECT model_cache_dir FROM ai_api_config WHERE user_id = 1')
        row = cursor.fetchone()
        cursor.close()
        db.close()
        return jsonify({
            'model_cache_dir': row['model_cache_dir'] if row else '',
            'default_path': _get_default_model_dir(),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/model-dir', methods=['PUT'])
def set_model_dir():
    """设置 AI 模型缓存目录。"""
    data = request.get_json(silent=True) or {}
    path = (data.get('model_cache_dir') or '').strip()

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('INSERT OR IGNORE INTO ai_api_config (user_id) VALUES (1)')
        cursor.execute(
            'UPDATE ai_api_config SET model_cache_dir = ?, updated_at = datetime("now","localtime") WHERE user_id = 1',
            (path,)
        )
        db.commit()
        cursor.close()
        db.close()

        from config.config import Config
        Config.AI_MODEL_CACHE_DIR = path or None
        from services.embedding import set_cache_dir, is_loaded
        set_cache_dir(path)

        return jsonify({
            'success': True,
            'model_cache_dir': path or None,
            'need_restart': is_loaded()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
