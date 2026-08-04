"""
MelodyBox 统一推荐引擎（重构版）

设计要点：
1. 所有模式走同一条流水线：候选生成 → 特征打分 → 规则过滤 → 多样性重排 → 解释。
2. 用户画像来自 profile.py（事件驱动、持久化），不再每次请求现算历史平均。
3. 向量查询走 vectors.VectorStore（归一化矩阵 + 向量化余弦），不再逐首循环。
4. 所有权重/阈值集中在 config/recommend_config.py，可配置、可评估。
5. 分数做特征级 min-max 归一化 + 最终 z-score→sigmoid 校准，跨模式可比。
"""
import logging
import time

import numpy as np

from config.recommend_config import (
    AUDIO_VECTOR_VERSION,
    TEXT_VECTOR_VERSION,
    COMPREHENSIVE_WEIGHTS,
    COMPREHENSIVE_FALLBACK_WEIGHTS,
    SIMILAR_WEIGHTS,
    MOOD_WEIGHTS,
    HIDDEN_GEM_SIM_WEIGHT,
    HIDDEN_GEM_COLD_WEIGHT,
    HIDDEN_GEM_MAX_PLAY_COUNT,
    MMR_LAMBDA,
    MMR_ARTIST_PENALTY,
    MMR_GENRE_PENALTY,
    EXPLORE_POOL_FACTOR,
    EXPLORE_JITTER,
    CANDIDATE_POOL,
    LANG_PREF_DEFAULT,
    LANG_NAMES,
    COMMON_LANGS,
    MOOD_LIST,
    MOOD_QUERIES,
    MOOD_LABELS,
)
from services.vectors import VectorStore, invalidate as _invalidate_vectors
from services.profile import get_profile

logger = logging.getLogger('melodybox.recommend')


# ==================== 兼容旧接口 ====================

def invalidate_embedding_cache():
    """向量重新生成/迁移后调用，使向量缓存失效。"""
    _invalidate_vectors()


# ==================== 纯函数工具 ====================

def _l2(v):
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def cosine_similarity(a, b):
    """计算两个向量的余弦相似度。"""
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def genre_match_score(genre_a, genre_b):
    """流派相似度：精确匹配 → 词级 Jaccard → 前缀兜底。"""
    if not genre_a or not genre_b:
        return 0.5
    ga = genre_a.strip().lower()
    gb = genre_b.strip().lower()
    if ga == gb:
        return 1.0
    words_a = set(ga.replace('-', ' ').replace('&', ' ').split())
    words_b = set(gb.replace('-', ' ').replace('&', ' ').split())
    if words_a and words_b:
        intersection = words_a & words_b
        union = words_a | words_b
        if intersection:
            return 0.3 + 0.7 * (len(intersection) / len(union))
    if len(ga) >= 4 and len(gb) >= 4 and ga[:4] == gb[:4]:
        return 0.4
    return 0.0


def _minmax(values):
    """min-max 归一化到 [0,1]；全等时给 0.5。"""
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _calibrate(scores):
    """z-score → sigmoid，映射到 (0,1)，保持排序不变。"""
    arr = np.asarray(scores, dtype=np.float64)
    if arr.size == 0:
        return []
    std = arr.std()
    if std < 1e-9:
        return [0.5] * arr.size
    z = (arr - arr.mean()) / std
    return (1.0 / (1.0 + np.exp(-z))).tolist()


def _softmax(x, temperature=0.1):
    x = np.asarray(x, dtype=np.float64) / temperature
    x = x - x.max()
    e = np.exp(x)
    return e / (e.sum() + 1e-12)


