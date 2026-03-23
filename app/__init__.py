# -*- coding: utf-8 -*-
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_compress import Compress
from config import config

login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
compress = Compress()


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # 확장 초기화
    from app.models import db
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    compress.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = '로그인이 필요합니다.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(user_id)

    # 블루프린트 등록
    from app.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.hq import hq_bp
    app.register_blueprint(hq_bp, url_prefix='/hq')

    from app.branch_portal import branch_bp
    app.register_blueprint(branch_bp, url_prefix='/branch')

    from app.cms import cms_bp
    app.register_blueprint(cms_bp, url_prefix='/cms')

    from app.notifications import notif_bp
    app.register_blueprint(notif_bp, url_prefix='/notifications')

    # 메인 라우트
    from flask import redirect, url_for
    from flask_login import current_user

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.is_hq:
                return redirect(url_for('hq.dashboard'))
            elif current_user.is_branch_owner or current_user.is_branch_staff:
                return redirect(url_for('branch.dashboard'))
        return redirect(url_for('auth.login'))

    # Jinja2 전역 필터
    from datetime import datetime

    @app.template_filter('format_number')
    def format_number(value):
        try:
            return f'{int(value):,}'
        except (ValueError, TypeError):
            return value

    @app.template_filter('kst')
    def kst_filter(value, fmt='%Y-%m-%d %H:%M'):
        if value is None:
            return ''
        from datetime import timezone, timedelta
        kst = timezone(timedelta(hours=9))
        if hasattr(value, 'replace'):
            value = value.replace(tzinfo=timezone.utc).astimezone(kst)
        return value.strftime(fmt)

    return app
