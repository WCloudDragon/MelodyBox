import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'melodybox-secret-key')
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'melodybox.db')
    COVER_DIR = os.path.join(os.environ.get('TEMP', '/tmp'), 'melodybox-covers')
    MAX_PAGE_SIZE = 10000
    # AI 模型缓存目录（可通过环境变量 MELODYBOX_AI_MODEL_DIR 覆盖，UI 设置优先）
    AI_MODEL_CACHE_DIR = os.environ.get('MELODYBOX_AI_MODEL_DIR', '').strip() or None
