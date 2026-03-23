# -*- coding: utf-8 -*-
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # 기본
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = False
    TESTING = False

    # 데이터베이스
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://localhost/momolib')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # Redis
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # 세션
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # 이메일
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME')

    # 파일 업로드
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')

    # GCS
    GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'momolib-files')

    # MOMOAI 연동 (Phase 3)
    MOMOAI_API_URL = os.environ.get('MOMOAI_API_URL', '')
    MOMOAI_API_KEY = os.environ.get('MOMOAI_API_KEY', '')

    # 기본 로열티 비율 (%)
    DEFAULT_ROYALTY_RATE = 20


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'postgresql://localhost/momolib_dev'
    )


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
