# -*- coding: utf-8 -*-
"""학생용 어휘 퀴즈 파일럿 대상 제한(allowlist)을 검증한다. 독립 로컬
PostgreSQL(운영 DB 아님)에서만 실행 - DATABASE_URL에 'test'가 없으면
즉시 중단한다.

검증 항목: allowlist가 비어 있으면(기본 상태) 어떤 student 계정도 전
라우트에서 403(기본 차단), 특정 레벨만 허용된 학생은 그 레벨만 접근
가능하고 다른 레벨은 403(LEVEL_NOT_ALLOWED), allowlist에 없는 학생은
콘텐츠가 있어도 index부터 403, 비allowlist 학생과 무관하게 게이트
미통과(비공개) 콘텐츠는 허용된 학생에게도 절대 노출되지 않음.

실행:
    set DATABASE_URL=postgresql://postgres@localhost:55433/momolib_vocab_student_test
    set FLASK_ENV=development
    python tests/test_vocab_quiz_student_pilot_allowlist.py
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
    u = User(email=email, name=f"allowlist테스트-{role}", role=role, is_active=True, is_verified=True)
    u.set_password("testpass123")
    db.session.add(u)
    db.session.commit()
    return u.user_id


def allow_pilot(user_id: str, levels: list[int]) -> None:
    db.session.add(VocabQuizPilotAllowlist(user_id=user_id, allowed_levels_json=json.dumps(levels)))
    db.session.commit()


def login(client, email: str, password: str = "testpass123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=False)


def make_eligible_content(tag: str, suffix: str, vocab_level: int):
    cid = f"AL_OK_{tag}_{suffix}"
    c = VocabQuizContent(
        content_id=cid, lemma=f"허용리스트단어{suffix}", pos="명사",
        canonical_definition=f"정의{suffix}", student_definition=f"정의{suffix}",
        example_sentence=f"예문{suffix}입니다.", example_target_form=f"단어{suffix}",
        batch_id="AL_SEED", source_version="vocab_quiz_allowlist_test_v1",
        student_exposure=True, public_ready=True, hold_reason=None,
        is_active=True, content_hash="4" * 64,
    )
    db.session.add(c)
    db.session.flush()
    db.session.add(VocabQuizContentLevel(
        content_id=cid, vocab_level=vocab_level, target_grade_band="테스트",
        level_status="PROVISIONAL_AUTO", boundary_flag=False,
        level_source="test", level_version=f"v_{tag}_{suffix}",
        level_reason_json=None, content_hash="4" * 64,
    ))
    iid = f"AL_ITEM_{tag}_{suffix}"
    options = [f"정의{suffix}", "오답1", "오답2", "오답3"]
    db.session.add(VocabQuizPilotItem(
        item_id=iid, pilot_key="l4l5" if vocab_level in (4, 5) else "l6", item_type="MEANING_CHOICE",
        source_content_id=cid, lemma=f"허용리스트단어{suffix}", pos="명사",
        prompt=f"'허용리스트단어{suffix}'의 뜻은?",
        options_json=json.dumps(options, ensure_ascii=False),
        correct_option=1,
        public_payload_json=json.dumps({"options": options}, ensure_ascii=False),
        answer_payload_json=json.dumps({"correct_option": 1}, ensure_ascii=False),
        explanation=f"해설{suffix}",
        source_version="vocab_quiz_allowlist_test_v1", is_active=True, item_hash="4" * 64,
    ))
    db.session.commit()
    return cid, iid


def make_ineligible_content(tag: str, suffix: str, vocab_level: int):
    """공개 게이트를 통과하지 못하는(HOLD) 콘텐츠 - allowlist로 허용된
    학생이라도 이 문항은 절대 나오면 안 된다(게이트와 allowlist는
    별개의 독립된 두 축)."""
    cid = f"AL_NG_{tag}_{suffix}"
    c = VocabQuizContent(
        content_id=cid, lemma="허용리스트비공개", pos="명사",
        canonical_definition="비공개", student_definition="비공개",
        example_sentence="비공개 예문입니다.", example_target_form="비공개",
        batch_id="AL_SEED", source_version="vocab_quiz_allowlist_test_v1",
        student_exposure=True, public_ready=True, hold_reason="검수 대기",
        is_active=True, content_hash="4" * 64,
    )
    db.session.add(c)
    db.session.flush()
    db.session.add(VocabQuizContentLevel(
        content_id=cid, vocab_level=vocab_level, target_grade_band="테스트",
        level_status="PROVISIONAL_AUTO", boundary_flag=False,
        level_source="test", level_version=f"v_{tag}_ng_{suffix}",
        level_reason_json=None, content_hash="4" * 64,
    ))
    iid = f"AL_ITEM_NG_{tag}_{suffix}"
    options = ["비공개", "x", "y", "z"]
    db.session.add(VocabQuizPilotItem(
        item_id=iid, pilot_key="l4l5" if vocab_level in (4, 5) else "l6", item_type="MEANING_CHOICE",
        source_content_id=cid, lemma="허용리스트비공개", pos="명사",
        prompt="'허용리스트비공개'의 뜻은?",
        options_json=json.dumps(options, ensure_ascii=False),
        correct_option=1,
        public_payload_json=json.dumps({"options": options}, ensure_ascii=False),
        answer_payload_json=json.dumps({"correct_option": 1}, ensure_ascii=False),
        explanation="보이면 안 되는 해설",
        source_version="vocab_quiz_allowlist_test_v1", is_active=True, item_hash="4" * 64,
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
    VocabQuizPilotAllowlist.query.filter(VocabQuizPilotAllowlist.user_id.in_(user_ids)).delete(synchronize_session=False)
    VocabQuizPilotItem.query.filter(VocabQuizPilotItem.item_id.in_(iids)).delete(synchronize_session=False)
    VocabQuizContent.query.filter(VocabQuizContent.content_id.in_(cids)).delete(synchronize_session=False)
    User.query.filter(User.user_id.in_(user_ids)).delete(synchronize_session=False)
    db.session.commit()


def main() -> bool:
    tag = uuid.uuid4().hex[:8]
    with app.app_context():
        pre_user_count = User.query.count()
        cid4, iid4 = make_eligible_content(tag, "l4", 4)
        cid5, iid5 = make_eligible_content(tag, "l5", 5)
        cid_ng4, iid_ng4 = make_ineligible_content(tag, "l4", 4)

        allowed_id = make_user(f"al_allowed_{tag}@test.local", "student")
        allow_pilot(allowed_id, [4])  # L4만 허용, L5는 허용 안 함
        not_allowed_id = make_user(f"al_notallowed_{tag}@test.local", "student")  # allowlist 행 자체가 없음

        cids = [cid4, cid5, cid_ng4]
        iids = [iid4, iid5, iid_ng4]
        user_ids = [allowed_id, not_allowed_id]

    app.config["VOCAB_QUIZ_STUDENT_ENABLED"] = True

    # --- 1. allowlist에 아예 없는 학생: feature flag가 켜져 있고 공개 콘텐츠가
    #        있어도 index부터 전부 403 ---
    with app.test_client() as client_not_allowed:
        login(client_not_allowed, f"al_notallowed_{tag}@test.local")
        r = client_not_allowed.get("/practice/vocab-quiz/")
        check(r.status_code == 403, "allowlist 미등록 학생: GET index -> 403(기본 차단)", f"status={r.status_code}")
        r = client_not_allowed.post("/practice/vocab-quiz/start", json={"vocab_level": 4})
        check(r.status_code == 403, "allowlist 미등록 학생: POST start(L4) -> 403", f"status={r.status_code}")

    # --- 2. L4만 허용된 학생: L4는 되고, L5(콘텐츠는 존재)는 403 ---
    with app.test_client() as client_allowed:
        login(client_allowed, f"al_allowed_{tag}@test.local")
        r = client_allowed.get("/practice/vocab-quiz/")
        check(r.status_code == 200, "L4만 허용된 학생: GET index -> 200", f"status={r.status_code}")

        r = client_allowed.post("/practice/vocab-quiz/start", json={"vocab_level": 4})
        check(r.status_code == 200, "L4만 허용된 학생: POST start(L4, 허용됨) -> 200", f"status={r.status_code}")
        if r.status_code == 200:
            sid = r.get_json()["session_id"]
            with app.app_context():
                s = db.session.get(VocabQuizStudentSession, sid)
                order = json.loads(s.item_order_json)
                check(iid_ng4 not in order, "허용된 학생이라도 게이트 미통과(HOLD) 문항은 세션에 없음")
                db.session.delete(s)
                db.session.commit()

        r = client_allowed.post("/practice/vocab-quiz/start", json={"vocab_level": 5})
        check(r.status_code == 403 and r.get_json().get("error") == "LEVEL_NOT_ALLOWED",
              "L4만 허용된 학생: POST start(L5, 미허용) -> 403 LEVEL_NOT_ALLOWED",
              f"status={r.status_code} body={r.get_json()}")

        r = client_allowed.post("/practice/vocab-quiz/start", json={"vocab_level": 6})
        check(r.status_code == 403 and r.get_json().get("error") == "LEVEL_NOT_ALLOWED",
              "L4만 허용된 학생: POST start(L6, 미허용) -> 403 LEVEL_NOT_ALLOWED")

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
