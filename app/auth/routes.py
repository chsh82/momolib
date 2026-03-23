# -*- coding: utf-8 -*-
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.models import db
from app.models.user import User


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error')
            return render_template('auth/login.html')

        if not user.is_active:
            flash('계정이 아직 승인되지 않았습니다. 관리자에게 문의하세요.', 'warning')
            return render_template('auth/login.html')

        from datetime import datetime
        user.last_login_at = datetime.utcnow()
        db.session.commit()

        login_user(user, remember=bool(remember))
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('auth.login'))
