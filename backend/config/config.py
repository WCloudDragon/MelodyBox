import os


def _default_model_dir():
    """默认模型缓存目录：%APPDATA%/melodybox/models/"""
    return os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'melodybox', 'models')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'melodybox-secret-key')
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'melodybox.db')
    COVER_DIR = os.path.join(os.environ.get('TEMP', '/tmp'), 'melodybox-covers')
    MAX_PAGE_SIZE = 10000
    # AI 模型缓存目录（优先级：环境变量 > settings.json > 默认路径）
    AI_MODEL_CACHE_DIR = os.environ.get('MELODYBOX_AI_MODEL_DIR', '').strip() or None

    @staticmethod
    def resolve_model_dir():
        """获取模型目录绝对路径（确保存在）"""
        d = Config.AI_MODEL_CACHE_DIR or _default_model_dir()
        os.makedirs(d, exist_ok=True)
        return d
