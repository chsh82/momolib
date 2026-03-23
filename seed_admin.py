# -*- coding: utf-8 -*-
"""초기 super_admin 계정 생성 스크립트
Usage: python seed_admin.py
"""
import os
from app import create_app
from app.models import db
from app.models.user import User

app = create_app(os.environ.get('FLASK_ENV', 'development'))

with app.app_context():
    existing = User.query.filter_by(email='admin@momolib.com').first()
    if existing:
        print(f'이미 존재합니다: {existing.email}')
    else:
        admin = User(
            email='admin@momolib.com',
            name='시스템 관리자',
            role='super_admin',
            branch_id=None,
            is_active=True,
            is_verified=True,
        )
        admin.set_password('momolib2026!')
        db.session.add(admin)
        db.session.commit()
        print(f'super_admin 계정 생성 완료: admin@momolib.com / momolib2026!')