def _mmr_rerank(scored, store, limit, lambda_=MMR_LAMBDA,
                artist_penalty=MMR_ARTIST_PENALTY,
                genre_penalty=MMR_GENRE_PENALTY):
    """
    MMR 多样性重排：保持相关性的同时惩罚与已选歌曲相似/同歌手/同流派的候选。

    实现上先对已选歌曲做一次矩阵乘得到全库相似度（N×k），
    再逐候选取最大值，避免旧实现"每个候选都对全库算一次"的 O(N×pool×k) 开销。
    """
    if len(scored) <= 1:
        return scored[:limit]

    text_mat = store.text_matrix
    text_idx = store.text_index
    if text_mat is None or text_idx is None:
        return scored[:limit]

    selected = [scored[0]]
    remaining = scored[1:]
    selected_artists = {selected[0][1].get('artist', '')}
    selected_genres = {(selected[0][1].get('genre') or '').strip()}

    while len(selected) < limit and remaining:
        # 已选歌曲行向量矩阵 → 与全库一次矩阵乘：(N, k)
        sel_rows = np.stack([
            text_mat[text_idx[sel['id']]]
            for _, sel in selected if sel['id'] in text_idx
        ])
        if sel_rows.shape[0] == 0:
            break
        sims_to_selected = text_mat @ sel_rows.T  # (N, k)

        best_idx = 0
        best_value = -float('inf')
        for i, (score, s) in enumerate(remaining):
            sid = s['id']
            penalty = 0.0
            if s.get('artist', '') in selected_artists:
                penalty += artist_penalty
            if (s.get('genre') or '').strip() in selected_genres:
                penalty += genre_penalty
            row = text_idx.get(sid)
            max_sim = float(sims_to_selected[row].max()) if row is not None else 0.0
            mmr = lambda_ * score - (1 - lambda_) * max_sim - penalty
            if mmr > best_value:
                best_value = mmr
                best_idx = i
        item = remaining.pop(best_idx)
        selected.append(item)
        selected_artists.add(item[1].get('artist', ''))
        selected_genres.add((item[1].get('genre') or '').strip())

    return selected


def _exclude_ids(profile, exclude_recent=True, exclude_played=False):
    ids = set(profile.get('dislike_ids') or [])
    if exclude_recent:
        ids.update(profile.get('recent_ids') or [])
    if exclude_played:
        ids.update(profile.get('played_ids') or [])
    return ids


def _build_result(store, song, score, reason):
    """统一响应格式（与旧版字段保持一致，前端零改动）。"""
    return {
        'song_id': song['id'],
        'title': song.get('title') or '',
        'artist': song.get('artist') or '',
        'album': song.get('album') or '',
        'cover_url': song.get('cover_url') or '',
        'file_path': song.get('file_path') or '',
        'genre': song.get('genre') or '',
        'year': song.get('year') or 0,
        'duration': song.get('duration') or 0,
        'lang': song.get('lang') or '',
        'lyrics': song.get('lyrics') or '',
        'reason': reason,
        'score': round(float(score), 4),
        'source': song.get('source', 'local'),
        'local_id': store.local_id_for(song.get('fingerprint')),
    }


def _finalize(ctx, scored, use_mmr=True):
    """
    排序 → 探索抖动（seed）→ MMR 重排 → 截断。
    scored: list[(score, song_dict)]，已按分数降序。
    """
    store, limit, seed = ctx['store'], ctx['limit'], ctx['seed']
    pool_size = min(len(scored), limit * EXPLORE_POOL_FACTOR)
    pool = scored[:pool_size]

    if seed is not None and pool_size > 1:
        rng = np.random.RandomState(seed)
        jittered = [
            (sc + rng.uniform(-EXPLORE_JITTER, EXPLORE_JITTER), s)
            for sc, s in pool
        ]
        jittered.sort(key=lambda x: x[0], reverse=True)
        pool = jittered

    if use_mmr and len(pool) > 1:
        return _mmr_rerank(pool, store, limit)
    return pool[:limit]


def _play_counts(db):
    """{fingerprint: play_count}（全局热度）。"""
    cursor = db.cursor()
    cursor.execute('SELECT fingerprint, play_count FROM play_stats')
    counts = {row['fingerprint']: (row['play_count'] or 0) for row in cursor.fetchall()}
    cursor.close()
    return counts


def _cold_start(ctx, exclude_recent=True):
    """无画像回退：全库热门（播放次数降序）。"""
    store = ctx['store']
    profile = ctx['profile']
    exclude = _exclude_ids(profile, exclude_recent=exclude_recent)
    counts = _play_counts(ctx['db'])
    candidates = [
        s for s in store.songs
        if s['id'] in store.text_song_set and s['id'] not in exclude
    ]
    candidates.sort(
        key=lambda s: counts.get((s.get('fingerprint') or '').strip(), 0),
        reverse=True,
    )
    top = candidates[:ctx['limit']]
    return [_build_result(store, s, 0.0, '热门推荐') for s in top]


# ==================== 综合推荐 ====================

