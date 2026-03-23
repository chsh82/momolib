# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


class RevenueRecord(db.Model):
    """수익 정산 내역"""
    __tablename__ = 'revenue_records'

    record_id = db.Column(db.String(36), primary_key=True)
    branch_id = db.Column(db.String(36), db.ForeignKey('branches.branch_id', ondelete='CASCADE'),
                          nullable=False, index=True)

    period_year = db.Column(db.Integer, nullable=False)   # 정산 연도
    period_month = db.Column(db.Integer, nullable=False)  # 정산 월

    gross_amount = db.Column(db.Integer, nullable=False, default=0)    # 총 수금액
    royalty_amount = db.Column(db.Integer, nullable=False, default=0)  # 본사 로열티
    monthly_fee = db.Column(db.Integer, nullable=False, default=0)     # 월 가맹비
    net_amount = db.Column(db.Integer, nullable=False, default=0)      # 지점 지급액

    # 상태: pending / confirmed / paid
    status = db.Column(db.String(20), nullable=False, default='pending')
    paid_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    branch = db.relationship('Branch')

    __table_args__ = (
        db.UniqueConstraint('branch_id', 'period_year', 'period_month', name='uq_revenue_period'),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.record_id:
            self.record_id = str(uuid.uuid4())

    @property
    def period_label(self):
        return f'{self.period_year}년 {self.period_month}월'

    @property
    def display_status(self):
        return {'pending': '정산 대기', 'confirmed': '확정', 'paid': '지급 완료'}.get(self.status, self.status)
