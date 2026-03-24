# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


class Branch(db.Model):
    __tablename__ = 'branches'

    branch_id = db.Column(db.String(36), primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)  # 예: BR001
    short_code = db.Column(db.String(4), nullable=True)  # 학생코드 접두어, 예: GN / BD
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(500), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(255), nullable=True)

    owner_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                         nullable=True)

    # 상태: active / suspended / closed
    status = db.Column(db.String(20), nullable=False, default='active')

    # 허용 기능 플래그
    feature_essay = db.Column(db.Boolean, default=True)    # 본사 첨삭 서비스
    feature_zoom = db.Column(db.Boolean, default=True)     # 온라인 수업
    feature_payment = db.Column(db.Boolean, default=True)  # 지점 결제 관리
    feature_cms = db.Column(db.Boolean, default=True)      # 본사 콘텐츠 수신

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = db.relationship('User', back_populates='branch',
                            foreign_keys='User.branch_id')
    owner = db.relationship('User', foreign_keys=[owner_id])
    contract = db.relationship('BranchContract', back_populates='branch',
                               uselist=False, cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.branch_id:
            self.branch_id = str(uuid.uuid4())

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def display_status(self):
        return {'active': '운영중', 'suspended': '정지', 'closed': '폐점'}.get(self.status, self.status)

    def __repr__(self):
        return f'<Branch {self.code} {self.name}>'


class BranchContract(db.Model):
    __tablename__ = 'branch_contracts'

    contract_id = db.Column(db.String(36), primary_key=True)
    branch_id = db.Column(db.String(36), db.ForeignKey('branches.branch_id', ondelete='CASCADE'),
                          nullable=False, unique=True)

    contract_start = db.Column(db.Date, nullable=False)
    contract_end = db.Column(db.Date, nullable=True)

    royalty_rate = db.Column(db.Numeric(5, 2), nullable=False, default=20.00)   # 본사 로열티 %
    revenue_share = db.Column(db.Numeric(5, 2), nullable=False, default=80.00)  # 지점 정산 %

    monthly_fee = db.Column(db.Integer, nullable=True)  # 월 고정 가맹비 (원)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    branch = db.relationship('Branch', back_populates='contract')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.contract_id:
            self.contract_id = str(uuid.uuid4())

    def __repr__(self):
        return f'<BranchContract {self.branch_id}>'
