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
_text_use_gpu = False
# 音频 embedding 完成信号（用于 CPU→GPU 切换）
_audio_embedding_done = threading.Event()


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


def _count_pending(db, audio=False):
    col = 'audio_vec' if audio else 'text_vec'
    vcol = 'audio_version' if audio else 'text_version'
    version = AUDIO_VECTOR_VERSION if audio else TEXT_VECTOR_VERSION
    cursor = db.cursor()
    cursor.execute(
        f'''SELECT
              (SELECT COUNT(*) FROM songs s WHERE NOT EXISTS (
                  SELECT 1 FROM song_vectors v
                  WHERE v.song_id = s.id AND v.source = 'local'
                    AND v.{col} IS NOT NULL AND v.{vcol} = ?)) +
              (SELECT COUNT(*) FROM cloud_songs s WHERE NOT EXISTS (
                  SELECT 1 FROM song_vectors v
                  WHERE v.song_id = s.id AND v.source = 'cloud'
                    AND v.{col} IS NOT NULL AND v.{vcol} = ?))
              AS cnt''',
        (version, version)
    )
    cnt = cursor.fetchone()['cnt']
    cursor.close()
    return cnt


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
        audio_done = _audio_done_count if audio_processing else audio_done_db
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
            from services.embedding import get_active_provider, is_generation_active
            provider = get_active_provider()
            generating = is_generation_active()
        except Exception:
            pass

        return jsonify({
            'total': total,
            'done': done,
            'pending': total - done,
            'ready': done > 0,
            'st_available': is_available(),
            'provider': provider,
            'langs': langs,
            'mood_scores_ready': mood_scores_ready,
            'audio_done': audio_done,
            'audio_total': _audio_total,
            'audio_available': audio_available,
            'audio_processing': audio_processing,
            'text_processing': text_processing,
            'text_provider': 'GPU' if _text_use_gpu and text_processing else ('CPU' if text_processing else 'idle'),
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
            (song_id, source, blob)
        )
    else:
        cursor.execute(
            '''INSERT INTO song_vectors (song_id, source, text_vec, text_version, updated_at)
               VALUES (?, ?, ?, ?, datetime('now','localtime'))
               ON CONFLICT(song_id, source) DO UPDATE SET
                 text_vec = excluded.text_vec,
                 text_version = excluded.text_version,
                 updated_at = datetime('now','localtime')''',
            (song_id, source, blob)
        )


def _run_generation(flask_app, pending_songs, audio_pending):
    """
    并行生成文本（CPU 起步，音频完成后切 GPU）与音频向量。
    全部完成后：失效向量缓存 → 异步刷新情绪分数 → 异步刷新用户画像。
    """
    global _generating_text_embeddings, _generating_audio_embeddings
    global _text_use_gpu, _audio_total, _audio_done_count

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

    threading.Thread(target=_start_e5_download, daemon=True).start()
    threading.Thread(target=_start_mert_download, daemon=True).start()

    def _text_worker():
        global _generating_text_embeddings, _text_use_gpu
        wait_for_e5_download(timeout=600)
        from services.embedding import _get_model
        if _get_model() is None:
            return
        _generating_text_embeddings = True
        _text_use_gpu = False
        use_cpu = True
        switched = False
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
                            batch, progress_callback=None, use_cpu=use_cpu
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
            if not _generating_audio_embeddings:
                set_generation_active(False)

    def _audio_worker():
        global _generating_audio_embeddings, _audio_total, _audio_done_count
        wait_for_mert_download(timeout=600)
        _generating_audio_embeddings = True
        try:
            with flask_app.app_context():
                if not audio_pending:
                    _audio_embedding_done.set()
                    return
                _audio_total = len(audio_pending)
                _audio_done_count = 0
                audio_pairs = [(sid, fp) for sid, fp, _src in audio_pending]
                results = encode_audio_batch(
                    audio_pairs,
                    batch_size=8,
                    progress_callback=lambda cur, tot: setattr(
                        sys.modules[__name__], '_audio_done_count', cur
                    ),
                )
                db = get_db()
                cursor = db.cursor()
                blob_count = 0
                for song_id, emb in results:
                    if emb is not None:
                        src = next((s for s in (audio_pending) if s[0] == song_id), None)
                        source = src[2] if src else 'local'
                        _upsert_vector(
                            cursor, song_id, source,
                            emb.astype('float32').tobytes(), audio=True
                        )
                        blob_count += 1
                db.commit()
                cursor.close()
                db.close()
                _audio_done_count = blob_count
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            _generating_audio_embeddings = False
            _audio_embedding_done.set()
            if not _generating_text_embeddings:
                set_generation_active(False)

    def _finalize():
        t1 = threading.Thread(target=_text_worker, daemon=True)
        t2 = threading.Thread(target=_audio_worker, daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # 向量已变更：失效缓存 + 异步刷新情绪分数与画像
        from services.recommender import invalidate_embedding_cache
        invalidate_embedding_cache()

        def _mood():
            try:
                with flask_app.app_context():
                    from services.recommender import compute_all_mood_scores
                    db = get_db()
                    compute_all_mood_scores(db)
                    db.close()
            except Exception:
                pass

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

        threading.Thread(target=_mood, daemon=True).start()
        threading.Thread(target=_profile, daemon=True).start()

    threading.Thread(target=_finalize, daemon=True).start()


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

        flask_app = current_app._get_current_object()
        _run_generation(flask_app, pending_songs, audio_pending)

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


def _start_embedding_generation(flask_app):
    """供 auto_generate_embeddings 使用的后台启动入口。"""
    def _worker():
        try:
            with flask_app.app_context():
                db = get_db()
                pending_songs = _pending_songs(db, audio=False)
                audio_pending = _pending_audio(db)
                db.close()
            if not pending_songs and not audio_pending:
                return
            _run_generation(flask_app, pending_songs, audio_pending)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def auto_generate_embeddings(flask_app):
    """扫描完成后自动为未生成向量的新歌生成向量。"""
    try:
        from services.embedding import is_available
        if not is_available():
            return
        with flask_app.app_context():
            db = get_db()
            pending = _count_pending(db, audio=False)
            db.close()
        if pending > 0:
            _start_embedding_generation(flask_app)
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
        # 每日推荐按日期轮换（当天结果稳定，次日自动换一批）
        day_part = time.strftime('%Y-%m-%d') if cache_mode == 'comprehensive' else ''
        cache_key = (
            f"rec:{cache_mode}:{day_part}:{lang or ''}:{mood or ''}:{song_id or ''}:{limit}:"
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
                    ORDER BY sms.score DESC LIMIT 1
                ''', (mood_key,))
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

        def _get_card_cover(mode, mood_key=None):
            if st_available:
                try:
                    res, _k, _h = _fetch_recommendations(
                        mode=mode, limit=20, mood=mood_key,
                    )
                    pick = _first_cover(res)
                    if pick:
                        return pick
                except Exception:
                    pass
            try:
                db = get_db()
                pick = _pick_cover_fallback(db, mode, mood_key)
                db.close()
                return pick
            except Exception:
                return None

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
