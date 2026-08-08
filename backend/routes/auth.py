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


# ==================== 会员体系 ====================

def _admin_required(f):
    """管理员权限装饰器（需配合 token_required 使用）"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if getattr(request, 'user_role', None) != 'admin':
            return jsonify({'error': '仅管理员可操作'}), 403
        return f(*args, **kwargs)
    return decorated


def _membership_ok(db, user_id, *levels):
    """判断用户是否具备指定会员等级；admin 直接通过；过期自动视为 free。"""
    cursor = db.cursor()
    cursor.execute(
        'SELECT role, membership_type, membership_expire FROM users WHERE id = ?',
        (user_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    if not row:
        return False
    if row['role'] == 'admin':
        return True
    mtype = row['membership_type'] or 'free'
    expire = row['membership_expire']
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if mtype not in levels:
        return False
    return not expire or expire > now


def require_membership(*levels):
    """
    会员权益装饰器：需登录；admin 直接通过；
    会员类型属于 levels 且未过期才放行，否则 403。
    用法：@token_required 之后叠加 @require_membership('vip')。
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            db = get_db()
            ok = _membership_ok(db, request.user_id, *levels)
            db.close()
            if not ok:
                return jsonify({'error': '该功能为会员专享，请先升级会员'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


@auth_bp.route('/membership/plans')
def list_membership_plans():
    """公开：获取在售会员方案。"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'SELECT id, name, price, duration_days, sort_order FROM membership_plans '
        'WHERE is_active = 1 ORDER BY sort_order, id'
    )
    plans = [dict(r) for r in cursor.fetchall()]
    cursor.close(); db.close()
    return jsonify({'plans': plans})


@auth_bp.route('/membership/status', methods=['GET'])
@token_required
def membership_status():
    """当前用户会员状态（自动降级过期会员）。"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'SELECT membership_type, membership_expire FROM users WHERE id = ?',
        (request.user_id,)
    )
    row = cursor.fetchone()
    if not row:
        cursor.close(); db.close()
        return jsonify({'error': '用户不存在'}), 404

    mtype = row['membership_type'] or 'free'
    expire = row['membership_expire']
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if mtype != 'free' and expire and expire <= now:
        cursor.execute(
            "UPDATE users SET membership_type = 'free', membership_expire = NULL, "
            "updated_at = datetime('now','localtime') WHERE id = ?",
            (request.user_id,)
        )
        db.commit()
        mtype, expire = 'free', None
    cursor.close(); db.close()

    return jsonify({
        'membership_type': mtype,
        'membership_expire': expire,
        'is_vip': mtype in ('vip', 'svip'),
        'is_svip': mtype == 'svip',
    })


@auth_bp.route('/membership/purchase', methods=['POST'])
@token_required
def purchase_membership():
    """
    模拟购买会员：方案必须上架，支付直接模拟成功，
    有效期在当前（或未过期）到期时间上累加。记录订单。
    """
    data = request.get_json(force=True, silent=True) or {}
    plan_id = data.get('plan_id')
    if not plan_id:
        return jsonify({'error': '请选择会员方案'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'SELECT * FROM membership_plans WHERE id = ? AND is_active = 1',
        (plan_id,)
    )
    plan = cursor.fetchone()
    if not plan:
        cursor.close(); db.close()
        return jsonify({'error': '方案不存在或已下架'}), 404

    cursor.execute(
        'SELECT membership_type, membership_expire FROM users WHERE id = ?',
        (request.user_id,)
    )
    user = cursor.fetchone()
    if not user:
        cursor.close(); db.close()
        return jsonify({'error': '用户不存在'}), 404

    now = datetime.datetime.now()
    base = now
    if user['membership_expire']:
        try:
            exp = datetime.datetime.strptime(
                user['membership_expire'], '%Y-%m-%d %H:%M:%S'
            )
            if exp > now:
                base = exp
        except Exception:
            pass

    new_expire = base + datetime.timedelta(days=plan['duration_days'])
    new_type = plan['name'] if plan['name'] in ('vip', 'svip') else 'vip'
    # 已 SVIP 时购买 VIP 不降级
    if new_type == 'vip' and user['membership_type'] == 'svip':
        new_type = 'svip'

    cursor.execute(
        "UPDATE users SET membership_type = ?, membership_expire = ?, "
        "updated_at = datetime('now','localtime') WHERE id = ?",
        (new_type, new_expire.strftime('%Y-%m-%d %H:%M:%S'), request.user_id)
    )
    cursor.execute(
        'INSERT INTO membership_orders (user_id, plan_id, amount, status) '
        'VALUES (?, ?, ?, ?)',
        (request.user_id, plan_id, plan['price'], 'paid')
    )
    db.commit()
    cursor.close(); db.close()

    return jsonify({
        'success': True,
        'message': '购买成功（模拟支付）',
        'membership_type': new_type,
        'membership_expire': new_expire.strftime('%Y-%m-%d %H:%M:%S'),
    })


# ==================== 会员管理（B/S 管理端） ====================

@auth_bp.route('/membership/admin/plans', methods=['GET'])
@token_required
@_admin_required
def admin_list_plans():
    """管理员：全部会员方案（含下架）。"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'SELECT * FROM membership_plans ORDER BY sort_order, id'
    )
    plans = [dict(r) for r in cursor.fetchall()]
    cursor.close(); db.close()
    return jsonify({'plans': plans})


@auth_bp.route('/membership/admin/plans', methods=['POST'])
@token_required
@_admin_required
def admin_create_plan():
    """管理员：新增会员方案。"""
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get('name') or '').strip()
    if name not in ('vip', 'svip'):
        return jsonify({'error': '方案名必须是 vip 或 svip'}), 400
    try:
        price = float(data.get('price') or 0)
        duration = int(data.get('duration_days') or 30)
    except (TypeError, ValueError):
        return jsonify({'error': '价格/时长格式不正确'}), 400
    if price < 0 or duration <= 0:
        return jsonify({'error': '价格不能为负、时长必须大于 0'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO membership_plans (name, price, duration_days, is_active, sort_order) '
        'VALUES (?, ?, ?, ?, ?)',
        (name, price, duration, 1 if data.get('is_active') else 0, int(data.get('sort_order') or 0))
    )
    db.commit()
    plan_id = cursor.lastrowid
    cursor.close(); db.close()
    return jsonify({'success': True, 'id': plan_id, 'message': '方案已创建'})


@auth_bp.route('/membership/admin/plans/<int:plan_id>', methods=['PUT'])
@token_required
@_admin_required
def admin_update_plan(plan_id):
    """管理员：修改方案（价格/时长/上下架/排序）。"""
    data = request.get_json(force=True, silent=True) or {}
    sets = []
    params = []
    if 'name' in data:
        name = (data.get('name') or '').strip()
        if name not in ('vip', 'svip'):
            return jsonify({'error': '方案名必须是 vip 或 svip'}), 400
        sets.append('name = ?'); params.append(name)
    if 'price' in data:
        try:
            price = float(data['price'])
        except (TypeError, ValueError):
            return jsonify({'error': '价格格式不正确'}), 400
        if price < 0:
            return jsonify({'error': '价格不能为负'}), 400
        sets.append('price = ?'); params.append(price)
    if 'duration_days' in data:
        try:
            duration = int(data['duration_days'])
        except (TypeError, ValueError):
            return jsonify({'error': '时长格式不正确'}), 400
        if duration <= 0:
            return jsonify({'error': '时长必须大于 0'}), 400
        sets.append('duration_days = ?'); params.append(duration)
    if 'is_active' in data:
        sets.append('is_active = ?'); params.append(1 if data['is_active'] else 0)
    if 'sort_order' in data:
        sets.append('sort_order = ?'); params.append(int(data['sort_order'] or 0))
    if not sets:
        return jsonify({'error': '没有需要更新的字段'}), 400

    sets.append("updated_at = datetime('now','localtime')")
    params.append(plan_id)
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        f'UPDATE membership_plans SET {", ".join(sets)} WHERE id = ?',
        params
    )
    db.commit()
    cursor.close(); db.close()
    return jsonify({'success': True, 'message': '方案已更新'})


@auth_bp.route('/membership/admin/plans/<int:plan_id>', methods=['DELETE'])
@token_required
@_admin_required
def admin_delete_plan(plan_id):
    """管理员：删除会员方案。"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('DELETE FROM membership_plans WHERE id = ?', (plan_id,))
    db.commit()
    cursor.close(); db.close()
    return jsonify({'success': True, 'message': '方案已删除'})


@auth_bp.route('/membership/admin/orders', methods=['GET'])
@token_required
@_admin_required
def admin_list_orders():
    """管理员：最近购买订单（模拟支付记录）。"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT o.id, o.user_id, u.username, p.name AS plan_name, p.price,
               o.amount, o.status, o.created_at
        FROM membership_orders o
        JOIN users u ON u.id = o.user_id
        JOIN membership_plans p ON p.id = o.plan_id
        ORDER BY o.id DESC
        LIMIT 100
    ''')
    orders = [dict(r) for r in cursor.fetchall()]
    cursor.close(); db.close()
    return jsonify({'orders': orders})
