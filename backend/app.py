from flask import Flask, g
from flask_cors import CORS
from config.config import Config
import os
import sys

# 国内网络环境自动使用 huggingface 镜像（hf-mirror.com）
# 确保模型下载、fastembed 等组件不受 DNS 污染影响
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
# Windows 下不支持软链接，关闭无关警告
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')

# 将项目 bin 目录加入 PATH，确保 Python 进程能找到 ffmpeg
# （librosa 加载 mp3 等格式需要 ffmpeg）
def _ensure_ffmpeg_path():
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包：exe 在 flask-dist/，bin 在 ../bin/
        bin_dir = os.path.join(os.path.dirname(sys.executable), '..', 'bin')
    else:
        bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bin')
    if os.path.isdir(bin_dir):
        os.environ['PATH'] = bin_dir + os.pathsep + os.environ.get('PATH', '')
        os.environ.setdefault('AUDIOREAD_FFMPEG_PATH', os.path.join(bin_dir, 'ffmpeg.exe'))

_ensure_ffmpeg_path()

import sqlite3

def init_db(app):
    """初始化 SQLite 数据库和全部 15 张表"""
    db_path = app.config['DB_PATH']
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode=WAL')
    cursor = conn.cursor()

    # ========== 1. users ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            email TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            membership_type TEXT DEFAULT 'free' CHECK(membership_type IN ('free','vip','svip')),
            membership_expire TEXT DEFAULT NULL,
            role TEXT DEFAULT 'user' CHECK(role IN ('user','admin')),
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')

    # ========== 2. songs ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT DEFAULT '',
            album TEXT DEFAULT '',
            file_path TEXT NOT NULL UNIQUE,
            cover_url TEXT DEFAULT '',
            lyrics TEXT DEFAULT '',
            year INTEGER DEFAULT 0,
            genre TEXT DEFAULT '',
            duration REAL DEFAULT 0,
            bitrate INTEGER DEFAULT 0,
            sample_rate INTEGER DEFAULT 0,
            bit_depth INTEGER DEFAULT 0,
            quality TEXT DEFAULT '',
            file_size INTEGER DEFAULT 0,
            file_mtime REAL DEFAULT 0,
            disc_number INTEGER DEFAULT 0,
            track_number INTEGER DEFAULT 0,
            fingerprint TEXT DEFAULT '',
            lang TEXT DEFAULT '',
            embedding BLOB DEFAULT NULL,
            audio_embedding BLOB DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_title ON songs(title)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_album ON songs(album)')

    # 兼容旧表：先加列，再建索引
    for col, col_def in [
        ('disc_number', 'INTEGER DEFAULT 0'),
        ('track_number', 'INTEGER DEFAULT 0'),
        ('bit_depth', 'INTEGER DEFAULT 0'),
        ('quality', 'TEXT DEFAULT ""'),
        ('fingerprint', 'TEXT DEFAULT ""'),
        ('lang', 'TEXT DEFAULT ""'),
        ('embedding', 'BLOB DEFAULT NULL'),
        ('audio_embedding', 'BLOB DEFAULT NULL'),
    ]:
        try: cursor.execute(f'ALTER TABLE songs ADD COLUMN {col} {col_def}')
        except sqlite3.OperationalError: pass

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_fingerprint ON songs(fingerprint)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_lang ON songs(lang)')

    # ========== 3. artists ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            bio TEXT DEFAULT '',
            image_url TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name)')

    # ========== 4. albums ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            cover_url TEXT DEFAULT '',
            year INTEGER DEFAULT 0,
            genre TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(title, year)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_albums_title ON albums(title)')

    # ========== 5. song_artist ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS song_artist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            role TEXT DEFAULT 'main' CHECK(role IN ('main','feat','composer','producer')),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
            UNIQUE(song_id, artist_id, role)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sa_song ON song_artist(song_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sa_artist ON song_artist(artist_id)')

    # ========== 6. song_album ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS song_album (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            album_id INTEGER NOT NULL,
            track_number INTEGER DEFAULT 0,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE,
            UNIQUE(song_id, album_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sal_song ON song_album(song_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sal_album ON song_album(album_id)')

    # ========== 7. play_stats (断联保留) ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS play_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER DEFAULT NULL,
            fingerprint TEXT NOT NULL,
            play_count INTEGER DEFAULT 1,
            last_played TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE SET NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ps_song ON play_stats(song_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ps_fp ON play_stats(fingerprint)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ps_count ON play_stats(play_count DESC)')

    # ========== 8. play_history ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS play_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER DEFAULT NULL,
            fingerprint TEXT NOT NULL,
            played_at TEXT DEFAULT (datetime('now','localtime')),
            duration_played REAL DEFAULT 0,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE SET NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ph_song ON play_history(song_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ph_time ON play_history(played_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ph_fp ON play_history(fingerprint)')

    # ========== 9. playlists ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            cover_url TEXT DEFAULT '',
            is_public INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pl_user ON playlists(user_id)')

    # ========== 10. playlist_song ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS playlist_song (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            song_id INTEGER NOT NULL,
            added_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            UNIQUE(playlist_id, song_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pls_pl ON playlist_song(playlist_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pls_song ON playlist_song(song_id)')

    # ========== 11. settings ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            theme TEXT DEFAULT 'dark',
            accent_color TEXT DEFAULT '#6366f1',
            blur_strength TEXT DEFAULT '10px',
            follow_system_theme INTEGER DEFAULT 0,
            show_lyrics INTEGER DEFAULT 1,
            lyrics_font_size INTEGER DEFAULT 32,
            lyrics_font_weight INTEGER DEFAULT 700,
            lyrics_trans_scale INTEGER DEFAULT 60,
            lyrics_active_scale INTEGER DEFAULT 115,
            enable_lyrics_blur INTEGER DEFAULT 1,
            enable_domino_scroll INTEGER DEFAULT 1,
            enable_word_lift INTEGER DEFAULT 1,
            word_anim_fps INTEGER DEFAULT 60,
            show_visualizer INTEGER DEFAULT 1,
            auto_scan INTEGER DEFAULT 0,
            language TEXT DEFAULT 'zh-CN',
            desktop_lyrics_font_size INTEGER DEFAULT 24,
            desktop_lyrics_active_scale INTEGER DEFAULT 120,
            desktop_lyrics_trans_scale INTEGER DEFAULT 60,
            desktop_lyrics_view_lines INTEGER DEFAULT 2,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # 桌面歌词设置迁移（SQLite ALTER TABLE 不支持 IF NOT EXISTS，静默忽略列已存在错误）
    for mig in [
        'ALTER TABLE settings ADD COLUMN desktop_lyrics_font_size INTEGER DEFAULT 24',
        'ALTER TABLE settings ADD COLUMN desktop_lyrics_active_scale INTEGER DEFAULT 120',
        'ALTER TABLE settings ADD COLUMN desktop_lyrics_trans_scale INTEGER DEFAULT 60',
        'ALTER TABLE settings ADD COLUMN desktop_lyrics_view_lines INTEGER DEFAULT 2',
        'ALTER TABLE settings ADD COLUMN enable_dynamic_bg INTEGER DEFAULT 1',
        'ALTER TABLE settings ADD COLUMN enable_audio_rhythm INTEGER DEFAULT 1',
    ]:
        try: conn.executescript(mig)
        except sqlite3.OperationalError: pass

    # ========== 12. ai_api_config ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_api_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            provider TEXT DEFAULT 'openai',
            api_key TEXT DEFAULT '',
            api_base TEXT DEFAULT '',
            model TEXT DEFAULT 'gpt-3.5-turbo',
            is_active INTEGER DEFAULT 0,
            model_cache_dir TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    # 兼容旧表
    try: cursor.execute("ALTER TABLE ai_api_config ADD COLUMN model_cache_dir TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass

    # ========== 13. banners ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_url TEXT NOT NULL,
            link_url TEXT DEFAULT '',
            title TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')

    # ========== 14. recommendations ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            reason TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
        )
    ''')

    # ========== 15. admin_logs ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # ========== 16. scan_directories ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_directories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            added_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')

    # ========== 17. song_mood_scores ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS song_mood_scores (
            song_id INTEGER NOT NULL,
            mood TEXT NOT NULL,
            score REAL NOT NULL,
            audio_score REAL DEFAULT NULL,
            PRIMARY KEY (song_id, mood),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
        )
    ''')
    # 兼容旧表：添加 audio_score 列
    try:
        cursor.execute('ALTER TABLE song_mood_scores ADD COLUMN audio_score REAL DEFAULT NULL')
    except Exception:
        pass  # 列已存在
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_mood_scores ON song_mood_scores(mood, score DESC)')

    conn.commit()
    cursor.close()
    conn.close()

    # 首次运行：创建默认管理员用户
    from werkzeug.security import generate_password_hash
    conn2 = sqlite3.connect(db_path)
    conn2.execute('PRAGMA foreign_keys = ON')
    cur2 = conn2.cursor()
    cur2.execute('SELECT COUNT(*) FROM users')
    if cur2.fetchone()[0] == 0:
        cur2.execute(
            'INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, ?)',
            ('admin', generate_password_hash('admin123'), 'admin@melodybox.local', 'admin')
        )
        conn2.commit()
        print('[db] 默认管理员已创建: admin / admin123')
    cur2.close()
    conn2.close()

    print(f'[db] SQLite 初始化完成 (15 张表): {db_path}')


def get_db(app):
    """获取数据库连接（Row 工厂，WAL 模式 + 超时避免并发锁）"""
    conn = sqlite3.connect(app.config['DB_PATH'], timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def _init_ai_model_dir(app):
    """从数据库读取并设置 AI 模型缓存路径"""
    try:
        with app.app_context():
            db = app.get_db()
            cursor = db.cursor()
            cursor.execute(
                'SELECT model_cache_dir FROM ai_api_config WHERE user_id = 1'
            )
            row = cursor.fetchone()
            cursor.close()
            db.close()
            if row and row['model_cache_dir']:
                from services.embedding import set_cache_dir
                set_cache_dir(row['model_cache_dir'])
                print(f'[app] AI 模型缓存路径: {row["model_cache_dir"]}')
    except Exception:
        pass


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config['COVER_DIR'], exist_ok=True)

    CORS(app)

    init_db(app)

    from routes import music_bp
    from routes.auth import auth_bp
    from routes.stats import stats_bp
    from routes.playlist import playlist_bp
    from routes.settings import settings_bp
    from routes.folders import folders_bp
    from routes.ai import ai_bp

    app.register_blueprint(music_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(playlist_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(folders_bp)
    app.register_blueprint(ai_bp)

    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'message': 'MelodyBox API is running'}

    app.get_db = lambda: get_db(app)
    app.db_path = app.config['DB_PATH']

    # 从数据库初始化 AI 模型缓存路径
    _init_ai_model_dir(app)

    return app


if __name__ == '__main__':
    app = create_app()
    print('MelodyBox API starting on http://127.0.0.1:5000')
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
