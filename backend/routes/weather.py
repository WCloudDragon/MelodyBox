"""
MelodyBox 天气路由

和风天气 v7 API 代理：IP 定位 + 天气实况。
使用 Ed25519 JWT 认证。
"""
from flask import Blueprint, request, jsonify, current_app
import time
import base64
import json
import gzip
import urllib.request
import urllib.parse
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

weather_bp = Blueprint('weather', __name__, url_prefix='/api/weather')

_cache = {}
_CACHE_TTL = 1800  # 30 分钟

# JWT 缓存（有效期最长 24h，我们设 30 分钟）
_jwt_cache = {'token': None, 'expire': 0}


def _get_db():
    return current_app.get_db()


def _get_weather_config():
    """从 settings 表读取天气配置"""
    try:
        db = _get_db()
        cursor = db.cursor()
        cursor.execute(
            'SELECT weather_private_key, weather_credential_id, weather_project_id, weather_api_host '
            'FROM settings WHERE user_id = 1'
        )
        row = cursor.fetchone()
        cursor.close()
        db.close()
        if row:
            return {
                'private_key': row['weather_private_key'] or None,
                'credential_id': row['weather_credential_id'] or None,
                'project_id': row['weather_project_id'] or None,
                'api_host': row['weather_api_host'] or '',
            }
    except Exception:
        pass
    return {'private_key': None, 'credential_id': None, 'project_id': None, 'api_host': ''}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _generate_jwt(config):
    """生成和风天气 Ed25519 JWT"""
    now = time.time()
    if _jwt_cache['token'] and _jwt_cache['expire'] > now:
        return _jwt_cache['token']

    private_key_pem = config['private_key']
    kid = config['credential_id']
    sub = config['project_id']

    # Header: {"alg":"EdDSA","typ":"JWT","kid":"xxx"}
    header = _b64url(json.dumps({'alg': 'EdDSA', 'typ': 'JWT', 'kid': kid}).encode())
    # Payload: {"sub":"xxx","iat":xxx,"exp":xxx}
    payload = _b64url(json.dumps({
        'sub': sub,
        'iat': int(now) - 30,
        'exp': int(now) + 1800,
    }).encode())

    signing_input = f'{header}.{payload}'.encode()

    # 加载 Ed25519 私钥并签名
    private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    signature = private_key.sign(signing_input)
    token = f'{header}.{payload}.{_b64url(signature)}'

    _jwt_cache['token'] = token
    _jwt_cache['expire'] = now + 1700  # 28 分钟后刷新
    print('[Weather] JWT generated (Ed25519)')
    return token


def _cache_get(key):
    entry = _cache.get(key)
    if entry and entry[0] > time.time():
        return entry[1]
    return None


def _cache_set(key, data):
    _cache[key] = (time.time() + _CACHE_TTL, data)


