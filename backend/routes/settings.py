from flask import Blueprint, request, jsonify, current_app

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@settings_bp.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        return '', 200


# 前端(camelCase) ↔ 数据库(snake_case) 字段映射
SNAKE_TO_CAMEL = {
    'theme': 'theme',
    'accent_color': 'accentColor',
    'blur_strength': 'blurStrength',
    'follow_system_theme': 'followSystemTheme',
    'show_lyrics': 'showLyrics',
    'lyrics_font_size': 'lyricsFontSize',
    'lyrics_font_weight': 'lyricsFontWeight',
    'lyrics_trans_scale': 'lyricsTransScale',
    'lyrics_active_scale': 'lyricsActiveScale',
    'enable_lyrics_blur': 'enableLyricsBlur',
    'enable_domino_scroll': 'enableDominoScroll',
    'enable_word_lift': 'enableWordLift',
    'word_anim_fps': 'wordAnimFps',
    'show_visualizer': 'showVisualizer',
    'auto_scan': 'autoScan',
    'language': 'language',
    'desktop_lyrics_font_size': 'desktopLyricsFontSize',
    'desktop_lyrics_active_scale': 'desktopLyricsActiveScale',
    'desktop_lyrics_trans_scale': 'desktopLyricsTransScale',
    'desktop_lyrics_view_lines': 'desktopLyricsViewLines',
}

CAMEL_TO_SNAKE = {v: k for k, v in SNAKE_TO_CAMEL.items()}

# 默认设置值（与 app.py 建表 DEFAULT 及前端 store 初始值一致）
DEFAULT_SETTINGS = {
    'theme': 'dark',
    'accent_color': '#6366f1',
    'blur_strength': '10px',
    'follow_system_theme': False,
    'show_lyrics': True,
    'lyrics_font_size': 32,
    'lyrics_font_weight': 700,
    'lyrics_trans_scale': 60,
    'lyrics_active_scale': 115,
    'enable_lyrics_blur': True,
    'enable_domino_scroll': True,
    'enable_word_lift': True,
    'word_anim_fps': 60,
    'show_visualizer': True,
    'auto_scan': False,
    'language': 'zh-CN',
    'desktop_lyrics_font_size': 24,
    'desktop_lyrics_active_scale': 120,
    'desktop_lyrics_trans_scale': 60,
    'desktop_lyrics_view_lines': 2,
}

# SQLite 中所有 settings 列（不含 id）
SETTINGS_COLUMNS = ['user_id'] + list(SNAKE_TO_CAMEL.keys())


def get_db():
    """获取数据库连接"""
    return current_app.get_db()


def row_to_settings(row):
    """将数据库行（snake_case）转换为前端格式（camelCase）"""
    result = {}
    for snake_key, camel_key in SNAKE_TO_CAMEL.items():
        val = row[snake_key]
        # SQLite 用 0/1 存布尔值，转为 Python bool
        if snake_key in ('follow_system_theme', 'show_lyrics', 'enable_lyrics_blur',
                         'enable_domino_scroll', 'enable_word_lift', 'show_visualizer', 'auto_scan'):
            val = bool(val)
        result[camel_key] = val
    return result


# ==================== 设置接口 ====================

@settings_bp.route('')
def get_settings():
    """获取当前用户设置（默认 user_id=1），无记录时自动初始化默认值"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM settings WHERE user_id = 1')
        row = cursor.fetchone()

        if row:
            result = row_to_settings(row)
        else:
            # 无记录：插入默认设置
            columns = ', '.join(SETTINGS_COLUMNS)
            placeholders = ', '.join(['?' for _ in SETTINGS_COLUMNS])
            values = [1] + [DEFAULT_SETTINGS[k] for k in SNAKE_TO_CAMEL.keys()]

            cursor.execute(f'INSERT INTO settings ({columns}) VALUES ({placeholders})', values)
            db.commit()

            result = DEFAULT_SETTINGS.copy()

        cursor.close()
        db.close()

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@settings_bp.route('', methods=['PUT'])
def update_settings():
    """更新用户设置（部分更新，camelCase → snake_case 映射）"""
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({'error': '请提供要更新的设置字段'}), 400

    # 只接受已知字段
    updates = {}
    for camel_key, value in data.items():
        snake_key = CAMEL_TO_SNAKE.get(camel_key)
        if snake_key is not None:
            updates[snake_key] = value

    if not updates:
        return jsonify({'error': '没有可识别的设置字段'}), 400

    try:
        db = get_db()
        cursor = db.cursor()

        # 读取现有设置（不存在则用默认值）
        cursor.execute('SELECT * FROM settings WHERE user_id = 1')
        row = cursor.fetchone()

        if row:
            current = {k: row[k] for k in SNAKE_TO_CAMEL.keys()}
        else:
            current = DEFAULT_SETTINGS.copy()

        # 合并更新
        current.update(updates)

        # INSERT OR REPLACE（user_id 有 UNIQUE 约束，冲突时替换整行）
        columns = ', '.join(SETTINGS_COLUMNS)
        placeholders = ', '.join(['?' for _ in SETTINGS_COLUMNS])
        values = [1] + [current[k] for k in SNAKE_TO_CAMEL.keys()]

        cursor.execute(
            f'INSERT OR REPLACE INTO settings ({columns}) VALUES ({placeholders})',
            values
        )
        db.commit()
        cursor.close()
        db.close()

        # 返回合并后的完整设置（snake → camel）
        result = {}
        for snake_key, camel_key in SNAKE_TO_CAMEL.items():
            val = current[snake_key]
            if snake_key in ('follow_system_theme', 'show_lyrics', 'enable_lyrics_blur',
                             'enable_domino_scroll', 'enable_word_lift', 'show_visualizer', 'auto_scan'):
                val = bool(val)
            result[camel_key] = val

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
