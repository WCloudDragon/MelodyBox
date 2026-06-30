"""
AI 推荐引擎

支持多种推荐模式：
- comprehensive  : 综合推荐（embedding + 流派 + 语种偏好）
- language       : 按语言推荐
- mood           : 按情绪推荐（embedding 语义搜索）
- similar        : 相似歌曲
- hidden_gem     : 冷门宝藏
"""
import numpy as np
from services.embedding import blob_to_embedding, get_model_dim


# 语言名映射（含 zh-cn/zh-tw 变体）
LANG_NAMES = {
    'zh': '中文', 'zh-cn': '中文', 'zh-tw': '中文',
    'ja': '日语', 'en': '英语', 'ko': '韩语',
    'de': '德语', 'ru': '俄语', 'fr': '法语', 'es': '西班牙语'
}

# 情绪关键词 → 语义搜索文本
MOOD_QUERIES = {
    'sad':       '悲伤抒情的歌曲，关于离别、失恋和回忆',
    'energetic': '激昂热血的歌曲，节奏强劲充满力量',
    'calm':      '舒缓放松的歌曲，安静温柔的氛围音乐',
    'upbeat':    '欢快动感的歌曲，让人想跟着跳舞',
    'fresh':     '清新自然的歌曲，民谣和轻音乐风格',
    'romantic':  '浪漫甜蜜的情歌，关于爱情的美好',
    'inspire':   '励志向上的歌曲，给人希望和勇气',
}

MOOD_LABELS = {
    'sad': '伤感', 'energetic': '激昂', 'calm': '舒缓',
    'upbeat': '动感', 'fresh': '清新', 'romantic': '浪漫', 'inspire': '励志',
}


def cosine_similarity(a, b):
    """计算两个向量的余弦相似度"""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _load_all_songs(db):
    """加载全库有 embedding 的歌曲"""
    cursor = db.cursor()
    cursor.execute(
        'SELECT id, title, artist, album, cover_url, file_path, '
        'genre, year, duration, lang, embedding, lyrics '
        'FROM songs WHERE embedding IS NOT NULL'
    )
    all_songs = [dict(row) for row in cursor.fetchall()]
    cursor.close()

    id_to_embedding = {}
    id_to_info = {}
    for s in all_songs:
        emb = blob_to_embedding(s['embedding'])
        id_to_embedding[s['id']] = emb
        id_to_info[s['id']] = s
    return all_songs, id_to_embedding, id_to_info


def _song_to_result(s, score, reason):
    """将歌曲 dict 转为统一响应格式"""
    return {
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
        'reason': reason,
        'score': round(score, 4)
    }


def _collect_lang_preference(history):
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
    if not genre_a or not genre_b:
        return 0.5
    ga = genre_a.strip().lower()
    gb = genre_b.strip().lower()
    if ga == gb:
        return 1.0
    if ga[:2] == gb[:2] and len(ga) > 2 and len(gb) > 2:
        return 0.5
    return 0.0


def _build_reason(song, similar_song):
    lang = (song.get('lang') or '').strip()
    genre = (song.get('genre') or '').strip()
    artist = (song.get('artist') or '').strip()
    similar_artist = (similar_song.get('artist') or '').strip()
    similar_genre = (similar_song.get('genre') or '').strip()
    similar_title = (similar_song.get('title') or '').strip()

    if similar_artist and artist and similar_artist == artist:
        return f"同为 {artist} 的作品"
    if similar_genre and genre and similar_genre == genre:
        return f"同为 {genre} 风格"
    if lang:
        return f"{LANG_NAMES.get(lang, lang)}歌曲推荐"
    return f"与你常听的 {similar_title} 风格相似"


# ==================== 综合推荐 ====================