def _qweather_get(path, params, config):
    """和风天气 API GET 请求（Ed25519 JWT 认证）"""
    token = _generate_jwt(config)
    url = f"https://{config['api_host']}{path}"
    query = urllib.parse.urlencode(params)
    full_url = f'{url}?{query}'
    print(f'[Weather] request: {full_url}')

    req = urllib.request.Request(full_url, headers={
        'User-Agent': 'MelodyBox/1.0',
        'Authorization': f'Bearer {token}',
        'Accept-Encoding': 'gzip',
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
        if raw[:2] == b'\x1f\x8b':  # gzip magic bytes
            raw = gzip.decompress(raw)
        return json.loads(raw.decode('utf-8'))


# ==================== 天气代码映射 ====================

WEATHER_TEXT_MAP = {
    '100': '晴', '101': '多云', '102': '少云', '103': '晴间多云', '104': '阴',
    '150': '晴', '153': '晴',
    '300': '阵雨', '301': '小雨', '302': '暴雨', '303': '雷阵雨',
    '304': '雷阵雨', '305': '小雨', '306': '中雨', '307': '大雨',
    '308': '暴雨', '309': '小雨', '310': '中雨', '311': '大雨',
    '312': '暴雨', '313': '冻雨',
    '350': '小雨', '351': '中雨',
    '400': '小雪', '401': '中雪', '402': '大雪', '403': '暴雪',
    '404': '雨夹雪', '405': '雨夹雪', '406': '冻雨', '407': '阵雪',
    '408': '大雪', '409': '大雪', '410': '暴雪',
    '456': '阵雪', '457': '阵雪',
    '500': '薄雾', '501': '雾', '502': '霾', '503': '扬沙',
    '504': '浮尘', '507': '沙尘暴', '508': '强沙尘暴',
    '509': '浓雾', '510': '霾', '514': '霾', '515': '霾',
    '900': '炎热', '901': '寒冷',
}

WEATHER_MOOD_MAP = {
    '100': 'fresh', '150': 'fresh', '153': 'fresh',
    '101': 'calm', '102': 'calm', '103': 'calm',
    '104': 'calm',
    '300': 'sad', '301': 'sad', '305': 'sad', '309': 'sad',
    '302': 'energetic', '303': 'energetic', '304': 'energetic',
    '306': 'sad', '307': 'sad', '308': 'sad',
    '310': 'sad', '311': 'sad', '312': 'sad', '313': 'sad',
    '350': 'sad', '351': 'sad',
    '400': 'romantic', '401': 'romantic', '402': 'romantic',
    '403': 'romantic', '404': 'romantic', '405': 'romantic',
    '406': 'calm', '407': 'romantic',
    '408': 'romantic', '409': 'romantic', '410': 'romantic',
    '456': 'romantic', '457': 'romantic',
    '500': 'calm', '501': 'calm', '502': 'calm',
    '503': 'energetic', '504': 'energetic',
    '507': 'energetic', '508': 'energetic',
    '509': 'calm', '510': 'calm', '514': 'calm', '515': 'calm',
    '900': 'upbeat',
    '901': 'calm',
}

MOOD_LABELS = {
    'sad': '伤感', 'energetic': '激昂', 'calm': '舒缓',
    'upbeat': '动感', 'fresh': '清新', 'romantic': '浪漫', 'inspire': '励志',
}


@weather_bp.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        return '', 200


def _get_city_by_ip():
    """通过 ip-api.com 获取城市名和坐标"""
    try:
        req = urllib.request.Request(
            'http://ip-api.com/json?lang=zh-CN&fields=city,country,lat,lon',
            headers={'User-Agent': 'MelodyBox/1.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            city = data.get('city', '')
            lat = data.get('lat')
            lon = data.get('lon')
            if city and lat is not None and lon is not None:
                return city, lat, lon
            return None, None, None
    except Exception as e:
        print(f'[Weather] ip-api.com failed: {e}')
        return None, None, None


@weather_bp.route('/current')
def get_current_weather():
    """获取当前天气信息"""
    config = _get_weather_config()
    print(f'[Weather] key={bool(config["private_key"])}, kid={bool(config["credential_id"])}, '
          f'pid={bool(config["project_id"])}, host={config["api_host"]}')

    if not all([config['private_key'], config['credential_id'], config['project_id'], config['api_host']]):
        return jsonify({'error': '天气配置不完整（需要私钥、凭据ID、项目ID、API Host）', 'configured': False}), 400

    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    try:
        if lat is not None and lon is not None:
            location_param = f'{lon:.2f},{lat:.2f}'
            city_name = ''
            cache_key = f'weather_coord_{lon:.2f}_{lat:.2f}'
        else:
            city_name, ip_lat, ip_lon = _get_city_by_ip()
            if not city_name:
                return jsonify({'error': 'IP 定位失败'}), 502
            location_param = f'{ip_lon:.2f},{ip_lat:.2f}'
            cache_key = f'weather_city_{city_name}'

        cached = _cache_get(cache_key)
        if cached:
            return jsonify(cached)

        weather_data = _qweather_get('/v7/weather/now', {'location': location_param}, config)
        print(f'[Weather] response code: {weather_data.get("code")}')

        if weather_data.get('code') != '200':
            return jsonify({'error': '天气查询失败', 'code': weather_data.get('code')}), 502

        now = weather_data.get('now', {})
        code = now.get('icon', '')
        text = WEATHER_TEXT_MAP.get(code, now.get('text', ''))
        mood = WEATHER_MOOD_MAP.get(code, 'calm')

        hour = int(time.strftime('%H', time.localtime()))
        time_mood = _time_based_mood(hour, mood)

        result = {
            'configured': True,
            'location': {'id': location_param, 'name': city_name, 'lat': lat or 0, 'lon': lon or 0},
            'weather': {
                'code': code, 'text': text, 'temp': now.get('temp', ''),
                'feelsLike': now.get('feelsLike', ''), 'humidity': now.get('humidity', ''),
                'windDir': now.get('windDir', ''), 'windScale': now.get('windScale', ''),
            },
            'recommendation': {
                'mood': time_mood, 'moodLabel': MOOD_LABELS.get(time_mood, '舒缓'),
                'suggestion': _build_suggestion(text, time_mood, hour),
            },
        }

        _cache_set(cache_key, result)
        print(f'[Weather] success: {text} {now.get("temp", "")}° {city_name}')
        return jsonify(result)

    except Exception as e:
        print(f'[Weather] exception: {e}')
        return jsonify({'error': str(e)}), 500


def _time_based_mood(hour, base_mood):
    if hour >= 23 or hour < 5:
        if base_mood in ('upbeat', 'energetic'):
            return 'calm'
    elif hour < 8:
        if base_mood in ('sad', 'calm'):
            return 'fresh'
    elif hour >= 21:
        if base_mood == 'upbeat':
            return 'calm'
        if base_mood == 'energetic':
            return 'romantic'
    return base_mood


def _build_suggestion(weather_text, mood, hour):
    mood_label = MOOD_LABELS.get(mood, '舒缓')
    if hour >= 23 or hour < 5:
        t = '夜深了'
    elif hour < 8:
        t = '清晨时分'
    elif hour < 12:
        t = '上午好'
    elif hour < 14:
        t = '午间时光'
    elif hour < 18:
        t = '午后'
    elif hour < 21:
        t = '傍晚时分'
    else:
        t = '夜晚'
    templates = {
        'sad': f'{weather_text}的{t}，来点{mood_label}的音乐吧',
        'calm': f'{weather_text}的{t}，适合{mood_label}的旋律',
        'fresh': f'{weather_text}的{t}，来首{mood_label}的歌',
        'upbeat': f'{weather_text}的{t}，来点{mood_label}的节奏',
        'energetic': f'{weather_text}的{t}，听{mood_label}的歌振奋精神',
        'romantic': f'{weather_text}的{t}，{mood_label}的旋律正合适',
        'inspire': f'{weather_text}的{t}，来点{mood_label}的歌',
    }
    return templates.get(mood, f'{weather_text}的{t}，推荐{mood_label}的音乐')
