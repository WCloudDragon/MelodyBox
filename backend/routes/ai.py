"""
MelodyBox AI 推荐路由

提供 Embedding 生成和 AI 推荐接口。
"""
from flask import Blueprint, request, jsonify, current_app
import threading
import time

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')


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

        # 可用的语言列表（在 close 前查询，只返回歌曲数 >= 20 的语言）
        cursor.execute('''
            SELECT lang, COUNT(*) as cnt FROM songs
            WHERE lang != "" AND embedding IS NOT NULL
            GROUP BY lang HAVING cnt >= 20
            ORDER BY cnt DESC
        ''')
        langs = [row['lang'] for row in cursor.fetchall()]

        cursor.close()
        db.close()

        # 推理后端信息
        provider = 'cpu'
        try:
            from services.embedding import get_active_provider
            provider = get_active_provider()
        except Exception:
            pass

        return jsonify({
            'total': total,
            'done': done,
            'pending': total - done,
            'ready': done > 0,
            'st_available': is_available(),
            'provider': provider,
            'langs': langs
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

        def _generate_async():
            from services.embedding import (
                encode_songs_batch, embedding_to_blob,
                set_generation_active
            )

            set_generation_active(True)

            with flask_app.app_context():
                db2 = get_db()
                cursor2 = db2.cursor()
                batch_size = 32

                try:
                    # 分批生成 + 分批写入，确保前端轮询能实时看到进度
                    total = len(pending_songs)
                    for offset in range(0, total, batch_size):
                        batch = pending_songs[offset:offset + batch_size]
                        embeddings = encode_songs_batch(batch, progress_callback=None)

                        for song, emb in zip(batch, embeddings):
                            blob = embedding_to_blob(emb)
                            cursor2.execute(
                                'UPDATE songs SET embedding = ? WHERE id = ?',
                                (blob, song['id'])
                            )
                        db2.commit()

                        current = min(offset + batch_size, total)
                        print(f'[embedding] 进度: {current}/{total}')

                    print(f'[embedding] 完成: {total} 首歌曲的 embedding 已生成')
                except Exception as e:
                    print(f'[embedding] 生成失败: {e}')
                    db2.rollback()
                finally:
                    cursor2.close()
                    db2.close()
                    set_generation_active(False)

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
            'model_cache_dir': row['model_cache_dir'] if row else ''
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

        # 同步到内存（模型未加载时立即生效）
        from services.embedding import set_cache_dir, is_loaded
        set_cache_dir(path)

        return jsonify({
            'success': True,
            'model_cache_dir': path or None,
            'need_restart': is_loaded()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