def _recommend_comprehensive(ctx):
    store, profile, db = ctx['store'], ctx['profile'], ctx['db']

    if profile.get('text_vec') is None and not profile.get('genre_dist'):
        return _cold_start(ctx)

    exclude = _exclude_ids(profile, exclude_recent=True)
    candidates = [
        s for s in store.songs
        if s['id'] in store.text_song_set and s['id'] not in exclude
    ]
    if not candidates:
        return _cold_start(ctx)
    candidates = candidates[:CANDIDATE_POOL]

    text_sims = (store.text_similarity(profile['text_vec'])
                 if profile.get('text_vec') is not None else {})
    audio_sims = (store.audio_similarity(profile['audio_vec'])
                  if profile.get('audio_vec') is not None else {})
    have_profile_audio = profile.get('audio_vec') is not None
    genre_dist = profile.get('genre_dist') or {}
    lang_dist = profile.get('lang_dist') or {}

    rows = []
    for s in candidates:
        sid = s['id']
        feats = {
            'text': text_sims.get(sid, 0.0),
            'audio': audio_sims.get(sid, 0.0),
            'genre': sum(
                w * genre_match_score(g, s.get('genre') or '')
                for g, w in genre_dist.items()
            ) if genre_dist else 0.5,
            'lang': lang_dist.get((s.get('lang') or '').strip(), LANG_PREF_DEFAULT),
        }
        rows.append((feats, s))

    # 特征级 min-max 归一化（先整列算，再逐行取值）
    feature_keys = ['text', 'audio', 'genre', 'lang']
    norm_cols = {
        k: _minmax([f[k] for f, _ in rows])
        for k in feature_keys
    }
    scored = []
    for i, (feats, s) in enumerate(rows):
        has_song_audio = have_profile_audio and s['id'] in store.audio_song_set
        weights = COMPREHENSIVE_WEIGHTS if has_song_audio \
            else COMPREHENSIVE_FALLBACK_WEIGHTS
        score = sum(weights[k] * norm_cols[k][i] for k in weights)
        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = _finalize(ctx, scored)
    scores = [sc for sc, _ in top]
    calibrated = _calibrate(scores) if scores else []

    # 解释：基于画像中最突出的偏好
    if genre_dist:
        top_genre = max(genre_dist.items(), key=lambda kv: kv[1])[0]
        reason = f'常听「{top_genre}」风格'
    elif lang_dist:
        top_lang = max(lang_dist.items(), key=lambda kv: kv[1])[0]
        reason = f'常听{LANG_NAMES.get(top_lang, top_lang)}歌曲'
    else:
        reason = '根据你的听歌偏好'

    return [
        _build_result(store, s, cal or sc, reason)
        for (sc, s), cal in zip(top, calibrated)
    ]


# ==================== 按语言推荐 ====================

def _lang_match(song_lang, lang):
    sl = (song_lang or '').strip().lower()
    if not sl:
        return False
    if lang == 'other':
        return sl not in COMMON_LANGS
    return sl == lang or sl.startswith(lang + '-')


def _recommend_language(ctx):
    store, profile, db = ctx['store'], ctx['profile'], ctx['db']
    lang = ctx['lang']
    lang_label = LANG_NAMES.get(lang, '其他语言' if lang == 'other' else lang)

    exclude = _exclude_ids(profile, exclude_recent=True)
    candidates = [
        s for s in store.songs
        if s['id'] in store.text_song_set
        and s['id'] not in exclude
        and _lang_match(s.get('lang'), lang)
    ]
    if not candidates:
        return []

    if profile.get('text_vec') is not None:
        text_sims = store.text_similarity(profile['text_vec'])
        scored = [(text_sims.get(s['id'], 0.0), s) for s in candidates]
    else:
        counts = _play_counts(db)
        scored = [
            (float(counts.get((s.get('fingerprint') or '').strip(), 0)), s)
            for s in candidates
        ]

    scored.sort(key=lambda x: x[0], reverse=True)
    top = _finalize(ctx, scored, use_mmr=False)
    return [
        _build_result(store, s, sc, f'{lang_label}歌曲推荐')
        for sc, s in top
    ]


# ==================== 按情绪推荐 ====================

def _recommend_mood(ctx):
    store, profile, db = ctx['store'], ctx['profile'], ctx['db']
    mood = ctx['mood']
    mood_label = MOOD_LABELS.get(mood, mood)
    if mood not in MOOD_QUERIES:
        return []

    exclude = _exclude_ids(profile, exclude_recent=True)
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*) AS cnt FROM song_mood_scores WHERE mood = ?', (mood,))
    has_scores = cursor.fetchone()['cnt'] > 0
    cursor.close()

    if has_scores:
        scored = _mood_from_table(db, mood, exclude, ctx['limit'] * EXPLORE_POOL_FACTOR)
        if not scored:
            scored = _mood_fallback(ctx, mood, exclude)
    else:
        scored = _mood_fallback(ctx, mood, exclude)

    scored.sort(key=lambda x: x[0], reverse=True)
    top = _finalize(ctx, scored)
    return [
        _build_result(store, s, sc, f'{mood_label}歌曲推荐')
        for sc, s in top
    ]


