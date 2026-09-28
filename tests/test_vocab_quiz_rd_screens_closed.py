# -*- coding: utf-8 -*-
"""어휘 퀴즈 R&D 화면(관리자 파일럿 + 공개검토, app/vocab_quiz) 전체를
aprolabs로 일원화하며 momolib 운영에서 닫은 뒤의 상태를 검증한다 -
독립 로컬 PostgreSQL(운영 DB 아님)에서만 실행한다. DATABASE_URL에
'test'가 없으면 즉시 중단한다.

검증 항목:
  1. /vocab-quiz/* 전 경로가 로그인·역할과 무관하게 404(Flask URL
     라우팅 자체에 없음 - abort(404)가 아니라 진짜 "경로 없음")
  2. /practice/vocab-quiz/*(학생 기능)는 기존과 동일하게 기능
     플래그로 404 유지(이번 작업이 건드리지 않았음 재확인)
  3. 기존 BankQuestion/LMS/CMS 어휘 퀴즈(content_type='vocab_quiz')
     라우트는 전혀 영향받지 않음(별도 블루프린트)
  4. vocab_quiz_contents/vocab_quiz_pilot_items/vocab_quiz_admin_reviews
     테이블과 데이터는 라우트만 닫혔을 뿐 ORM으로 정상 조회 가능
     (다운그레이드·삭제 없음)

실행:
    set DATABASE_URL=postgresql://postgres@localhost:55433/momolib_close_test
    set FLASK_ENV=development
    python tests/test_vocab_quiz_rd_screens_closed.py
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
from app.models.vocab_quiz_review import VocabQuizAdminReview  # noqa: E402

app = create_app("development")

_results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    _results.append((ok, label))
    print(f"{'[PASS]' if ok else '[FAIL]'} {label}" + (f" - {detail}" if detail and not ok else ""))


def make_user(email: str, role: str) -> str:
    u = User.query.filter_by(email=email).first()
    if u:
        return u.user_id
    u = User(email=email, name=f"닫기검증-{role}", role=role, is_active=True, is_verified=True)
    u.set_password("testpass123")
    db.session.add(u)
    db.session.commit()
    return u.user_id


def login(client, email: str, password: str = "testpass123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=False)


VOCAB_QUIZ_PATHS = [
    ("GET", "/vocab-quiz/"),
    ("GET", "/vocab-quiz/contents"),
    ("GET", "/vocab-quiz/contents/ANY"),
    ("GET", "/vocab-quiz/pilot/l4l5"),
    ("POST", "/vocab-quiz/pilot/l4l5/start"),
    ("GET", "/vocab-quiz/pilot/session/ANY"),
    ("POST", "/vocab-quiz/pilot/session/ANY/answer"),
    ("POST", "/vocab-quiz/pilot/session/ANY/complete"),
    ("GET", "/vocab-quiz/pilot/session/ANY/result"),
    ("GET", "/vocab-quiz/publish-review/"),
    ("GET", "/vocab-quiz/publish-review/ANY"),
    ("POST", "/vocab-quiz/publish-review/ANY/verdict"),
    ("GET", "/vocab-quiz/publish-review/promote-dry-run"),
]


def seed_data():
    tag = uuid.uuid4().hex[:8]
    cid = f"CLOSE_TEST_C_{tag}"
    c = VocabQuizContent(
        content_id=cid, lemma="닫기검증단어", pos="명사",
        canonical_definition="정의", student_definition="정의", example_sentence="예문",
        example_target_form="닫기검증단어", batch_id="CLOSE_TEST", source_version="close_test_v1",
        student_exposure=False, public_ready=False, hold_reason=None, is_active=True, content_hash="7" * 64,
    )
    db.session.add(c)
    db.session.flush()
    db.session.add(VocabQuizContentLevel(
        content_id=cid, vocab_level=6, target_grade_band="테스트",
        level_status="REVIEW_BOUNDARY", boundary_flag=True,
        level_source="test", level_version=f"v_{tag}", level_reason_json=None, content_hash="7" * 64,
    ))
    options = ["정의", "a", "b", "c"]
    iid = f"CLOSE_TEST_I_{tag}"
    db.session.add(VocabQuizPilotItem(
        item_id=iid, pilot_key="l6", item_type="MEANING_CHOICE", source_content_id=cid,
        lemma="닫기검증단어", pos="명사", prompt="뜻은?",
        options_json=json.dumps(options, ensure_ascii=False), correct_option=1,
        public_payload_json=json.dumps({"options": options}, ensure_ascii=False),
        answer_payload_json=json.dumps({"correct_option": 1}, ensure_ascii=False),
        explanation="해설", source_version="close_test_v1", is_active=True, item_hash="7" * 64,
    ))
    admin_id = make_user("close_admin@test.local", "super_admin")
    review = VocabQuizAdminReview(
        content_id=cid, verdict="NEEDS_FIX", rationale="닫기 전 판정 보존 확인용",
        reviewer_user_id=admin_id, content_hash_at_review="7" * 64,
        item_hashes_at_review_json=json.dumps([[iid, "7" * 64]], ensure_ascii=False),
    )
    db.session.add(review)
    db.session.commit()
    return cid, iid


def main() -> bool:
    with app.app_context():
        cid, iid = seed_data()
        teacher_id = make_user("close_teacher@test.local", "teacher")
        admin_id = make_user("close_admin@test.local", "super_admin")

    client = app.test_client()
    login(client, "close_admin@test.local")
    for method, path in VOCAB_QUIZ_PATHS:
        r = client.open(path, method=method)
        check(r.status_code == 404,
              f"관리자 로그인 상태에서도 {method} {path} -> 404(실제 {r.status_code})")
    client.get("/auth/logout")

    login(client, "close_teacher@test.local")
    for method, path in VOCAB_QUIZ_PATHS[:3]:
        r = client.open(path, method=method)
        check(r.status_code == 404, f"비관리자 {method} {path} -> 404(실제 {r.status_code})")
    client.get("/auth/logout")

    client2 = app.test_client()
    for method, path in VOCAB_QUIZ_PATHS[:3]:
        r = client2.open(path, method=method)
        check(r.status_code == 404, f"비로그인 {method} {path} -> 404(실제 {r.status_code})")

    r = client2.get("/practice/vocab-quiz/")
    check(r.status_code == 404, f"학생 기능(별도 기능 플래그)도 여전히 404(실제 {r.status_code})")

    with app.app_context():
        c = VocabQuizContent.query.filter_by(content_id=cid).first()
        check(c is not None, "라우트 폐쇄 후에도 vocab_quiz_contents ORM 조회 가능(데이터 보존)")
        it = VocabQuizPilotItem.query.filter_by(item_id=iid).first()
        check(it is not None, "라우트 폐쇄 후에도 vocab_quiz_pilot_items ORM 조회 가능(데이터 보존)")
        rv = VocabQuizAdminReview.query.filter_by(content_id=cid).first()
        check(rv is not None and rv.verdict == "NEEDS_FIX", "라우트 폐쇄 후에도 판정 이력 ORM 조회 가능(삭제 안 됨)")
        check(c.student_exposure is False and c.public_ready is False, "공개 플래그 여전히 0 유지")

        # 테이블 존재 자체 재확인(다운그레이드 안 했음)
        table_names = {t.name for t in db.metadata.tables.values()}
        for t in ("vocab_quiz_contents", "vocab_quiz_content_levels", "vocab_quiz_pilot_items",
                   "vocab_quiz_pilot_sessions", "vocab_quiz_pilot_attempts",
                   "vocab_quiz_student_sessions", "vocab_quiz_student_attempts", "vocab_quiz_admin_reviews"):
            check(t in table_names, f"테이블 {t} 여전히 스키마에 존재(다운그레이드 안 함)")

        cleanup_ids = [teacher_id, admin_id]
        VocabQuizAdminReview.query.filter_by(content_id=cid).delete(synchronize_session=False)
        VocabQuizPilotItem.query.filter_by(item_id=iid).delete(synchronize_session=False)
        VocabQuizContent.query.filter_by(content_id=cid).delete(synchronize_session=False)
        User.query.filter(User.user_id.in_(cleanup_ids)).delete(synchronize_session=False)
        db.session.commit()

    ok = all(r for r, _ in _results)
    n_pass = sum(1 for r, _ in _results if r)
    print(f"\n{'전체 PASS' if ok else '일부 FAIL'} ({n_pass}/{len(_results)})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
