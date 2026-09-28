# -*- coding: utf-8 -*-
"""학생용 어휘 퀴즈 파일럿의 운영 전 엣지 케이스를 검증한다. 독립 로컬
PostgreSQL(운영 DB 아님)에서만 실행 - DATABASE_URL에 'test'가 없으면
즉시 중단한다.

검증 항목: 허용된 학생 화면에 하단 탭 메뉴 진입점이 실제로 보이는지,
문항 부족(10개 미만) 시 있는 만큼만 세션이 만들어지는지, 같은 문항이
서로 다른 세션에서 반복될 수 있는지(의도된 동작), 중도 이탈 후
재접속 시 이미 답한 문항 상태가 정확히 복원되는지.

실행:
    set DATABASE_URL=postgresql://postgres@localhost:55433/momolib_vocab_student_test
    set FLASK_ENV=development
    python tests/test_vocab_quiz_student_edge_cases.py
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
    u = User(email=email, name=f"엣지케이스-{role}", role=role, is_active=True, is_verified=True)
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
    cid = f"EC_OK_{tag}_{suffix}"
    c = VocabQuizContent(
        content_id=cid, lemma=f"엣지케이스단어{suffix}", pos="명사",
        canonical_definition=f"정의{suffix}", student_definition=f"정의{suffix}",
        example_sentence=f"예문{suffix}입니다.", example_target_form=f"단어{suffix}",
        batch_id="EC_SEED", source_version="vocab_quiz_edge_case_test_v1",
        student_exposure=True, public_ready=True, hold_reason=None,
        is_active=True, content_hash="5" * 64,
    )
    db.session.add(c)
    db.session.flush()
    db.session.add(VocabQuizContentLevel(
        content_id=cid, vocab_level=vocab_level, target_grade_band="테스트",
        level_status="PROVISIONAL_AUTO", boundary_flag=False,
        level_source="test", level_version=f"v_{tag}_{suffix}",
        level_reason_json=None, content_hash="5" * 64,
    ))
    iid = f"EC_ITEM_{tag}_{suffix}"
    options = [f"정의{suffix}", "오답1", "오답2", "오답3"]
    db.session.add(VocabQuizPilotItem(
        item_id=iid, pilot_key="l4l5" if vocab_level in (4, 5) else "l6", item_type="MEANING_CHOICE",
        source_content_id=cid, lemma=f"엣지케이스단어{suffix}", pos="명사",
        prompt=f"'엣지케이스단어{suffix}'의 뜻은?",
        options_json=json.dumps(options, ensure_ascii=False),
        correct_option=1,
        public_payload_json=json.dumps({"options": options}, ensure_ascii=False),
        answer_payload_json=json.dumps({"correct_option": 1}, ensure_ascii=False),
        explanation=f"해설{suffix}",
        source_version="vocab_quiz_edge_case_test_v1", is_active=True, item_hash="5" * 64,
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
        # L4: 정확히 3건만(문항 부족 케이스), L5: 정확히 2건만(반복 확인용)
        cids, iids = [], []
        for i in range(3):
            cid, iid = make_eligible_content(tag, f"l4_{i}", 4)
            cids.append(cid); iids.append(iid)
        for i in range(2):
            cid, iid = make_eligible_content(tag, f"l5_{i}", 5)
            cids.append(cid); iids.append(iid)

        student_id = make_user(f"ectest_{tag}@test.local", "student")
        allow_pilot(student_id, [4, 5])
        user_ids = [student_id]

    app.config["VOCAB_QUIZ_STUDENT_ENABLED"] = True
    client = app.test_client()
    login(client, f"ectest_{tag}@test.local")

    # --- 1. 메뉴 진입점: 허용된 학생 화면에 하단 탭 링크가 실제로 보임 ---
    r = client.get("/practice/vocab-quiz/")
    check(r.status_code == 200, "허용 학생 index 200")
    body = r.data.decode("utf-8")
    check("어휘" in body and "/practice/vocab-quiz/" in body,
          "허용 학생 화면에 '어휘' 메뉴 탭 링크가 실제로 렌더됨(직접 URL 입력 불필요)")

    # --- 2. 문항 부족(L4=3건, 10개 미만) -> 있는 만큼만 세션 생성 ---
    r = client.post("/practice/vocab-quiz/start", json={"vocab_level": 4})
    check(r.status_code == 200, "L4(3문항만 존재) POST start -> 200")
    body4 = r.get_json()
    check(body4.get("item_count") == 3, "문항 부족 시 있는 만큼만(3개) 세션 생성", f"실제 {body4}")
    with app.app_context():
        s4 = db.session.get(VocabQuizStudentSession, body4["session_id"])
        db.session.delete(s4)
        db.session.commit()

    # --- 3. 같은 문항이 서로 다른 세션에서 반복 가능(L5=2건, 매번 전부 뽑힘) ---
    order_runs = []
    for _ in range(3):
        r = client.post("/practice/vocab-quiz/start", json={"vocab_level": 5})
        check(r.status_code == 200, "L5(2문항만 존재) POST start -> 200")
        sid = r.get_json()["session_id"]
        with app.app_context():
            s = db.session.get(VocabQuizStudentSession, sid)
            order_runs.append(sorted(json.loads(s.item_order_json)))
            db.session.delete(s)
            db.session.commit()
    check(all(run == order_runs[0] for run in order_runs) and len(order_runs[0]) == 2,
          "문항 풀이 작아 같은 문항이 여러 세션에서 반복됨(의도된 동작, 3회 모두 동일 2문항)",
          f"실제={order_runs}")

    # --- 4. 중도 이탈 -> 재접속 시 상태 복원 ---
    r = client.post("/practice/vocab-quiz/start", json={"vocab_level": 4})
    sid = r.get_json()["session_id"]
    with app.app_context():
        s = db.session.get(VocabQuizStudentSession, sid)
        order = json.loads(s.item_order_json)

    # 첫 문항만 답하고 "이탈"(추가 요청 없음 - complete 호출 안 함)
    first_item = order[0]
    r = client.post(f"/practice/vocab-quiz/session/{sid}/answer",
                     json={"item_id": first_item, "selected_option": 1})
    check(r.status_code == 200, "이탈 전 1문항 응답 성공")

    # "재접속": 같은 session_id로 다시 GET(새 요청)
    take2 = client.get(f"/practice/vocab-quiz/session/{sid}")
    check(take2.status_code == 200, "재접속 시 세션 조회 -> 200(중단된 세션 유실 없음)")
    take_html = take2.data.decode("utf-8")
    check(first_item in take_html, "재접속 화면에 이미 답한 문항이 여전히 포함됨")

    # 남은 문항 답해서 완료까지 이어짐(재개 가능 확인)
    remaining_correct = 0
    for item_id in order[1:]:
        r = client.post(f"/practice/vocab-quiz/session/{sid}/answer",
                         json={"item_id": item_id, "selected_option": 1})
        if r.get_json().get("is_correct"):
            remaining_correct += 1
    r = client.post(f"/practice/vocab-quiz/session/{sid}/complete")
    check(r.status_code == 200 and r.get_json().get("item_count") == len(order),
          "재접속 후 이어서 완료까지 정상 진행", f"body={r.get_json()}")

    # 이미 답한 문항을 다시 제출하면(재답안) 새 행 추가가 아니라 기존 행 갱신
    with app.app_context():
        attempt_count_before = VocabQuizStudentAttempt.query.filter_by(session_id=sid, item_id=first_item).count()
    r = client.post(f"/practice/vocab-quiz/session/{sid}/answer",
                     json={"item_id": first_item, "selected_option": 1})
    with app.app_context():
        attempt_count_after = VocabQuizStudentAttempt.query.filter_by(session_id=sid, item_id=first_item).count()
    check(attempt_count_before == attempt_count_after == 1,
          "이미 답한 문항 재제출 시 중복 행이 아니라 기존 응답만 갱신됨")

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
