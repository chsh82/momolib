# -*- coding: utf-8 -*-
from flask import jsonify, request, render_template, current_app
from flask_login import login_required, current_user
from app.notifications import notif_bp
from app.models import db
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription


@notif_bp.route('/api/unread-count')
@login_required
def unread_count():
    count = Notification.query.filter_by(
        user_id=current_user.user_id, is_read=False).count()
    return jsonify({'count': count})


@notif_bp.route('/api/recent')
@login_required
def recent():
    items = Notification.query.filter_by(user_id=current_user.user_id)\
        .order_by(Notification.created_at.desc()).limit(10).all()
    return jsonify([{
        'id': n.notif_id,
        'title': n.title,
        'message': n.message,
        'link_url': n.link_url,
        'is_read': n.is_read,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
    } for n in items])


@notif_bp.route('/api/read/<notif_id>', methods=['POST'])
@login_required
def mark_read(notif_id):
    n = Notification.query.filter_by(
        notif_id=notif_id, user_id=current_user.user_id).first_or_404()
    n.mark_read()
    db.session.commit()
    return jsonify({'success': True})


@notif_bp.route('/api/read-all', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(
        user_id=current_user.user_id, is_read=False).update(
        {'is_read': True})
    db.session.commit()
    return jsonify({'success': True})


@notif_bp.route('/api/push/vapid-key')
@login_required
def vapid_public_key():
    key = current_app.config.get('VAPID_PUBLIC_KEY', '')
    return jsonify({'publicKey': key})


@notif_bp.route('/api/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    data = request.get_json()
    endpoint = data.get('endpoint')
    p256dh = data.get('keys', {}).get('p256dh')
    auth = data.get('keys', {}).get('auth')

    if not all([endpoint, p256dh, auth]):
        return jsonify({'error': 'invalid'}), 400

    existing = PushSubscription.query.filter_by(
        user_id=current_user.user_id, endpoint=endpoint).first()
    if not existing:
        sub = PushSubscription(
            user_id=current_user.user_id,
            endpoint=endpoint, p256dh=p256dh, auth=auth)
        db.session.add(sub)
        db.session.commit()

    return jsonify({'success': True})


@notif_bp.route('/api/push/unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    data = request.get_json()
    endpoint = data.get('endpoint')
    PushSubscription.query.filter_by(
        user_id=current_user.user_id, endpoint=endpoint).delete()
    db.session.commit()
    return jsonify({'success': True})


@notif_bp.route('/')
@login_required
def index():
    """전체 알림 목록 페이지"""
    page = request.args.get('page', 1, type=int)
    pagination = Notification.query.filter_by(user_id=current_user.user_id)\
        .order_by(Notification.created_at.desc()).paginate(page=page, per_page=20)

    # 모두 읽음 처리
    Notification.query.filter_by(
        user_id=current_user.user_id, is_read=False).update({'is_read': True})
    db.session.commit()

    return render_template('notifications/index.html', pagination=pagination)
