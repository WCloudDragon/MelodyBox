import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'melodybox-secret-key')
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'melodybox.db')
    COVER_DIR = os.path.join(os.environ.get('TEMP', '/tmp'), 'melodybox-covers')
    MAX_PAGE_SIZE = 10000
