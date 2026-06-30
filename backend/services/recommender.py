"""
AI 推荐引擎

基于 Embedding 向量的语义相似度推荐，结合流派匹配和语种偏好。
公式: score = 0.6 * cosine_similarity + 0.2 * genre_match + 0.2 * lang_preference
"""
import numpy as np
import hashlib
import time
from services.embedding import blob_to_embedding, get_model_dim


def cosine_similarity(a, b):
    """计算两个向量的余弦相似度"""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _collect_lang_preference(history):
    """
    从播放历史统计语种偏好分布。

    Args:
        history: list of dict, 每个 dict 包含 lang 字段

    Returns:
        dict: { 'zh': 0.45, 'ja': 0.25, ... }
    """
    lang_counts = {}
    total = 0
    for h in history:
        lang = (h.get('lang') or '').strip()
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
            total += 1

    if total == 0:
        return {}

    return {lang: count / total for lang, count in lang_counts.items()}


def _genre_match_score(genre_a, genre_b):
    """两个流派是否匹配（精确匹配 + 宽松匹配）"""
    if not genre_a or not genre_b:
        return 0.5  # 未知流派给中性分数
    ga = genre_a.strip().lower()
    gb = genre_b.strip().lower()
    if ga == gb:
        return 1.0
    # J-Pop / J-Rock / J- 前缀的视为半匹配
    if ga[:2] == gb[:2] and len(ga) > 2 and len(gb) > 2:
        return 0.5
    return 0.0


def _build_reason(song, similar_song):
    """根据匹配类型生成推荐理由"""
    lang = (song.get('lang') or '').strip()
    genre = (song.get('genre') or '').strip()
    artist = (song.get('artist') or '').strip()
    similar_artist = (similar_song.get('artist') or '').strip()
    similar_genre = (similar_song.get('genre') or '').strip()
    similar_title = (similar_song.get('title') or '').strip()

    reasons = []
    if similar_artist and artist and similar_artist == artist:
        reasons.append(f"同为 {artist} 的作品")
    elif similar_genre and genre and similar_genre == genre:
        reasons.append(f"同为 {genre} 风格")
    elif lang:
        lang_names = {
            'zh': '中文', 'ja': '日语', 'en': '英语', 'ko': '韩语',
            'de': '德语', 'ru': '俄语', 'fr': '法语', 'es': '西班牙语'
        }
        lang_label = lang_names.get(lang, lang)
        reasons.append(f"{lang_label}歌曲推荐")

    # 保底理由
    if not reasons:
        reasons.append(f"与你常听的 {similar_title} 风格相似")

    return reasons[0]


