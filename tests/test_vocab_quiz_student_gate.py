# -*- coding: utf-8 -*-
"""학생 공개 자격 단일 게이트(app/vocab_quiz/eligibility.py) 검증 -
독립 로컬 PostgreSQL(운영 DB 아님)에서만 실행한다. DATABASE_URL에 'test'가
없으면 즉시 중단한다.

레벨(4/5/6) x 문항 유형(MEANING_CHOICE/CONTEXT_MEANING) 조합마다
1개의 "공개 가능" 기준 문항과, 배제 사유별("REVIEW_BOUNDARY",
"boundary_flag만 True", "HOLD", "student_exposure=0", "public_ready=0",
"콘텐츠 is_active=False", "문항 is_active=False", "레벨 정보 없음",
"복수 콘텐츠 참조 중 일부만 부적격") 문항을 각각 만들어, 게이트를 통과한
문항 집합에 기준 문항만 있고 배제 사유 문항은 전부 없는지 확인한다.
운영 데이터는 전혀 건드리지 않는다(이 스크립트가 만든 행은 끝에서 전부
삭제).

실행:
    set DATABASE_URL=postgresql://postgres@localhost:55433/momolib_vocab_student_test
    set FLASK_ENV=development
    python tests/test_vocab_quiz_student_gate.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

DB_URL = os.environ.get("DATABASE_URL", "")
if "test" not in DB_URL.lower():
    print(f"거부: DATABASE_URL에 'test'가 없습니다({DB_URL!r}) - 운영 DB 오염 방지를 위해 중단합니다.")
    sys.exit(1)

from app import create_app  # noqa: E402
from app.models import db  # noqa: E402
from app.models.vocab_quiz import VocabQuizContent, VocabQuizContentLevel, VocabQuizPilotItem  # noqa: E402
from app.vocab_quiz.eligibility import eligible_content_ids, eligible_pilot_items, item_is_eligible  # noqa: E402

app = create_app("development")

_results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    _results.append((ok, label))
    print(f"{'[PASS]' if ok else '[FAIL]'} {label}" + (f" - {detail}" if detail and not ok else ""))


LEVELS = [4, 5, 6]
ITEM_TYPES = ["MEANING_CHOICE", "CONTEXT_MEANING"]

REASONS = [
    "eligible_baseline",
    "review_boundary_status",
    "boundary_flag_only",
    "hold_reason",
    "no_student_exposure",
    "no_public_ready",
    "content_inactive",
    "item_inactive",
    "no_level_rows",
    "multi_content_partial",
]


def _mk_content(tag: str, *, exposure=True, public_ready=True, hold=None, active=True) -> VocabQuizContent:
    cid = f"TEST_C_{tag}_{uuid.uuid4().hex[:8]}"
    c = VocabQuizContent(
        content_id=cid, lemma=f"테스트{tag}", pos="명사",
        canonical_definition="테스트 정의", student_definition="테스트 학생용 정의",
        example_sentence="테스트 예문입니다.", example_target_form="테스트",
        batch_id="TEST_BATCH", source_version="vocab_quiz_student_gate_test_v1",
        student_exposure=exposure, public_ready=public_ready,
        hold_reason=hold, is_active=active, content_hash="0" * 64,
    )
    db.session.add(c)
    return c


def _mk_level(content_id: str, level: int, *, status="PROVISIONAL_AUTO", boundary=False) -> VocabQuizContentLevel:
    lv = VocabQuizContentLevel(
        content_id=content_id, vocab_level=level, target_grade_band="테스트밴드",
        level_status=status, boundary_flag=boundary, level_source="test",
        level_version=f"v_{uuid.uuid4().hex[:8]}", level_reason_json=None,
        content_hash="0" * 64,
    )
    db.session.add(lv)
    return lv


def _mk_item(tag: str, item_type: str, source_content_id=None, source_content_ids=None, active=True) -> VocabQuizPilotItem:
    iid = f"TEST_I_{tag}_{uuid.uuid4().hex[:8]}"
    it = VocabQuizPilotItem(
        item_id=iid, pilot_key="l6", item_type=item_type,
        source_content_id=source_content_id,
        source_content_ids_json=json.dumps(source_content_ids) if source_content_ids else None,
        lemma="테스트", pos="명사", prompt="테스트 문항입니다.",
        options_json=json.dumps(["a", "b", "c", "d"], ensure_ascii=False),
        correct_option=1,
        public_payload_json=json.dumps({"options": ["a", "b", "c", "d"]}, ensure_ascii=False),
        answer_payload_json=json.dumps({"correct_option": 1}, ensure_ascii=False),
        explanation="테스트 해설입니다.", source_version="vocab_quiz_student_gate_test_v1",
        is_active=active, item_hash="0" * 64,
    )
    db.session.add(it)
    return it


def build_fixtures() -> dict:
    """(level, item_type, reason) -> item_id 매핑을 만들어 반환."""
    mapping = {}
    for level in LEVELS:
        for item_type in ITEM_TYPES:
            tagbase = f"L{level}_{item_type[:2]}"

            # 1) 기준(공개 가능) 문항
            c = _mk_content(f"{tagbase}_OK")
            db.session.flush()
            _mk_level(c.content_id, level)
            it = _mk_item(f"{tagbase}_OK", item_type, source_content_id=c.content_id)
            db.session.flush()
            mapping[(level, item_type, "eligible_baseline")] = it.item_id

            # 2) REVIEW_BOUNDARY
            c = _mk_content(f"{tagbase}_RB")
            db.session.flush()
            _mk_level(c.content_id, level, status="REVIEW_BOUNDARY")
            it = _mk_item(f"{tagbase}_RB", item_type, source_content_id=c.content_id)
            db.session.flush()
            mapping[(level, item_type, "review_boundary_status")] = it.item_id

            # 3) boundary_flag만 True(level_status는 PROVISIONAL_AUTO)
            c = _mk_content(f"{tagbase}_BF")
            db.session.flush()
            _mk_level(c.content_id, level, status="PROVISIONAL_AUTO", boundary=True)
            it = _mk_item(f"{tagbase}_BF", item_type, source_content_id=c.content_id)
            db.session.flush()
            mapping[(level, item_type, "boundary_flag_only")] = it.item_id

            # 4) HOLD
            c = _mk_content(f"{tagbase}_HOLD", hold="테스트 HOLD 사유")
            db.session.flush()
            _mk_level(c.content_id, level)
            it = _mk_item(f"{tagbase}_HOLD", item_type, source_content_id=c.content_id)
            db.session.flush()
            mapping[(level, item_type, "hold_reason")] = it.item_id

            # 5) student_exposure = False
            c = _mk_content(f"{tagbase}_NE", exposure=False)
            db.session.flush()
            _mk_level(c.content_id, level)
            it = _mk_item(f"{tagbase}_NE", item_type, source_content_id=c.content_id)
            db.session.flush()
            mapping[(level, item_type, "no_student_exposure")] = it.item_id

            # 6) public_ready = False
            c = _mk_content(f"{tagbase}_NP", public_ready=False)
            db.session.flush()
            _mk_level(c.content_id, level)
            it = _mk_item(f"{tagbase}_NP", item_type, source_content_id=c.content_id)
            db.session.flush()
            mapping[(level, item_type, "no_public_ready")] = it.item_id

            # 7) 콘텐츠 is_active = False
            c = _mk_content(f"{tagbase}_CI", active=False)
            db.session.flush()
            _mk_level(c.content_id, level)
            it = _mk_item(f"{tagbase}_CI", item_type, source_content_id=c.content_id)
            db.session.flush()
            mapping[(level, item_type, "content_inactive")] = it.item_id

            # 8) 문항 is_active = False (콘텐츠 자체는 정상)
            c = _mk_content(f"{tagbase}_II")
            db.session.flush()
            _mk_level(c.content_id, level)
            it = _mk_item(f"{tagbase}_II", item_type, source_content_id=c.content_id, active=False)
            db.session.flush()
            mapping[(level, item_type, "item_inactive")] = it.item_id

            # 9) 레벨 정보 없음
            c = _mk_content(f"{tagbase}_NL")
            db.session.flush()
            it = _mk_item(f"{tagbase}_NL", item_type, source_content_id=c.content_id)
            db.session.flush()
            mapping[(level, item_type, "no_level_rows")] = it.item_id

            # 10) 복수 콘텐츠 참조 중 하나만 부적격(HOLD)
            c_ok = _mk_content(f"{tagbase}_MULTI_OK")
            c_bad = _mk_content(f"{tagbase}_MULTI_BAD", hold="부적격 콘텐츠")
            db.session.flush()
            _mk_level(c_ok.content_id, level)
            _mk_level(c_bad.content_id, level)
            it = _mk_item(f"{tagbase}_MULTI", item_type,
                          source_content_id=c_ok.content_id,
                          source_content_ids=[c_ok.content_id, c_bad.content_id])
            db.session.flush()
            mapping[(level, item_type, "multi_content_partial")] = it.item_id

    db.session.commit()
    return mapping


def cleanup(mapping: dict) -> None:
    item_ids = list(mapping.values())
    items = VocabQuizPilotItem.query.filter(VocabQuizPilotItem.item_id.in_(item_ids)).all()
    content_ids = {it.source_content_id for it in items if it.source_content_id}
    for it in items:
        if it.source_content_ids_json:
            content_ids.update(json.loads(it.source_content_ids_json))
    for it in items:
        db.session.delete(it)
    contents = VocabQuizContent.query.filter(VocabQuizContent.content_id.in_(content_ids)).all()
    for c in contents:
        db.session.delete(c)
    db.session.commit()


def main() -> bool:
    with app.app_context():
        pre_content = VocabQuizContent.query.count()
        pre_item = VocabQuizPilotItem.query.count()

        mapping = build_fixtures()
        check(len(mapping) == len(LEVELS) * len(ITEM_TYPES) * len(REASONS),
              f"픽스처 {len(LEVELS)*len(ITEM_TYPES)*len(REASONS)}건 생성",
              detail=f"실제 {len(mapping)}건")

        eligible_ids = {it.item_id for it in eligible_pilot_items()}

        for (level, item_type, reason), item_id in mapping.items():
            should_pass = (reason == "eligible_baseline")
            actually_passed = item_id in eligible_ids
            check(
                actually_passed == should_pass,
                f"L{level}/{item_type}/{reason}: {'노출됨' if should_pass else '차단됨'}이 맞아야 함",
                detail=f"item_id={item_id}, 실제 노출됨={actually_passed}",
            )

        # item_is_eligible() 단건 API도 동일 결과를 내는지 교차 확인
        cids = eligible_content_ids()
        for (level, item_type, reason), item_id in mapping.items():
            it = VocabQuizPilotItem.query.filter_by(item_id=item_id).first()
            should_pass = (reason == "eligible_baseline")
            single_check = item_is_eligible(it, cids)
            check(single_check == should_pass,
                  f"item_is_eligible() 단건 결과 일치: L{level}/{item_type}/{reason}",
                  detail=f"item_is_eligible={single_check}")

        cleanup(mapping)

        post_content = VocabQuizContent.query.count()
        post_item = VocabQuizPilotItem.query.count()
        check(pre_content == post_content, "테스트용 콘텐츠 정리 후 원상복구",
              detail=f"이전 {pre_content} 이후 {post_content}")
        check(pre_item == post_item, "테스트용 문항 정리 후 원상복구",
              detail=f"이전 {pre_item} 이후 {post_item}")

    ok = all(r for r, _ in _results)
    n_pass = sum(1 for r, _ in _results if r)
    print(f"\n{'전체 PASS' if ok else '일부 FAIL'} ({n_pass}/{len(_results)})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
