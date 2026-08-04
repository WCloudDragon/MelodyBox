"""
用户画像服务（重构版新增）

画像由行为事件聚合而来，持久化到 user_profiles 表：
- text_vec / audio_vec：历史歌曲向量按时间衰减加权平均（正负样本混合）
- genre_dist / lang_dist：流派与语种偏好分布（JSON）
- recent_ids：最近 N 天听过的歌（推荐时排除，避免重复）
- played_ids：用户听过的全部歌（冷门宝藏排除"已听过"）
- version：每次刷新 +1，用于推荐缓存失效

推荐引擎每次请求直接读画像，不再临时现算历史平均。
"""
import json
import numpy as np

from config.recommend_config import (
    PROFILE_VERSION,
    PROFILE_HISTORY_DAYS,
    PROFILE_DECAY_HALF_LIFE_DAYS,
    PROFILE_MAX_HISTORY,
    RECENT_EXCLUDE_DAYS,
    NEGATIVE_WEIGHT,
)
from services.vectors import VectorStore, _l2

_POSITIVE_EVENTS = ('play', 'complete', 'like')
_NEGATIVE_EVENTS = ('skip', 'dislike')


def _recency_weight(ts, now_ts, half_life_days=PROFILE_DECAY_HALF_LIFE_DAYS):
    """指数时间衰减：half_life_days 天内权重减半。"""
    import datetime as _dt
    try:
        if isinstance(ts, str):
            dt = _dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            ts_num = dt.timestamp()
        else:
            ts_num = float(ts or now_ts)
    except Exception:
        ts_num = now_ts
    age_days = max(0.0, (now_ts - ts_num) / 86400.0)
    return float(np.power(0.5, age_days / half_life_days))


def ensure_profile(db, user_id=1):
    cursor = db.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO user_profiles (user_id) VALUES (?)',
        (user_id,)
    )
    db.commit()
    cursor.close()


def _empty_profile(user_id=1):
    return {
        'user_id': user_id,
        'text_vec': None,
        'audio_vec': None,
        'genre_dist': {},
        'lang_dist': {},
        'recent_ids': [],
        'played_ids': [],
        'dislike_ids': [],
        'version': PROFILE_VERSION,
    }


def _backfill_from_play_history(db, user_id=1):
    """老用户冷启动：把 play_history 回填为 events（只执行一次）。"""
    cursor = db.cursor()
    cursor.execute(
        '''INSERT OR IGNORE INTO events (user_id, song_id, fingerprint,
                                        event_type, duration_ratio, ts)
           SELECT ?, song_id, fingerprint, 'play',
                  NULLIF(duration_played, 0), played_at
           FROM play_history
           WHERE song_id IS NOT NULL''',
        (user_id,)
    )
    db.commit()
    cursor.close()


def _collect_events(db, user_id):
    cursor = db.cursor()
    cursor.execute(
        '''SELECT song_id, fingerprint, event_type, duration_ratio, ts
           FROM events
           WHERE user_id = ? AND song_id IS NOT NULL
           ORDER BY ts DESC
           LIMIT ?''',
        (user_id, PROFILE_MAX_HISTORY)
    )
    rows = [dict(r) for r in cursor.fetchall()]
    cursor.close()
    return rows