def recommend(db, user_history_song_ids, limit=20, seed=None):
    """
    基于用户播放历史生成推荐。

    Args:
        db: SQLite 数据库连接
        user_history_song_ids: 用户最近播放的歌曲 ID 列表（按时间倒序，最多取 20）
        limit: 返回推荐数量
        seed: 随机种子，用于洗牌（None=不洗牌，每次同一顺序）

    Returns:
        list of dict: [{ song_id, title, artist, album, cover_url, file_path,
                         genre, year, duration, lang, reason, score }, ...]
    """
    cursor = db.cursor()

    # ---- 1. 加载全库歌曲的 embedding 向量 ----
    cursor.execute(
        'SELECT id, title, artist, album, cover_url, file_path, '
        'genre, year, duration, lang, embedding, lyrics '
        'FROM songs WHERE embedding IS NOT NULL'
    )
    all_songs = [dict(row) for row in cursor.fetchall()]

    if len(all_songs) < 2:
        cursor.close()
        return []

    # 构建索引: song_id → embedding / info
    id_to_embedding = {}
    id_to_info = {}
    for s in all_songs:
        emb = blob_to_embedding(s['embedding'])
        id_to_embedding[s['id']] = emb
        id_to_info[s['id']] = s

    # ---- 2. 获取用户播放历史，过滤出有 embedding 的歌曲 ----
    history = []
    for sid in user_history_song_ids:
        if sid in id_to_embedding:
            cursor.execute(
                'SELECT title, artist, genre, lang FROM songs WHERE id = ?', (sid,)
            )
            row = cursor.fetchone()
            if row:
                history.append({
                    'id': sid,
                    'title': row['title'],
                    'artist': row['artist'],
                    'genre': row['genre'],
                    'lang': row['lang']
                })

    if not history:
        # 冷启动：返回全库播放次数最多的歌曲
        cursor.execute('''
            SELECT s.id, s.title, s.artist, s.album, s.cover_url, s.file_path,
                   s.genre, s.year, s.duration, s.lang, s.lyrics
            FROM songs s
            LEFT JOIN play_stats ps ON s.fingerprint = ps.fingerprint
            WHERE s.embedding IS NOT NULL
            ORDER BY ps.play_count DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        cursor.close()
        results = []
        for row in rows:
            results.append({
                'song_id': row['id'],
                'title': row['title'] or '',
                'artist': row['artist'] or '',
                'album': row['album'] or '',
                'cover_url': row['cover_url'] or '',
                'file_path': row['file_path'] or '',
                'genre': row['genre'] or '',
                'year': row['year'] or 0,
                'duration': row['duration'] or 0,
                'lang': row['lang'] or '',
                'reason': '热门推荐',
                'score': 0
            })
        return results

    # ---- 3. 计算用户向量（加权平均） ----
    # 权重：越近播放的权重越高（线性衰减）
    dim = get_model_dim()
    n = len(history)
    weights = np.linspace(1.0, 0.3, n)  # 最近权重 1.0，最远 0.3

    user_vector = np.zeros(dim)
    total_weight = 0
    for i, h in enumerate(history):
        emb = id_to_embedding[h['id']]
        user_vector += emb * weights[i]
        total_weight += weights[i]

    if total_weight > 0:
        user_vector /= total_weight

    # ---- 4. 语种偏好 ----
    lang_pref = _collect_lang_preference(history)

    # ---- 5. 计算每首歌的得分 ----
    history_ids = set(h['id'] for h in history)
    scored = []

    for s in all_songs:
        if s['id'] in history_ids:
            continue  # 排除已听过的

        emb = id_to_embedding[s['id']]
        # 余弦相似度
        emb_sim = float(cosine_similarity(user_vector, emb))

        # 流派匹配分：取历史中最高的流派匹配分
        genre_score = 0.0
        for h in history:
            gs = _genre_match_score(h.get('genre', ''), s.get('genre', ''))
            if gs > genre_score:
                genre_score = gs

        # 语种偏好分
        lang = (s.get('lang') or '').strip()
        lang_score = lang_pref.get(lang, 0.1)  # 未出现过的语种给 0.1 保底，保留发现新音乐的可能

        # 综合得分
        score = 0.6 * emb_sim + 0.2 * genre_score + 0.2 * lang_score

        scored.append((score, s))

    # ---- 6. 按得分降序取 Top-N ----
    scored.sort(key=lambda x: x[0], reverse=True)

    # 若有 seed，在 Top N*3 中随机采样，保证刷新生效
    if seed is not None:
        rng = np.random.RandomState(seed)
        pool_size = min(len(scored), limit * 3)
        pool = scored[:pool_size]
        # 用抖动值排序，分数差距小时不同 seed 会产生不同顺序
        jittered = [(score + rng.uniform(-0.03, 0.03), s) for score, s in pool]
        jittered.sort(key=lambda x: x[0], reverse=True)
        top = jittered[:limit]
    else:
        top = scored[:limit]

    # ---- 7. 生成推荐理由 ----
    # 用用户向量最相似的一首历史歌曲作为 anchor
    best_history = max(history, key=lambda h: float(
        cosine_similarity(user_vector, id_to_embedding[h['id']])
    ))

    results = []
    for score, s in top:
        results.append({
            'song_id': s['id'],
            'title': s['title'] or '',
            'artist': s['artist'] or '',
            'album': s['album'] or '',
            'cover_url': s['cover_url'] or '',
            'file_path': s['file_path'] or '',
            'genre': s['genre'] or '',
            'year': s['year'] or 0,
            'duration': s['duration'] or 0,
            'lang': s['lang'] or '',
            'reason': _build_reason(s, best_history),
            'score': round(score, 4)
        })

    cursor.close()
    return results
