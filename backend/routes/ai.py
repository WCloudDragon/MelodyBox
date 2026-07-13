"""
MelodyBox AI 推荐路由

提供 Embedding 生成和 AI 推荐接口。
"""
from flask import Blueprint, request, jsonify, current_app
import threading
import time
import hashlib
import numpy as np
import sys
from utils.cache import cache

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# embedding 生成状态（模块级标志）
_generating_text_embeddings = False
_generating_audio_embeddings = False
_audio_total = 0
_audio_done_count = 0
_text_use_gpu = False  # E5 当前是否在使用 GPU
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


# ==================== Embedding 生成 ====================

@ai_bp.route('/embedding/status')
def embedding_status():
    """获取全库 embedding 生成状态"""
    try:
        from services.embedding import is_available

        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT COUNT(*) as total FROM songs')
        local_total = cursor.fetchone()['total']
        cursor.execute('SELECT COUNT(*) as total FROM cloud_songs')
        cloud_total = cursor.fetchone()['total']
        total = local_total + cloud_total

        cursor.execute('SELECT COUNT(*) as done FROM songs WHERE embedding IS NOT NULL')
        local_done = cursor.fetchone()['done']
        cursor.execute('SELECT COUNT(*) as done FROM cloud_songs WHERE embedding IS NOT NULL')
        cloud_done = cursor.fetchone()['done']
        done = local_done + cloud_done

        # 可用的语言列表（在 close 前查询）
        cursor.execute('''
            SELECT lang, COUNT(*) as cnt FROM songs
            WHERE lang != "" AND embedding IS NOT NULL
            GROUP BY lang
            ORDER BY cnt DESC
        ''')
        langs = [row['lang'] for row in cursor.fetchall()]

        # 检查情绪分数是否已预计算
        cursor.execute('SELECT COUNT(*) as cnt FROM song_mood_scores')
        mood_scores_ready = cursor.fetchone()['cnt'] > 0

        # 音频 embedding 统计（处理中用实时计数，完成后用数据库计数）
        cursor.execute('SELECT COUNT(*) as done FROM songs WHERE audio_embedding IS NOT NULL')
        local_audio_done = cursor.fetchone()['done']
        cursor.execute('SELECT COUNT(*) as done FROM cloud_songs WHERE audio_embedding IS NOT NULL')
        cloud_audio_done = cursor.fetchone()['done']
        audio_done_db = local_audio_done + cloud_audio_done
        audio_processing = _generating_audio_embeddings
        text_processing = _generating_text_embeddings
        # 处理中用实时进度，完成后用数据库实际数量
        audio_done = _audio_done_count if audio_processing else audio_done_db
        audio_available = False
        try:
            from services.embedding import is_audio_available
            audio_available = is_audio_available()
        except Exception:
            pass

        # 获取模型下载进度
        e5_download = {'status': 'completed', 'percent': 100}
        mert_download = {'status': 'completed', 'percent': 100}
        try:
            from services.embedding import get_download_progress, get_mert_download_progress
            e5_download = get_download_progress()
            mert_download = get_mert_download_progress()
        except Exception:
            pass

        cursor.close()
        db.close()

        # 推理后端信息
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