def refresh_profile(db, user_id=1, vectors=None):
    """
    从事件重建用户画像并持久化。

    Args:
        vectors: 可选 VectorStore；不传则内部加载。
    返回 profile dict（与 get_profile 同构）。
    """
    ensure_profile(db, user_id)
    events = _collect_events(db, user_id)
    if not events:
        _backfill_from_play_history(db, user_id)
        events = _collect_events(db, user_id)
    if not events:
        profile = _empty_profile(user_id)
        _save_profile(db, profile)
        return profile

    if vectors is None:
        vectors = VectorStore.load(db)

    import time as _time
    now_ts = _time.time()

    positives = [e for e in events if e['event_type'] in _POSITIVE_EVENTS]
    negatives = [e for e in events if e['event_type'] in _NEGATIVE_EVENTS]

    # ---- 加权正样本向量（含时间衰减）----
    text_parts = []
    audio_parts = []
    genre_counts = {}
    lang_counts = {}
    for e in positives:
        sid = e['song_id']
        song = vectors.id_to_song.get(sid)
        if not song:
            continue
        w = _recency_weight(e['ts'], now_ts)
        if vectors.has_text(sid):
            text_parts.append((w, vectors.text_embedding(sid)))
        if vectors.has_audio(sid):
            audio_parts.append((w, vectors.audio_embedding(sid)))
        genre = (song.get('genre') or '').strip()
        if genre:
            genre_counts[genre] = genre_counts.get(genre, 0) + w
        lang = (song.get('lang') or '').strip()
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + w

    # ---- 负样本向量（扣减，权重减半）----
    for e in negatives:
        sid = e['song_id']
        w = _recency_weight(e['ts'], now_ts) * NEGATIVE_WEIGHT
        if vectors.has_text(sid):
            text_parts.append((-w, vectors.text_embedding(sid)))
        if vectors.has_audio(sid):
            audio_parts.append((-w, vectors.audio_embedding(sid)))

    def _combine(parts):
        if not parts:
            return None
        vec = np.zeros_like(parts[0][1], dtype=np.float32)
        for w, v in parts:
            vec += w * v
        return _l2(vec)

    text_vec = _combine(text_parts)
    audio_vec = _combine(audio_parts)

    total_w = sum(genre_counts.values()) or 1.0
    genre_dist = {g: round(c / total_w, 4) for g, c in genre_counts.items()}
    total_l = sum(lang_counts.values()) or 1.0
    lang_dist = {l: round(c / total_l, 4) for l, c in lang_counts.items()}

    # ---- 最近听过（用于排除重复推荐）----
    recent_ids = []
    recent_song_ids = set()
    for e in positives:
        sid = e['song_id']
        if sid in recent_song_ids:
            continue
        age_days = max(0.0, (now_ts - _ts_num(e['ts'], now_ts)) / 86400.0)
        if age_days <= RECENT_EXCLUDE_DAYS:
            recent_ids.append(sid)
            recent_song_ids.add(sid)
        if len(recent_ids) >= 100:
            break

    played_ids = []
    seen = set()
    for e in positives:
        sid = e['song_id']
        if sid not in seen:
            seen.add(sid)
            played_ids.append(sid)
        if len(played_ids) >= 1000:
            break

    dislike_ids = [
        e['song_id'] for e in events if e['event_type'] == 'dislike'
    ]

    profile = {
        'user_id': user_id,
        'text_vec': text_vec,
        'audio_vec': audio_vec,
        'genre_dist': genre_dist,
        'lang_dist': lang_dist,
        'recent_ids': recent_ids,
        'played_ids': played_ids,
        'dislike_ids': dislike_ids,
        'version': PROFILE_VERSION,
    }
    _save_profile(db, profile)
    return profile


def _ts_num(ts, now_ts):
    import datetime as _dt
    try:
        dt = _dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt.timestamp()
    except Exception:
        return now_ts


def _save_profile(db, profile):
    cursor = db.cursor()
    cursor.execute(
        '''UPDATE user_profiles
           SET text_vec = ?, audio_vec = ?, genre_dist = ?, lang_dist = ?,
               recent_ids = ?, played_ids = ?, version = ?,
               updated_at = datetime('now','localtime')
           WHERE user_id = ?''',
        (
            profile['text_vec'].tobytes() if profile['text_vec'] is not None else None,
            profile['audio_vec'].tobytes() if profile['audio_vec'] is not None else None,
            json.dumps(profile['genre_dist'], ensure_ascii=False),
            json.dumps(profile['lang_dist'], ensure_ascii=False),
            json.dumps(profile['recent_ids']),
            json.dumps(profile['played_ids']),
            profile['version'],
            profile['user_id'],
        )
    )
    db.commit()
    cursor.close()


def get_profile(db, user_id=1, ensure=True):
    """
    读取用户画像；无画像时自动构建（读取比刷新便宜）。
    返回 profile dict。
    """
    if ensure:
        ensure_profile(db, user_id)
    cursor = db.cursor()
    cursor.execute(
        '''SELECT text_vec, audio_vec, genre_dist, lang_dist,
                  recent_ids, played_ids, version
           FROM user_profiles WHERE user_id = ?''',
        (user_id,)
    )
    row = cursor.fetchone()
    cursor.close()

    if row is None:
        return refresh_profile(db, user_id)

    def _load_vec(blob):
        if blob is None:
            return None
        v = np.frombuffer(blob, dtype=np.float32)
        return _l2(v)

    def _load_json(s, default):
        try:
            return json.loads(s) if s else default
        except Exception:
            return default

    profile = {
        'user_id': user_id,
        'text_vec': _load_vec(row['text_vec']),
        'audio_vec': _load_vec(row['audio_vec']),
        'genre_dist': _load_json(row['genre_dist'], {}),
        'lang_dist': _load_json(row['lang_dist'], {}),
        'recent_ids': _load_json(row['recent_ids'], []),
        'played_ids': _load_json(row['played_ids'], []),
        'dislike_ids': [],
        'version': row['version'] or PROFILE_VERSION,
    }

    # 无有效画像（例如空向量）时重建
    if profile['text_vec'] is None and not profile['genre_dist']:
        return refresh_profile(db, user_id)
    return profile
