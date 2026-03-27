# -*- coding: utf-8 -*-
import json
from flask import current_app
from pywebpush import webpush, WebPushException
from app.models import db
from app.models.push_subscription import PushSubscription


def send_push(user_id, title, body, url='/'):
    """특정 사용자의 모든 기기에 푸시 알림 전송"""
    subs = PushSubscription.query.filter_by(user_id=user_id).all()
    if not subs:
        return

    private_key = current_app.config.get('VAPID_PRIVATE_KEY', '')
    claims_sub = current_app.config.get('VAPID_CLAIMS_SUB', 'mailto:admin@momolib.com')

    if not private_key:
        return

    data = json.dumps({'title': title, 'body': body, 'url': url})
    failed = []

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth}
                },
                data=data,
                vapid_private_key=private_key,
                vapid_claims={'sub': claims_sub},
            )
        except WebPushException as e:
            # 만료된 구독 제거
            if e.response and e.response.status_code in (404, 410):
                failed.append(sub)

    for sub in failed:
        db.session.delete(sub)
    if failed:
        db.session.commit()


def send_push_to_branch(branch_id, title, body, url='/', roles=None):
    """지점 내 사용자들에게 푸시 알림 전송"""
    from app.models.user import User
    query = User.query.filter_by(branch_id=branch_id, is_active=True)
    if roles:
        query = query.filter(User.role.in_(roles))
    for user in query.all():
        send_push(user.user_id, title, body, url)
