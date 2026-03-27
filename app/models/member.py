# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


def generate_student_code(branch):
    """지점코드-연도-순번 형식으로 학생 코드 자동 생성 (예: GN-25-0001)"""
    from datetime import datetime
    from sqlalchemy import func

    short = (branch.short_code or branch.code[:4]).upper()
    year = datetime.now().strftime('%y')
    prefix = f'{short}-{year}-'

    max_code = db.session.query(func.max(StudentProfile.student_code)).filter(
        StudentProfile.branch_id == branch.branch_id,
        StudentProfile.student_code.like(f'{prefix}%')
    ).scalar()

    if max_code:
        try:
            last_num = int(max_code.split('-')[-1])
        except (ValueError, IndexError):
            last_num = 0
        return f'{prefix}{(last_num + 1):04d}'
    return f'{prefix}0001'


GRADE_CHOICES = [
    ('elementary_1', '초등 1학년'), ('elementary_2', '초등 2학년'),
    ('elementary_3', '초등 3학년'), ('elementary_4', '초등 4학년'),
    ('elementary_5', '초등 5학년'), ('elementary_6', '초등 6학년'),
    ('middle_1', '중학교 1학년'), ('middle_2', '중학교 2학년'),
    ('middle_3', '중학교 3학년'),
    ('high_1', '고등학교 1학년'), ('high_2', '고등학교 2학년'),
    ('high_3', '고등학교 3학년'),
]

GRADE_DISPLAY = dict(GRADE_CHOICES)


class StudentProfile(db.Model):
    """학생 추가 정보 (User 1:1)"""
    __tablename__ = 'student_profiles'

    profile_id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                        nullable=False, unique=True)
    branch_id = db.Column(db.String(36), db.ForeignKey('branches.branch_id', ondelete='CASCADE'),
                          nullable=False)

    student_code = db.Column(db.String(20), nullable=True)  # 지점 내 학생 코드
    grade = db.Column(db.String(20), nullable=True)         # elementary_1 ~ high_3
    school = db.Column(db.String(100), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)               # 강사용 메모

    # 담당 강사 배정
    assigned_teacher_id = db.Column(db.String(36),
        db.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True)

    enrolled_at = db.Column(db.Date, nullable=True)         # 등록일
    status = db.Column(db.String(20), default='active')     # active / inactive / graduated
    mileage = db.Column(db.Integer, nullable=False, default=0)  # 마일리지 잔액

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', foreign_keys='StudentProfile.user_id',
                           backref=db.backref('student_profile', uselist=False))
    branch = db.relationship('Branch', backref='student_profiles')
    assigned_teacher = db.relationship('User', foreign_keys=[assigned_teacher_id])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.profile_id:
            self.profile_id = str(uuid.uuid4())

    @property
    def grade_display(self):
        return GRADE_DISPLAY.get(self.grade, self.grade or '-')

    def __repr__(self):
        return f'<StudentProfile {self.user_id}>'


class ParentStudent(db.Model):
    """학부모-학생 연결"""
    __tablename__ = 'parent_students'

    link_id = db.Column(db.String(36), primary_key=True)
    branch_id = db.Column(db.String(36), db.ForeignKey('branches.branch_id', ondelete='CASCADE'),
                          nullable=False)
    parent_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                          nullable=False)
    student_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                           nullable=False)

    relation = db.Column(db.String(20), default='parent')  # parent / guardian / other
    is_active = db.Column(db.Boolean, default=True)

    linked_at = db.Column(db.DateTime, default=datetime.utcnow)
    linked_by = db.Column(db.String(36), nullable=True)    # 연결한 관리자 user_id

    __table_args__ = (
        db.UniqueConstraint('parent_id', 'student_id', name='uq_parent_student'),
    )

    # Relationships
    parent = db.relationship('User', foreign_keys=[parent_id],
                             backref=db.backref('children_links', lazy='dynamic'))
    student = db.relationship('User', foreign_keys=[student_id],
                              backref=db.backref('parent_links', lazy='dynamic'))
    branch = db.relationship('Branch')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.link_id:
            self.link_id = str(uuid.uuid4())

    def __repr__(self):
        return f'<ParentStudent {self.parent_id} → {self.student_id}>'
