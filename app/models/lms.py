# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


CONTENT_TYPE_DISPLAY = {
    'vocab_quiz':   '어휘 퀴즈',
    'book_quiz':    '독서 퀴즈',
    'reading_quiz': '토론질문',
    'video':        '강의영상',
    'essay':        '글쓰기',
}


class Curriculum(db.Model):
    """커리큘럼 (1주차 단위 학습 묶음)"""
    __tablename__ = 'curricula'

    curriculum_id = db.Column(db.String(36), primary_key=True,
                              default=lambda: str(uuid.uuid4()))
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    version     = db.Column(db.Integer, default=1, nullable=False)
    is_active   = db.Column(db.Boolean, default=True)
    created_by  = db.Column(db.String(36), db.ForeignKey('users.user_id',
                             ondelete='SET NULL'), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow,
                            onupdate=datetime.utcnow)

    items   = db.relationship('CurriculumItem', back_populates='curriculum',
                              cascade='all, delete-orphan',
                              order_by='CurriculumItem.order_num')
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def item_count(self):
        return len(self.items)

    @property
    def type_summary(self):
        """콘텐츠 타입별 개수 요약"""
        counts = {}
        for item in self.items:
            counts[item.content_type] = counts.get(item.content_type, 0) + 1
        return counts


class CurriculumItem(db.Model):
    """커리큘럼 내 개별 콘텐츠 항목"""
    __tablename__ = 'curriculum_items'

    item_id       = db.Column(db.Integer, primary_key=True, autoincrement=True)
    curriculum_id = db.Column(db.String(36), db.ForeignKey('curricula.curriculum_id',
                               ondelete='CASCADE'), nullable=False, index=True)
    order_num     = db.Column(db.Integer, default=0)
    content_type  = db.Column(db.String(20), nullable=False)
    # vocab_quiz / book_quiz / reading_quiz / video / essay
    content_id    = db.Column(db.String(36), nullable=False)
    # option_group: 같은 값이면 "그 중 1개 선택" 그룹 (주로 essay)
    option_group  = db.Column(db.String(50), nullable=True)

    curriculum = db.relationship('Curriculum', back_populates='items')

    @property
    def content_type_display(self):
        return CONTENT_TYPE_DISPLAY.get(self.content_type, self.content_type)

    @property
    def content_object(self):
        from app.models.content_bank import BankQuestion, LectureVideo
        if self.content_type == 'video':
            return LectureVideo.query.get(self.content_id)
        return BankQuestion.query.filter_by(
            question_id=self.content_id, is_active=True).first()

    @property
    def content_title(self):
        obj = self.content_object
        return obj.title if obj else f'(삭제된 콘텐츠)'


class Package(db.Model):
    """패키지 (커리큘럼 묶음, 일반적으로 12주 과정)"""
    __tablename__ = 'packages'

    package_id  = db.Column(db.String(36), primary_key=True,
                            default=lambda: str(uuid.uuid4()))
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_ordered  = db.Column(db.Boolean, default=True)
    # True=순서 강제 (1주차→2주차→...), False=자유 순서
    version     = db.Column(db.Integer, default=1, nullable=False)
    is_active   = db.Column(db.Boolean, default=True)
    created_by  = db.Column(db.String(36), db.ForeignKey('users.user_id',
                             ondelete='SET NULL'), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow,
                            onupdate=datetime.utcnow)

    curricula = db.relationship('PackageCurriculum', back_populates='package',
                                cascade='all, delete-orphan',
                                order_by='PackageCurriculum.order_num')
    creator   = db.relationship('User', foreign_keys=[created_by])

    @property
    def curriculum_count(self):
        return len(self.curricula)


class PackageCurriculum(db.Model):
    """패키지 ↔ 커리큘럼 연결 (버전 스냅샷 포함)"""
    __tablename__ = 'package_curricula'

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    package_id          = db.Column(db.String(36), db.ForeignKey('packages.package_id',
                                    ondelete='CASCADE'), nullable=False, index=True)
    curriculum_id       = db.Column(db.String(36), db.ForeignKey('curricula.curriculum_id',
                                    ondelete='CASCADE'), nullable=False)
    curriculum_version  = db.Column(db.Integer, nullable=False)
    # 연결 시점의 커리큘럼 버전 저장 → 이후 수정돼도 기준 보존
    order_num           = db.Column(db.Integer, default=0)

    package    = db.relationship('Package', back_populates='curricula')
    curriculum = db.relationship('Curriculum')
