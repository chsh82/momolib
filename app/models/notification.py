# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


class Notification(db.Model):
    __tablename__ = 'notifications'

    notif_id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                        nullable=False, index=True)

    # 유형: system / revenue_confirmed / revenue_paid / new_notice / branch_joined
    notif_type = db.Column(db.String(40), nullable=False, default='system')
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=True)
    link_url = db.Column(db.String(500), nullable=True)

    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.notif_id:
            self.notif_id = str(uuid.uuid4())

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()

    @classmethod
    def create(cls, user_id, title, notif_type='system', message=None, link_url=None):
        n = cls(user_id=user_id, title=title, notif_type=notif_type,
                message=message, link_url=link_url)
        db.session.add(n)
        return n

    @classmethod
    def send_to_branch(cls, branch_id, title, notif_type='new_notice',
                       message=None, link_url=None, roles=None):
        """지점 내 특정 역할 전체에게 발송"""
        from app.models.user import User
        query = User.query.filter_by(branch_id=branch_id, is_active=True)
        if roles:
            query = query.filter(User.role.in_(roles))
        for user in query.all():
            cls.create(user.user_id, title, notif_type, message, link_url)

    @classmethod
    def send_to_all_branches(cls, title, notif_type='new_notice',
                             message=None, link_url=None, roles=None):
        """전체 지점 특정 역할에게 발송"""
        from app.models.user import User
        query = User.query.filter(User.branch_id.isnot(None), User.is_active == True)
        if roles:
            query = query.filter(User.role.in_(roles))
        for user in query.all():
            cls.create(user.user_id, title, notif_type, message, link_url)

    def __repr__(self):
        return f'<Notification {self.user_id} {self.title[:20]}>'