def recommend_comprehensive(db, user_history_song_ids, limit=20, seed=None):
    """
    综合推荐：embedding 余弦相似度 + 流派匹配 + 语种偏好。
    公式: score = 0.6 * cosine_similarity + 0.2 * genre_match + 0.2 * lang_preference
    """
    all_songs, id_to_embedding, id_to_info = _load_all_songs(db)

    if len(all_songs) < 2:
        return []

    # 获取用户播放历史
    cursor = db.cursor()
    history = []
    for sid in user_history_song_ids:
        if sid in id_to_embedding:
            cursor.execute('SELECT title, artist, genre, lang FROM songs WHERE id = ?', (sid,))
            row = cursor.fetchone()
            if row:
                history.append({
                    'id': sid, 'title': row['title'],
                    'artist': row['artist'], 'genre': row['genre'], 'lang': row['lang']
                })
    cursor.close()

    if not history:
        return _cold_start(db, limit)

    # 用户向量（加权平均）
    dim = get_model_dim()
    n = len(history)
    weights = np.linspace(1.0, 0.3, n)
    user_vector = np.zeros(dim)
    total_weight = 0
    for i, h in enumerate(history):
        emb = id_to_embedding[h['id']]
        user_vector += emb * weights[i]
        total_weight += weights[i]
    if total_weight > 0:
        user_vector /= total_weight

    lang_pref = _collect_lang_preference(history)

    # 评分
    history_ids = set(h['id'] for h in history)
    scored = []
    for s in all_songs:
        if s['id'] in history_ids:
            continue
        emb = id_to_embedding[s['id']]
        emb_sim = float(cosine_similarity(user_vector, emb))
        genre_score = max((_genre_match_score(h.get('genre', ''), s.get('genre', '')) for h in history), default=0.5)
        lang = (s.get('lang') or '').strip()
        lang_score = lang_pref.get(lang, 0.1)
        score = 0.6 * emb_sim + 0.2 * genre_score + 0.2 * lang_score
        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 种子抖动
    if seed is not None:
        rng = np.random.RandomState(seed)
        pool_size = min(len(scored), limit * 3)
        pool = scored[:pool_size]
        jittered = [(score + rng.uniform(-0.03, 0.03), s) for score, s in pool]
        jittered.sort(key=lambda x: x[0], reverse=True)
        top = jittered[:limit]
    else:
        top = scored[:limit]

    best_history = max(history, key=lambda h: float(
        cosine_similarity(user_vector, id_to_embedding[h['id']])
    ))

    return [_song_to_result(s, score, _build_reason(s, best_history)) for score, s in top]


# ==================== 按语言推荐 ====================

def recommend_by_language(db, lang, user_history_song_ids, limit=20, seed=None):
    """
    按语言推荐：SQL 过滤 lang，再用 embedding 语义相似度排序。
    """
    all_songs, id_to_embedding, id_to_info = _load_all_songs(db)

    # 过滤目标语言（支持前缀匹配：zh 匹配 zh-cn/zh-tw）
    def _lang_match(song_lang):
        sl = (song_lang or '').strip().lower()
        if not sl:
            return False
        return sl == lang or sl.startswith(lang + '-')
    target_songs = [s for s in all_songs if _lang_match(s.get('lang'))]
    if not target_songs:
        return []

    history_ids = set(user_history_song_ids)
    history_songs = [s for s in target_songs if s['id'] in history_ids]
    candidates = [s for s in target_songs if s['id'] not in history_ids]

    if not candidates:
        return []

    # 有播放历史时，用历史歌曲向量计算相似度
    if history_songs:
        dim = get_model_dim()
        seed_list = history_songs[:min(20, len(history_songs))]
        history_vec = np.zeros(dim)
        for h in seed_list:
            history_vec += id_to_embedding[h['id']]
        history_vec /= len(seed_list)

        scored = []
        for s in candidates:
            sim = float(cosine_similarity(history_vec, id_to_embedding[s['id']]))
            scored.append((sim, s))
        scored.sort(key=lambda x: x[0], reverse=True)
    else:
        # 无历史：按播放次数排序
        cursor = db.cursor()
        # 批量获取候选歌曲的 fingerprint
        candidate_ids = [s['id'] for s in candidates]
        placeholders = ','.join(['?'] * len(candidate_ids))
        cursor.execute(
            f'SELECT id, fingerprint FROM songs WHERE id IN ({placeholders})',
            candidate_ids
        )
        id_to_fp = {row['id']: row['fingerprint'] for row in cursor.fetchall()}

        cursor.execute('SELECT fingerprint, play_count FROM play_stats')
        fp_to_count = {row['fingerprint']: (row['play_count'] or 0) for row in cursor.fetchall()}
        cursor.close()

        scored = []
        for s in candidates:
            fp = id_to_fp.get(s['id'], '')
            score = float(fp_to_count.get(fp, 0))
            scored.append((score, s))
        scored.sort(key=lambda x: x[0], reverse=True)

    # 种子抖动
    if seed is not None and len(scored) > limit:
        rng = np.random.RandomState(seed)
        pool_size = min(len(scored), limit * 3)
        pool = scored[:pool_size]
        jittered = [(score + rng.uniform(-0.03, 0.03), s) for score, s in pool]
        jittered.sort(key=lambda x: x[0], reverse=True)
        top = jittered[:limit]
    else:
        top = scored[:limit]

    lang_label = LANG_NAMES.get(lang, lang)
    return [_song_to_result(s, score, f"{lang_label}歌曲推荐") for score, s in top]


# ==================== 按情绪推荐 ====================

