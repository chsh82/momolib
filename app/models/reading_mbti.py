# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


class ReadingMBTITest(db.Model):
    """독서MBTI 테스트 문항 설정"""
    __tablename__ = 'reading_mbti_tests'

    test_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, default='독서MBTI 테스트')
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship('ReadingMBTIQuestion', back_populates='test',
                                 order_by='ReadingMBTIQuestion.order_num',
                                 cascade='all, delete-orphan')
    results = db.relationship('ReadingMBTIResult', back_populates='test',
                               cascade='all, delete-orphan')


class ReadingMBTIQuestion(db.Model):
    """독서MBTI 문항"""
    __tablename__ = 'reading_mbti_questions'

    question_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_id = db.Column(db.Integer, db.ForeignKey('reading_mbti_tests.test_id',
                         ondelete='CASCADE'), nullable=False)

    # 문항 유형: absolute(절대평가 1~5점), comparison(비교평가)
    question_type = db.Column(db.String(20), nullable=False, default='absolute')
    # 영역: reading(독해력), thinking(사고력), writing(서술력)
    domain = db.Column(db.String(20), nullable=True)
    # 수준: beginner, intermediate, advanced
    level = db.Column(db.String(20), nullable=True)

    question_text = db.Column(db.Text, nullable=False)
    # comparison 문항의 두 번째 항목 텍스트
    question_text_b = db.Column(db.Text, nullable=True)
    order_num = db.Column(db.Integer, default=0)

    test = db.relationship('ReadingMBTITest', back_populates='questions')
    responses = db.relationship('ReadingMBTIResponse', back_populates='question',
                                 cascade='all, delete-orphan')


class ReadingMBTIType(db.Model):
    """독서MBTI 유형 정의 (27가지)"""
    __tablename__ = 'reading_mbti_types'

    type_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 예: 독해력-중급, 사고력-초급, 서술력-고급 → "intermediate_beginner_advanced"
    type_code = db.Column(db.String(50), unique=True, nullable=False)
    type_name = db.Column(db.String(100), nullable=False)
    reading_level = db.Column(db.String(20), nullable=False)   # beginner/intermediate/advanced
    thinking_level = db.Column(db.String(20), nullable=False)
    writing_level = db.Column(db.String(20), nullable=False)

    description = db.Column(db.Text, nullable=True)
    strengths = db.Column(db.Text, nullable=True)
    weaknesses = db.Column(db.Text, nullable=True)
    recommendation = db.Column(db.Text, nullable=True)
    emoji = db.Column(db.String(10), nullable=True)


class ReadingMBTIResponse(db.Model):
    """사용자 응답 저장"""
    __tablename__ = 'reading_mbti_responses'

    response_id = db.Column(db.String(36), primary_key=True,
                             default=lambda: str(uuid.uuid4()))
    result_id = db.Column(db.String(36), db.ForeignKey('reading_mbti_results.result_id',
                           ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('reading_mbti_questions.question_id',
                             ondelete='CASCADE'), nullable=False)

    score = db.Column(db.Integer, nullable=False)   # 1-5 (absolute) or 1/2 (comparison: A/B)

    result = db.relationship('ReadingMBTIResult', back_populates='responses')
    question = db.relationship('ReadingMBTIQuestion', back_populates='responses')


class ReadingMBTIResult(db.Model):
    """테스트 결과"""
    __tablename__ = 'reading_mbti_results'

    result_id = db.Column(db.String(36), primary_key=True,
                           default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id',
                         ondelete='CASCADE'), nullable=False, index=True)
    test_id = db.Column(db.Integer, db.ForeignKey('reading_mbti_tests.test_id',
                         ondelete='CASCADE'), nullable=False)

    # 영역별 원점수
    reading_score = db.Column(db.Float, nullable=True)
    thinking_score = db.Column(db.Float, nullable=True)
    writing_score = db.Column(db.Float, nullable=True)

    # 영역별 수준
    reading_level = db.Column(db.String(20), nullable=True)
    thinking_level = db.Column(db.String(20), nullable=True)
    writing_level = db.Column(db.String(20), nullable=True)

    type_code = db.Column(db.String(50), nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])
    test = db.relationship('ReadingMBTITest', back_populates='results')
    responses = db.relationship('ReadingMBTIResponse', back_populates='result',
                                 cascade='all, delete-orphan')

    @property
    def type_info(self):
        if self.type_code:
            return ReadingMBTIType.query.filter_by(type_code=self.type_code).first()
        return None

    @property
    def level_display(self):
        m = {'beginner': '초급', 'intermediate': '중급', 'advanced': '고급'}
        return {
            'reading': m.get(self.reading_level, '-'),
            'thinking': m.get(self.thinking_level, '-'),
            'writing': m.get(self.writing_level, '-'),
        }
