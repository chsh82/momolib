# -*- coding: utf-8 -*-
"""관리자 공개검토 화면이 쓰는 순수 로직(우선순위 분류, 연결 문항 조회,
판정 저장, 신선도 판별, 온라인 QA 참고자료). 라우트를 정의하지 않는다 -
app/vocab_quiz/routes.py(관리자 화면)에서만 import해서 쓴다.

우선순위 분류(aprolabs 보고서 `vocab_quiz_momolib_publish_candidates_
dryrun_20260928.md` 3절과 동일한 기준을 코드로 재구현):
  1순위 - 관리자 파일럿(vocab_quiz_pilot_items)이 실제로 참조하는 콘텐츠
          (배치 자동검사 + 구조·의미 검증 + 2026-09-28 온라인 QA까지 통과)
  2순위 - source_version='schema_reading_l6_evidence_grounded_v1'이면서
          1순위가 아닌 콘텐츠(독립 출처 근거 등급 통과, 온라인 QA는 없음)
  3순위 - 나머지 전부(literacy.db 기반 자동검사만)
"""
from __future__ import annotations

import hashlib
import json

from app.models import db
from app.models.vocab_quiz import VocabQuizContent, VocabQuizPilotItem
from app.models.vocab_quiz_review import VocabQuizAdminReview

TIER2_SOURCE_VERSION = 'schema_reading_l6_evidence_grounded_v1'

# 2026-09-28 온라인 QA(momolib 운영 관리자 화면에서 80문항 실제 응시)에서
# 조사 오류가 발견·수정된 문항 - aprolabs 보고서
# vocab_quiz_momolib_online_qa_followup_fix_20260928.md 참고.
ONLINE_QA_FIXED_ITEM_IDS = {'MF_A_SC_SRL4L5PILOT_20260925_L4_003'}


def linked_items(content_id: str) -> list[VocabQuizPilotItem]:
    """이 콘텐츠를 참조하는 파일럿 문항 전부(source_content_id 단일 참조
    + source_content_ids_json 복수 참조 둘 다 포함)."""
    direct = VocabQuizPilotItem.query.filter_by(source_content_id=content_id).all()
    direct_ids = {it.item_id for it in direct}
    extra = []
    for it in VocabQuizPilotItem.query.filter(VocabQuizPilotItem.source_content_ids_json.isnot(None)).all():
        if it.item_id in direct_ids:
            continue
        try:
            ids = json.loads(it.source_content_ids_json)
        except (TypeError, ValueError):
            continue
        if content_id in ids:
            extra.append(it)
    return direct + extra


def tier1_content_ids() -> set[str]:
    return {
        cid for (cid,) in db.session.query(VocabQuizPilotItem.source_content_id)
        .filter(VocabQuizPilotItem.source_content_id.isnot(None)).distinct().all()
    }


def ordered_tier1_content_ids() -> list[str]:
    """목록 화면과 완전히 같은 순서(표제어 가나다순) - 판정 저장 후
    '다음 항목'을 정할 때도 이 순서를 그대로 쓴다."""
    t1_ids = tier1_content_ids()
    rows = (
        VocabQuizContent.query
        .filter(VocabQuizContent.content_id.in_(t1_ids))
        .order_by(VocabQuizContent.lemma)
        .all()
    )
    return [c.content_id for c in rows]


def next_content_id(content_id: str) -> str | None:
    """이 콘텐츠 다음 순서의 content_id. 마지막이면 None(목록으로)."""
    ordered = ordered_tier1_content_ids()
    if content_id not in ordered:
        return None
    idx = ordered.index(content_id)
    if idx + 1 < len(ordered):
        return ordered[idx + 1]
    return None


def tier_of(content: VocabQuizContent, t1_ids: set[str] | None = None) -> int:
    if t1_ids is None:
        t1_ids = tier1_content_ids()
    if content.content_id in t1_ids:
        return 1
    if content.source_version == TIER2_SOURCE_VERSION:
        return 2
    return 3


def online_qa_note(item: VocabQuizPilotItem) -> str:
    if item.pilot_key in ('l4l5', 'l6'):
        base = "2026-09-28 momolib 운영 관리자 화면에서 실제 응시 확인(정답 처리·해설 표시 정상)."
        if item.item_id in ONLINE_QA_FIXED_ITEM_IDS:
            return base + " 최초 응시 시 조사(은/는·이라는/라는) 오류 1건 발견 → 수정 완료(momolib 2c84a04)."
        return base
    return "온라인 QA 대상 아님(관리자 파일럿에 포함되지 않은 문항)."


def _current_item_hash_pairs(content_id: str) -> list[list[str]]:
    items = linked_items(content_id)
    return sorted([[it.item_id, it.item_hash] for it in items])


def latest_review(content_id: str) -> VocabQuizAdminReview | None:
    return (
        VocabQuizAdminReview.query.filter_by(content_id=content_id)
        .order_by(VocabQuizAdminReview.reviewed_at.desc(), VocabQuizAdminReview.id.desc())
        .first()
    )


def review_history(content_id: str) -> list[VocabQuizAdminReview]:
    return (
        VocabQuizAdminReview.query.filter_by(content_id=content_id)
        .order_by(VocabQuizAdminReview.reviewed_at.desc(), VocabQuizAdminReview.id.desc())
        .all()
    )


def review_is_stale(review: VocabQuizAdminReview, content: VocabQuizContent) -> bool:
    """판정 이후 콘텐츠나 연결 문항이 하나라도 바뀌었으면(해시 불일치)
    True. 판정 당시 존재하지 않던 새 문항이 연결됐거나, 있던 문항이
    삭제된 경우도 잡아낸다(정렬된 (item_id, item_hash) 쌍 전체를 비교)."""
    if review.content_hash_at_review != content.content_hash:
        return True
    current_pairs = _current_item_hash_pairs(content.content_id)
    try:
        stored_pairs = json.loads(review.item_hashes_at_review_json)
    except (TypeError, ValueError):
        return True
    return current_pairs != stored_pairs


def save_review(content_id: str, verdict: str, rationale: str, reviewer_user_id: str) -> VocabQuizAdminReview:
    content = VocabQuizContent.query.filter_by(content_id=content_id).first_or_404()
    review = VocabQuizAdminReview(
        content_id=content_id,
        verdict=verdict,
        rationale=rationale,
        reviewer_user_id=reviewer_user_id,
        content_hash_at_review=content.content_hash,
        item_hashes_at_review_json=json.dumps(_current_item_hash_pairs(content_id), ensure_ascii=False),
    )
    db.session.add(review)
    db.session.commit()
    return review


def content_hash_debug(content: VocabQuizContent) -> str:
    """디버그/테스트 전용 - 실제 저장된 content_hash와 별개로, 지금 이
    순간의 필드값으로 해시를 다시 계산해 보여준다(진짜 변경 감지는
    content.content_hash 컬럼과 review 스냅샷 비교로 하고, 이 함수는
    화면에 참고용으로만 쓴다)."""
    blob = json.dumps({
        'lemma': content.lemma, 'canonical_definition': content.canonical_definition,
        'student_definition': content.student_definition,
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()
