# -*- coding: utf-8 -*-
"""학생용 어휘 연습(app/vocab_quiz_student) 통합 테스트 - 독립 로컬
PostgreSQL(운영 DB 아님)에서만 실행한다. DATABASE_URL에 'test'가 없으면
즉시 중단한다.

검증 항목: 비로그인/비학생 역할 차단, 학생 접근 허용, 세션 시작이 게이트를
통과한 문항만 뽑는지(REVIEW_BOUNDARY 문항은 세션에 한 번도 나오지 않음),
제출 전 정답 비노출, 제출 후 채점, 완료·결과 화면, 관리자 파일럿
테이블(vocab_quiz_pilot_sessions/_attempts)은 학생 응시로 전혀 늘지
않음(완전히 분리된 테이블에 기록됨), 다른 학생의 세션 접근 차단, 기존
사용자 데이터 불변.

주의(Flask 테스트 클라이언트 사용법): 여러 test_client()를 동시에 써서
서로 다른 사용자로 로그인/요청하는 부분은 반드시 활성 app.app_context()
블록 **밖에서** 실행해야 한다 - app_context가 열린 채로 여러 클라이언트의
요청을 보내면 Flask-Login의 current_user가 먼저 로그인한 클라이언트의
사용자로 뒤섞이는 것을 직접 재현해 확인했다(애플리케이션 라우트 코드의
버그가 아니라 테스트 스크립트가 공식 권장 패턴을 어겼을 때만 나타나는
테스트 하네스 버그). DB 접근이 필요한 지점만 짧게 app_context를 열고
닫는다.

실행:
    set DATABASE_URL=postgresql://postgres@localhost:55433/momolib_vocab_student_test
    set FLASK_ENV=development
    python tests/test_vocab_quiz_student_integration.py
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
from app.models.vocab_quiz import (VocabQuizContent, VocabQuizContentLevel, VocabQuizPilotItem,  # noqa: E402
                                    VocabQuizPilotSession, VocabQuizPilotAttempt)
from app.models.vocab_quiz_student import VocabQuizStudentAttempt, VocabQuizStudentSession  # noqa: E402

app = create_app("development")

_results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    _results.append((ok, label))
    print(f"{'[PASS]' if ok else '[FAIL]'} {label}" + (f" - {detail}" if detail and not ok else ""))


def make_user(email: str, role: str) -> str:
    u = User.query.filter_by(email=email).first()
    if u:
        return u.user_id
    u = User(email=email, name=f"통합테스트-{role}", role=role, is_active=True, is_verified=True)
    u.set_password("testpass123")
    db.session.add(u)
    db.session.commit()
    return u.user_id


def login(client, email: str, password: str = "testpass123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=False)


def seed_items():
    """공개 가능 3건(6문항) + REVIEW_BOUNDARY 1건(1문항, 세션에 절대 나오면
    안 됨)을 만든다."""
    tag = uuid.uuid4().hex[:8]
    created_cids, created_iids = [], []

    for i in range(3):
        cid = f"IT_OK_{tag}_{i}"
        c = VocabQuizContent(
            content_id=cid, lemma=f"통합테스트단어{i}", pos="명사",
            canonical_definition=f"통합테스트 정의{i}", student_definition=f"통합테스트 정의{i}",
            example_sentence=f"통합테스트 예문{i}입니다.", example_target_form=f"통합테스트{i}",
            batch_id="IT_SEED", source_version="vocab_quiz_student_it_test_v1",
            student_exposure=True, public_ready=True, hold_reason=None,
            is_active=True, content_hash="2" * 64,
        )
        db.session.add(c)
        db.session.flush()
        db.session.add(VocabQuizContentLevel(
            content_id=cid, vocab_level=4, target_grade_band="테스트",
            level_status="PROVISIONAL_AUTO", boundary_flag=False,
            level_source="test", level_version=f"v_{tag}_{i}",
            level_reason_json=None, content_hash="2" * 64,
        ))
        db.session.flush()
        created_cids.append(cid)
        for item_type in ("MEANING_CHOICE", "CONTEXT_MEANING"):
            iid = f"IT_ITEM_{tag}_{i}_{item_type[:2]}"
            options = [f"통합테스트 정의{i}", "오답1", "오답2", "오답3"]
            db.session.add(VocabQuizPilotItem(
                item_id=iid, pilot_key="l4l5", item_type=item_type,
                source_content_id=cid, lemma=f"통합테스트단어{i}", pos="명사",
                prompt=f"'통합테스트단어{i}'의 뜻은?",
                options_json=json.dumps(options, ensure_ascii=False),
                correct_option=1,
                public_payload_json=json.dumps({"options": options}, ensure_ascii=False),
                answer_payload_json=json.dumps({"correct_option": 1}, ensure_ascii=False),
                explanation=f"통합테스트 해설{i}",
                source_version="vocab_quiz_student_it_test_v1", is_active=True, item_hash="2" * 64,
            ))
            created_iids.append(iid)

    boundary_cid = f"IT_BOUNDARY_{tag}"
    c = VocabQuizContent(
        content_id=boundary_cid, lemma="통합테스트비공개", pos="명사",
        canonical_definition="비공개 정의", student_definition="비공개 정의",
        example_sentence="비공개 예문입니다.", example_target_form="통합테스트비공개",
        batch_id="IT_SEED", source_version="vocab_quiz_student_it_test_v1",
        student_exposure=True, public_ready=True, hold_reason=None,
        is_active=True, content_hash="2" * 64,
    )
    db.session.add(c)
    db.session.flush()
    db.session.add(VocabQuizContentLevel(
        content_id=boundary_cid, vocab_level=4, target_grade_band="테스트",
        level_status="REVIEW_BOUNDARY", boundary_flag=True,
        level_source="test", level_version=f"v_{tag}_boundary",
        level_reason_json=None, content_hash="2" * 64,
    ))
    boundary_item_id = f"IT_ITEM_{tag}_boundary"
    db.session.add(VocabQuizPilotItem(
        item_id=boundary_item_id, pilot_key="l4l5", item_type="MEANING_CHOICE",
        source_content_id=boundary_cid, lemma="통합테스트비공개", pos="명사",
        prompt="'통합테스트비공개'의 뜻은?",
        options_json=json.dumps(["비공개 정의", "x", "y", "z"], ensure_ascii=False),
        correct_option=1,
        public_payload_json=json.dumps({"options": ["비공개 정의", "x", "y", "z"]}, ensure_ascii=False),
        answer_payload_json=json.dumps({"correct_option": 1}, ensure_ascii=False),
        explanation="보이면 안 되는 해설",
        source_version="vocab_quiz_student_it_test_v1", is_active=True, item_hash="2" * 64,
    ))
    created_cids.append(boundary_cid)
    created_iids.append(boundary_item_id)

    db.session.commit()
    return created_cids, created_iids, boundary_item_id


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
    with app.app_context():
        pre_user_count = User.query.count()
        pre_pilot_session_count = VocabQuizPilotSession.query.count()
        pre_pilot_attempt_count = VocabQuizPilotAttempt.query.count()
        cids, iids, boundary_item_id = seed_items()
        teacher_id = make_user("it_teacher@test.local", "teacher")
        student_id = make_user("it_student@test.local", "student")
        user_ids = [teacher_id, student_id]

    # 학생용 블루프린트는 기능 플래그 기본 OFF(app/vocab_quiz_student/
    # __init__.py의 before_request) - 이 통합 테스트는 그 플래그를 켜야만
    # 의미가 있으므로 테스트 안에서만 명시적으로 켠다. 플래그 자체의
    # 기본값/on-off 동작은 tests/test_vocab_quiz_publish_review.py가
    # 별도로 검증한다.
    app.config["VOCAB_QUIZ_STUDENT_ENABLED"] = True

    # --- 여기서부터 클라이언트 요청은 app_context 밖에서 수행한다 ---
    client = app.test_client()

    r = client.get("/practice/vocab-quiz/")
    check(r.status_code in (302, 401), f"비로그인 GET /practice/vocab-quiz/ 차단(실제 {r.status_code})")

    login(client, "it_teacher@test.local")
    r = client.get("/practice/vocab-quiz/")
    check(r.status_code == 403, f"teacher role GET /practice/vocab-quiz/ -> 403(실제 {r.status_code})")
    client.get("/auth/logout")

    lr = login(client, "it_student@test.local")
    check(lr.status_code in (302, 200), f"student 로그인 성공(실제 {lr.status_code})")

    r = client.get("/practice/vocab-quiz/")
    check(r.status_code == 200, f"student GET /practice/vocab-quiz/ -> 200(실제 {r.status_code})")

    boundary_ever_appeared = False
    for _ in range(20):
        r = client.post("/practice/vocab-quiz/start")
        if r.status_code != 200:
            continue
        sid = r.get_json()["session_id"]
        take = client.get(f"/practice/vocab-quiz/session/{sid}")
        if boundary_item_id.encode("utf-8") in take.data:
            boundary_ever_appeared = True
    check(not boundary_ever_appeared,
          "REVIEW_BOUNDARY 문항이 20회 세션 생성 중 단 한 번도 등장하지 않음")

    r = client.post("/practice/vocab-quiz/start")
    check(r.status_code == 200, f"세션 시작 200(실제 {r.status_code})")
    session_id = r.get_json()["session_id"]

    r = client.get(f"/practice/vocab-quiz/session/{session_id}")
    check(r.status_code == 200, "세션 응시 화면 200")
    body_text = r.data.decode("utf-8")
    check("answer_payload_json" not in body_text, "응시 화면에 answer_payload_json 미노출")
    check("correct_option" not in body_text, "응시 화면에 correct_option 미노출")

    with app.app_context():
        session_obj = db.session.get(VocabQuizStudentSession, session_id)
        order = json.loads(session_obj.item_order_json)
        # 격리 DB에 이 테스트 밖에서 만들어진 다른 공개 문항(예: 수동 데모
        # 시드)이 이미 있을 수 있으므로, 세션에 실제로 뽑힌 item_id 기준으로
        # 조회한다(이 테스트가 만든 6문항으로만 한정하지 않음).
        items = VocabQuizPilotItem.query.filter(VocabQuizPilotItem.item_id.in_(order)).all()
        correct_options = {it.item_id: it.correct_option for it in items}

    correct_answers = 0
    for item_id in order:
        r = client.post(
            f"/practice/vocab-quiz/session/{session_id}/answer",
            json={"item_id": item_id, "selected_option": correct_options[item_id]},
        )
        if r.status_code != 200:
            check(False, f"answer POST 실패 item={item_id} status={r.status_code}")
            continue
        data = r.get_json()
        if data["is_correct"]:
            correct_answers += 1
    check(correct_answers == len(order), f"전부 정답 응답 시 전부 is_correct=True(실제 {correct_answers}/{len(order)})")

    r = client.post(f"/practice/vocab-quiz/session/{session_id}/complete")
    check(r.status_code == 200, "세션 완료 처리 200")
    completed = r.get_json()
    check(completed["correct_count"] == len(order), "완료 후 correct_count == 문항 수(전부 정답)")

    r = client.get(f"/practice/vocab-quiz/session/{session_id}/result")
    check(r.status_code == 200, "결과 화면 200")
    check("해설".encode("utf-8") in r.data, "결과 화면에 해설 텍스트 렌더")

    with app.app_context():
        other_student_id = make_user("it_student2@test.local", "student")
        user_ids.append(other_student_id)

    client2 = app.test_client()
    login(client2, "it_student2@test.local")
    r = client2.get(f"/practice/vocab-quiz/session/{session_id}")
    check(r.status_code == 403, f"다른 학생의 세션 조회 차단(실제 {r.status_code})")

    with app.app_context():
        post_pilot_session_count = VocabQuizPilotSession.query.count()
        post_pilot_attempt_count = VocabQuizPilotAttempt.query.count()
        check(pre_pilot_session_count == post_pilot_session_count,
              "학생 응시가 관리자 파일럿 세션 테이블에 전혀 기록되지 않음(완전 분리)")
        check(pre_pilot_attempt_count == post_pilot_attempt_count,
              "학생 응시가 관리자 파일럿 응답 테이블에 전혀 기록되지 않음(완전 분리)")

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
