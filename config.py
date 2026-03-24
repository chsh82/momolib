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

    # AI API 키
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')    # Gemini + Books API

    # 네이버 도서 API
    NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID', '')
    NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET', '')

    # SMS (coolsms)
    SMS_API_KEY = os.environ.get('SMS_API_KEY', '')
    SMS_USER_ID = os.environ.get('SMS_USER_ID', '')
    SMS_SENDER = os.environ.get('SMS_SENDER', '')

    # 카카오
    KAKAO_API_KEY = os.environ.get('KAKAO_API_KEY', '')
    KAKAO_USER_ID = os.environ.get('KAKAO_USER_ID', '')
    KAKAO_SENDER_KEY = os.environ.get('KAKAO_SENDER_KEY', '')

    # Toss 결제
    TOSS_CLIENT_KEY = os.environ.get('TOSS_CLIENT_KEY', '')
    TOSS_SECRET_KEY = os.environ.get('TOSS_SECRET_KEY', '')

    # PWA 푸시 알림 (VAPID)
    VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
    VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
    VAPID_CLAIMS_SUB = os.environ.get('VAPID_CLAIMS_SUB', '')

    # 기본 로열티 비율 (%)
    DEFAULT_ROYALTY_RATE = 20


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'sqlite:///momolib_dev.db'
    )


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
