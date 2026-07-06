from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin
import sqlite3
import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.before_request
def handle_preflight():
    """处理 CORS 预检请求（OPTIONS）"""
    if request.method == 'OPTIONS':
        return '', 200


def get_db():
    return current_app.get_db()


def _get_serializer():
    """获取 token 序列化器"""
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _generate_token(user_id, role):
    """生成带过期时间的 token，30 天有效"""
    s = _get_serializer()
    return s.dumps({'user_id': user_id, 'role': role})


def _parse_token(token):
    """解析 token，返回 payload 或 None"""
    s = _get_serializer()
    try:
        return s.loads(token, max_age=30 * 24 * 3600)
    except Exception:
        return None


def _ensure_users_table_and_admin():
    """确保 users 表存在，首次运行时创建默认管理员"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            membership_type TEXT DEFAULT 'free',
            membership_expire TEXT DEFAULT NULL,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    db.commit()

    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        pwd_hash = generate_password_hash('admin123')
        cursor.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            ('admin', pwd_hash, 'admin')
        )
        db.commit()
        print('[auth] 默认管理员已创建: admin / admin123')

    cursor.close()
    db.close()


def token_required(f):
    """认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': '未登录'}), 401
        payload = _parse_token(token)
        if not payload:
            return jsonify({'error': '登录已过期或无效凭证'}), 401
        request.user_id = payload['user_id']
        request.user_role = payload.get('role', 'user')
        return f(*args, **kwargs)
    return decorated


def get_user_id_from_token():
    """从 Authorization header 提取 user_id，不强制要求登录"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return None
    payload = _parse_token(token)
    return payload['user_id'] if payload else None


def _user_to_dict(row):
    return {
        'id': row['id'],
        'username': row['username'],
        'email': row['email'],
        'avatar_url': row['avatar_url'],
        'membership_type': row['membership_type'],
        'membership_expire': row['membership_expire'],
        'role': row['role'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


# ==================== 路由 ====================

@auth_bp.route('/register', methods=['POST'])
def register():
    _ensure_users_table_and_admin()
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400

    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    email = (data.get('email') or '').strip()

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    if len(username) > 50:
        return jsonify({'error': '用户名不能超过50个字符'}), 400
    if len(password) < 6:
        return jsonify({'error': '密码长度不能少于6位'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    if cursor.fetchone():
        cursor.close(); db.close()
        return jsonify({'error': '用户名已存在'}), 409

    pwd_hash = generate_password_hash(password)
    cursor.execute(
        'INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)',
        (username, pwd_hash, email)
    )
    db.commit()
    cursor.close(); db.close()
    return jsonify({'success': True, 'message': '注册成功'})


@auth_bp.route('/login', methods=['POST'])
def login():
    _ensure_users_table_and_admin()
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400

    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    cursor.close(); db.close()

    if not user:
        return jsonify({'error': '用户名或密码错误'}), 401
    if not check_password_hash(user['password_hash'], password):
        return jsonify({'error': '用户名或密码错误'}), 401

    token = _generate_token(user['id'], user['role'])
    return jsonify({'token': token, 'user': _user_to_dict(user)})


@auth_bp.route('/profile', methods=['GET'])
@token_required
def profile():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (request.user_id,))
    user = cursor.fetchone()
    cursor.close(); db.close()
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    return jsonify(_user_to_dict(user))


@auth_bp.route('/users', methods=['GET'])
@token_required
def list_users():
    """管理员获取所有用户列表（用于管理后台统计）"""
    if request.user_role != 'admin':
        return jsonify({'error': '仅管理员可查看'}), 403
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, username, email, role, membership_type, created_at FROM users ORDER BY id')
    users = [dict(row) for row in cursor.fetchall()]
    cursor.close(); db.close()
    return jsonify({'users': users, 'total': len(users)})


@auth_bp.route('/password', methods=['PUT'])
@cross_origin()
@token_required
def change_password():
    """修改当前用户密码，需提供旧密码验证"""
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400

    old_password = (data.get('oldPassword') or '').strip()
    new_password = (data.get('newPassword') or '').strip()

    if not old_password or not new_password:
        return jsonify({'error': '新旧密码不能为空'}), 400
    if len(new_password) < 6:
        return jsonify({'error': '新密码长度不能少于6位'}), 400
    if old_password == new_password:
        return jsonify({'error': '新密码不能与旧密码相同'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (request.user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close(); db.close()
        return jsonify({'error': '用户不存在'}), 404

    if not check_password_hash(user['password_hash'], old_password):
        cursor.close(); db.close()
        return jsonify({'error': '旧密码不正确'}), 403

    new_hash = generate_password_hash(new_password)
    cursor.execute(
        "UPDATE users SET password_hash = ?, updated_at = datetime('now','localtime') WHERE id = ?",
        (new_hash, request.user_id)
    )
    db.commit()
    cursor.close(); db.close()

    return jsonify({'success': True, 'message': '密码修改成功，请重新登录'})


@auth_bp.route('/account', methods=['DELETE'])
@token_required
def delete_account():
    """注销当前账户，需提供密码确认。注意：不可注销 admin 账户"""
    data = request.get_json(force=True, silent=True) or {}
    password = (data.get('password') or '').strip()

    if not password:
        return jsonify({'error': '请输入密码确认'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (request.user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close(); db.close()
        return jsonify({'error': '用户不存在'}), 404

    if user['role'] == 'admin':
        cursor.close(); db.close()
        return jsonify({'error': '管理员账户不可注销'}), 403

    if not check_password_hash(user['password_hash'], password):
        cursor.close(); db.close()
        return jsonify({'error': '密码不正确'}), 403

    # 先清除该用户的设置和统计数据（已有外键级联，但显式清理更安全）
    cursor.execute('DELETE FROM settings WHERE user_id = ?', (request.user_id,))
    cursor.execute('DELETE FROM playlists WHERE user_id = ?', (request.user_id,))
    cursor.execute('DELETE FROM ai_api_config WHERE user_id = ?', (request.user_id,))
    # 删除用户（play_stats/play_history 的 song_id 外键是 ON DELETE SET NULL，不受影响）
    cursor.execute('DELETE FROM users WHERE id = ?', (request.user_id,))
    db.commit()
    cursor.close(); db.close()

    return jsonify({'success': True, 'message': '账户已注销，数据已清除'})
