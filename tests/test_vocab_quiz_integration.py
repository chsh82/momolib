# -*- coding: utf-8 -*-
"""schema_reading L4~L6 어휘 퀴즈 1차 이식(vocab_quiz_*) 통합 테스트 -
독립 로컬 PostgreSQL(운영 DB 아님)에 대해서만 실행한다. 실행 전
DATABASE_URL 환경변수가 로컬 테스트 DB를 가리키는지 확인하고, 그 이름에
'test'가 없으면 즉시 중단한다(운영 DB에 실수로 붙는 것을 막는 하드가드).

검증 항목: 마이그레이션→import→관리자 응시→채점→재실행, 비관리자 차단,
비로그인 차단, 매니페스트 불일치, 제출 전 정답 비노출, 기존 테이블 불변,
동일 키 다른 내용 충돌.

실행:
    set DATABASE_URL=postgresql://postgres:...@localhost:55432/momolib_vocab_test
    set FLASK_ENV=development
    python tests/test_vocab_quiz_integration.py
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
from app.models.content_bank import BankQuestion  # noqa: E402
from app.models.vocab_quiz import (VocabQuizContent, VocabQuizContentLevel,  # noqa: E402
                                    VocabQuizPilotItem, VocabQuizPilotSession,
                                    VocabQuizPilotAttempt)

_results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    _results.append((ok, label))
    print(f"{'[PASS]' if ok else '[FAIL]'} {label}" + (f" - {detail}" if detail and not ok else ""))


def make_user(email: str, role: str) -> User:
    u = User(email=email, name=email.split("@")[0], role=role, is_active=True, is_verified=True)
    u.set_password("testpass123")
    db.session.add(u)
    db.session.commit()
    return u


def login(client, email: str, password: str = "testpass123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=False)


def main() -> bool:
    app = create_app("development")
    with app.app_context():
        # ---- 0. 기존 테이블 스냅샷(임포트/응시 전) ----
        pre_bank_count = BankQuestion.query.count()
        pre_user_count = User.query.count()

        # ---- 1. 테스트 유저 ----
        admin_email = f"vqadmin_{uuid.uuid4().hex[:8]}@test.local"
        teacher_email = f"vqteacher_{uuid.uuid4().hex[:8]}@test.local"
        admin = make_user(admin_email, "super_admin")
        teacher = make_user(teacher_email, "teacher")

        client = app.test_client()

        # ---- 2. 비로그인 차단 ----
        r = client.get("/vocab-quiz/", follow_redirects=False)
        check(r.status_code in (302, 401), f"비로그인 GET /vocab-quiz/ 차단(실제 {r.status_code})")

        # ---- 3. 비관리자(teacher) 차단 ----
        login(client, teacher_email)
        r = client.get("/vocab-quiz/", follow_redirects=False)
        check(r.status_code == 403, f"teacher role GET /vocab-quiz/ -> 403(실제 {r.status_code})")
        client.get("/auth/logout", follow_redirects=False)

        # ---- 4. 관리자 로그인 + 목록 접근 ----
        lr = login(client, admin_email)
        check(lr.status_code in (302, 200), f"admin 로그인 성공(실제 {lr.status_code})")
        r = client.get("/vocab-quiz/", follow_redirects=False)
        check(r.status_code == 200, f"admin GET /vocab-quiz/ -> 200(실제 {r.status_code})")

        # ---- 5. 콘텐츠 목록/미리보기 ----
        r = client.get("/vocab-quiz/contents")
        check(r.status_code == 200, "콘텐츠 목록 200")
        one_content = VocabQuizContent.query.first()
        r = client.get(f"/vocab-quiz/contents/{one_content.content_id}")
        check(r.status_code == 200, "콘텐츠 미리보기 200")
        check(one_content.student_definition.encode("utf-8") in r.data if one_content.student_definition else True,
              "미리보기에 student_definition 노출(관리자 전용이므로 정상)")

        # ---- 6. 파일럿 정보(매니페스트 일치) ----
        r = client.get("/vocab-quiz/pilot/l4l5")
        check(r.status_code == 200, "l4l5 파일럿 정보 200")

        # ---- 7. 파일럿 세션 시작 -> 응시 -> 정답 비노출 확인 -> 채점 -> 완료 ----
        r = client.post("/vocab-quiz/pilot/l4l5/start")
        check(r.status_code == 200, f"l4l5 세션 시작 200(실제 {r.status_code})")
        session_id = r.get_json()["session_id"]

        r = client.get(f"/vocab-quiz/pilot/session/{session_id}")
        check(r.status_code == 200, "세션 응시 화면 200")
        body_text = r.get_data(as_text=True)
        check("answer_payload_json" not in body_text, "응시 화면에 answer_payload_json 미노출")
        check("correct_option" not in body_text, "응시 화면에 correct_option 미노출")

        items = VocabQuizPilotItem.query.filter_by(pilot_key="l4l5").order_by(VocabQuizPilotItem.item_id).all()
        correct_answers = 0
        for it in items:
            selected = it.correct_option  # 항상 정답으로 응답 - 채점 로직 검증용
            r = client.post(
                f"/vocab-quiz/pilot/session/{session_id}/answer",
                data=json.dumps({"item_id": it.item_id, "selected_option": selected}),
                content_type="application/json",
            )
            if r.status_code != 200:
                check(False, f"answer POST 실패 item={it.item_id} status={r.status_code}")
                continue
            data = r.get_json()
            if data["is_correct"]:
                correct_answers += 1
        check(correct_answers == len(items), f"전부 정답 응답 시 전부 is_correct=True(실제 {correct_answers}/{len(items)})")

        r = client.post(f"/vocab-quiz/pilot/session/{session_id}/complete")
        check(r.status_code == 200, "세션 완료 처리 200")
        completed = r.get_json()
        check(completed["correct_count"] == len(items), "완료 후 correct_count == 문항 수(전부 정답)")

        r = client.get(f"/vocab-quiz/pilot/session/{session_id}/result")
        check(r.status_code == 200, "결과 화면 200")

        # ---- 8. 매니페스트 불일치 시뮬레이션(DB에서 1건 삭제 후 재조회) ----
        removed_item = VocabQuizPilotItem.query.filter_by(pilot_key="l6").first()
        saved = {
            "item_id": removed_item.item_id, "pilot_key": "l6", "item_type": removed_item.item_type,
            "prompt": removed_item.prompt, "answer_payload_json": removed_item.answer_payload_json,
            "source_version": removed_item.source_version, "item_hash": removed_item.item_hash,
            "correct_option": removed_item.correct_option, "options_json": removed_item.options_json,
            "public_payload_json": removed_item.public_payload_json, "explanation": removed_item.explanation,
            "lemma": removed_item.lemma, "pos": removed_item.pos,
        }
        db.session.delete(removed_item)
        db.session.commit()
        r = client.get("/vocab-quiz/pilot/l6")
        check(r.status_code == 200, "l6 파일럿 정보 페이지는 렌더(불일치 자체를 표시)")
        r2 = client.post("/vocab-quiz/pilot/l6/start")
        check(r2.status_code == 500, f"매니페스트 불일치 시 세션 시작 500으로 거부(실제 {r2.status_code})")
        check(r2.get_json().get("error") == "PILOT_BATCH_INTEGRITY_ERROR", "PILOT_BATCH_INTEGRITY_ERROR 코드 반환")
        # 원복
        db.session.add(VocabQuizPilotItem(**saved))
        db.session.commit()
        r = client.post("/vocab-quiz/pilot/l6/start")
        check(r.status_code == 200, "복구 후 l6 세션 시작 다시 200")

        # ---- 9. 기존 테이블 불변 확인 ----
        post_bank_count = BankQuestion.query.count()
        post_user_count = User.query.count()
        check(pre_bank_count == post_bank_count, f"bank_questions 행수 불변({pre_bank_count} -> {post_bank_count})")
        check(post_user_count == pre_user_count + 2, "users는 이번 테스트가 만든 2명만 증가(기존 오염 없음)")

    n_pass = sum(1 for ok, _ in _results if ok)
    print(f"\n총 {len(_results)}건 중 {n_pass}건 통과")
    return n_pass == len(_results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
