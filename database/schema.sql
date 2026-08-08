-- ============================================================
-- MelodyBox 数据库结构（SQLite）
--
-- 本文件与 backend/app.py 的 init_db() 保持一致，是实际运行的权威结构。
-- 共 23 张表 + 1 个视图（all_songs）。
-- 说明：
--   - 时间统一存 TEXT，格式 'YYYY-MM-DD HH:MM:SS'（localtime）
--   - songs/cloud_songs 中的 embedding / audio_embedding 为历史遗留列，
--     新向量存入 song_vectors 表（带版本号）
--   - WAL 模式 + foreign_keys=ON
-- ============================================================

-- 1. 用户与会员
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
);

-- 2. 歌曲主表（本地曲库）
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
    embedding BLOB DEFAULT NULL,        -- 历史遗留：文本向量（新数据写 song_vectors）
    audio_embedding BLOB DEFAULT NULL,  -- 历史遗留：音频向量（新数据写 song_vectors）
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_songs_title ON songs(title);
CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist);
CREATE INDEX IF NOT EXISTS idx_songs_album ON songs(album);
CREATE INDEX IF NOT EXISTS idx_songs_fingerprint ON songs(fingerprint);
CREATE INDEX IF NOT EXISTS idx_songs_lang ON songs(lang);

-- 3. 艺术家
CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    bio TEXT DEFAULT '',
    image_url TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name);

-- 4. 专辑
CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    cover_url TEXT DEFAULT '',
    year INTEGER DEFAULT 0,
    genre TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(title, year)
);
CREATE INDEX IF NOT EXISTS idx_albums_title ON albums(title);

-- 5. 歌曲-艺术家关联
CREATE TABLE IF NOT EXISTS song_artist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL,
    artist_id INTEGER NOT NULL,
    role TEXT DEFAULT 'main' CHECK(role IN ('main','feat','composer','producer')),
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
    UNIQUE(song_id, artist_id, role)
);
CREATE INDEX IF NOT EXISTS idx_sa_song ON song_artist(song_id);
CREATE INDEX IF NOT EXISTS idx_sa_artist ON song_artist(artist_id);

-- 6. 歌曲-专辑关联
CREATE TABLE IF NOT EXISTS song_album (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL,
    album_id INTEGER NOT NULL,
    track_number INTEGER DEFAULT 0,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE,
    UNIQUE(song_id, album_id)
);
CREATE INDEX IF NOT EXISTS idx_sal_song ON song_album(song_id);
CREATE INDEX IF NOT EXISTS idx_sal_album ON song_album(album_id);

-- 7. 播放统计（断联保留：歌曲删除后 song_id 置 NULL，指纹保留）
CREATE TABLE IF NOT EXISTS play_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER DEFAULT NULL,
    fingerprint TEXT NOT NULL,
    play_count INTEGER DEFAULT 1,
    last_played TEXT DEFAULT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_ps_song ON play_stats(song_id);
CREATE INDEX IF NOT EXISTS idx_ps_fp ON play_stats(fingerprint);
CREATE INDEX IF NOT EXISTS idx_ps_count ON play_stats(play_count DESC);

-- 8. 播放历史明细
CREATE TABLE IF NOT EXISTS play_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER DEFAULT NULL,
    fingerprint TEXT NOT NULL,
    played_at TEXT DEFAULT (datetime('now','localtime')),
    duration_played REAL DEFAULT 0,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_ph_song ON play_history(song_id);
CREATE INDEX IF NOT EXISTS idx_ph_time ON play_history(played_at DESC);
CREATE INDEX IF NOT EXISTS idx_ph_fp ON play_history(fingerprint);

-- 9. 歌单
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
);
CREATE INDEX IF NOT EXISTS idx_pl_user ON playlists(user_id);

-- 10. 歌单-歌曲关联
CREATE TABLE IF NOT EXISTS playlist_song (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL,
    song_id INTEGER NOT NULL,
    added_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    UNIQUE(playlist_id, song_id)
);
CREATE INDEX IF NOT EXISTS idx_pls_pl ON playlist_song(playlist_id);
CREATE INDEX IF NOT EXISTS idx_pls_song ON playlist_song(song_id);

-- 11. 用户设置
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
    enable_dynamic_bg INTEGER DEFAULT 1,
    enable_audio_rhythm INTEGER DEFAULT 1,
    weather_private_key TEXT DEFAULT '',
    weather_credential_id TEXT DEFAULT '',
    weather_project_id TEXT DEFAULT '',
    weather_api_host TEXT DEFAULT 'api.qweather.com',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 12. AI API 配置（模型缓存目录；LLM 字段预留）
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
);

