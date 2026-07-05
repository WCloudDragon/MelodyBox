"""
MelodyBox AI 推荐路由

提供 Embedding 生成和 AI 推荐接口。
"""
from flask import Blueprint, request, jsonify, current_app
import threading
import time
import numpy as np
import sys

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# embedding 生成状态（模块级标志）
_generating_text_embeddings = False
_generating_audio_embeddings = False
_audio_total = 0
_audio_done_count = 0
_text_use_gpu = False  # E5 当前是否在使用 GPU


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
        total = cursor.fetchone()['total']
        cursor.execute('SELECT COUNT(*) as done FROM songs WHERE embedding IS NOT NULL')
        done = cursor.fetchone()['done']

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
        audio_done_db = cursor.fetchone()['done']
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

        # 查询尚未生成 embedding 的歌曲
        cursor.execute(
            'SELECT id, title, artist, genre, year, lyrics, lang '
            'FROM songs WHERE embedding IS NULL'
        )
        pending_songs = [dict(row) for row in cursor.fetchall()]
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
                print(f'[embedding] E5 模型加载失败: {e}')

        def _start_mert_download():
            """后台触发 MERT 模型下载+ONNX 导出"""
            from services.embedding import _get_audio_model
            try:
                _get_audio_model()  # 首次调用会触发下载+导出
            except Exception as e:
                print(f'[audio-embedding] MERT 模型加载失败: {e}')

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
            print('[embedding] 等待 E5 模型就绪...')
            wait_for_e5_download(timeout=600)
            # 检查模型是否真的加载成功
            from services.embedding import _get_model
            if _get_model() is None:
                print('[embedding] E5 模型加载失败，文本分析跳过')
                _generating_text_embeddings = False
                return
            _generating_text_embeddings = True
            print('[embedding] E5 模型就绪，开始编码')

            with flask_app.app_context():
                db2 = get_db()
                cursor2 = db2.cursor()
                batch_size = 5
                use_cpu = True  # 初始 CPU，与 MERT GPU 并行
                _text_use_gpu = False
                switched = False
                was_audio_processing = False  # 追踪音频状态变化（False→True→False = 完成）
                try:
                    total = len(pending_songs)
                    for offset in range(0, total, batch_size):
                        # 检测音频是否刚刚完成（True→False 跳变），完成后切 GPU
                        audio_just_finished = was_audio_processing and not _generating_audio_embeddings
                        if use_cpu and audio_just_finished and not switched:
                            use_cpu = False
                            switched = True
                            _text_use_gpu = True
                            print('[embedding] 音频任务已完成，切换到 GPU 加速...')
                            from services.embedding import _get_model
                            _get_model()
                        was_audio_processing = _generating_audio_embeddings

                        batch = pending_songs[offset:offset + batch_size]
                        embeddings = encode_songs_batch(batch, progress_callback=None, use_cpu=use_cpu)
                        for song, emb in zip(batch, embeddings):
                            blob = embedding_to_blob(emb)
                            cursor2.execute(
                                'UPDATE songs SET embedding = ? WHERE id = ?',
                                (blob, song['id'])
                            )
                        db2.commit()
                        current = min(offset + batch_size, total)
                        provider = 'GPU' if not use_cpu else 'CPU'
                        print(f'[embedding] 进度: {current}/{total} ({provider})')
                    print(f'[embedding] 完成: {total} 首歌曲的 embedding 已生成')
                except Exception as e:
                    print(f'[embedding] 生成失败: {e}')
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
                    print('[audio-embedding] 等待 MERT 模型就绪...')
                    from services.embedding import wait_for_mert_download
                    wait_for_mert_download(timeout=600)
                    _generating_audio_embeddings = True
                    print('[audio-embedding] MERT 模型就绪，开始编码')
                    # 查询所有需要音频 embedding 的歌曲（不依赖文本 embedding 完成）
                    db3 = get_db()
                    cursor3 = db3.cursor()
                    cursor3.execute(
                        'SELECT id, file_path FROM songs WHERE audio_embedding IS NULL'
                    )
                    audio_pending = [(row['id'], row['file_path']) for row in cursor3.fetchall()]
                    cursor3.close()
                    db3.close()

                    if not audio_pending:
                        print('[audio-embedding] 所有歌曲音频 embedding 已生成')
                        return

                    _audio_total = len(audio_pending)
                    _audio_done_count = 0
                    print(f'[audio-embedding] 待处理: {_audio_total} 首')

                    from services.embedding import encode_audio_batch
                    results = encode_audio_batch(
                        audio_pending,
                        batch_size=8,
                        progress_callback=lambda cur, tot: (
                            setattr(sys.modules[__name__], '_audio_done_count', cur),
                            print(f'[audio-embedding] 进度: {cur}/{tot}')
                        )
                    )
                    db4 = get_db()
                    cursor4 = db4.cursor()
                    blob_audio_count = 0
                    for song_id, emb in results:
                        if emb is not None:
                            blob = emb.astype(np.float32).tobytes()
                            cursor4.execute(
                                'UPDATE songs SET audio_embedding = ? WHERE id = ?',
                                (blob, song_id)
                            )
                            blob_audio_count += 1
                    db4.commit()
                    cursor4.close()
                    db4.close()
                    _audio_done_count = blob_audio_count
                    print(f'[audio-embedding] 完成: {blob_audio_count}/{_audio_total} 首')
                except Exception as e:
                    print(f'[audio-embedding] 音频 embedding 生成失败: {e}')
                    import traceback
                    traceback.print_exc()
                finally:
                    _generating_audio_embeddings = False
                    # 两个 worker 都完成后才清除生成状态
                    if not _generating_text_embeddings:
                        from services.embedding import set_generation_active
                        set_generation_active(False)

        def _generate_async():
            """并行启动文本（CPU）和音频（GPU）embedding，完成后计算情绪分数"""
            # 并行启动两个线程
            t_text = threading.Thread(target=_text_worker, daemon=True)
            t_audio = threading.Thread(target=_audio_worker, daemon=True)
            t_text.start()
            t_audio.start()

            # 等待两者都完成
            t_text.join()
            t_audio.join()

            # 顺带计算情绪分数
            try:
                print('[mood] 开始计算情绪分数...')
                with flask_app.app_context():
                    from services.recommender import compute_all_mood_scores
                    mood_db = get_db()
                    mood_count = compute_all_mood_scores(mood_db)
                    mood_db.close()
                    print(f'[mood] 情绪分数计算完成: {mood_count} 条记录')
            except Exception as e:
                print(f'[mood] 情绪分数计算失败: {e}')

        threading.Thread(target=_generate_async, daemon=True).start()

        return jsonify({
            'success': True,
            'message': f'开始生成 {len(pending_songs)} 首歌曲的 embedding...'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 推荐接口 ====================

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

        db = get_db()
        cursor = db.cursor()

        # 获取用户最近播放的歌曲 ID（按播放时间倒序）
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
        db.close()

        # 调用推荐引擎
        from services.recommender import recommend as do_recommend

        # 推荐参数
        mode = request.args.get('mode', 'comprehensive', type=str)
        lang = request.args.get('lang', type=str)
        mood = request.args.get('mood', type=str)
        song_id = request.args.get('song_id', type=int)

        # 需要重新获取带 Row factory 的连接
        db2 = get_db()
        # 种子：可用请求参数指定，否则用当前时间戳确保每次刷新不同
        seed = request.args.get('seed', type=int)
        if seed is None:
            seed = int(time.time() * 1000) % (2 ** 31)
        results = do_recommend(db2, history_ids, mode=mode, limit=limit, seed=seed,
                               lang=lang, mood=mood, song_id=song_id)

        # 处理封面 URL
        for r in results:
            cover = r.get('cover_url', '')
            if cover and not cover.startswith('http'):
                r['cover_url'] = f"http://127.0.0.1:5000/api/music/cover?path={cover}"

        return jsonify(results)

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
                    print(f'[mood] 情绪分数刷新完成: {mood_count} 条记录')
                except Exception as e:
                    print(f'[mood] 情绪分数刷新失败: {e}')

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
