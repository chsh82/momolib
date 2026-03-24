# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


class BranchPost(db.Model):
    """지점 공지사항 - 지점장/매니저가 작성, 강사/학생/학부모가 수신"""
    __tablename__ = 'branch_posts'

    post_id = db.Column(db.String(36), primary_key=True,
                        default=lambda: str(uuid.uuid4()))
    branch_id = db.Column(db.String(36), db.ForeignKey('branches.branch_id',
                          ondelete='CASCADE'), nullable=False, index=True)
    author_id = db.Column(db.String(36), db.ForeignKey('users.user_id',
                          ondelete='SET NULL'), nullable=True)

    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # 수신 대상: 쉼표 구분 'teacher,student,parent' 또는 'all'
    target_roles = db.Column(db.String(50), nullable=False, default='all')

    is_published = db.Column(db.Boolean, default=True)
    is_pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    # Relationships
    author = db.relationship('User', foreign_keys=[author_id])
    reads = db.relationship('BranchPostRead', back_populates='post',
                            cascade='all, delete-orphan')

    @property
    def target_label(self):
        if self.target_roles == 'all':
            return '전체'
        labels = {'teacher': '강사', 'student': '학생', 'parent': '학부모'}
        return ', '.join(labels.get(r, r) for r in self.target_roles.split(','))

    def is_visible_to(self, role):
        if self.target_roles == 'all':
            return True
        return role in self.target_roles.split(',')

    def __repr__(self):
        return f'<BranchPost {self.title}>'


class BranchPostRead(db.Model):
    """지점 공지 읽음 기록"""
    __tablename__ = 'branch_post_reads'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.String(36), db.ForeignKey('branch_posts.post_id',
                        ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id',
                        ondelete='CASCADE'), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship('BranchPost', back_populates='reads')

    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='uq_branch_post_read'),
    )
