# -*- coding: utf-8 -*-
import uuid
import os
from datetime import datetime
from app.models import db


# ─── 어휘/독서/서술형 문제은행 ───────────────────────────

# 어휘 퀴즈 대/중/소 분류 체계
VOCAB_CATEGORIES = {
    '배경지식·스키마 어휘': {
        '문학': ['동화·아동문학', '소설', '시·시조', '수필·기행문'],
        '비문학': ['사회·경제', '과학·기술', '역사·문화', '예술·체육', '철학·윤리'],
        '어법·표현': ['사자성어·속담', '관용어', '한자어', '외래어'],
    },
    '학습 도구어': {
        '사고·인지 동사': ['분석', '비교·대조', '추론', '평가', '종합', '적용'],
        '텍스트 구조어': ['원인·결과', '과정·단계', '특징·차이', '분류·유형', '문제·해결'],
        '논증·담화어': ['주장·근거', '반론·반박', '결론·요약', '전제·가정'],
        '접속·연결어': ['인과', '역접', '나열·예시', '강조'],
        '메타 개념어': ['관점·입장', '맥락·배경', '해석·의미', '가치·판단'],
    },
}

# 독서 퀴즈 대/중/소 분류 체계
READING_CATEGORIES = {
    '문학': {
        '소설·동화': ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고등'],
        '시·동시':   ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고등'],
        '수필·일기': ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고등'],
        '희곡·시나리오': ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고등'],
    },
    '비문학': {
        '설명문·정보글': ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고등'],
        '논설문·주장글': ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고등'],
        '전기·인물이야기': ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고등'],
        '사회·역사':    ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고등'],
        '과학·기술':    ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고등'],
        '예술·문화':    ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고등'],
    },
}

# 독해 유형 (5가지)
READING_TYPE_CHOICES = [
    ('사실적', '사실적 독해'),
    ('분석적', '분석적 독해'),
    ('추론적', '추론적 독해'),
    ('적용적', '적용적 독해'),
    ('비판적', '비판적 독해'),
]

BANK_QUESTION_TYPES = [
    ('vocab_quiz',   '어휘 퀴즈'),
    ('reading_quiz', '독서 퀴즈'),
    ('essay',        '서술형 문항'),
]

DIFFICULTY_CHOICES = [
    ('easy',   '쉬움'),
    ('medium', '보통'),
    ('hard',   '어려움'),
]


class BankQuestion(db.Model):
    """문제은행 - 어휘퀴즈 / 독서퀴즈 / 서술형 통합 모델"""
    __tablename__ = 'bank_questions'

    question_id = db.Column(db.String(36), primary_key=True,
                            default=lambda: str(uuid.uuid4()))
    type = db.Column(db.String(20), nullable=False)   # vocab_quiz / reading_quiz / essay

    # 선택적 연결
    book_id = db.Column(db.String(36), db.ForeignKey('books.book_id',
                         ondelete='SET NULL'), nullable=True, index=True)
    week_num = db.Column(db.Integer, nullable=True)    # 주차 커리큘럼

    title = db.Column(db.String(200), nullable=False)  # 문항 제목/분류
    difficulty = db.Column(db.String(10), nullable=True, default='medium')
    tags = db.Column(db.String(300), nullable=True)    # 쉼표 구분

    # 대/중/소 분류 (어휘·독서 퀴즈 공통)
    cat_large  = db.Column(db.String(30), nullable=True)
    cat_medium = db.Column(db.String(30), nullable=True)
    cat_small  = db.Column(db.String(30), nullable=True)

    # 독서 퀴즈 전용: 독해 유형 (사실적/분석적/추론적/적용적/비판적)
    reading_type = db.Column(db.String(20), nullable=True)

    # 타입별 JSON 데이터
    # vocab_quiz:   {word, definition, choices:[str×4], correct_idx:0~3}
    # reading_quiz: {passage, question, choices:[str×4], correct_idx:0~3, explanation}
    # essay:        {prompt, rubric, max_score, sample_answer}
    data = db.Column(db.JSON, nullable=False, default=dict)

    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id',
                            ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    book = db.relationship('Book', foreign_keys=[book_id])
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def type_display(self):
        return dict(BANK_QUESTION_TYPES).get(self.type, self.type)

    @property
    def difficulty_display(self):
        return dict(DIFFICULTY_CHOICES).get(self.difficulty, '-')

    @property
    def tag_list(self):
        return [t.strip() for t in (self.tags or '').split(',') if t.strip()]


# ─── 독서 강의 영상 ──────────────────────────────────────