def _mood_from_table(db, mood, exclude, limit):
    placeholders = ','.join(['?'] * len(exclude)) if exclude else '1=1'
    params = [mood] + (list(exclude) if exclude else []) + [limit]
    cursor = db.cursor()
    cursor.execute(f'''
        SELECT s.id, s.title, s.artist, s.album, s.cover_url, s.file_path,
               s.genre, s.year, s.duration, s.lang, s.lyrics,
               s.fingerprint, 'local' AS source, ms.score, ms.audio_score
        FROM song_mood_scores ms
        JOIN songs s ON ms.song_id = s.id
        WHERE ms.mood = ? AND s.id NOT IN ({placeholders})
        ORDER BY (CASE WHEN ms.audio_score IS NOT NULL
                       THEN {MOOD_WEIGHTS['text']} * ms.score + {MOOD_WEIGHTS['audio']} * ms.audio_score
                       ELSE ms.score END) DESC
        LIMIT ?
    ''', params)
    rows = [dict(r) for r in cursor.fetchall()]
    cursor.close()
    scored = []
    for r in rows:
        if r.get('audio_score') is not None:
            sc = MOOD_WEIGHTS['text'] * r['score'] + MOOD_WEIGHTS['audio'] * r['audio_score']
        else:
            sc = r['score']
        scored.append((sc, r))
    return scored


def _mood_fallback(ctx, mood, exclude):
    """song_mood_scores 为空时：实时编码情绪查询文本 + 余弦。"""
    store = ctx['store']
    try:
        from services.embedding import encode_text
        query_vec = encode_text(MOOD_QUERIES[mood])
    except Exception:
        return []
    text_sims = store.text_similarity(query_vec)
    return [
        (text_sims.get(s['id'], 0.0), s)
        for s in store.songs
        if s['id'] in store.text_song_set and s['id'] not in exclude
    ]


# ==================== 相似歌曲 ====================

def _recommend_similar(ctx):
    store = ctx['store']
    sid = ctx['song_id']
    target = store.id_to_song.get(sid)
    if target is None:
        return []
    target_title = target.get('title') or '这首歌'

    if sid not in store.text_song_set and sid not in store.audio_song_set:
        return []

    text_sims = (store.text_similarity(store.text_embedding(sid))
                 if sid in store.text_song_set else {})
    audio_sims = (store.audio_similarity(store.audio_embedding(sid))
                  if sid in store.audio_song_set else {})

    scored = []
    for s in store.songs:
        if s['id'] == sid or s['id'] not in store.text_song_set:
            continue
        text_sim = text_sims.get(s['id'], 0.0)
        if sid in store.audio_song_set and s['id'] in store.audio_song_set:
            score = (SIMILAR_WEIGHTS['text'] * text_sim
                     + SIMILAR_WEIGHTS['audio'] * audio_sims.get(s['id'], 0.0))
        else:
            score = text_sim
        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = _finalize(ctx, scored)
    return [
        _build_result(store, s, sc, f'与「{target_title}」相似')
        for sc, s in top
    ]


# ==================== 冷门宝藏 ====================

