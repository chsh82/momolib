# -*- coding: utf-8 -*-
"""학생용 어휘 퀴즈 세션·응답 - vocab_quiz_pilot_items(문항 원본, 관리자
파일럿과 공유)를 읽기 전용으로 참조하지만, 실제 학생 응시 기록은 관리자
파일럿 감사 기록(vocab_quiz_pilot_sessions/_attempts)과 완전히 분리된
별도 테이블에 남긴다 - 관리자 QA 이력에 실제 학생 데이터가 섞이지 않게
하기 위함이다.

이 세션이 어떤 문항을 뽑을 수 있는지는 app/vocab_quiz/eligibility.py의
단일 게이트만 거친다(이 모델 자체는 게이트 로직을 갖지 않는다)."""
from __future__ import annotations

import uuid
from datetime import datetime

from app.models import db


class VocabQuizStudentSession(db.Model):
    __tablename__ = 'vocab_quiz_student_sessions'
    __table_args__ = (
        db.CheckConstraint("status IN ('in_progress', 'completed')", name='ck_vqss_status'),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False, index=True)
    item_count = db.Column(db.Integer, nullable=False)
    correct_count = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='in_progress')
    item_order_json = db.Column(db.Text, nullable=False)  # 세션 시작 시점에 뽑은 item_id 순서 고정 스냅샷
    gate_version = db.Column(db.String(40), nullable=False)  # 이 세션이 통과한 게이트 로직 버전(감사용)
    vocab_level = db.Column(db.Integer, nullable=True, index=True)  # 학생이 명시적으로 고른 레벨(4/5/6) - 레벨 선택 도입 이전 세션은 NULL
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User')
    attempts = db.relationship('VocabQuizStudentAttempt', backref='session', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<VocabQuizStudentSession {self.id} user={self.user_id} {self.status}>'


class VocabQuizStudentAttempt(db.Model):
    __tablename__ = 'vocab_quiz_student_attempts'
    __table_args__ = (
        db.UniqueConstraint('session_id', 'item_id', name='uq_vqsa_session_item'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey('vocab_quiz_student_sessions.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    item_id = db.Column(db.String(120), nullable=False)
    order_index = db.Column(db.Integer, nullable=False)
    selected_option = db.Column(db.Integer, nullable=True)
    correct_option = db.Column(db.Integer, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    answered_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<VocabQuizStudentAttempt session={self.session_id} item={self.item_id}>'
