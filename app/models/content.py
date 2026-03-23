# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


class ContentItem(db.Model):
    """본사 CMS 콘텐츠"""
    __tablename__ = 'content_items'

    content_id = db.Column(db.String(36), primary_key=True)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                           nullable=True)

    # 유형: notice / material / template / video / announcement
    content_type = db.Column(db.String(30), nullable=False, default='notice')
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)

    is_published = db.Column(db.Boolean, default=False)
    is_global = db.Column(db.Boolean, default=False)  # True면 모든 지점 공개

    publish_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by])
    permissions = db.relationship('ContentPermission', back_populates='content',
                                  cascade='all, delete-orphan')
    views = db.relationship('ContentView', back_populates='content',
                            cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.content_id:
            self.content_id = str(uuid.uuid4())

    @property
    def display_type(self):
        return {
            'notice': '공지', 'material': '교재', 'template': '템플릿',
            'video': '영상', 'announcement': '안내'
        }.get(self.content_type, self.content_type)

    def __repr__(self):
        return f'<ContentItem {self.title}>'


class ContentPermission(db.Model):
    """콘텐츠 지점별 접근 권한"""
    __tablename__ = 'content_permissions'

    permission_id = db.Column(db.String(36), primary_key=True)
    content_id = db.Column(db.String(36), db.ForeignKey('content_items.content_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    branch_id = db.Column(db.String(36), db.ForeignKey('branches.branch_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    granted_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                           nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    content = db.relationship('ContentItem', back_populates='permissions')
    branch = db.relationship('Branch')

    __table_args__ = (
        db.UniqueConstraint('content_id', 'branch_id', name='uq_content_branch'),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.permission_id:
            self.permission_id = str(uuid.uuid4())


class ContentView(db.Model):
    """콘텐츠 열람 기록"""
    __tablename__ = 'content_views'

    view_id = db.Column(db.String(36), primary_key=True)
    content_id = db.Column(db.String(36), db.ForeignKey('content_items.content_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                        nullable=False)
    branch_id = db.Column(db.String(36), db.ForeignKey('branches.branch_id', ondelete='SET NULL'),
                          nullable=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)

    content = db.relationship('ContentItem', back_populates='views')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.view_id:
            self.view_id = str(uuid.uuid4())
