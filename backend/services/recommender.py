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
from services.embedding import blob_to_embedding, get_model_dim, get_audio_model_dim


# ==================== 模块级 embedding 缓存 ====================
# 避免每次推荐请求都全量反序列化 BLOB（1000 首歌 = 4MB numpy 转换）
_embedding_cache = {}          # {song_id: numpy_array}
_audio_embedding_cache = {}    # {song_id: numpy_array}


def invalidate_embedding_cache():
    """清空 embedding 缓存（歌曲变更后调用）"""
    global _embedding_cache, _audio_embedding_cache
    _embedding_cache.clear()
    _audio_embedding_cache.clear()


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


def compute_all_mood_scores(db):
    """
    为所有已有 embedding 的歌曲计算与 7 种情绪的余弦相似度，存入 song_mood_scores 表。
    同时计算音频维度的情绪分数（基于音频嵌入与情绪音频原型的相似度）。

    需要在模型已加载后调用（内部会调用 encode_text）。
    返回写入的记录数。
    """
    from services.embedding import encode_text, blob_to_embedding

    # 加载全库歌曲 embedding（文本 + 音频）
    cursor = db.cursor()
    cursor.execute('SELECT id, embedding, audio_embedding FROM songs WHERE embedding IS NOT NULL')
    rows = cursor.fetchall()

    if not rows:
        cursor.close()
        return 0

    song_embs = [(row['id'], blob_to_embedding(row['embedding'])) for row in rows]
    # 音频 embedding（可能部分歌曲未生成）
    song_audio_embs = {}
    for row in rows:
        if row['audio_embedding'] is not None:
            song_audio_embs[row['id']] = blob_to_embedding(row['audio_embedding'])
    has_audio = len(song_audio_embs) > 0
    cursor.close()

    # 编码 7 种情绪查询文本
    print('[mood] 编码 7 种情绪查询向量...')
    mood_vecs = {}
    for mood_key, query_text in MOOD_QUERIES.items():
        mood_vecs[mood_key] = encode_text(query_text)
    print(f'[mood] 情绪查询向量编码完成，共 {len(mood_vecs)} 种')

    # 计算文本情绪分数，并按 mood 分组排序
    mood_text_scores = {}  # {mood_key: [(song_id, score), ...]}
    for mood_key, mood_vec in mood_vecs.items():
        scores = []
        for song_id, song_emb in song_embs:
            score = float(cosine_similarity(song_emb, mood_vec))
            scores.append((song_id, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        mood_text_scores[mood_key] = scores

    # 如果有音频 embedding，为每种情绪构建音频原型（top-5 文本匹配歌曲的音频平均向量）
    mood_audio_prototypes = {}
    if has_audio:
        print('[mood] 构建 7 种情绪的音频原型向量...')
        audio_dim = get_audio_model_dim()
        for mood_key in MOOD_QUERIES:
            top_songs = mood_text_scores[mood_key][:5]
            prototype = np.zeros(audio_dim)
            count = 0
            for sid, _ in top_songs:
                if sid in song_audio_embs:
                    prototype += song_audio_embs[sid]
                    count += 1
            if count > 0:
                mood_audio_prototypes[mood_key] = prototype / count

    # 写入数据库
    cursor = db.cursor()
    cursor.execute('DELETE FROM song_mood_scores')  # 全量刷新
    count = 0
    for mood_key in MOOD_QUERIES:
        for song_id, text_score in mood_text_scores[mood_key]:
            audio_score = None
            if mood_key in mood_audio_prototypes and song_id in song_audio_embs:
                audio_score = float(cosine_similarity(
                    mood_audio_prototypes[mood_key], song_audio_embs[song_id]
                ))
                cursor.execute(
                    'INSERT INTO song_mood_scores (song_id, mood, score, audio_score) VALUES (?, ?, ?, ?)',
                    (song_id, mood_key, text_score, audio_score)
                )
            else:
                cursor.execute(
                    'INSERT INTO song_mood_scores (song_id, mood, score) VALUES (?, ?, ?)',
                    (song_id, mood_key, text_score)
                )
            count += 1
    db.commit()
    cursor.close()
    return count


def cosine_similarity(a, b):
    """计算两个向量的余弦相似度"""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _load_all_songs(db):
    """加载全库有 embedding 的歌曲（文本 + 音频），使用模块级缓存避免重复反序列化 BLOB"""
    global _embedding_cache, _audio_embedding_cache

    cursor = db.cursor()
    cursor.execute(
        'SELECT id, title, artist, album, cover_url, file_path, '
        'genre, year, duration, lang, embedding, audio_embedding, lyrics '
        'FROM songs WHERE embedding IS NOT NULL'
    )
    rows = cursor.fetchall()
    cursor.close()

    all_songs = []
    id_to_embedding = {}
    id_to_audio_embedding = {}
    id_to_info = {}

    for row in rows:
        sid = row['id']
        song_dict = dict(row)
        all_songs.append(song_dict)
        id_to_info[sid] = song_dict

        # 文本 embedding：命中缓存则跳过 BLOB 反序列化
        if sid not in _embedding_cache:
            _embedding_cache[sid] = blob_to_embedding(song_dict['embedding'])
        id_to_embedding[sid] = _embedding_cache[sid]

        # 音频 embedding 可能为 NULL（旧数据或生成中）
        if song_dict['audio_embedding'] is not None:
            if sid not in _audio_embedding_cache:
                _audio_embedding_cache[sid] = blob_to_embedding(song_dict['audio_embedding'])
            id_to_audio_embedding[sid] = _audio_embedding_cache[sid]

    return all_songs, id_to_embedding, id_to_audio_embedding, id_to_info


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


def _mmr_rerank(scored_songs, id_to_embedding, limit, lambda_param=0.7):
    """
    MMR (Maximal Marginal Relevance) 多样性重排。
    在保持相关性的同时，惩罚与已选歌曲相似度高的候选项，避免同一艺术家扎堆。
    """
    if len(scored_songs) <= limit:
        return scored_songs

    selected = [scored_songs[0]]
    remaining = scored_songs[1:]
    selected_artists = {selected[0][1].get('artist', '')}

    while len(selected) < limit and remaining:
        best_idx = 0
        best_score = -float('inf')
        for i, (score, s) in enumerate(remaining):
            artist_penalty = 0.3 if s.get('artist', '') in selected_artists else 0.0
            max_sim = min(
                1.0,
                max(
                    cosine_similarity(id_to_embedding[s['id']], id_to_embedding[sel[1]['id']])
                    for sel in selected
                )
            )
            mmr_score = lambda_param * score - (1 - lambda_param) * max_sim - artist_penalty
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        best_item = remaining.pop(best_idx)
        selected.append(best_item)
        selected_artists.add(best_item[1].get('artist', ''))

    return selected


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
    综合推荐：文本语义 + 音频特征 + 流派匹配 + 语种偏好。
    公式: score = 0.40 * text_sim + 0.30 * audio_sim + 0.15 * genre_match + 0.15 * lang_pref
    当音频 embedding 不可用时，回退到纯文本模式 (0.60 / 0.20 / 0.20)。
    """
    all_songs, id_to_embedding, id_to_audio_embedding, id_to_info = _load_all_songs(db)

    if len(all_songs) < 2:
        return []

    has_audio = len(id_to_audio_embedding) > 0

    # 获取用户播放历史（单次 IN 查询，避免 N+1）
    history = []
    valid_ids = [sid for sid in user_history_song_ids if sid in id_to_embedding]
    if valid_ids:
        cursor = db.cursor()
        placeholders = ','.join(['?'] * len(valid_ids))
        cursor.execute(
            f'SELECT id, title, artist, genre, lang FROM songs WHERE id IN ({placeholders})',
            valid_ids
        )
        for row in cursor.fetchall():
            history.append({
                'id': row['id'], 'title': row['title'],
                'artist': row['artist'], 'genre': row['genre'], 'lang': row['lang']
            })
        cursor.close()

    if not history:
        return _cold_start(db, limit)

    # 用户文本向量（加权平均）
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

    # 用户音频向量（加权平均，仅当有历史音频 embedding 时）
    user_audio_vector = None
    if has_audio:
        audio_dim = get_audio_model_dim()
        user_audio_vector = np.zeros(audio_dim)
        audio_total_weight = 0
        for i, h in enumerate(history):
            if h['id'] in id_to_audio_embedding:
                audio_emb = id_to_audio_embedding[h['id']]
                user_audio_vector += audio_emb * weights[i]
                audio_total_weight += weights[i]
        if audio_total_weight > 0:
            user_audio_vector /= audio_total_weight
        else:
            user_audio_vector = None

    lang_pref = _collect_lang_preference(history)

    # 评分
    history_ids = set(h['id'] for h in history)
    scored = []
    for s in all_songs:
        if s['id'] in history_ids:
            continue

        emb = id_to_embedding[s['id']]
        text_sim = float(cosine_similarity(user_vector, emb))

        # 音频相似度
        audio_sim = 0.0
        audio_available = False
        if has_audio and user_audio_vector is not None and s['id'] in id_to_audio_embedding:
            audio_sim = float(cosine_similarity(user_audio_vector, id_to_audio_embedding[s['id']]))
            audio_available = True

        genre_score = max((_genre_match_score(h.get('genre', ''), s.get('genre', '')) for h in history), default=0.5)
        lang = (s.get('lang') or '').strip()
        lang_score = lang_pref.get(lang, 0.1)

        if audio_available:
            score = 0.40 * text_sim + 0.30 * audio_sim + 0.15 * genre_score + 0.15 * lang_score
        else:
            # 回退纯文本模式
            score = 0.60 * text_sim + 0.20 * genre_score + 0.20 * lang_score

        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 种子抖动：取 Top(limit×3) 加小幅随机扰动，增加刷新新鲜感
    if seed is not None:
        rng = np.random.RandomState(seed)
        pool_size = min(len(scored), limit * 3)
        pool = scored[:pool_size]
        jittered = [(score + rng.uniform(-0.03, 0.03), s) for score, s in pool]
        jittered.sort(key=lambda x: x[0], reverse=True)
        top = _mmr_rerank(jittered, id_to_embedding, limit)
    else:
        top = _mmr_rerank(scored, id_to_embedding, limit)

    best_history = max(history, key=lambda h: float(
        cosine_similarity(user_vector, id_to_embedding[h['id']])
    ))

    return [_song_to_result(s, score, _build_reason(s, best_history)) for score, s in top]


# ==================== 按语言推荐 ====================

# 常见语言列表，"其他"分类排除这些
_COMMON_LANGS = {'inst', 'zh', 'zh-cn', 'zh-tw', 'ja', 'en', 'ko', 'de', 'ru',
                 'fr', 'es', 'pt', 'it', 'vi', 'nl', 'sv', 'no', 'da',
                 'fi', 'tr', 'pl', 'ar', 'th', 'id', 'hi'}


def recommend_by_language(db, lang, user_history_song_ids, limit=20, seed=None):
    """
    按语言推荐：SQL 过滤 lang，再用 embedding 语义相似度排序。
    支持 lang=other 匹配所有非通用语言。
    """
    all_songs, id_to_embedding, _, id_to_info = _load_all_songs(db)

    if lang == 'other':
        def _lang_match(song_lang):
            sl = (song_lang or '').strip().lower()
            return bool(sl) and sl not in _COMMON_LANGS
        lang_label = '其他语言'
    else:
        def _lang_match(song_lang):
            sl = (song_lang or '').strip().lower()
            if not sl:
                return False
            return sl == lang or sl.startswith(lang + '-')
        lang_label = LANG_NAMES.get(lang, lang)

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

    return [_song_to_result(s, score, f"{lang_label}歌曲推荐") for score, s in top]


# ==================== 按情绪推荐 ====================

def recommend_by_mood(db, mood, user_history_song_ids, limit=20, seed=None):
    """
    按情绪推荐：从 song_mood_scores 表直接查询预计算好的分数。
    当 audio_score 可用时，使用文本+音频加权评分（0.5×文本 + 0.5×音频）。
    """
    mood_label = MOOD_LABELS.get(mood, mood)
    mood_query_text = MOOD_QUERIES.get(mood)
    if not mood_query_text:
        return []

    # 从预计算表中查询
    history_ids = set(user_history_song_ids)
    cursor = db.cursor()

    # 先查总数判断是否有数据
    cursor.execute('SELECT COUNT(*) as cnt FROM song_mood_scores WHERE mood = ?', (mood,))
    if cursor.fetchone()['cnt'] == 0:
        cursor.close()
        # 回退：实时计算（首次生成 embedding 后才会存表）
        return _recommend_by_mood_fallback(db, mood, user_history_song_ids, limit, seed, mood_label)

    placeholders = ','.join(['?'] * len(history_ids)) if history_ids else '1=1'
    history_filter = f'AND s.id NOT IN ({placeholders})' if history_ids else ''

    # 音频分数可用时加权排序，否则回退纯文本分数
    cursor.execute(f'''
        SELECT s.id, s.title, s.artist, s.album, s.cover_url, s.file_path,
               s.genre, s.year, s.duration, s.lang, s.lyrics,
               ms.score, ms.audio_score
        FROM song_mood_scores ms
        JOIN songs s ON ms.song_id = s.id
        WHERE ms.mood = ? {history_filter}
        ORDER BY (CASE WHEN ms.audio_score IS NOT NULL
                       THEN 0.5 * ms.score + 0.5 * ms.audio_score
                       ELSE ms.score END) DESC
        LIMIT ?
    ''', [mood] + (list(history_ids) if history_ids else []) + [limit])

    rows = cursor.fetchall()
    cursor.close()

    if not rows:
        return []

    results = []
    for row in rows:
        d = dict(row)
        # 使用加权分数（如果有音频分数），否则用纯文本分数
        if d.get('audio_score') is not None:
            d['score'] = 0.5 * d['score'] + 0.5 * d['audio_score']
        results.append(_song_to_result(d, d['score'], f"{mood_label}歌曲推荐"))

    # 种子抖动
    if seed is not None and len(results) > limit:
        rng = np.random.RandomState(seed)
        jittered = [(r['score'] + rng.uniform(-0.03, 0.03), r) for r in results]
        jittered.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in jittered[:limit]]

    return results


def _recommend_by_mood_fallback(db, mood, user_history_song_ids, limit, seed, mood_label):
    """回退：实时编码情绪向量并做余弦相似度（旧逻辑，song_mood_scores 表为空时使用）"""
    from services.embedding import encode_text

    mood_text = MOOD_QUERIES.get(mood)
    if not mood_text:
        return []

    all_songs, id_to_embedding, _, id_to_info = _load_all_songs(db)

    if not all_songs:
        return []

    query_vec = encode_text(mood_text)
    history_ids = set(user_history_song_ids)
    scored = []
    for s in all_songs:
        if s['id'] in history_ids:
            continue
        sim = float(cosine_similarity(query_vec, id_to_embedding[s['id']]))
        scored.append((sim, s))

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

    return [_song_to_result(s, score, f"{mood_label}歌曲推荐") for score, s in top]


# ==================== 相似歌曲 ====================

def recommend_similar(db, song_id, limit=20):
    """给定一首歌曲，找 Top-N 相似歌曲（文本语义 + 音频特征）"""
    all_songs, id_to_embedding, id_to_audio_embedding, id_to_info = _load_all_songs(db)

    if len(all_songs) < 2:
        return []

    if song_id not in id_to_embedding:
        return []

    target_emb = id_to_embedding[song_id]
    target_audio_emb = id_to_audio_embedding.get(song_id)
    target_info = id_to_info.get(song_id, {})
    target_title = target_info.get('title', '这首歌')
    has_audio = target_audio_emb is not None

    scored = []
    for s in all_songs:
        if s['id'] == song_id:
            continue
        text_sim = float(cosine_similarity(target_emb, id_to_embedding[s['id']]))
        if has_audio and s['id'] in id_to_audio_embedding:
            audio_sim = float(cosine_similarity(target_audio_emb, id_to_audio_embedding[s['id']]))
            score = 0.5 * text_sim + 0.5 * audio_sim
        else:
            score = text_sim
        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    return [_song_to_result(s, score, f"与「{target_title}」相似") for score, s in top]


# ==================== 冷门宝藏 ====================

def recommend_hidden_gems(db, user_history_song_ids, limit=20, seed=None):
    """
    冷门宝藏：低播放次数 + 高语义相似度。
    找用户可能喜欢但很少被播放的歌曲。
    """
    all_songs, id_to_embedding, _, id_to_info = _load_all_songs(db)

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
