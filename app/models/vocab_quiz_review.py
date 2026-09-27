# -*- coding: utf-8 -*-
"""관리자 공개검토 판정 기록 - vocab_quiz_contents/vocab_quiz_pilot_items를
읽기 전용으로 참조하지만, 이 테이블에 판정을 남기는 것만으로는
student_exposure/public_ready/level_status/boundary_flag 등 어떤 공개
플래그도 바뀌지 않는다(실제 공개 전환은 app/vocab_quiz/promotion.py의
별도 dry-run/승격 절차에서만 다룬다 - 이 파일은 그 로직을 전혀 갖지
않는다).

판정은 append-only로 쌓는다(같은 콘텐츠에 여러 번 판정을 남길 수 있고,
가장 최근 것이 "현재 판정"이다) - 판정자·시각·근거가 언제나 감사
가능해야 하므로 UPDATE로 덮어쓰지 않는다.

판정 시점의 content_hash/문항 item_hash 스냅샷을 함께 저장해, 이후
콘텐츠나 문항이 수정되면 그 판정이 "현재 버전"에는 더 이상 유효하지
않음을 판별할 수 있게 한다(app/vocab_quiz/publish_review.py의
review_is_stale() 참고)."""
from __future__ import annotations

from datetime import datetime

from app.models import db

VERDICT_CHOICES = ('APPROVED_CANDIDATE', 'NEEDS_FIX', 'HOLD')
VERDICT_LABELS = {
    'APPROVED_CANDIDATE': '승인후보',
    'NEEDS_FIX': '수정필요',
    'HOLD': '보류',
}


class VocabQuizAdminReview(db.Model):
    __tablename__ = 'vocab_quiz_admin_reviews'
    __table_args__ = (
        db.CheckConstraint("verdict IN ('APPROVED_CANDIDATE', 'NEEDS_FIX', 'HOLD')",
                            name='ck_vqar_verdict'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    content_id = db.Column(db.String(120), db.ForeignKey('vocab_quiz_contents.content_id', ondelete='CASCADE'),
                            nullable=False, index=True)
    verdict = db.Column(db.String(30), nullable=False)
    rationale = db.Column(db.Text, nullable=False)
    reviewer_user_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False, index=True)
    reviewed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # 판정 시점 버전 스냅샷(신선도 판별용) - 이후 콘텐츠/문항이 바뀌어도
    # 이 값 자체는 절대 갱신하지 않는다(그 판정이 "그때 그 버전"에 대한
    # 것이었다는 사실 자체가 감사 기록이므로).
    content_hash_at_review = db.Column(db.String(64), nullable=False)
    item_hashes_at_review_json = db.Column(db.Text, nullable=False)  # [[item_id, item_hash], ...]

    reviewer = db.relationship('User')

    def __repr__(self):
        return f'<VocabQuizAdminReview content={self.content_id} verdict={self.verdict}>'