class LectureVideo(db.Model):
    """독서 강의 영상"""
    __tablename__ = 'lecture_videos'

    video_id = db.Column(db.String(36), primary_key=True,
                         default=lambda: str(uuid.uuid4()))

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(500), nullable=False)
    thumbnail_url = db.Column(db.String(500), nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)

    # 선택적 연결
    book_id = db.Column(db.String(36), db.ForeignKey('books.book_id',
                         ondelete='SET NULL'), nullable=True, index=True)
    week_num = db.Column(db.Integer, nullable=True)
    tags = db.Column(db.String(300), nullable=True)

    # 대/중/소 분류 (독서 퀴즈와 동일한 체계)
    cat_large  = db.Column(db.String(30), nullable=True)
    cat_medium = db.Column(db.String(30), nullable=True)
    cat_small  = db.Column(db.String(30), nullable=True)

    is_published = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id',
                            ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    book = db.relationship('Book', foreign_keys=[book_id])
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def duration_display(self):
        if not self.duration_seconds:
            return '-'
        m, s = divmod(self.duration_seconds, 60)
        return f'{m}:{s:02d}'

    @property
    def is_youtube(self):
        return 'youtube.com' in (self.url or '') or 'youtu.be' in (self.url or '')

    @property
    def youtube_id(self):
        url = self.url or ''
        if 'v=' in url:
            return url.split('v=')[-1].split('&')[0]
        if 'youtu.be/' in url:
            return url.split('youtu.be/')[-1].split('?')[0]
        return None


# ─── 모의고사 ────────────────────────────────────────────

EXAM_QUESTION_TYPES = [
    ('multiple_choice', '객관식'),
    ('short_answer',    '단답형'),
    ('essay',           '서술형'),
]


class MockExam(db.Model):
    """모의고사"""
    __tablename__ = 'mock_exams'

    exam_id = db.Column(db.String(36), primary_key=True,
                        default=lambda: str(uuid.uuid4()))

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    time_limit_minutes = db.Column(db.Integer, nullable=True)  # None=무제한

    # 선택적 연결
    book_id = db.Column(db.String(36), db.ForeignKey('books.book_id',
                         ondelete='SET NULL'), nullable=True, index=True)
    week_num = db.Column(db.Integer, nullable=True)
    tags = db.Column(db.String(300), nullable=True)

    is_published = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id',
                            ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    book = db.relationship('Book', foreign_keys=[book_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    questions = db.relationship('MockExamQuestion', back_populates='exam',
                                cascade='all, delete-orphan',
                                order_by='MockExamQuestion.order_num')

    @property
    def question_count(self):
        return len(self.questions)

    @property
    def total_score(self):
        return sum(q.score or 0 for q in self.questions)


class MockExamQuestion(db.Model):
    """모의고사 문항 (독립 입력, 문제은행과 별도)"""
    __tablename__ = 'mock_exam_questions'

    mq_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    exam_id = db.Column(db.String(36), db.ForeignKey('mock_exams.exam_id',
                         ondelete='CASCADE'), nullable=False, index=True)

    question_type = db.Column(db.String(20), nullable=False, default='multiple_choice')
    passage = db.Column(db.Text, nullable=True)      # 지문 (독해 문항)
    question_text = db.Column(db.Text, nullable=False)
    # multiple_choice: ['보기1','보기2','보기3','보기4']
    choices = db.Column(db.JSON, nullable=True)
    correct_answer = db.Column(db.String(500), nullable=True)
    explanation = db.Column(db.Text, nullable=True)
    score = db.Column(db.Float, nullable=True, default=1.0)  # 배점
    order_num = db.Column(db.Integer, default=0)

    exam = db.relationship('MockExam', back_populates='questions')

    @property
    def type_display(self):
        return dict(EXAM_QUESTION_TYPES).get(self.question_type, self.question_type)


# ─── 학습 교재 ───────────────────────────────────────────

MATERIAL_TYPES = [
    ('pdf', 'PDF'),
    ('hwp', 'HWP'),
    ('docx', 'Word'),
    ('pptx', 'PPT'),
    ('xlsx', 'Excel'),
    ('zip', 'ZIP'),
    ('other', '기타'),
]


class StudyMaterial(db.Model):
    """학습 교재 (파일 업로드)"""
    __tablename__ = 'study_materials'

    material_id = db.Column(db.String(36), primary_key=True,
                            default=lambda: str(uuid.uuid4()))

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    file_name = db.Column(db.String(300), nullable=True)   # 원본 파일명
    file_path = db.Column(db.String(500), nullable=True)   # 저장 경로
    file_type = db.Column(db.String(10), nullable=True)    # pdf/hwp/...
    file_size = db.Column(db.Integer, nullable=True)       # bytes

    # 선택적 연결
    book_id = db.Column(db.String(36), db.ForeignKey('books.book_id',
                         ondelete='SET NULL'), nullable=True, index=True)
    week_num = db.Column(db.Integer, nullable=True)
    tags = db.Column(db.String(300), nullable=True)

    is_published = db.Column(db.Boolean, default=False)
    download_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id',
                            ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    book = db.relationship('Book', foreign_keys=[book_id])
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def file_size_display(self):
        if not self.file_size:
            return '-'
        if self.file_size < 1024:
            return f'{self.file_size}B'
        elif self.file_size < 1024 * 1024:
            return f'{self.file_size // 1024}KB'
        return f'{self.file_size / 1024 / 1024:.1f}MB'

    @property
    def type_display(self):
        return dict(MATERIAL_TYPES).get(self.file_type, self.file_type or '-')