@ai_bp.route('/embedding/generate', methods=['POST'])
def generate_embeddings():
    """
    为全库中尚未生成 embedding 的歌曲批量生成向量。
    异步执行，前端可轮询 /api/ai/embedding/status 查看进度。

    返回: { success: true, message: "开始生成 X 首歌曲的 embedding..." }
    """
    from services.embedding import is_available
    if not is_available():
        return jsonify({
            'error': 'fastembed 未安装。请在终端运行: pip install fastembed'
        }), 503

    try:
        db = get_db()
        cursor = db.cursor()

        # 查询尚未生成 embedding 的歌曲（本地 + 云端）
        cursor.execute(
            'SELECT id, title, artist, genre, year, lyrics, lang, "local" AS source '
            'FROM songs WHERE embedding IS NULL'
        )
        pending_songs = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            'SELECT id, title, artist, genre, year, lyrics, lang, "cloud" AS source '
            'FROM cloud_songs WHERE embedding IS NULL'
        )
        pending_songs.extend([dict(row) for row in cursor.fetchall()])
        cursor.close()
        db.close()

        if not pending_songs:
            return jsonify({'success': True, 'message': '所有歌曲的 embedding 已生成'})

        flask_app = current_app._get_current_object()

        # 标记生成任务开始（整个生成周期有效，不因单个 worker 失败而提前清除）
        from services.embedding import set_generation_active
        set_generation_active(True)

        # --- 并行启动两个模型下载（如果尚未就绪） ---
        def _start_e5_download():
            """后台触发 E5 模型下载（fastembed 会自动缓存）"""
            from services.embedding import _get_model
            try:
                _get_model()  # 首次调用会触发下载
            except Exception as e:
                pass

        def _start_mert_download():
            """后台触发 MERT 模型下载+ONNX 导出"""
            from services.embedding import _get_audio_model
            try:
                _get_audio_model()  # 首次调用会触发下载+导出
            except Exception as e:
                pass

        # 启动下载线程（如果模型已就绪会立即返回）
        threading.Thread(target=_start_e5_download, daemon=True).start()
        threading.Thread(target=_start_mert_download, daemon=True).start()

        def _text_worker():
            """文本 embedding 线程：等待 E5 下载完成后开始编码"""
            global _generating_text_embeddings, _text_use_gpu
            from services.embedding import (
                encode_songs_batch, embedding_to_blob,
                set_generation_active, wait_for_e5_download
            )

            # 等待 E5 模型就绪
            wait_for_e5_download(timeout=600)
            # 检查模型是否真的加载成功
            from services.embedding import _get_model
            if _get_model() is None:
                _generating_text_embeddings = False
                return
            _generating_text_embeddings = True

            with flask_app.app_context():
                db2 = get_db()
                cursor2 = db2.cursor()
                batch_size = 5
                use_cpu = True  # 初始 CPU，与 MERT GPU 并行
                _text_use_gpu = False
                switched = False
                try:
                    total = len(pending_songs)
                    for offset in range(0, total, batch_size):
                        # 检测音频是否已完成（Event 信号），完成后切 GPU
                        if use_cpu and not switched and _audio_embedding_done.is_set():
                            use_cpu = False
                            switched = True
                            _text_use_gpu = True
                            from services.embedding import _get_model
                            _get_model()

                        batch = pending_songs[offset:offset + batch_size]
                        embeddings = encode_songs_batch(batch, progress_callback=None, use_cpu=use_cpu)
                        for song, emb in zip(batch, embeddings):
                            blob = embedding_to_blob(emb)
                            table = 'cloud_songs' if song.get('source') == 'cloud' else 'songs'
                            cursor2.execute(
                                f'UPDATE {table} SET embedding = ? WHERE id = ?',
                                (blob, song['id'])
                            )
                        db2.commit()
                        current = min(offset + batch_size, total)
                        provider = 'GPU' if not use_cpu else 'CPU'
                except Exception as e:
                    db2.rollback()
                finally:
                    cursor2.close()
                    db2.close()
                    _generating_text_embeddings = False
                    # 两个 worker 都完成后才清除生成状态
                    if not _generating_audio_embeddings:
                        set_generation_active(False)

        def _audio_worker():
            """音频 embedding 线程：等待 MERT 下载+导出完成后开始编码"""
            global _generating_audio_embeddings, _audio_total, _audio_done_count
            with flask_app.app_context():
                try:
                    # 等待 MERT 模型就绪
                    from services.embedding import wait_for_mert_download
                    wait_for_mert_download(timeout=600)
                    _generating_audio_embeddings = True
                    # 查询所有需要音频 embedding 的歌曲（不依赖文本 embedding 完成）
                    db3 = get_db()
                    cursor3 = db3.cursor()
                    cursor3.execute(
                        'SELECT id, file_path, "local" AS source FROM songs WHERE audio_embedding IS NULL'
                    )
                    audio_pending = [(row['id'], row['file_path'], row['source']) for row in cursor3.fetchall()]
                    cursor3.execute(
                        'SELECT id, file_path, "cloud" AS source FROM cloud_songs WHERE audio_embedding IS NULL'
                    )
                    audio_pending.extend([(row['id'], row['file_path'], row['source']) for row in cursor3.fetchall()])
                    cursor3.close()
                    db3.close()

                    if not audio_pending:
                        _audio_embedding_done.set()
                        return

                    _audio_total = len(audio_pending)
                    _audio_done_count = 0

                    from services.embedding import encode_audio_batch
                    # 构建 (song_id, source) 映射，传递给 encode 函数时只传 (song_id, file_path)
                    audio_source_map = {sid: src for sid, _, src in audio_pending}
                    audio_pairs = [(sid, fp) for sid, fp, _ in audio_pending]
                    results = encode_audio_batch(
                        audio_pairs,
                        batch_size=8,
                        progress_callback=lambda cur, tot:
                            setattr(sys.modules[__name__], '_audio_done_count', cur)
                    )
                    db4 = get_db()
                    cursor4 = db4.cursor()
                    blob_audio_count = 0
                    for song_id, emb in results:
                        if emb is not None:
                            blob = emb.astype(np.float32).tobytes()
                            table = 'cloud_songs' if audio_source_map.get(song_id) == 'cloud' else 'songs'
                            cursor4.execute(
                                f'UPDATE {table} SET audio_embedding = ? WHERE id = ?',
                                (blob, song_id)
                            )
                            blob_audio_count += 1
                    db4.commit()
                    cursor4.close()
                    db4.close()
                    _audio_done_count = blob_audio_count
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                finally:
                    _generating_audio_embeddings = False
                    _audio_embedding_done.set()
                    # 两个 worker 都完成后才清除生成状态
                    if not _generating_text_embeddings:
                        from services.embedding import set_generation_active
                        set_generation_active(False)

        def _generate_async():
            """并行启动文本（CPU）和音频（GPU）embedding，完成后异步计算情绪分数"""
            # 重置音频完成信号
            _audio_embedding_done.clear()

            # 并行启动两个线程
            t_text = threading.Thread(target=_text_worker, daemon=True)
            t_audio = threading.Thread(target=_audio_worker, daemon=True)
            t_text.start()
            t_audio.start()

            # 等待两者都完成
            t_text.join()
            t_audio.join()

            # 清空 embedding 缓存，确保新生成的 embedding 可见
            from services.recommender import invalidate_embedding_cache
            invalidate_embedding_cache()

            # 情绪分数异步计算（不阻塞 embedding 生成完成回调）
            def _compute_mood_async():
                try:
                    with flask_app.app_context():
                        from services.recommender import compute_all_mood_scores
                        mood_db = get_db()
                        mood_count = compute_all_mood_scores(mood_db)
                        mood_db.close()
                except Exception as e:
                    pass

            threading.Thread(target=_compute_mood_async, daemon=True).start()

        threading.Thread(target=_generate_async, daemon=True).start()

        return jsonify({
            'success': True,
            'message': f'开始生成 {len(pending_songs)} 首歌曲的 embedding...'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 自动 Embedding（供扫描完成后调用） ====================

def auto_generate_embeddings(flask_app):
    """
    自动为新入库的歌曲生成 embedding。
    供扫描完成后调用，内部检查 fastembed 可用性和待处理歌曲数量。
    """
    try:
        from services.embedding import is_available
        if not is_available():
            return

        with flask_app.app_context():
            db = get_db()
            cursor = db.cursor()
            cursor.execute('SELECT COUNT(*) as cnt FROM songs WHERE embedding IS NULL')
            pending = cursor.fetchone()['cnt']
            cursor.close()
            db.close()

        if pending > 0:
            # 复用 generate_embeddings 的逻辑（直接调用会因缺少 request 上下文失败）
            # 所以直接启动后台线程执行核心逻辑
            _start_embedding_generation(flask_app)
    except Exception as e:
        pass


def _start_embedding_generation(flask_app):
    """启动 embedding 生成（内部函数，供 auto_generate_embeddings 和 generate_embeddings 共用）"""
    import routes.ai as ai_module

    def _worker():
        try:
            with flask_app.app_context():
                db = get_db()
                cursor = db.cursor()
                cursor.execute(
                    'SELECT id, title, artist, genre, year, lyrics, lang, "local" AS source '
                    'FROM songs WHERE embedding IS NULL'
                )
                pending_songs = [dict(row) for row in cursor.fetchall()]
                cursor.execute(
                    'SELECT id, title, artist, genre, year, lyrics, lang, "cloud" AS source '
                    'FROM cloud_songs WHERE embedding IS NULL'
                )
                pending_songs.extend([dict(row) for row in cursor.fetchall()])
                cursor.close()
                db.close()

            if not pending_songs:
                return

            from services.embedding import set_generation_active
            set_generation_active(True)

            # --- 并行启动两个模型下载 ---
            def _start_e5_download():
                from services.embedding import _get_model
                try:
                    _get_model()
                except Exception as e:
                    pass

            def _start_mert_download():
                from services.embedding import _get_audio_model
                try:
                    _get_audio_model()
                except Exception as e:
                    pass

            threading.Thread(target=_start_e5_download, daemon=True).start()
            threading.Thread(target=_start_mert_download, daemon=True).start()

            def _text_worker():
                from services.embedding import (
                    encode_songs_batch, embedding_to_blob,
                    set_generation_active, wait_for_e5_download
                )
                wait_for_e5_download(timeout=600)
                from services.embedding import _get_model
                if _get_model() is None:
                    return
                ai_module._generating_text_embeddings = True

                with flask_app.app_context():
                    db2 = get_db()
                    cursor2 = db2.cursor()
                    batch_size = 5
                    try:
                        total = len(pending_songs)
                        for offset in range(0, total, batch_size):
                            batch = pending_songs[offset:offset + batch_size]
                            embeddings = encode_songs_batch(batch, progress_callback=None, use_cpu=True)
                            for song, emb in zip(batch, embeddings):
                                blob = embedding_to_blob(emb)
                                table = 'cloud_songs' if song.get('source') == 'cloud' else 'songs'
                                cursor2.execute(f'UPDATE {table} SET embedding = ? WHERE id = ?', (blob, song['id']))
                            db2.commit()
                    except Exception as e:
                        db2.rollback()
                    finally:
                        cursor2.close()
                        db2.close()
                        ai_module._generating_text_embeddings = False
                        if not ai_module._generating_audio_embeddings:
                            set_generation_active(False)

            def _audio_worker():
                from services.embedding import wait_for_mert_download, encode_audio_batch
                wait_for_mert_download(timeout=600)
                ai_module._generating_audio_embeddings = True

                with flask_app.app_context():
                    db3 = get_db()
                    cursor3 = db3.cursor()
                    cursor3.execute('SELECT id, file_path, "local" AS source FROM songs WHERE audio_embedding IS NULL')
                    audio_pending = [(row['id'], row['file_path'], row['source']) for row in cursor3.fetchall()]
                    cursor3.execute('SELECT id, file_path, "cloud" AS source FROM cloud_songs WHERE audio_embedding IS NULL')
                    audio_pending.extend([(row['id'], row['file_path'], row['source']) for row in cursor3.fetchall()])
                    cursor3.close()
                    db3.close()

                    if not audio_pending:
                        ai_module._generating_audio_embeddings = False
                        return

                    audio_source_map = {sid: src for sid, _, src in audio_pending}
                    audio_pairs = [(sid, fp) for sid, fp, _ in audio_pending]
                    results = encode_audio_batch(audio_pairs, batch_size=8)

                    db4 = get_db()
                    cursor4 = db4.cursor()
                    for song_id, emb in results:
                        if emb is not None:
                            blob = emb.astype(np.float32).tobytes()
                            table = 'cloud_songs' if audio_source_map.get(song_id) == 'cloud' else 'songs'
                            cursor4.execute(f'UPDATE {table} SET audio_embedding = ? WHERE id = ?', (blob, song_id))
                    db4.commit()
                    cursor4.close()
                    db4.close()

                ai_module._generating_audio_embeddings = False
                if not ai_module._generating_text_embeddings:
                    from services.embedding import set_generation_active
                    set_generation_active(False)

            def _run_all():
                t1 = threading.Thread(target=_text_worker, daemon=True)
                t2 = threading.Thread(target=_audio_worker, daemon=True)
                t1.start()
                t2.start()
                t1.join()
                t2.join()

                from services.recommender import invalidate_embedding_cache
                invalidate_embedding_cache()

                # 异步计算情绪分数
                def _mood():
                    try:
                        with flask_app.app_context():
                            from services.recommender import compute_all_mood_scores
                            mood_db = get_db()
                            compute_all_mood_scores(mood_db)
                            mood_db.close()
                    except Exception:
                        pass
                threading.Thread(target=_mood, daemon=True).start()

            threading.Thread(target=_run_all, daemon=True).start()

        except Exception as e:
            pass

    threading.Thread(target=_worker, daemon=True).start()


# ==================== 推荐接口 ====================

def _get_history_ids(db):
    """获取用户最近播放的歌曲 ID（按播放时间倒序，最多 20 首）。"""
    cursor = db.cursor()
    cursor.execute('''
        SELECT DISTINCT s.id
        FROM play_history ph
        JOIN songs s ON ph.song_id = s.id
        WHERE ph.song_id IS NOT NULL
        GROUP BY ph.fingerprint
        ORDER BY MAX(ph.played_at) DESC
        LIMIT 20
    ''')
    history_ids = [row['id'] for row in cursor.fetchall()]
    cursor.close()
    return history_ids


def _fetch_recommendations(mode='comprehensive', limit=20, lang=None, mood=None, song_id=None,
                           cache_ttl=300):
    """
    走完整推荐引擎获取结果（含缓存 + 封面 URL 处理）。
    供 /recommend 接口与 /recommend/previews 卡片封面共用，确保卡片封面
    与点击进入推荐页后看到的第一首歌保持一致。

    Returns:
        (results, cache_key, hit) — results 为推荐结果列表；
        hit 为 True 表示命中缓存。失败时 results 为 []。
    """
    from services.recommender import recommend as do_recommend

    db = get_db()
    try:
        history_ids = _get_history_ids(db)

        # 构建缓存 key（含用户历史，确保不同用户历史得到不同推荐）
        # weather 与 mood 共享缓存，确保天气卡片封面 = 推荐列表榜首
        cache_mode = 'mood' if mode == 'weather' else mode
        cache_key = f"rec:{cache_mode}:{lang or ''}:{mood or ''}:{song_id or ''}:{limit}:{hashlib.md5(str(history_ids).encode()).hexdigest()[:8]}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, cache_key, True

        # 使用确定性种子（基于缓存 key），同一缓存周期内结果一致
        seed = int(hashlib.md5(cache_key.encode()).hexdigest()[:8], 16)
        results = do_recommend(db, history_ids, mode=mode, limit=limit, seed=seed,
                               lang=lang, mood=mood, song_id=song_id)

        # 处理封面 URL
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
        mode  (str, 默认 comprehensive): 推荐模式
              - comprehensive  : 综合推荐
              - language       : 按语言推荐（需传 lang 参数）
              - mood           : 按情绪推荐（需传 mood 参数）
              - similar        : 相似歌曲（需传 song_id 参数）
              - hidden_gem     : 冷门宝藏
        lang  (str, 可选): ISO 639-1 语言代码，如 zh/ja/en/ko/de/ru
        mood  (str, 可选): 情绪关键词 sad/energetic/calm/upbeat/fresh/romantic/inspire
        song_id (int, 可选): mode=similar 时的参考歌曲 ID
        limit (int, 默认 20, 最大 50): 返回推荐数量
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

        # 推荐参数
        mode = request.args.get('mode', 'comprehensive', type=str)
        lang = request.args.get('lang', type=str)
        mood = request.args.get('mood', type=str)
        song_id = request.args.get('song_id', type=int)

        results, cache_key, hit = _fetch_recommendations(
            mode=mode, limit=limit, lang=lang, mood=mood, song_id=song_id, cache_ttl=300
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
    1. 推荐引擎优先 — 走 _fetch_recommendations 获取推荐结果，
       取第一首带封面的歌（与推荐页榜首一致）。
    2. DB fallback 保底 — 推荐引擎返回空 / 全部无封面 / 抛异常时，
       直接查库取一首带封面的歌（确保不显示 emoji）。

    返回 { daily, hidden_gem, moods: { sad, energetic, calm, ... } }
    """
    try:
        from services.embedding import is_available
        st_available = is_available()

        def _first_cover(results):
            """从推荐结果列表取第一首带封面的歌曲，返回卡片预览 dict。"""
            for r in results:
                cover = r.get('cover_url') or ''
                if cover:
                    return {'title': r.get('title', ''), 'artist': r.get('artist', ''), 'cover': cover}
            return None

        def _pick_cover_fallback(db, category, mood_key=None):
            """
            DB 保底：直接查库取一首带封面的歌（WHERE cover_url IS NOT NULL AND != ''）。
            确保封面 URL 一定非空。
            """
            cursor = db.cursor()

            if category == 'hidden_gem':
                order_by = 'COALESCE(ps.play_count, 0) ASC'
            else:
                order_by = 'ps.play_count DESC'

            if mood_key and category == 'mood':
                # 情绪模式：从 song_mood_scores 取最高分且带封面的歌
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
                    # 情绪表无数据，按播放量取
                    cursor.execute('''
                        SELECT s.title, s.artist, s.cover_url
                        FROM songs s
                        LEFT JOIN play_stats ps ON s.fingerprint = ps.fingerprint
                        WHERE s.cover_url IS NOT NULL AND s.cover_url != ''
                          AND s.embedding IS NOT NULL
                        ORDER BY ps.play_count DESC LIMIT 1
                    ''')
                    row = cursor.fetchone()
            else:
                # daily / hidden_gem：按播放量排序取带封面的歌
                cursor.execute(f'''
                    SELECT s.title, s.artist, s.cover_url
                    FROM songs s
                    LEFT JOIN play_stats ps ON s.fingerprint = ps.fingerprint
                    WHERE s.cover_url IS NOT NULL AND s.cover_url != ''
                      AND s.embedding IS NOT NULL
                    ORDER BY {order_by} LIMIT 1
                ''')
                row = cursor.fetchone()
                if not row:
                    # 本地无结果，尝试云端
                    cursor.execute('''
                        SELECT title, artist, cover_url
                        FROM cloud_songs
                        WHERE cover_url IS NOT NULL AND cover_url != ''
                          AND embedding IS NOT NULL
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
            """
            获取单个卡片的封面：推荐引擎优先，DB fallback 保底。
            返回 { title, artist, cover } 或 None。
            """
            tag = mood_key or mode

            # 第一道防线：推荐引擎
            if st_available:
                try:
                    res, _, _ = _fetch_recommendations(
                        mode=mode, limit=50, mood=mood_key, cache_ttl=300
                    )
                    pick = _first_cover(res)
                    if pick:
                        return pick
                except Exception as e:
                    pass

            # 第二道防线：DB 直接查询
            try:
                db = get_db()
                pick = _pick_cover_fallback(db, mode, mood_key)
                db.close()
                return pick
            except Exception as e:
                return None

        # 生成各卡片封面
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
    """
    为已有 embedding 的歌曲刷新情绪分数。
    异步执行，完成后情绪推荐即可免模型查询。
    """
    from services.embedding import is_available
    if not is_available():
        return jsonify({
            'error': 'fastembed 未安装。请在终端运行: pip install fastembed'
        }), 503

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT COUNT(*) as cnt FROM songs WHERE embedding IS NOT NULL')
        count = cursor.fetchone()['cnt']
        cursor.close()
        db.close()

        if count == 0:
            return jsonify({'success': True, 'message': '没有已生成 embedding 的歌曲'})

        flask_app = current_app._get_current_object()

        def _refresh_async():
            with flask_app.app_context():
                try:
                    from services.recommender import compute_all_mood_scores
                    mood_db = get_db()
                    mood_count = compute_all_mood_scores(mood_db)
                    mood_db.close()
                except Exception as e:
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
    """获取模型下载进度（前端轮询）"""
    from services.embedding import get_download_progress
    return jsonify(get_download_progress())

# ==================== 模型路径配置 ====================

@ai_bp.route('/model-dir', methods=['GET'])
def get_model_dir():
    """获取 AI 模型缓存目录配置"""
    try:
        db = get_db()
        cursor = db.cursor()
        # 自动初始化 ai_api_config 行
        cursor.execute(
            'INSERT OR IGNORE INTO ai_api_config (user_id) VALUES (1)'
        )
        cursor.execute(
            'SELECT model_cache_dir FROM ai_api_config WHERE user_id = 1'
        )
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
    """设置 AI 模型缓存目录"""
    data = request.get_json(silent=True) or {}
    path = (data.get('model_cache_dir') or '').strip()

    try:
        db = get_db()
        cursor = db.cursor()
        # 确保行存在
        cursor.execute(
            'INSERT OR IGNORE INTO ai_api_config (user_id) VALUES (1)'
        )
        cursor.execute(
            'UPDATE ai_api_config SET model_cache_dir = ?, updated_at = datetime("now","localtime") WHERE user_id = 1',
            (path,)
        )
        db.commit()
        cursor.close()
        db.close()

        # 同步到 Config 和 embedding 模块（模型未加载时立即生效）
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
