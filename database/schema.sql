-- ============================================
-- MelodyBox 数据库建表脚本
-- 数据库: MySQL 8.0+
-- ============================================

CREATE DATABASE IF NOT EXISTS melodybox CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE melodybox;

-- 1. 用户与会员权益表
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    avatar_url VARCHAR(500),
    membership_type ENUM('free', 'vip', 'svip') DEFAULT 'free',
    membership_expire DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. 用户歌曲播放次数统计表
CREATE TABLE user_song_stats (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    song_id BIGINT NOT NULL,
    play_count INT DEFAULT 0,
    last_played DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3. 用户播放历史明细表
CREATE TABLE play_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    song_id BIGINT NOT NULL,
    played_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration_played INT DEFAULT 0 COMMENT '播放时长(秒)',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 4. 歌曲主表
CREATE TABLE songs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(200) NOT NULL,
    file_path VARCHAR(500) NOT NULL UNIQUE COMMENT '本地文件路径',
    cover_url VARCHAR(500) COMMENT '封面图片URL',
    lyrics TEXT COMMENT '歌词内容',
    year INT,
    genre VARCHAR(50),
    duration INT COMMENT '时长(秒)',
    bitrate INT COMMENT '比特率(bps)',
    sample_rate INT COMMENT '采样率(Hz)',
    file_size BIGINT COMMENT '文件大小(字节)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 5. 歌手表
CREATE TABLE artists (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    bio TEXT,
    image_url VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 6. 专辑表
CREATE TABLE albums (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(200) NOT NULL,
    cover_url VARCHAR(500),
    year INT,
    genre VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 7. 歌曲与歌手关联表
CREATE TABLE song_artist (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    song_id BIGINT NOT NULL,
    artist_id BIGINT NOT NULL,
    role ENUM('main', 'feat', 'composer', 'producer') DEFAULT 'main',
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
    UNIQUE KEY uk_song_artist (song_id, artist_id, role)
) ENGINE=InnoDB;

-- 8. 歌曲与专辑关联表
CREATE TABLE song_album (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    song_id BIGINT NOT NULL,
    album_id BIGINT NOT NULL,
    track_number INT,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE,
    UNIQUE KEY uk_song_album (song_id, album_id)
) ENGINE=InnoDB;

-- 9. 歌单表
CREATE TABLE playlists (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    cover_url VARCHAR(500),
    is_public BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 10. 歌单与歌曲关联表
CREATE TABLE playlist_song (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    playlist_id BIGINT NOT NULL,
    song_id BIGINT NOT NULL,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    UNIQUE KEY uk_playlist_song (playlist_id, song_id)
) ENGINE=InnoDB;

-- 11. 轮播图配置表
CREATE TABLE banners (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    image_url VARCHAR(500) NOT NULL,
    link_url VARCHAR(500),
    title VARCHAR(100),
    sort_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 12. 推荐曲目配置表
CREATE TABLE recommendations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    song_id BIGINT NOT NULL,
    reason VARCHAR(200),
    sort_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 13. 设置参数表
CREATE TABLE settings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL UNIQUE,
    theme VARCHAR(20) DEFAULT 'dark',
    accent_color VARCHAR(10) DEFAULT '#6366f1',
    blur_strength VARCHAR(10) DEFAULT '10px',
    show_lyrics BOOLEAN DEFAULT TRUE,
    lyrics_font_size INT DEFAULT 16,
    show_visualizer BOOLEAN DEFAULT TRUE,
    auto_scan BOOLEAN DEFAULT FALSE,
    language VARCHAR(10) DEFAULT 'zh-CN',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 索引
CREATE INDEX idx_songs_title ON songs(title);
CREATE INDEX idx_songs_year ON songs(year);
CREATE INDEX idx_songs_genre ON songs(genre);
CREATE INDEX idx_play_history_user ON play_history(user_id, played_at);
CREATE INDEX idx_user_song_stats_user ON user_song_stats(user_id);
