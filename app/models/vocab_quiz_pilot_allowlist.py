# -*- coding: utf-8 -*-
"""학생용 어휘 퀴즈 파일럿 대상 제한 - 기본 차단(fail-closed) 방식.

이 테이블에 행이 없는 학생은 VOCAB_QUIZ_STUDENT_ENABLED가 켜져 있어도
아무 것도 볼 수 없다(전역 feature flag는 "기능 자체를 켤지"만 결정하고,
"누가 볼 수 있는지"는 이 allowlist가 별도로 결정한다 - 두 게이트가
모두 통과해야 접근 가능). 레벨(4/5/6)별로도 개별 허용 목록을 두어,
허용된 학생이라도 지정되지 않은 레벨은 볼 수 없다."""
from __future__ import annotations

from datetime import datetime

from app.models import db


class VocabQuizPilotAllowlist(db.Model):
    __tablename__ = 'vocab_quiz_pilot_allowlist'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                         nullable=False, unique=True, index=True)
    allowed_levels_json = db.Column(db.Text, nullable=False)  # 예: "[4, 5]" - 빈 리스트면 사실상 미허용과 동일
    added_by_user_id = db.Column(db.String(36), nullable=True)  # 등록한 관리자 user_id(스냅샷, FK 아님)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User')

    def __repr__(self):
        return f'<VocabQuizPilotAllowlist user={self.user_id} levels={self.allowed_levels_json}>'
