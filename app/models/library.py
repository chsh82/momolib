# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


GENRE_CHOICES = [
    ('literature', '문학'), ('nonfiction', '비문학'), ('essay', '에세이'),
    ('science', '과학'), ('history', '역사'), ('social', '사회'),
    ('philosophy', '철학/인문'), ('art', '예술'), ('economy', '경제'),
    ('other', '기타'),
]

LEVEL_CHOICES = [
    ('all', '전체'), ('elementary', '초등'), ('middle', '중등'), ('high', '고등'),
]

CONTENT_TYPES = [
    ('video', '영상 시청'),
    ('quiz', '객관식 퀴즈'),
    ('initial_quiz', '초성 퀴즈'),
    ('vocab_quiz', '어휘 퀴즈'),
    ('essay', '서술형 평가'),
]


class Book(db.Model):
    """도서 카탈로그"""
    __tablename__ = 'books'

    book_id = db.Column(db.String(36), primary_key=True,
                        default=lambda: str(uuid.uuid4()))
    isbn = db.Column(db.String(20), unique=True, nullable=True, index=True)

    title = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(200), nullable=True)
    publisher = db.Column(db.String(100), nullable=True)
    publication_year = db.Column(db.Integer, nullable=True)
    cover_image_url = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text, nullable=True)

    genre = db.Column(db.String(20), nullable=True)   # literature, nonfiction...
    level = db.Column(db.String(20), default='all')   # all, elementary, middle, high
    page_count = db.Column(db.Integer, nullable=True)
    tags = db.Column(db.String(200), nullable=True)   # 쉼표 구분

    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id',
                           ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by])
    contents = db.relationship('LearningContent', back_populates='book',
                               cascade='all, delete-orphan',
                               order_by='LearningContent.order_num')
    reading_records = db.relationship('ReadingRecord', back_populates='book',
                                      cascade='all, delete-orphan')

    @property
    def genre_display(self):
        return dict(GENRE_CHOICES).get(self.genre, self.genre or '-')

    @property
    def level_display(self):
        return dict(LEVEL_CHOICES).get(self.level, self.level or '-')

    @property
    def content_count(self):
        return len([c for c in self.contents if c.is_published])

    def __repr__(self):
        return f'<Book {self.title}>'


class LearningContent(db.Model):
    """도서에 연결된 학습 콘텐츠"""
    __tablename__ = 'learning_contents'

    content_id = db.Column(db.String(36), primary_key=True,
                           default=lambda: str(uuid.uuid4()))
    book_id = db.Column(db.String(36), db.ForeignKey('books.book_id',
                        ondelete='CASCADE'), nullable=False, index=True)

    type = db.Column(db.String(20), nullable=False)  # video/quiz/essay/initial_quiz/vocab_quiz
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # 타입별 데이터 (JSON)
    # video: {url, duration_seconds, thumbnail_url}
    # essay: {prompt, rubric, max_score}
    # quiz/initial_quiz/vocab_quiz: 문항은 QuizQuestion 테이블
    data = db.Column(db.JSON, nullable=True)

    order_num = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id',
                           ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    book = db.relationship('Book', back_populates='contents')
    questions = db.relationship('QuizQuestion', back_populates='content',
                                cascade='all, delete-orphan',
                                order_by='QuizQuestion.order_num')
    completions = db.relationship('ContentCompletion', back_populates='content',
                                  cascade='all, delete-orphan')
    essay_submissions = db.relationship('EssaySubmission', back_populates='content',
                                        cascade='all, delete-orphan')

    @property
    def type_display(self):
        return dict(CONTENT_TYPES).get(self.type, self.type)

    @property
    def type_icon(self):
        return {'video': '🎬', 'quiz': '📝', 'initial_quiz': '🔤',
                'vocab_quiz': '📖', 'essay': '✍️'}.get(self.type, '📄')

    def __repr__(self):
        return f'<LearningContent {self.title} ({self.type})>'


class QuizQuestion(db.Model):
    """퀴즈 문항 (객관식 / 초성 / 어휘)"""
    __tablename__ = 'quiz_questions'

    question_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    content_id = db.Column(db.String(36), db.ForeignKey('learning_contents.content_id',
                           ondelete='CASCADE'), nullable=False, index=True)

    question_text = db.Column(db.Text, nullable=False)
    # choices: [{"text": "...", "is_correct": true}, ...]
    # initial_quiz: {"answer": "ㄱㄴㄷ", "hint": "..."}
    # vocab_quiz: {"word": "...", "choices": [...], "correct_idx": 0}
    choices = db.Column(db.JSON, nullable=True)
    correct_answer = db.Column(db.String(200), nullable=True)  # 정답 or 정답 인덱스
    explanation = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    order_num = db.Column(db.Integer, default=0)

    content = db.relationship('LearningContent', back_populates='questions')


class ReadingRecord(db.Model):
    """학생 독서 기록"""
    __tablename__ = 'reading_records'

    record_id = db.Column(db.String(36), primary_key=True,
                          default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('users.user_id',
                           ondelete='CASCADE'), nullable=False, index=True)
    book_id = db.Column(db.String(36), db.ForeignKey('books.book_id',
                        ondelete='CASCADE'), nullable=False)
    branch_id = db.Column(db.String(36), db.ForeignKey('branches.branch_id',
                          ondelete='CASCADE'), nullable=False)

    status = db.Column(db.String(20), default='reading')  # reading / completed
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)

    rating = db.Column(db.Integer, nullable=True)   # 1-5
    review = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'book_id', name='uq_student_book'),
    )

    # Relationships
    student = db.relationship('User', foreign_keys=[student_id])
    book = db.relationship('Book', back_populates='reading_records')

    @property
    def status_display(self):
        return {'reading': '읽는 중', 'completed': '완료'}.get(self.status, self.status)


class ContentCompletion(db.Model):
    """학습 콘텐츠 완료 기록"""
    __tablename__ = 'content_completions'

    completion_id = db.Column(db.String(36), primary_key=True,
                              default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('users.user_id',
                           ondelete='CASCADE'), nullable=False, index=True)
    content_id = db.Column(db.String(36), db.ForeignKey('learning_contents.content_id',
                           ondelete='CASCADE'), nullable=False)

    score = db.Column(db.Float, nullable=True)        # 획득 점수
    max_score = db.Column(db.Float, nullable=True)    # 만점
    answer_data = db.Column(db.JSON, nullable=True)   # 제출 답안
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'content_id', name='uq_student_content'),
    )

    content = db.relationship('LearningContent', back_populates='completions')

    @property
    def score_pct(self):
        if self.score is not None and self.max_score:
            return round(self.score / self.max_score * 100)
        return None


class EssaySubmission(db.Model):
    """서술형 평가 제출"""
    __tablename__ = 'essay_submissions'

    submission_id = db.Column(db.String(36), primary_key=True,
                              default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('users.user_id',
                           ondelete='CASCADE'), nullable=False, index=True)
    content_id = db.Column(db.String(36), db.ForeignKey('learning_contents.content_id',
                           ondelete='CASCADE'), nullable=False)

    text = db.Column(db.Text, nullable=False)
    score = db.Column(db.Float, nullable=True)
    max_score = db.Column(db.Float, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    graded_by = db.Column(db.String(36), db.ForeignKey('users.user_id',
                          ondelete='SET NULL'), nullable=True)
    graded_at = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('User', foreign_keys=[student_id])
    grader = db.relationship('User', foreign_keys=[graded_by])
    content = db.relationship('LearningContent', back_populates='essay_submissions')

    @property
    def is_graded(self):
        return self.score is not None
