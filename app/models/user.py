# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.String(36), primary_key=True)
    branch_id = db.Column(db.String(36), db.ForeignKey('branches.branch_id', ondelete='SET NULL'),
                          nullable=True, index=True)  # null = 본사 계정

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)

    # 역할: super_admin / hq_manager / hq_essay_manager /
    #       branch_owner / branch_manager / teacher / parent / student
    role = db.Column(db.String(30), nullable=False, default='student')

    # 역할 레벨 (낮을수록 높은 권한)
    # 1=super_admin, 2=hq_manager, 3=hq_essay_manager,
    # 4=branch_owner, 5=branch_manager, 6=teacher, 7=parent, 8=student
    role_level = db.Column(db.Integer, nullable=False, default=8)

    is_active = db.Column(db.Boolean, default=False)   # 관리자 승인 후 활성화
    is_verified = db.Column(db.Boolean, default=False)  # 이메일 인증
    profile_image = db.Column(db.String(500), nullable=True)

    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    branch = db.relationship('Branch', back_populates='users', foreign_keys=[branch_id])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.user_id:
            self.user_id = str(uuid.uuid4())
        # role_level 자동 설정
        role_level_map = {
            'super_admin': 1, 'hq_manager': 2, 'hq_essay_manager': 3,
            'branch_owner': 4, 'branch_manager': 5,
            'teacher': 6, 'parent': 7, 'student': 8,
        }
        if self.role and not kwargs.get('role_level'):
            self.role_level = role_level_map.get(self.role, 8)

    def get_id(self):
        return self.user_id

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # 역할 확인 프로퍼티
    @property
    def is_super_admin(self):
        return self.role == 'super_admin'

    @property
    def is_hq(self):
        return self.role_level <= 3  # 본사 계정

    @property
    def is_branch_owner(self):
        return self.role == 'branch_owner'

    @property
    def is_branch_staff(self):
        return self.role_level in (4, 5, 6)  # 지점 운영

    @property
    def is_teacher(self):
        return self.role == 'teacher'

    @property
    def is_parent(self):
        return self.role == 'parent'

    @property
    def is_student(self):
        return self.role == 'student'

    @property
    def display_role(self):
        role_names = {
            'super_admin': '본사 최고관리자', 'hq_manager': '본사 매니저',
            'hq_essay_manager': '본사 첨삭 담당', 'branch_owner': '지점장',
            'branch_manager': '지점 매니저', 'teacher': '강사',
            'parent': '학부모', 'student': '학생',
        }
        return role_names.get(self.role, self.role)

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'
