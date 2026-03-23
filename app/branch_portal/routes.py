# -*- coding: utf-8 -*-
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.branch_portal import branch_bp
from app.models import db
from app.models.user import User
from app.models.branch import Branch
from app.models.content import ContentItem, ContentView
from app.utils.decorators import requires_role


@branch_bp.route('/')
@login_required
@requires_role('branch_owner', 'branch_manager', 'teacher')
def dashboard():
    """지점장 대시보드"""
    branch = Branch.query.get(current_user.branch_id)
    if not branch:
        flash('소속 지점 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('auth.logout'))

    # 지점 통계
    total_users = User.query.filter_by(branch_id=branch.branch_id).count()
    teachers = User.query.filter_by(branch_id=branch.branch_id, role='teacher').count()
    students = User.query.filter_by(branch_id=branch.branch_id, role='student').count()

    # 읽지 않은 본사 공지
    from sqlalchemy import or_
    unread_notices = ContentItem.query.filter(
        ContentItem.is_published == True,
        ContentItem.content_type == 'notice',
        or_(ContentItem.is_global == True,
            ContentItem.permissions.any(branch_id=branch.branch_id))
    ).filter(
        ~ContentItem.views.any(user_id=current_user.user_id)
    ).count()

    return render_template('branch/dashboard.html',
                           branch=branch,
                           total_users=total_users,
                           teachers=teachers,
                           students=students,
                           unread_notices=unread_notices)


@branch_bp.route('/notices')
@login_required
@requires_role('branch_owner', 'branch_manager', 'teacher')
def notices():
    """본사 공지 수신함"""
    from sqlalchemy import or_
    branch_id = current_user.branch_id

    items = ContentItem.query.filter(
        ContentItem.is_published == True,
        or_(ContentItem.is_global == True,
            ContentItem.permissions.any(branch_id=branch_id))
    ).order_by(ContentItem.created_at.desc()).all()

    # 읽음 여부
    read_ids = {v.content_id for v in ContentView.query.filter_by(
        user_id=current_user.user_id).all()}

    return render_template('branch/notices.html', items=items, read_ids=read_ids)


@branch_bp.route('/notices/<content_id>')
@login_required
@requires_role('branch_owner', 'branch_manager', 'teacher')
def notice_detail(content_id):
    """공지 상세 + 읽음 처리"""
    item = ContentItem.query.get_or_404(content_id)

    # 읽음 기록
    existing = ContentView.query.filter_by(
        content_id=content_id, user_id=current_user.user_id).first()
    if not existing:
        view = ContentView(content_id=content_id,
                           user_id=current_user.user_id,
                           branch_id=current_user.branch_id)
        db.session.add(view)
        db.session.commit()

    return render_template('branch/notice_detail.html', item=item)
