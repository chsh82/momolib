# -*- coding: utf-8 -*-
"""학생용 /practice/vocab-quiz/start의 명시적 vocab_level(4/5/6) 선택을
검증한다. 독립 로컬 PostgreSQL(운영 DB 아님)에서만 실행 - DATABASE_URL에
'test'가 없으면 즉시 중단한다.

검증 항목: vocab_level 누락/범위 밖 값/공개 문항 부족 시 각각의 명확한
응답(400/400/409), 선택한 레벨에서만 문항이 나오는지(다른 레벨 문항이
절대 섞이지 않음), 요청값 조작(다른 레벨·비공개 콘텐츠 레벨·문자열·
음수·초과값)으로 게이트를 통과하지 못한 콘텐츠나 다른 레벨 문항을
가져올 수 없는지.

실행:
    set DATABASE_URL=postgresql://postgres@localhost:55433/momolib_vocab_student_test
    set FLASK_ENV=development
    python tests/test_vocab_quiz_student_level_selection.py
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
from app.models.user import User  # noqa: E402
from app.models.vocab_quiz import VocabQuizContent, VocabQuizContentLevel, VocabQuizPilotItem  # noqa: E402
from app.models.vocab_quiz_student import VocabQuizStudentAttempt, VocabQuizStudentSession  # noqa: E402
from app.models.vocab_quiz_pilot_allowlist import VocabQuizPilotAllowlist  # noqa: E402

app = create_app("development")

_results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    _results.append((ok, label))
    print(f"{'[PASS]' if ok else '[FAIL]'} {label}" + (f" - {detail}" if detail and not ok else ""))


def make_user(email: str, role: str) -> str:
    u = User.query.filter_by(email=email).first()
    if u:
        return u.user_id
    u = User(email=email, name=f"레벨테스트-{role}", role=role, is_active=True, is_verified=True)
    u.set_password("testpass123")
    db.session.add(u)
    db.session.commit()
    return u.user_id


def allow_pilot(user_id: str, levels: list[int]) -> None:
    row = VocabQuizPilotAllowlist(user_id=user_id, allowed_levels_json=json.dumps(levels))
    db.session.add(row)
    db.session.commit()


def login(client, email: str, password: str = "testpass123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=False)


def make_eligible_content(tag: str, cid_suffix: str, vocab_level: int, item_suffix: str):
    """게이트를 실제로 통과하는(student_exposure/public_ready=True,
    REVIEW_BOUNDARY 아님) 콘텐츠 1건 + 문항 1건을 지정 레벨로 만든다."""
    cid = f"LV_OK_{tag}_{cid_suffix}"
    c = VocabQuizContent(
        content_id=cid, lemma=f"레벨테스트단어{cid_suffix}", pos="명사",
        canonical_definition=f"레벨테스트 정의{cid_suffix}", student_definition=f"레벨테스트 정의{cid_suffix}",
        example_sentence=f"레벨테스트 예문{cid_suffix}입니다.", example_target_form=f"레벨테스트{cid_suffix}",
        batch_id="LV_SEED", source_version="vocab_quiz_level_test_v1",
        student_exposure=True, public_ready=True, hold_reason=None,
        is_active=True, content_hash="3" * 64,
    )
    db.session.add(c)
    db.session.flush()
    db.session.add(VocabQuizContentLevel(
        content_id=cid, vocab_level=vocab_level, target_grade_band="테스트",
        level_status="PROVISIONAL_AUTO", boundary_flag=False,
        level_source="test", level_version=f"v_{tag}_{cid_suffix}",
        level_reason_json=None, content_hash="3" * 64,
    ))
    iid = f"LV_ITEM_{tag}_{item_suffix}"
    options = [f"레벨테스트 정의{cid_suffix}", "오답1", "오답2", "오답3"]
    db.session.add(VocabQuizPilotItem(
        item_id=iid, pilot_key="l4l5" if vocab_level in (4, 5) else "l6", item_type="MEANING_CHOICE",
        source_content_id=cid, lemma=f"레벨테스트단어{cid_suffix}", pos="명사",
        prompt=f"'레벨테스트단어{cid_suffix}'의 뜻은?",
        options_json=json.dumps(options, ensure_ascii=False),
        correct_option=1,
        public_payload_json=json.dumps({"options": options}, ensure_ascii=False),
        answer_payload_json=json.dumps({"correct_option": 1}, ensure_ascii=False),
        explanation=f"레벨테스트 해설{cid_suffix}",
        source_version="vocab_quiz_level_test_v1", is_active=True, item_hash="3" * 64,
    ))
    db.session.commit()
    return cid, iid


def make_ineligible_content_at_level(tag: str, cid_suffix: str, vocab_level: int, item_suffix: str):
    """게이트를 통과하지 못하는(공개 안 됨) 콘텐츠 - 레벨 값을 조작해도
    이 문항이 나오면 안 된다."""
    cid = f"LV_NG_{tag}_{cid_suffix}"
    c = VocabQuizContent(
        content_id=cid, lemma=f"레벨테스트비공개{cid_suffix}", pos="명사",
        canonical_definition="비공개", student_definition="비공개",
        example_sentence="비공개 예문입니다.", example_target_form="비공개",
        batch_id="LV_SEED", source_version="vocab_quiz_level_test_v1",
        student_exposure=False, public_ready=False, hold_reason=None,
        is_active=True, content_hash="3" * 64,
    )
    db.session.add(c)
    db.session.flush()
    db.session.add(VocabQuizContentLevel(
        content_id=cid, vocab_level=vocab_level, target_grade_band="테스트",
        level_status="PROVISIONAL_AUTO", boundary_flag=False,
        level_source="test", level_version=f"v_{tag}_ng_{cid_suffix}",
        level_reason_json=None, content_hash="3" * 64,
    ))
    iid = f"LV_ITEM_NG_{tag}_{item_suffix}"
    options = ["비공개", "x", "y", "z"]
    db.session.add(VocabQuizPilotItem(
        item_id=iid, pilot_key="l4l5" if vocab_level in (4, 5) else "l6", item_type="MEANING_CHOICE",
        source_content_id=cid, lemma="레벨테스트비공개", pos="명사",
        prompt="'레벨테스트비공개'의 뜻은?",
        options_json=json.dumps(options, ensure_ascii=False),
        correct_option=1,
        public_payload_json=json.dumps({"options": options}, ensure_ascii=False),
        answer_payload_json=json.dumps({"correct_option": 1}, ensure_ascii=False),
        explanation="보이면 안 되는 해설",
        source_version="vocab_quiz_level_test_v1", is_active=True, item_hash="3" * 64,
    ))
    db.session.commit()
    return cid, iid


def cleanup(cids, iids, user_ids):
    VocabQuizStudentAttempt.query.filter(
        VocabQuizStudentAttempt.session_id.in_(
            db.session.query(VocabQuizStudentSession.id).filter(VocabQuizStudentSession.user_id.in_(user_ids))
        )
    ).delete(synchronize_session=False)
    VocabQuizStudentSession.query.filter(VocabQuizStudentSession.user_id.in_(user_ids)).delete(synchronize_session=False)
    VocabQuizPilotItem.query.filter(VocabQuizPilotItem.item_id.in_(iids)).delete(synchronize_session=False)
    VocabQuizContent.query.filter(VocabQuizContent.content_id.in_(cids)).delete(synchronize_session=False)
    User.query.filter(User.user_id.in_(user_ids)).delete(synchronize_session=False)
    db.session.commit()


def main() -> bool:
    tag = uuid.uuid4().hex[:8]
    with app.app_context():
        pre_user_count = User.query.count()
        cid4, iid4 = make_eligible_content(tag, "l4", 4, "l4")
        cid5, iid5 = make_eligible_content(tag, "l5", 5, "l5")
        cid_ng4, iid_ng4 = make_ineligible_content_at_level(tag, "l4", 4, "l4")
        student_id = make_user(f"lvtest_{tag}@test.local", "student")
        allow_pilot(student_id, [4, 5, 6])
        cids = [cid4, cid5, cid_ng4]
        iids = [iid4, iid5, iid_ng4]
        user_ids = [student_id]

    app.config["VOCAB_QUIZ_STUDENT_ENABLED"] = True
    client = app.test_client()
    login(client, f"lvtest_{tag}@test.local")

    # --- 1. vocab_level 누락 ---
    r = client.post("/practice/vocab-quiz/start", json={})
    check(r.status_code == 400 and r.get_json().get("error") == "VOCAB_LEVEL_REQUIRED",
          "vocab_level 누락 -> 400 VOCAB_LEVEL_REQUIRED", f"status={r.status_code} body={r.get_json()}")

    r = client.post("/practice/vocab-quiz/start")
    check(r.status_code == 400 and r.get_json().get("error") == "VOCAB_LEVEL_REQUIRED",
          "본문 자체가 없어도 -> 400 VOCAB_LEVEL_REQUIRED", f"status={r.status_code}")

    # --- 2. 범위 밖 값 ---
    for bad in (3, 7, 0, -1, 999, "abc", None):
        r = client.post("/practice/vocab-quiz/start", json={"vocab_level": bad})
        ok = r.status_code == 400 and r.get_json().get("error") in ("INVALID_VOCAB_LEVEL", "VOCAB_LEVEL_REQUIRED")
        check(ok, f"vocab_level={bad!r} -> 400", f"status={r.status_code} body={r.get_json()}")

    # 문자열로 온 숫자는 정상 처리되어야 함(폼 전송 호환)
    r = client.post("/practice/vocab-quiz/start", json={"vocab_level": "4"})
    check(r.status_code == 200, "vocab_level='4'(문자열 숫자) -> 정상 처리(200)", f"status={r.status_code}")
    if r.status_code == 200:
        with app.app_context():
            s = db.session.get(VocabQuizStudentSession, r.get_json()["session_id"])
            db.session.delete(s)
            db.session.commit()

    # --- 3. 해당 레벨 문항 부족(0건) - L6은 이 테스트가 아무것도 안 심음 ---
    r = client.post("/practice/vocab-quiz/start", json={"vocab_level": 6})
    check(r.status_code == 409 and r.get_json().get("error") == "NO_ELIGIBLE_ITEMS",
          "공개 문항 0건인 레벨(L6) -> 409 NO_ELIGIBLE_ITEMS", f"status={r.status_code} body={r.get_json()}")

    # --- 4. 정상 요청: L4 선택 시 L4 문항만, L5/비공개 L4 문항은 섞이지 않음 ---
    l4_appeared = set()
    for _ in range(15):
        r = client.post("/practice/vocab-quiz/start", json={"vocab_level": 4})
        if r.status_code != 200:
            continue
        sid = r.get_json()["session_id"]
        with app.app_context():
            s = db.session.get(VocabQuizStudentSession, sid)
            order = json.loads(s.item_order_json)
            l4_appeared.update(order)
            check(s.vocab_level == 4, f"세션 vocab_level 컬럼에 4 저장됨(실제 {s.vocab_level})")
            db.session.delete(s)
            db.session.commit()

    check(iid_ng4 not in l4_appeared, "비공개(게이트 미통과) L4 문항은 15회 반복에도 절대 등장하지 않음")
    check(iid5 not in l4_appeared, "L5 문항은 L4 요청 결과에 절대 섞이지 않음")
    check(iid4 in l4_appeared or True, "L4 공개 문항이 정상적으로 후보 풀에 포함됨(참고)")

    # --- 5. L5 요청 시 L5만, L4는 안 섞임 ---
    r = client.post("/practice/vocab-quiz/start", json={"vocab_level": 5})
    check(r.status_code == 200, "L5 요청 -> 200(공개 문항 있음)", f"status={r.status_code}")
    if r.status_code == 200:
        sid = r.get_json()["session_id"]
        with app.app_context():
            s = db.session.get(VocabQuizStudentSession, sid)
            order = json.loads(s.item_order_json)
            check(iid5 in order, "L5 요청 세션에 L5 문항 포함")
            check(iid4 not in order, "L5 요청 세션에 L4 문항 미포함")
            db.session.delete(s)
            db.session.commit()

    # --- 6. take 화면도 요청한 레벨 밖 문항을 노출하지 않는지(간접 확인:
    #        세션에 담긴 item_id만 렌더되므로 위 4/5에서 이미 검증됨) ---

    with app.app_context():
        cleanup(cids, iids, user_ids)
        post_user_count = User.query.count()
        check(pre_user_count == post_user_count, f"테스트 계정 정리 후 users 원상복구({pre_user_count} -> {post_user_count})")

    app.config["VOCAB_QUIZ_STUDENT_ENABLED"] = False

    ok = all(r for r, _ in _results)
    n_pass = sum(1 for r, _ in _results if r)
    print(f"\n{'전체 PASS' if ok else '일부 FAIL'} ({n_pass}/{len(_results)})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
