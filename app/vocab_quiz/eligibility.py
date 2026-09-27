# -*- coding: utf-8 -*-
"""학생 공개 자격을 검사하는 단일 게이트.

어떤 학생용 화면·쿼리도 vocab_quiz_contents/vocab_quiz_content_levels/
vocab_quiz_pilot_items에서 직접 필터 조건을 다시 작성하지 않는다 - 전부
이 모듈의 함수만 거친다. 새 제외 조건이 생기면 여기 한 곳만 고치면
된다(요건 2: "콘텐츠 공개 자격을 검사하는 단일 게이트").

제외 규칙(하나라도 해당하면 제외):
  - content.is_active = False
  - content.student_exposure = False
  - content.public_ready = False
  - content.hold_reason 이 비어있지 않음(HOLD)
  - 이 콘텐츠에 연결된 레벨이 하나도 없음(레벨 미확정 콘텐츠는 안전
    기본값으로 제외)
  - 연결된 레벨 중 하나라도 level_status == 'REVIEW_BOUNDARY' 이거나
    boundary_flag = True 인 것이 있음(REVIEW_BOUNDARY)
  - item_type 의 경우: item.is_active = False, 또는 item이 참조하는
    콘텐츠(source_content_id, 그리고 source_content_ids_json에 여러
    개가 있다면 그 전부) 중 하나라도 위 조건으로 제외되면 그 문항도
    제외(전부 통과해야 노출) - 안전 쪽으로 보수적으로 판단한다.

이 모듈은 아무 라우트도 정의하지 않는다(관리자 인증 데코레이터와
무관) - 관리자 화면(app/vocab_quiz/routes.py)이나 학생 화면
(app/vocab_quiz_student/routes.py) 양쪽에서 값을 "보여줄 문항을
고를 때"만 import해서 쓴다.
"""
from __future__ import annotations

import json

from app.models import db
from app.models.vocab_quiz import VocabQuizContent, VocabQuizContentLevel, VocabQuizPilotItem

# 게이트 규칙이 바뀌면 올린다 - 세션에 기록해 두면 "이 세션이 그때
# 어떤 규칙으로 걸러졌는지" 나중에 감사할 수 있다.
GATE_VERSION = "vocab_quiz_student_gate_v1"


def content_is_eligible(content: VocabQuizContent) -> bool:
    """콘텐츠 하나가 학생에게 노출 가능한 상태인지(단일 진실 소스)."""
    if not content.is_active:
        return False
    if not content.student_exposure:
        return False
    if not content.public_ready:
        return False
    if content.hold_reason and content.hold_reason.strip():
        return False
    levels = list(content.levels)
    if not levels:
        return False
    for lv in levels:
        if lv.boundary_flag:
            return False
        if lv.level_status == 'REVIEW_BOUNDARY':
            return False
    return True


def eligible_content_ids() -> set[str]:
    """지금 시점에 학생에게 노출 가능한 content_id 집합. 콘텐츠 규모가
    작아(수백 건) 서버 메모리에서 필터링해도 무리 없고, source_content_ids_json
    의 "전부 통과해야 함" 조건을 SQL보다 단순하게 표현할 수 있다."""
    ineligible_level_content_ids = {
        cid for (cid,) in db.session.query(VocabQuizContentLevel.content_id)
        .filter(db.or_(VocabQuizContentLevel.boundary_flag.is_(True),
                        VocabQuizContentLevel.level_status == 'REVIEW_BOUNDARY'))
        .all()
    }
    content_ids_with_level = {
        cid for (cid,) in db.session.query(VocabQuizContentLevel.content_id).distinct().all()
    }
    eligible = set()
    contents = (
        VocabQuizContent.query
        .filter_by(is_active=True, student_exposure=True, public_ready=True)
        .all()
    )
    for c in contents:
        if c.hold_reason and c.hold_reason.strip():
            continue
        if c.content_id not in content_ids_with_level:
            continue
        if c.content_id in ineligible_level_content_ids:
            continue
        eligible.add(c.content_id)
    return eligible


def item_is_eligible(item: VocabQuizPilotItem, eligible_cids: set[str] | None = None) -> bool:
    """문항 하나가 학생에게 노출 가능한지. item이 참조하는 콘텐츠가
    여러 개(source_content_ids_json)라면 전부 통과해야 한다."""
    if not item.is_active:
        return False
    if eligible_cids is None:
        eligible_cids = eligible_content_ids()

    referenced_cids = []
    if item.source_content_id:
        referenced_cids.append(item.source_content_id)
    if item.source_content_ids_json:
        try:
            extra = json.loads(item.source_content_ids_json)
        except (TypeError, ValueError):
            return False  # 파싱 불가한 참조는 안전하게 노출하지 않음
        referenced_cids.extend(extra)

    if not referenced_cids:
        return False  # 어떤 콘텐츠도 참조하지 않는 문항은 노출하지 않음(안전 기본값)

    return all(cid in eligible_cids for cid in referenced_cids)


def eligible_pilot_items(pilot_key: str | None = None) -> list[VocabQuizPilotItem]:
    """게이트를 통과한 문항 목록. 학생용 세션 구성은 반드시 이 함수(또는
    이 함수가 쓰는 item_is_eligible)를 거쳐야 한다."""
    cids = eligible_content_ids()
    q = VocabQuizPilotItem.query.filter_by(is_active=True)
    if pilot_key:
        q = q.filter_by(pilot_key=pilot_key)
    return [it for it in q.all() if item_is_eligible(it, cids)]


def eligible_pilot_item_count(pilot_key: str | None = None) -> int:
    return len(eligible_pilot_items(pilot_key=pilot_key))
