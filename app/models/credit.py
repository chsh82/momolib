# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


class EssayCredit(db.Model):
    """학생 첨삭 이용권 잔고"""
    __tablename__ = 'essay_credits'

    credit_id = db.Column(db.String(36), primary_key=True,
                          default=lambda: str(uuid.uuid4()))
    branch_id = db.Column(db.String(36),
        db.ForeignKey('branches.branch_id', ondelete='CASCADE'),
        nullable=False, index=True)
    student_id = db.Column(db.String(36),
        db.ForeignKey('users.user_id', ondelete='CASCADE'),
        nullable=False, unique=True)

    total_credits = db.Column(db.Integer, nullable=False, default=0)  # 누적 충전
    used_credits  = db.Column(db.Integer, nullable=False, default=0)  # 누적 사용

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    # Relationships
    student = db.relationship('User', foreign_keys=[student_id])
    logs = db.relationship('EssayCreditLog', back_populates='credit',
                           cascade='all, delete-orphan',
                           order_by='EssayCreditLog.created_at.desc()')

    @property
    def remaining(self):
        return max(0, self.total_credits - self.used_credits)

    def add(self, amount, note='', added_by=None):
        self.total_credits += amount
        db.session.add(EssayCreditLog(
            credit_id=self.credit_id,
            student_id=self.student_id,
            action='add',
            amount=amount,
            note=note,
            created_by=added_by,
        ))

    def deduct(self, amount=1, note='첨삭 제출'):
        if self.remaining < amount:
            raise ValueError('이용권이 부족합니다.')
        self.used_credits += amount
        db.session.add(EssayCreditLog(
            credit_id=self.credit_id,
            student_id=self.student_id,
            action='deduct',
            amount=amount,
            note=note,
        ))

    def __repr__(self):
        return f'<EssayCredit {self.student_id} remaining={self.remaining}>'


class EssayCreditLog(db.Model):
    """이용권 충전/차감 이력"""
    __tablename__ = 'essay_credit_logs'

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    credit_id = db.Column(db.String(36),
        db.ForeignKey('essay_credits.credit_id', ondelete='CASCADE'),
        nullable=False, index=True)
    student_id = db.Column(db.String(36),
        db.ForeignKey('users.user_id', ondelete='CASCADE'),
        nullable=False)

    action = db.Column(db.String(10), nullable=False)   # 'add' | 'deduct'
    amount = db.Column(db.Integer, nullable=False)
    note   = db.Column(db.String(200), nullable=True)
    created_by = db.Column(db.String(36), nullable=True)  # 처리한 관리자 user_id
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    credit = db.relationship('EssayCredit', back_populates='logs')

    @property
    def action_label(self):
        return '충전' if self.action == 'add' else '차감'
