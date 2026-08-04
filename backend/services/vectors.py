"""
向量存储服务（重构版）

统一从 song_vectors 表加载歌曲向量，L2 归一化后以矩阵形式提供
向量化余弦相似度计算，避免旧实现逐首 Python 循环 + 手动 dict 缓存。

缓存以 (text_version, audio_version, generation) 为 key：
- 向量重新生成 / 迁移后调用 invalidate() 使 generation +1，缓存自动失效；
- 模型升级时版本号变化，旧版本向量自然不参与计算。
"""
import threading
import numpy as np

from config.recommend_config import TEXT_VECTOR_VERSION, AUDIO_VECTOR_VERSION

_generation = 0
_lock = threading.Lock()
_cache = {}


def invalidate():
    """向量变更（重新生成/迁移/删歌）后调用，使全部缓存失效。"""
    global _generation
    with _lock:
        _generation += 1
        _cache.clear()


def get_generation():
    with _lock:
        return _generation


def normalize_rows(mat):
    """逐行 L2 归一化（零向量保持零向量）。"""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (mat / norms).astype(np.float32)


def _l2(v):
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


class VectorStore:
    """全库歌曲元数据 + 归一化向量矩阵，提供批量相似度查询。"""

    def __init__(self, db, text_version=TEXT_VECTOR_VERSION,
                 audio_version=AUDIO_VECTOR_VERSION):
        self.db = db
        self.text_version = text_version
        self.audio_version = audio_version

        self.songs = []            # list[dict] 全库歌曲（指纹去重后）
        self.id_to_song = {}
        self._fingerprint_to_local = {}

        # 文本向量
        self.text_song_ids = None  # np.array[int64]
        self.text_matrix = None    # (N, d) float32 已归一化
        self.text_index = {}       # song_id -> 行号
        self.text_dim = 0
        self.text_song_set = set()

        # 音频向量
        self.audio_song_ids = None
        self.audio_matrix = None
        self.audio_index = {}
        self.audio_dim = 0
        self.audio_song_set = set()

    # ==================== 加载 ====================

    @classmethod
    def load(cls, db, text_version=TEXT_VECTOR_VERSION,
             audio_version=AUDIO_VECTOR_VERSION):
        """获取（或从缓存取）当前版本的向量存储。"""
        key = (text_version, audio_version, _generation)
        with _lock:
            cached = _cache.get(key)
        if cached is not None:
            return cached
        store = cls(db, text_version, audio_version)
        store._load()
        with _lock:
            _cache[key] = store
        return store

    def _load(self):
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT id, title, artist, album, cover_url, file_path, genre, year,
                   duration, lang, lyrics, fingerprint, source
            FROM all_songs
        ''')
        rows = [dict(r) for r in cursor.fetchall()]
        cursor.close()

        # 指纹去重：本地优先；同时建立 fingerprint → 本地 id 映射
        fingerprint_to_local = {}
        for r in rows:
            fp = (r.get('fingerprint') or '').strip()
            if fp and r.get('source') == 'local':
                fingerprint_to_local[fp] = r['id']
        self._fingerprint_to_local = fingerprint_to_local

        seen = set()
        songs = []
        for r in rows:
            fp = (r.get('fingerprint') or '').strip()
            if fp:
                if fp in seen:
                    continue
                seen.add(fp)
            songs.append(r)

        self.songs = songs
        self.id_to_song = {s['id']: s for s in songs}
        if not songs:
            return

        # 批量加载向量（避免 N+1）
        song_ids = [s['id'] for s in songs]
        placeholders = ','.join(['?'] * len(song_ids))
        cursor = self.db.cursor()
        cursor.execute(
            f'''SELECT song_id, source, text_vec, audio_vec,
                       text_version, audio_version
                FROM song_vectors
                WHERE song_id IN ({placeholders})''',
            song_ids
        )
        vec_rows = cursor.fetchall()
        cursor.close()

        text_map = {}
        audio_map = {}
        for vr in vec_rows:
            key = (vr['song_id'], vr['source'])
            if (vr['text_vec'] is not None
                    and vr['text_version'] == self.text_version):
                text_map[key] = np.frombuffer(vr['text_vec'], dtype=np.float32)
            if (vr['audio_vec'] is not None
                    and vr['audio_version'] == self.audio_version):
                audio_map[key] = np.frombuffer(vr['audio_vec'], dtype=np.float32)

        self._build_text_matrix(songs, text_map)
        self._build_audio_matrix(songs, audio_map)

    def _build_text_matrix(self, songs, text_map):
        rows = [(s['id'], text_map[(s['id'], s['source'])])
                for s in songs if (s['id'], s['source']) in text_map]
        if not rows:
            return
        dims = {v.shape[0] for _, v in rows}
        dim = max(dims)
        ids, vecs = [], []
        for sid, v in rows:
            if v.shape[0] == dim:
                ids.append(sid)
                vecs.append(v)
        if not ids:
            return
        self.text_dim = dim
        self.text_song_ids = np.array(ids, dtype=np.int64)
        self.text_matrix = normalize_rows(np.stack(vecs))
        self.text_index = {int(sid): i for i, sid in enumerate(ids)}
        self.text_song_set = set(int(s) for s in ids)

    def _build_audio_matrix(self, songs, audio_map):
        rows = [(s['id'], audio_map[(s['id'], s['source'])])
                for s in songs if (s['id'], s['source']) in audio_map]
        if not rows:
            return
        dims = {v.shape[0] for _, v in rows}
        dim = max(dims)
        ids, vecs = [], []
        for sid, v in rows:
            if v.shape[0] == dim:
                ids.append(sid)
                vecs.append(v)
        if not ids:
            return
        self.audio_dim = dim
        self.audio_song_ids = np.array(ids, dtype=np.int64)
        self.audio_matrix = normalize_rows(np.stack(vecs))
        self.audio_index = {int(sid): i for i, sid in enumerate(ids)}
        self.audio_song_set = set(int(s) for s in ids)

    # ==================== 查询 ====================

    def has_text(self, sid):
        return sid in self.text_song_set

    def has_audio(self, sid):
        return sid in self.audio_song_set

    def text_embedding(self, sid):
        """返回已归一化的文本向量（copy），无则 None。"""
        i = self.text_index.get(sid)
        if i is None:
            return None
        return self.text_matrix[i].copy()

    def audio_embedding(self, sid):
        i = self.audio_index.get(sid)
        if i is None:
            return None
        return self.audio_matrix[i].copy()

    def text_similarity(self, query_vec):
        """与全库文本向量的余弦相似度，返回 {song_id: sim}。"""
        if self.text_matrix is None or self.text_matrix.shape[0] == 0:
            return {}
        q = _l2(query_vec)
        sims = self.text_matrix @ q
        return {int(sid): float(s) for sid, s in zip(self.text_song_ids, sims)}

    def audio_similarity(self, query_vec):
        if self.audio_matrix is None or self.audio_matrix.shape[0] == 0:
            return {}
        q = _l2(query_vec)
        sims = self.audio_matrix @ q
        return {int(sid): float(s) for sid, s in zip(self.audio_song_ids, sims)}

    def row_text_sims(self, sid):
        """指定歌曲与全库的文本相似度（MMR 用）。"""
        i = self.text_index.get(sid)
        if i is None or self.text_matrix is None:
            return {}
        sims = self.text_matrix @ self.text_matrix[i]
        return {int(s): float(v) for s, v in zip(self.text_song_ids, sims)}

    def local_id_for(self, fingerprint):
        fp = (fingerprint or '').strip()
        return self._fingerprint_to_local.get(fp)
