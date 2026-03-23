# -*- coding: utf-8 -*-
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.cms import cms_bp
from app.models import db
from app.models.branch import Branch
from app.models.content import ContentItem, ContentPermission, ContentView
from app.utils.decorators import requires_role
from app.models.notification import Notification


@cms_bp.route('/')
@login_required
@requires_role('super_admin', 'hq_manager')
def index():
    """CMS 콘텐츠 목록"""
    items = ContentItem.query.order_by(ContentItem.created_at.desc()).all()
    return render_template('cms/index.html', items=items)


@cms_bp.route('/new', methods=['GET', 'POST'])
@login_required
@requires_role('super_admin', 'hq_manager')
def new_content():
    """콘텐츠 작성"""
    branches = Branch.query.filter_by(status='active').order_by(Branch.code).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content_type = request.form.get('content_type', 'notice')
        body = request.form.get('body', '').strip()
        is_global = request.form.get('is_global') == 'on'
        target_branches = request.form.getlist('target_branches')
        is_published = request.form.get('is_published') == 'on'

        if not title:
            flash('제목을 입력해주세요.', 'error')
            return render_template('cms/new_content.html', branches=branches)

        item = ContentItem(
            title=title,
            content_type=content_type,
            body=body,
            is_global=is_global,
            is_published=is_published,
            created_by=current_user.user_id
        )
        db.session.add(item)
        db.session.flush()

        # 특정 지점 권한 설정 (is_global이 아닐 때)
        if not is_global and target_branches:
            for branch_id in target_branches:
                perm = ContentPermission(
                    content_id=item.content_id,
                    branch_id=branch_id,
                    granted_by=current_user.user_id
                )
                db.session.add(perm)

        db.session.flush()

        # 발행 시 알림 전송
        if is_published:
            notif_link = url_for('branch.notice_detail', content_id=item.content_id)
            if is_global:
                Notification.send_to_all_branches(
                    title=f'[본사 공지] {title}',
                    notif_type='new_notice',
                    link_url=notif_link,
                    roles=['branch_owner', 'branch_manager', 'teacher'],
                )
            elif target_branches:
                for bid in target_branches:
                    Notification.send_to_branch(
                        branch_id=bid,
                        title=f'[본사 공지] {title}',
                        notif_type='new_notice',
                        link_url=notif_link,
                        roles=['branch_owner', 'branch_manager', 'teacher'],
                    )

        db.session.commit()
        flash(f'콘텐츠 "{title}"이 {"발행" if is_published else "저장"}되었습니다.', 'success')
        return redirect(url_for('cms.index'))

    return render_template('cms/new_content.html', branches=branches)


@cms_bp.route('/<content_id>/publish', methods=['POST'])
@login_required
@requires_role('super_admin', 'hq_manager')
def publish(content_id):
    """콘텐츠 발행/취소"""
    item = ContentItem.query.get_or_404(content_id)
    item.is_published = not item.is_published
    db.session.commit()
    status = '발행' if item.is_published else '발행 취소'
    return jsonify({'success': True, 'published': item.is_published, 'message': f'{status}되었습니다.'})


@cms_bp.route('/<content_id>/views')
@login_required
@requires_role('super_admin', 'hq_manager')
def view_stats(content_id):
    """콘텐츠 열람 현황"""
    item = ContentItem.query.get_or_404(content_id)
    views = ContentView.query.filter_by(content_id=content_id)\
        .order_by(ContentView.viewed_at.desc()).all()
    branches = Branch.query.filter_by(status='active').all()
    return render_template('cms/view_stats.html', item=item, views=views, branches=branches)
