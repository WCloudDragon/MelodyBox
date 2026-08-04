"""
新推荐引擎冒烟测试（安全：使用临时数据库副本，不碰真实 melodybox.db）。

用法:
    cd Code/backend
    D:\\flask_env\\Scripts\\python.exe tools\\test_recommender.py
"""
import os
import shutil
import sys
import tempfile

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

SRC_DB = os.path.join(BACKEND_DIR, 'melodybox.db')
tmpdir = tempfile.mkdtemp(prefix='melodybox_test_')
db_path = os.path.join(tmpdir, 'melodybox.db')
if os.path.exists(SRC_DB):
    shutil.copy2(SRC_DB, db_path)

from config.config import Config
Config.DB_PATH = db_path

from app import create_app
app = create_app()

# 防止情绪回退触发真实模型加载（2.2GB），冒烟测试中直接返回空
def _no_model(*_a, **_k):
    raise RuntimeError('smoke test: model disabled')
import services.embedding
services.embedding.encode_text = _no_model

from services import recommender, profile, vectors

with app.app_context():
    db = app.get_db()

    p = profile.refresh_profile(db, user_id=1)
    print('[profile] version =', p['version'],
          '| genre =', list(p['genre_dist'].items())[:3],
          '| recent =', len(p['recent_ids']),
          '| played =', len(p['played_ids']))

    vs = vectors.VectorStore.load(db)
    print('[vectors] songs =', len(vs.songs),
          '| text =', vs.text_matrix.shape if vs.text_matrix is not None else None,
          '| audio =', vs.audio_matrix.shape if vs.audio_matrix is not None else None)

    modes = [
        ('comprehensive', {}),
        ('language', {'lang': 'zh'}),
        ('mood', {'mood': 'calm'}),
        ('hidden_gem', {}),
        ('similar', {'song_id': int(vs.text_song_ids[0])}),
    ]
    for mode, kw in modes:
        try:
            res = recommender.recommend(db, mode=mode, limit=5, **kw)
            print(f'[rec:{mode}] n={len(res)} |',
                  [(r['title'], round(r['score'], 3), r['reason']) for r in res[:2]])
        except Exception as e:
            import traceback
            print(f'[rec:{mode}] ERROR:', repr(e))
            traceback.print_exc()
    db.close()

client = app.test_client()
for path in [
    '/api/ai/embedding/status',
    '/api/ai/recommend?mode=comprehensive&limit=5',
    '/api/ai/recommend?mode=mood&mood=calm&limit=5',
    '/api/ai/recommend/previews',
]:
    r = client.get(path)
    body = r.get_json(silent=True)
    if r.status_code == 200 and body is not None:
        preview = len(body) if isinstance(body, list) else list(body.keys())[:6] if isinstance(body, dict) else body
        print(f'[http] {path} -> {r.status_code} |', preview)
    else:
        print(f'[http] {path} -> {r.status_code} |', body)

r = client.post('/api/stats/feedback', json={
    'title': '测试歌曲', 'artist': '测试', 'album': '测试',
    'event': 'skip', 'duration_ratio': 0.2,
})
print('[http] /api/stats/feedback ->', r.status_code, r.get_json(silent=True))

shutil.rmtree(tmpdir, ignore_errors=True)
print('SMOKE_DONE')
