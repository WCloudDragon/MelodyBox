"""
MelodyBox 推荐引擎统一配置

所有可调参数集中于此，重构后不再散落在各推荐函数里。
调参/评估时只需改这里，配合 tools/evaluate_recommendations.py 验证效果。
"""

# ==================== 向量版本 ====================
# 模型或向量结构变化时 +1，旧版本向量会被标记为待重新生成
TEXT_VECTOR_VERSION = 2
AUDIO_VECTOR_VERSION = 2

# ==================== 用户画像 ====================
PROFILE_VERSION = 1
PROFILE_HISTORY_DAYS = 30            # 画像只考虑最近 30 天的行为
PROFILE_DECAY_HALF_LIFE_DAYS = 14    # 时间衰减指数半衰期
PROFILE_MAX_HISTORY = 500            # 画像最多取最近 500 条行为
RECENT_EXCLUDE_DAYS = 7              # 最近 N 天听过的歌不重复推荐
NEGATIVE_WEIGHT = 0.5                # 跳过/不喜欢的歌在画像向量中的负权重

# ==================== 综合推荐 ====================
COMPREHENSIVE_WEIGHTS = {'text': 0.40, 'audio': 0.30, 'genre': 0.15, 'lang': 0.15}
COMPREHENSIVE_FALLBACK_WEIGHTS = {'text': 0.60, 'genre': 0.20, 'lang': 0.20}

# ==================== 相似歌曲 ====================
SIMILAR_WEIGHTS = {'text': 0.50, 'audio': 0.50}

# ==================== 情绪推荐 ====================
MOOD_WEIGHTS = {'text': 0.50, 'audio': 0.50}

# ==================== 冷门宝藏 ====================
HIDDEN_GEM_SIM_WEIGHT = 0.9
HIDDEN_GEM_COLD_WEIGHT = 0.1
HIDDEN_GEM_MAX_PLAY_COUNT = 3        # 全局播放次数低于该值才算"冷门"

# ==================== 多样性重排 (MMR) ====================
MMR_LAMBDA = 0.7
MMR_ARTIST_PENALTY = 0.3
MMR_GENRE_PENALTY = 0.15

# ==================== 探索/新鲜感 ====================
EXPLORE_POOL_FACTOR = 3              # 抖动池 = limit × factor
EXPLORE_JITTER = 0.03                # ±0.03 确定性微扰（替代硬编码随机）

# ==================== 候选池 ====================
CANDIDATE_POOL = 300                 # 每模式候选上限

# ==================== 缓存 ====================
RECOMMEND_CACHE_TTL = 300            # 秒

# ==================== 语言 ====================
LANG_PREF_DEFAULT = 0.1              # 无偏好语言时的兜底分
COMMON_LANGS = {'inst', 'zh', 'zh-cn', 'zh-tw', 'ja', 'en', 'ko', 'de', 'ru',
                'fr', 'es', 'pt', 'it', 'vi', 'nl', 'sv', 'no', 'da',
                'fi', 'tr', 'pl', 'ar', 'th', 'id', 'hi'}

LANG_NAMES = {
    'zh': '中文', 'zh-cn': '中文', 'zh-tw': '中文',
    'ja': '日语', 'en': '英语', 'ko': '韩语',
    'de': '德语', 'ru': '俄语', 'fr': '法语', 'es': '西班牙语'
}

# ==================== 情绪 ====================
MOOD_LIST = ('sad', 'energetic', 'calm', 'upbeat', 'fresh', 'romantic', 'inspire')

MOOD_QUERIES = {
    'sad':       '悲伤抒情的歌曲，关于离别、失恋和回忆',
    'energetic': '激昂热血的歌曲，节奏强劲充满力量',
    'calm':      '舒缓放松的歌曲，安静温柔的氛围音乐',
    'upbeat':    '欢快动感的歌曲，让人想跟着跳舞',
    'fresh':     '清新自然的歌曲，民谣和轻音乐风格',
    'romantic':  '浪漫甜蜜的情歌，关于爱情的美好',
    'inspire':   '励志向上的歌曲，给人希望和勇气',
}

MOOD_LABELS = {
    'sad': '伤感', 'energetic': '激昂', 'calm': '舒缓',
    'upbeat': '动感', 'fresh': '清新', 'romantic': '浪漫', 'inspire': '励志',
}
