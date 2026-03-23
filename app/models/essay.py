# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


class Essay(db.Model):
    __tablename__ = 'essays'

    essay_id = db.Column(db.String(36), primary_key=True)
    branch_id = db.Column(db.String(36), db.ForeignKey('branches.branch_id', ondelete='CASCADE'),
                          nullable=False, index=True)

    student_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                           nullable=False)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                           nullable=True)  # null = 본사 첨삭

    title = db.Column(db.String(300), nullable=False)
    original_text = db.Column(db.Text, nullable=False)
    grade = db.Column(db.String(20), nullable=True)

    # 상태: draft / processing / reviewing / completed / failed
    status = db.Column(db.String(20), nullable=False, default='draft', index=True)

    # 첨삭 모델: standard / elementary
    correction_model = db.Column(db.String(20), nullable=False, default='standard')

    # 강사 사전 가이드 (프롬프트에 포함)
    teacher_guide = db.Column(db.Text, nullable=True)

    current_version = db.Column(db.Integer, default=0)
    is_finalized = db.Column(db.Boolean, default=False)
    finalized_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    branch = db.relationship('Branch', backref='essays')
    student = db.relationship('User', foreign_keys=[student_id],
                              backref=db.backref('student_essays', lazy='dynamic'))
    teacher = db.relationship('User', foreign_keys=[teacher_id],
                              backref=db.backref('teacher_essays', lazy='dynamic'))
    versions = db.relationship('EssayVersion', back_populates='essay',
                               order_by='EssayVersion.version_number',
                               cascade='all, delete-orphan')
    result = db.relationship('EssayResult', back_populates='essay',
                             uselist=False, cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.essay_id:
            self.essay_id = str(uuid.uuid4())

    @property
    def latest_version(self):
        if not self.versions:
            return None
        return self.versions[-1]

    @property
    def status_display(self):
        return {
            'draft': '제출됨',
            'processing': '처리 중',
            'reviewing': '검토 중',
            'completed': '첨삭 완료',
            'failed': '처리 실패',
        }.get(self.status, self.status)

    @property
    def status_color(self):
        return {
            'draft': 'yellow',
            'processing': 'blue',
            'reviewing': 'purple',
            'completed': 'green',
            'failed': 'red',
        }.get(self.status, 'gray')

    def __repr__(self):
        return f'<Essay {self.essay_id[:8]} {self.title[:20]}>'


class EssayVersion(db.Model):
    __tablename__ = 'essay_versions'

    version_id = db.Column(db.String(36), primary_key=True)
    essay_id = db.Column(db.String(36), db.ForeignKey('essays.essay_id', ondelete='CASCADE'),
                         nullable=False)
    version_number = db.Column(db.Integer, nullable=False, default=1)
    html_content = db.Column(db.Text, nullable=True)   # 직접 저장 (파일 없이)
    revision_note = db.Column(db.Text, nullable=True)  # 수정 요청 내용
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    essay = db.relationship('Essay', back_populates='versions')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.version_id:
            self.version_id = str(uuid.uuid4())

    def __repr__(self):
        return f'<EssayVersion {self.essay_id[:8]} v{self.version_number}>'


class EssayResult(db.Model):
    __tablename__ = 'essay_results'

    result_id = db.Column(db.String(36), primary_key=True)
    essay_id = db.Column(db.String(36), db.ForeignKey('essays.essay_id', ondelete='CASCADE'),
                         nullable=False, unique=True)
    version_id = db.Column(db.String(36), db.ForeignKey('essay_versions.version_id'),
                           nullable=True)

    total_score = db.Column(db.Numeric(4, 1), nullable=True)
    final_grade = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    essay = db.relationship('Essay', back_populates='result')
    version = db.relationship('EssayVersion')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.result_id:
            self.result_id = str(uuid.uuid4())

    def __repr__(self):
        return f'<EssayResult {self.essay_id[:8]} {self.total_score}>'
