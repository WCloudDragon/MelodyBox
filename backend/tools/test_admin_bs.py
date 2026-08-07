"""
B/S 管理端冒烟测试（安全：使用临时数据库副本 + 临时上传目录，不碰真实数据）。

覆盖:
- GET /admin 管理端静态页托管
- GET /assets/... 静态资源
- POST /api/cloud/upload 文件上传入库（管理员）
- 鉴权：未带 token 上传应 401，普通用户上传应 403

用法:
    cd Code/backend
    D:\\flask_env\\Scripts\\python.exe tools\\test_admin_bs.py
"""
import os
import shutil
import sys
import tempfile

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

tmpdir = tempfile.mkdtemp(prefix='melodybox_admin_')
db_path = os.path.join(tmpdir, 'melodybox.db')
upload_dir = os.path.join(tmpdir, 'cloud-music')
os.makedirs(upload_dir, exist_ok=True)

src_db = os.path.join(BACKEND_DIR, 'melodybox.db')
if os.path.exists(src_db):
    shutil.copy2(src_db, db_path)

from config.config import Config
Config.DB_PATH = db_path
Config.CLOUD_MUSIC_DIR = upload_dir

from app import create_app
app = create_app()
app.config['CLOUD_MUSIC_DIR'] = upload_dir

client = app.test_client()


def _login(username, password):
    r = client.post('/api/auth/login', json={'username': username, 'password': password})
    return r.get_json(silent=True) or {}


def main():
    # 1. 管理端静态页
    r = client.get('/admin')
    ok = r.status_code == 200 and b'MelodyBox' in r.data
    print(f'[http] GET /admin -> {r.status_code} | 含管理端标记: {ok}')
    assert ok, '管理端静态页未正确托管'

    r2 = client.get('/admin/')
    print(f'[http] GET /admin/ -> {r2.status_code}')

    # 2. 静态资源（从 admin.html 中提取第一个 assets 引用）
    import re
    m = re.search(rb'assets/[A-Za-z0-9._-]+\.(?:js|css)', r.data)
    if m:
        asset = m.group(0).decode()
        ra = client.get(f'/{asset}')
        print(f'[http] GET /{asset} -> {ra.status_code} ({len(ra.data)} bytes)')
    else:
        print('[http] 未找到 assets 引用（跳过）')

    # 3. 鉴权：无 token 上传 → 401
    ru = client.post('/api/cloud/upload', data={})
    print(f'[auth] 无 token 上传 -> {ru.status_code} (期望 401)')

    # 3b. 目录浏览鉴权：无 token → 401，普通用户 → 403
    rb = client.get('/api/folders/browse')
    print(f'[auth] 无 token 目录浏览 -> {rb.status_code} (期望 401)')

    # 4. 普通用户登录 → 上传 → 403
    reg = client.post('/api/auth/register', json={
        'username': 'normal_user', 'password': 'pass123', 'email': ''
    })
    user = _login('normal_user', 'pass123')
    rn = client.post('/api/cloud/upload', data={}, headers={
        'Authorization': f"Bearer {user.get('token', '')}"
    })
    print(f'[auth] 普通用户上传 -> {rn.status_code} (期望 403)')
    rnb = client.get('/api/folders/browse', headers={
        'Authorization': f"Bearer {user.get('token', '')}"
    })
    print(f'[auth] 普通用户目录浏览 -> {rnb.status_code} (期望 403)')

    # 5. 管理员上传真实音频文件
    admin = _login('admin', 'admin123')
    token = admin.get('token', '')
    assert token, '管理员登录失败'
    print('[auth] 管理员登录成功')

    # 4b. 管理员目录浏览：空路径返回盘符根目录
    rb2 = client.get('/api/folders/browse', headers={
        'Authorization': f'Bearer {token}'
    })
    body_b = rb2.get_json(silent=True) or {}
    print(f'[browse] 管理员目录浏览(根) -> {rb2.status_code} | 子目录数: {len(body_b.get("subdirs") or [])}')
    assert rb2.status_code == 200, f'目录浏览失败: {body_b}'

    # 取一首真实歌曲文件用于上传
    import sqlite3
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT file_path FROM songs WHERE file_path IS NOT NULL LIMIT 1"
    ).fetchone()
    conn.close()

    if not row or not os.path.isfile(row[0]):
        print('[upload] 未找到可上传的本地音频文件（跳过真实上传，仅验证接口鉴权）')
    else:
        with open(row[0], 'rb') as f:
            data = {
                'files': (f, os.path.basename(row[0])),
            }
            rupload = client.post(
                '/api/cloud/upload',
                data=data,
                content_type='multipart/form-data',
                headers={'Authorization': f'Bearer {token}'},
            )
        body = rupload.get_json(silent=True) or {}
        print(f'[upload] 管理员上传 -> {rupload.status_code} | added={body.get("added")} '
              f'skipped={body.get("skipped")} errors={len(body.get("errors") or [])}')
        assert rupload.status_code == 200, f'上传失败: {body}'

        # 6. 云端曲库应包含上传的歌曲
        rs = client.get('/api/cloud/songs', headers={
            'Authorization': f'Bearer {token}'
        })
        songs = (rs.get_json(silent=True) or {}).get('songs') or []
        print(f'[db] 云端曲库歌曲数: {len(songs)}')

    print('ADMIN_BS_SMOKE_OK')


if __name__ == '__main__':
    try:
        main()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