-- 13. 轮播图（预留）
CREATE TABLE IF NOT EXISTS banners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_url TEXT NOT NULL,
    link_url TEXT DEFAULT '',
    title TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 14. 推荐位（预留）
CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
);

-- 15. 管理日志
CREATE TABLE IF NOT EXISTS admin_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target TEXT DEFAULT '',
    detail TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 16. 扫描目录
CREATE TABLE IF NOT EXISTS scan_directories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    added_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 17. 歌曲情绪分数（推荐预计算）
CREATE TABLE IF NOT EXISTS song_mood_scores (
    song_id INTEGER NOT NULL,
    mood TEXT NOT NULL,
    score REAL NOT NULL,
    audio_score REAL DEFAULT NULL,
    PRIMARY KEY (song_id, mood),
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_mood_scores ON song_mood_scores(mood, score DESC);

-- 18. 歌曲向量（重构版：文本/音频向量 + 模型版本号）
CREATE TABLE IF NOT EXISTS song_vectors (
    song_id INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'local',
    text_vec BLOB DEFAULT NULL,
    audio_vec BLOB DEFAULT NULL,
    text_version INTEGER DEFAULT 0,
    audio_version INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (song_id, source)
);

-- 19. 用户行为事件（画像数据源）
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    song_id INTEGER DEFAULT NULL,
    fingerprint TEXT DEFAULT '',
    event_type TEXT NOT NULL,
    duration_ratio REAL DEFAULT NULL,
    ts TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events(user_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

-- 20. 用户画像
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INTEGER PRIMARY KEY,
    text_vec BLOB DEFAULT NULL,
    audio_vec BLOB DEFAULT NULL,
    genre_dist TEXT DEFAULT '{}',
    lang_dist TEXT DEFAULT '{}',
    recent_ids TEXT DEFAULT '[]',
    played_ids TEXT DEFAULT '[]',
    version INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 21. 会员方案（管理端可调价/上下架，客户端模拟购买）
CREATE TABLE IF NOT EXISTS membership_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL DEFAULT 0,
    duration_days INTEGER NOT NULL DEFAULT 30,
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 22. 会员订单（模拟支付记录）
CREATE TABLE IF NOT EXISTS membership_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'paid',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES membership_plans(id)
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON membership_orders(user_id, created_at DESC);

-- 23. 云端曲库（管理员上传/管理，当前为本地演示部署）
CREATE TABLE IF NOT EXISTS cloud_songs (
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
    fingerprint TEXT DEFAULT '',
    lang TEXT DEFAULT '',
    embedding BLOB DEFAULT NULL,        -- 历史遗留（新数据写 song_vectors）
    audio_embedding BLOB DEFAULT NULL,  -- 历史遗留
    status TEXT DEFAULT 'online' CHECK(status IN ('online','offline')),
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_cloud_fingerprint ON cloud_songs(fingerprint);

-- 云端歌曲自定义元数据（管理员覆盖值）
CREATE TABLE IF NOT EXISTS cloud_metadata (
    cloud_song_id INTEGER PRIMARY KEY REFERENCES cloud_songs(id) ON DELETE CASCADE,
    title TEXT DEFAULT NULL,
    artist TEXT DEFAULT NULL,
    album TEXT DEFAULT NULL,
    genre TEXT DEFAULT NULL,
    cover_url TEXT DEFAULT NULL,
    lyrics TEXT DEFAULT NULL,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 统一视图：本地 + 云端歌曲（仅上架，云端元数据 COALESCE 覆盖）
CREATE VIEW IF NOT EXISTS all_songs AS
SELECT id, title, artist, album, file_path, cover_url, lyrics,
       genre, year, duration, lang, fingerprint, embedding, audio_embedding,
       'local' AS source
FROM songs
UNION ALL
SELECT cs.id,
       COALESCE(cm.title, cs.title) AS title,
       COALESCE(cm.artist, cs.artist) AS artist,
       COALESCE(cm.album, cs.album) AS album,
       cs.file_path,
       COALESCE(cm.cover_url, cs.cover_url) AS cover_url,
       COALESCE(cm.lyrics, cs.lyrics) AS lyrics,
       COALESCE(cm.genre, cs.genre) AS genre,
       cs.year, cs.duration, cs.lang, cs.fingerprint,
       cs.embedding, cs.audio_embedding,
       'cloud' AS source
FROM cloud_songs cs
LEFT JOIN cloud_metadata cm ON cm.cloud_song_id = cs.id
WHERE cs.status = 'online';
