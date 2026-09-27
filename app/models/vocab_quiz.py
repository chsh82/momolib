# -*- coding: utf-8 -*-
"""aprolabs 연구 사이트(schema_reading L4~L6 어휘 퀴즈) 1차 이식 - 관리자
전용 미리보기 + 파일럿 응시까지만. 기존 app/models/content_bank.py
(BankQuestion)·app/models/library.py(QuizQuestion)·app/models/lms.py의
학생용 퀴즈 파이프라인과 완전히 분리된 별도 테이블이다 - 어디에도 FK를
걸지 않고, 어떤 CMS/LMS 라우트도 이 테이블을 참조하지 않는다(연결하지
말라는 지시).

aprolabs `app/vocabulary_quiz/models.py`의 컬럼을 그대로 보존한다(추측으로
새로 설계하지 않음) - content_id/item_id, source_version, level_status,
student_exposure/public_ready, 문항 payload(public_payload_json vs
answer_payload_json 분리)가 원본과 동일한 이름·의미로 존재해야 이식 자체가
검증 가능하다.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from app.models import db


class VocabQuizContent(db.Model):
    __tablename__ = 'vocab_quiz_contents'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    content_id = db.Column(db.String(120), nullable=False, unique=True, index=True)
    lemma = db.Column(db.String(200), nullable=False, index=True)
    pos = db.Column(db.String(30), nullable=True)
    canonical_definition = db.Column(db.Text, nullable=True)
    student_definition = db.Column(db.Text, nullable=True)
    example_sentence = db.Column(db.Text, nullable=True)
    example_target_form = db.Column(db.String(300), nullable=True)
    batch_id = db.Column(db.String(120), nullable=True)
    source_version = db.Column(db.String(120), nullable=False, index=True)
    student_exposure = db.Column(db.Boolean, nullable=False, default=False)
    public_ready = db.Column(db.Boolean, nullable=False, default=False)
    hold_reason = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    content_hash = db.Column(db.String(64), nullable=False)  # 자연키 충돌 감지용(importer)
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)

    levels = db.relationship('VocabQuizContentLevel', backref='content', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<VocabQuizContent {self.content_id} {self.lemma}>'


class VocabQuizContentLevel(db.Model):
    __tablename__ = 'vocab_quiz_content_levels'
    __table_args__ = (
        db.UniqueConstraint('content_id', 'level_version', name='uq_vqcl_content_version'),
        db.CheckConstraint("level_status IN ('PROVISIONAL_AUTO', 'REVIEW_BOUNDARY')", name='ck_vqcl_level_status'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    content_id = db.Column(db.String(120), db.ForeignKey('vocab_quiz_contents.content_id', ondelete='CASCADE'),
                            nullable=False, index=True)
    vocab_level = db.Column(db.Integer, nullable=False)
    target_grade_band = db.Column(db.String(50), nullable=True)
    level_status = db.Column(db.String(30), nullable=False)
    boundary_flag = db.Column(db.Boolean, nullable=False, default=False)
    level_source = db.Column(db.String(60), nullable=True)
    level_version = db.Column(db.String(60), nullable=False, index=True)
    level_reason_json = db.Column(db.Text, nullable=True)
    content_hash = db.Column(db.String(64), nullable=False)

    def __repr__(self):
        return f'<VocabQuizContentLevel {self.content_id} L{self.vocab_level} {self.level_status}>'


class VocabQuizPilotItem(db.Model):
    """L4·L5(pilot_key='l4l5')/L6(pilot_key='l6') 파일럿 문항. aprolabs
    vocabulary_multiformat_items 중 파일럿 source_version 40+40건만 이식한다.

    answer_payload_json/correct_option은 채점 전용 - 라우트가 이 두 컬럼을
    세션 진행 중(GET) 응답에 절대 포함하지 않는다(app/vocab_quiz/routes.py
    참고, 제출(POST) 채점 이후에만 그 문항의 결과를 돌려준다)."""
    __tablename__ = 'vocab_quiz_pilot_items'
    __table_args__ = (
        db.CheckConstraint("pilot_key IN ('l4l5', 'l6')", name='ck_vqpi_pilot_key'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    item_id = db.Column(db.String(120), nullable=False, unique=True, index=True)
    pilot_key = db.Column(db.String(10), nullable=False, index=True)
    item_type = db.Column(db.String(40), nullable=False)
    source_content_id = db.Column(db.String(120), nullable=True, index=True)
    source_content_ids_json = db.Column(db.Text, nullable=True)
    lemma = db.Column(db.String(200), nullable=True)
    pos = db.Column(db.String(30), nullable=True)
    prompt = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, nullable=True)
    correct_option = db.Column(db.Integer, nullable=True)
    public_payload_json = db.Column(db.Text, nullable=True)
    answer_payload_json = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, nullable=True)
    source_version = db.Column(db.String(120), nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    item_hash = db.Column(db.String(64), nullable=False)
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<VocabQuizPilotItem {self.item_id} {self.pilot_key}>'


class VocabQuizPilotSession(db.Model):
    __tablename__ = 'vocab_quiz_pilot_sessions'
    __table_args__ = (
        db.CheckConstraint("pilot_key IN ('l4l5', 'l6')", name='ck_vqps_pilot_key'),
        db.CheckConstraint("status IN ('in_progress', 'completed')", name='ck_vqps_status'),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pilot_key = db.Column(db.String(10), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False, index=True)
    question_count = db.Column(db.Integer, nullable=False)
    correct_count = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='in_progress')
    item_order_json = db.Column(db.Text, nullable=False)  # 세션 시작 시점에 뽑은 item_id 순서 고정 스냅샷
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User')
    attempts = db.relationship('VocabQuizPilotAttempt', backref='session', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<VocabQuizPilotSession {self.id} {self.pilot_key} {self.status}>'


class VocabQuizPilotAttempt(db.Model):
    __tablename__ = 'vocab_quiz_pilot_attempts'
    __table_args__ = (
        db.UniqueConstraint('session_id', 'item_id', name='uq_vqpa_session_item'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey('vocab_quiz_pilot_sessions.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    item_id = db.Column(db.String(120), nullable=False)
    order_index = db.Column(db.Integer, nullable=False)
    selected_option = db.Column(db.Integer, nullable=True)
    correct_option = db.Column(db.Integer, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    answered_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<VocabQuizPilotAttempt session={self.session_id} item={self.item_id}>'