def _recommend_hidden_gems(ctx):
    store, profile, db = ctx['store'], ctx['profile'], ctx['db']
    if profile.get('text_vec') is None:
        return _cold_start(ctx)

    exclude = _exclude_ids(profile, exclude_recent=True, exclude_played=True)
    counts = _play_counts(db)
    text_sims = store.text_similarity(profile['text_vec'])

    rows = []
    for s in store.songs:
        sid = s['id']
        if sid not in store.text_song_set or sid in exclude:
            continue
        fp = (s.get('fingerprint') or '').strip()
        play_count = counts.get(fp, 0)
        if play_count >= HIDDEN_GEM_MAX_PLAY_COUNT:
            continue
        rows.append((s, text_sims.get(sid, 0.0), play_count))

    if not rows:
        return []

    sims = _minmax([r[1] for r in rows])
    colds = _minmax([1.0 / (r[2] + 1) for r in rows])
    scored = [
        (HIDDEN_GEM_SIM_WEIGHT * sim + HIDDEN_GEM_COLD_WEIGHT * cold, s)
        for (s, _sim, _cnt), sim, cold in zip(rows, sims, colds)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    top = _finalize(ctx, scored)
    return [_build_result(store, s, sc, '冷门宝藏') for sc, s in top]


# ==================== 情绪分数预计算（软原型，重构版） ====================

def compute_all_mood_scores(db):
    """
    为全库有向量的歌曲计算 7 种情绪分数，写入 song_mood_scores。

    相比旧版改进：
    - 文本分数用全库 softmax 加权（温度 0.1），而非只看 top-5；
    - 音频原型 = 全库音频向量按文本情绪权重加权平均（软原型），
      不再是"top-5 文本匹配歌曲的音频均值"的自证循环。

    返回写入记录数；模型不可用时返回 0（情绪推荐走实时回退）。
    """
    store = VectorStore.load(db)
    if store.text_matrix is None or store.text_matrix.shape[0] == 0:
        return 0

    try:
        from services.embedding import encode_text
        mood_vecs = {m: encode_text(MOOD_QUERIES[m]) for m in MOOD_LIST}
    except Exception:
        return 0

    # 文本分数矩阵 (N_text, 7)
    text_scores = np.column_stack([
        store.text_matrix @ _l2(mood_vecs[m]) for m in MOOD_LIST
    ])

    # 音频软原型：按文本情绪 softmax 权重对全库音频加权
    audio_prototypes = {}
    if store.audio_matrix is not None and store.audio_matrix.shape[0] > 0:
        audio_row_of = {int(sid): i for i, sid in enumerate(store.audio_song_ids)}
        text_row_of = {int(sid): i for i, sid in enumerate(store.text_song_ids)}
        for mi, m in enumerate(MOOD_LIST):
            weights = _softmax(text_scores[:, mi], temperature=0.1)
            proto = np.zeros(store.audio_dim, dtype=np.float64)
            total = 0.0
            for sid, i in text_row_of.items():
                j = audio_row_of.get(sid)
                if j is not None:
                    proto += weights[i] * store.audio_matrix[j]
                    total += weights[i]
            if total > 0:
                audio_prototypes[m] = _l2(proto)

    cursor = db.cursor()
    cursor.execute('DELETE FROM song_mood_scores')
    count = 0
    for mi, m in enumerate(MOOD_LIST):
        proto = audio_prototypes.get(m)
        for i, sid in enumerate(store.text_song_ids):
            sid = int(sid)
            text_score = float(text_scores[i, mi])
            if proto is not None and sid in store.audio_song_set:
                audio_score = float(cosine_similarity(proto, store.audio_embedding(sid)))
                cursor.execute(
                    'INSERT INTO song_mood_scores (song_id, mood, score, audio_score) VALUES (?, ?, ?, ?)',
                    (sid, m, text_score, audio_score)
                )
            else:
                cursor.execute(
                    'INSERT INTO song_mood_scores (song_id, mood, score) VALUES (?, ?, ?)',
                    (sid, m, text_score)
                )
            count += 1
    db.commit()
    cursor.close()
    return count


# ==================== 统一入口 ====================

def recommend(db, user_id=1, mode='comprehensive', limit=20, seed=None,
              lang=None, mood=None, song_id=None):
    """
    统一推荐入口。

    Args:
        db: sqlite3 连接（Row 工厂）
        user_id: 目标用户
        mode: comprehensive | language | mood | similar | hidden_gem | weather
        lang/mood/song_id: 模式子参数
        seed: 确定性探索种子（同参数下结果稳定）
    """
    t0 = time.time()
    store = VectorStore.load(db)
    profile = get_profile(db, user_id)
    ctx = {
        'db': db,
        'store': store,
        'profile': profile,
        'user_id': user_id,
        'limit': min(max(int(limit or 20), 1), 50),
        'seed': seed,
        'lang': lang,
        'mood': mood,
        'song_id': song_id,
    }

    mode = mode or 'comprehensive'
    if mode == 'weather':
        mode = 'mood'

    if mode == 'language' and lang:
        results = _recommend_language(ctx)
    elif mode == 'mood' and mood:
        results = _recommend_mood(ctx)
    elif mode == 'similar' and song_id:
        results = _recommend_similar(ctx)
    elif mode == 'hidden_gem':
        results = _recommend_hidden_gems(ctx)
    else:
        results = _recommend_comprehensive(ctx)

    logger.info(
        'recommend user=%s mode=%s limit=%d seed=%s elapsed=%.1fms n=%d',
        user_id, mode, ctx['limit'], seed,
        (time.time() - t0) * 1000, len(results),
    )
    return results