def recommend_by_mood(db, mood, user_history_song_ids, limit=20, seed=None):
    """
    按情绪推荐：用情绪关键词编码为向量 → embedding 语义搜索。
    不依赖历史，纯基于情绪的全局搜索。
    """
    from services.embedding import encode_text

    mood_text = MOOD_QUERIES.get(mood)
    if not mood_text:
        return []

    all_songs, id_to_embedding, id_to_info = _load_all_songs(db)
    if not all_songs:
        return []

    # 编码情绪查询
    query_vec = encode_text(mood_text)

    # 计算所有歌曲与情绪查询的相似度
    history_ids = set(user_history_song_ids)
    scored = []
    for s in all_songs:
        if s['id'] in history_ids:
            continue
        sim = float(cosine_similarity(query_vec, id_to_embedding[s['id']]))
        scored.append((sim, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 种子抖动
    if seed is not None and len(scored) > limit:
        rng = np.random.RandomState(seed)
        pool_size = min(len(scored), limit * 3)
        pool = scored[:pool_size]
        jittered = [(score + rng.uniform(-0.03, 0.03), s) for score, s in pool]
        jittered.sort(key=lambda x: x[0], reverse=True)
        top = jittered[:limit]
    else:
        top = scored[:limit]

    mood_label = MOOD_LABELS.get(mood, mood)
    return [_song_to_result(s, score, f"{mood_label}歌曲推荐") for score, s in top]


# ==================== 相似歌曲 ====================

def recommend_similar(db, song_id, limit=20):
    """给定一首歌曲，找 Top-N 相似歌曲"""
    all_songs, id_to_embedding, id_to_info = _load_all_songs(db)

    if len(all_songs) < 2:
        return []

    if song_id not in id_to_embedding:
        return []

    target_emb = id_to_embedding[song_id]
    target_info = id_to_info.get(song_id, {})
    target_title = target_info.get('title', '这首歌')

    scored = []
    for s in all_songs:
        if s['id'] == song_id:
            continue
        sim = float(cosine_similarity(target_emb, id_to_embedding[s['id']]))
        scored.append((sim, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    return [_song_to_result(s, score, f"与「{target_title}」相似") for score, s in top]


# ==================== 冷门宝藏 ====================

def recommend_hidden_gems(db, user_history_song_ids, limit=20, seed=None):
    """
    冷门宝藏：低播放次数 + 高语义相似度。
    找用户可能喜欢但很少被播放的歌曲。
    """
    all_songs, id_to_embedding, id_to_info = _load_all_songs(db)

    if len(all_songs) < 2:
        return []

    # 获取用户历史向量
    history = [h for h in user_history_song_ids if h in id_to_embedding]
    history_ids = set(history)

    if not history:
        return _cold_start(db, limit)

    dim = get_model_dim()
    history_vec = np.zeros(dim)
    for sid in history[:20]:
        history_vec += id_to_embedding[sid]
    history_vec /= min(len(history), 20)

    # 获取所有歌曲的播放次数
    cursor = db.cursor()
    play_counts = {}
    cursor.execute('SELECT fingerprint, play_count FROM play_stats')
    for row in cursor.fetchall():
        play_counts[row['fingerprint']] = row['play_count'] or 0
    cursor.close()

    scored = []
    for s in all_songs:
        if s['id'] in history_ids:
            continue
        fp = s.get('fingerprint', '')
        play_count = play_counts.get(fp, 0)

        # 只考虑播放次数低（< 3）或未播放过的
        if play_count >= 3:
            continue

        emb_sim = float(cosine_similarity(history_vec, id_to_embedding[s['id']]))
        # 相似度为主，播放次数微调（越少越好）
        cold_bonus = 1.0 / max(play_count + 1, 1)
        score = 0.9 * emb_sim + 0.1 * cold_bonus
        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    if seed is not None and len(scored) > limit:
        rng = np.random.RandomState(seed)
        pool_size = min(len(scored), limit * 3)
        pool = scored[:pool_size]
        jittered = [(score + rng.uniform(-0.03, 0.03), s) for score, s in pool]
        jittered.sort(key=lambda x: x[0], reverse=True)
        top = jittered[:limit]
    else:
        top = scored[:limit]

    return [_song_to_result(s, score, '冷门宝藏') for score, s in top]


# ==================== 冷启动 ====================

def _cold_start(db, limit=20):
    """无播放历史时的回退：全库热门"""
    cursor = db.cursor()
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
    return [_song_to_result(dict(row), 0, '热门推荐') for row in rows]


# ==================== 调度入口 ====================

def recommend(db, user_history_song_ids, mode='comprehensive', limit=20, seed=None,
              lang=None, mood=None, song_id=None):
    """
    统一推荐入口。

    Args:
        mode: comprehensive | language | mood | similar | hidden_gem
        lang: mode=language 时指定 ISO 639-1 语言代码
        mood: mode=mood 时指定情绪关键词
        song_id: mode=similar 时指定参考歌曲 ID
    """
    if mode == 'language' and lang:
        return recommend_by_language(db, lang, user_history_song_ids, limit, seed)
    elif mode == 'mood' and mood:
        return recommend_by_mood(db, mood, user_history_song_ids, limit, seed)
    elif mode == 'similar' and song_id:
        return recommend_similar(db, song_id, limit)
    elif mode == 'hidden_gem':
        return recommend_hidden_gems(db, user_history_song_ids, limit, seed)
    else:
        return recommend_comprehensive(db, user_history_song_ids, limit, seed)
