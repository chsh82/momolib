# -*- coding: utf-8 -*-
"""관리자 공개검토 화면(app/vocab_quiz/publish_review*.py) 통합 테스트 -
독립 로컬 PostgreSQL(운영 DB 아님)에서만 실행한다. DATABASE_URL에 'test'가
없으면 즉시 중단한다.

검증 항목:
  1. 판정 저장이 vocab_quiz_admin_reviews에만 쓰고, student_exposure/
     public_ready/level_status/boundary_flag는 전혀 바꾸지 않음
  2. 판정자·시각·근거·콘텐츠/문항 버전 스냅샷이 정확히 기록됨
  3. 콘텐츠/문항이 바뀌면 이전 판정이 "신선도 만료(stale)"로 표시됨
  4. 승격 dry-run이 실제로 아무것도 바꾸지 않고, 차단 사유/변경 예정
     필드를 정확히 계산함(1순위 후보 전부 REVIEW_BOUNDARY인 현재 상태에서는
     '승인후보'만으로 승격되지 않고 반드시 변경 예정 필드가 나열됨)
  5. 학생용 블루프린트 기능 플래그 기본 OFF(비로그인/학생 모두 404),
     명시적으로 켰을 때만 정상 응답
  6. 비관리자(teacher)는 공개검토 화면에 들어갈 수 없음

실행:
    set DATABASE_URL=postgresql://postgres@localhost:55433/momolib_vocab_student_test
    set FLASK_ENV=development
    python tests/test_vocab_quiz_publish_review.py
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
from app.vocab_quiz import publish_review as pr  # noqa: E402

app = create_app("development")

_results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    _results.append((ok, label))
    print(f"{'[PASS]' if ok else '[FAIL]'} {label}" + (f" - {detail}" if detail and not ok else ""))


def make_user(email: str, role: str) -> User:
    u = User.query.filter_by(email=email).first()
    if u:
        return u
    u = User(email=email, name=f"공개검토테스트-{role}", role=role, is_active=True, is_verified=True)
    u.set_password("testpass123")
    db.session.add(u)
    db.session.commit()
    return u


def login(client, email: str, password: str = "testpass123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=False)


def seed_tier1_content() -> tuple[str, str]:
    """운영 실제 상태(REVIEW_BOUNDARY/비공개)를 그대로 흉내 낸 1순위
    콘텐츠 1건 + 연결 문항 1건을 만든다."""
    tag = uuid.uuid4().hex[:8]
    cid = f"PR_TEST_C_{tag}"
    c = VocabQuizContent(
        content_id=cid, lemma=f"공개검토테스트{tag}", pos="명사",
        canonical_definition="원천 정의", student_definition="학생용 정의",
        example_sentence="예문입니다.", example_target_form="공개검토테스트",
        batch_id="PR_TEST", source_version="vocab_quiz_publish_review_test_v1",
        student_exposure=False, public_ready=False, hold_reason=None,
        is_active=True, content_hash="3" * 64,
    )
    db.session.add(c)
    db.session.flush()
    db.session.add(VocabQuizContentLevel(
        content_id=cid, vocab_level=6, target_grade_band="테스트",
        level_status="REVIEW_BOUNDARY", boundary_flag=True,
        level_source="test", level_version=f"v_{tag}",
        level_reason_json=None, content_hash="3" * 64,
    ))
    item_id = f"PR_TEST_I_{tag}"
    options = ["학생용 정의", "오답1", "오답2", "오답3"]
    db.session.add(VocabQuizPilotItem(
        item_id=item_id, pilot_key="l6", item_type="MEANING_CHOICE",
        source_content_id=cid, lemma=f"공개검토테스트{tag}", pos="명사",
        prompt=f"'공개검토테스트{tag}'의 뜻은?",
        options_json=json.dumps(options, ensure_ascii=False),
        correct_option=1,
        public_payload_json=json.dumps({"options": options}, ensure_ascii=False),
        answer_payload_json=json.dumps({"correct_option": 1}, ensure_ascii=False),
        explanation="테스트 해설",
        source_version="vocab_quiz_publish_review_test_v1", is_active=True, item_hash="3" * 64,
    ))
    db.session.commit()
    return cid, item_id


def cleanup(cid: str, item_id: str, user_ids: list[str]) -> None:
    VocabQuizAdminReview.query.filter_by(content_id=cid).delete(synchronize_session=False)
    VocabQuizPilotItem.query.filter_by(item_id=item_id).delete(synchronize_session=False)
    VocabQuizContent.query.filter_by(content_id=cid).delete(synchronize_session=False)
    User.query.filter(User.user_id.in_(user_ids)).delete(synchronize_session=False)
    db.session.commit()


def main() -> bool:
    with app.app_context():
        cid, item_id = seed_tier1_content()
        admin = make_user("pr_admin@test.local", "super_admin")
        teacher = make_user("pr_teacher@test.local", "teacher")
        user_ids = [admin.user_id, teacher.user_id]

        # --- 1. 순수 로직: 티어 분류 ---
        t1_ids = pr.tier1_content_ids()
        check(cid in t1_ids, "seed한 콘텐츠가 1순위(tier1)로 분류됨")

        # --- 2. 판정 저장 전/후 공개 플래그 불변 ---
        content = VocabQuizContent.query.filter_by(content_id=cid).first()
        before_exposure = (content.student_exposure, content.public_ready)
        level_before = VocabQuizContentLevel.query.filter_by(content_id=cid).first()
        before_level = (level_before.level_status, level_before.boundary_flag)

        review1 = pr.save_review(cid, "NEEDS_FIX", "예문이 목표어를 포함하지 않음", admin.user_id)
        content = VocabQuizContent.query.filter_by(content_id=cid).first()
        level_after = VocabQuizContentLevel.query.filter_by(content_id=cid).first()
        check((content.student_exposure, content.public_ready) == before_exposure,
              "판정 저장이 student_exposure/public_ready를 바꾸지 않음")
        check((level_after.level_status, level_after.boundary_flag) == before_level,
              "판정 저장이 level_status/boundary_flag(REVIEW_BOUNDARY)를 바꾸지 않음")

        # --- 3. 판정자/시각/근거/버전 스냅샷 기록 ---
        check(review1.reviewer_user_id == admin.user_id, "판정자 기록됨")
        check(review1.reviewed_at is not None, "판정 시각 기록됨")
        check(review1.rationale == "예문이 목표어를 포함하지 않음", "판정 근거 기록됨")
        check(review1.content_hash_at_review == content.content_hash, "콘텐츠 버전 스냅샷 기록됨")
        stored_pairs = json.loads(review1.item_hashes_at_review_json)
        check(stored_pairs == [[item_id, "3" * 64]], "연결 문항 버전 스냅샷 기록됨")

        # --- 4. 신선도(staleness) ---
        check(not pr.review_is_stale(review1, content), "방금 저장한 판정은 아직 신선함(stale 아님)")

        content.content_hash = "4" * 64  # 콘텐츠가 수정됐다고 가정(실제 편집 파이프라인은 이번 범위 밖)
        db.session.commit()
        content = VocabQuizContent.query.filter_by(content_id=cid).first()
        check(pr.review_is_stale(review1, content), "콘텐츠 해시가 바뀌면 판정이 stale로 표시됨")

        content.content_hash = "3" * 64  # 원복
        db.session.commit()
        content = VocabQuizContent.query.filter_by(content_id=cid).first()
        check(not pr.review_is_stale(review1, content), "콘텐츠 해시를 되돌리면 다시 신선함")

        item = VocabQuizPilotItem.query.filter_by(item_id=item_id).first()
        item.item_hash = "5" * 64  # 문항이 수정됐다고 가정
        db.session.commit()
        check(pr.review_is_stale(review1, content), "연결 문항 해시가 바뀌면 판정이 stale로 표시됨")

        # 두 번째 판정(재검토) - 이력이 쌓이는지
        review2 = pr.save_review(cid, "APPROVED_CANDIDATE", "재검토 결과 문제 없음", admin.user_id)
        history = pr.review_history(cid)
        check(len(history) == 2, f"판정 이력 2건 누적(실제 {len(history)}건)")
        check(pr.latest_review(cid).id == review2.id, "최신 판정이 가장 마지막에 저장한 것")
        check(not pr.review_is_stale(review2, content), "재검토 판정은 최신 버전 기준 신선함")

        # --- 5. HTTP 화면(관리자) ---
        client = app.test_client()
        r = client.get(f"/vocab-quiz/publish-review/{cid}")
        check(r.status_code in (302, 401), f"비로그인 공개검토 화면 차단(실제 {r.status_code})")

        login(client, "pr_teacher@test.local")
        r = client.get(f"/vocab-quiz/publish-review/{cid}")
        check(r.status_code == 403, f"비관리자(teacher) 공개검토 화면 차단(실제 {r.status_code})")
        client.get("/auth/logout")

        login(client, "pr_admin@test.local")
        r = client.get("/vocab-quiz/publish-review/")
        check(r.status_code == 200, f"공개검토 목록 200(실제 {r.status_code})")
        check(cid.encode() in r.data, "1순위 목록에 seed 콘텐츠 노출")

        r = client.get(f"/vocab-quiz/publish-review/{cid}")
        check(r.status_code == 200, f"공개검토 상세 200(실제 {r.status_code})")
        check("학생용 정의".encode("utf-8") in r.data, "상세 화면에 학생용 뜻풀이 표시")
        check(item_id.encode() in r.data, "상세 화면에 연결 문항 표시")
        check("온라인 QA".encode("utf-8") in r.data, "상세 화면에 온라인 QA 참고자료 표시")

        r = client.post(f"/vocab-quiz/publish-review/{cid}/verdict",
                        data={"verdict": "HOLD", "rationale": "HTTP 경로로 저장한 판정"})
        check(r.status_code == 200, f"판정 저장 POST 200(실제 {r.status_code})")
        check(pr.latest_review(cid).verdict == "HOLD", "HTTP로 저장한 판정이 실제로 반영됨")

        content_after_http = VocabQuizContent.query.filter_by(content_id=cid).first()
        check(content_after_http.student_exposure is False and content_after_http.public_ready is False,
              "HTTP 판정 저장 이후에도 공개 플래그 불변")

        # --- 6. 승격 dry-run ---
        r = client.get("/vocab-quiz/publish-review/promote-dry-run")
        check(r.status_code == 200, f"승격 dry-run 200(실제 {r.status_code})")
        body = r.data.decode("utf-8")
        check("판정이 승인후보 아님" in body or "HOLD" in body,
              "판정이 HOLD인 콘텐츠는 승격 dry-run에서 차단 사유로 표시됨")

        # 승인후보로 바꾼 뒤 다시 확인 - 그래도 REVIEW_BOUNDARY라 '변경 예정'에 레벨 항목이 나와야 함
        pr.save_review(cid, "APPROVED_CANDIDATE", "최종 승인후보 처리", admin.user_id)
        r = client.get("/vocab-quiz/publish-review/promote-dry-run")
        body = r.data.decode("utf-8")
        check("student_exposure" in body, "승인후보 콘텐츠는 변경 예정 필드(student_exposure 등)가 표시됨")
        check("boundary_flag" in body or "level_status" in body,
              "REVIEW_BOUNDARY 레벨도 변경 예정 필드로 표시됨(자동 승격 아님, dry-run만)")

        # dry-run 조회 자체가 데이터를 바꾸지 않았는지 재확인
        content_final = VocabQuizContent.query.filter_by(content_id=cid).first()
        level_final = VocabQuizContentLevel.query.filter_by(content_id=cid).first()
        check(content_final.student_exposure is False and content_final.public_ready is False,
              "dry-run 조회 후에도 student_exposure/public_ready 불변")
        check(level_final.level_status == "REVIEW_BOUNDARY" and level_final.boundary_flag is True,
              "dry-run 조회 후에도 REVIEW_BOUNDARY/boundary_flag 불변")

        cleanup(cid, item_id, user_ids)

    # --- 7. 학생용 블루프린트 기능 플래그 ---
    client2 = app.test_client()
    r = client2.get("/practice/vocab-quiz/")
    check(r.status_code == 404, f"기능 플래그 기본 OFF - 비로그인도 404(실제 {r.status_code})")

    with app.app_context():
        student = make_user("pr_student_flag@test.local", "student")
        student_id = student.user_id
    login(client2, "pr_student_flag@test.local")
    r = client2.get("/practice/vocab-quiz/")
    check(r.status_code == 404, f"기능 플래그 기본 OFF - 학생으로 로그인해도 404(실제 {r.status_code})")

    app.config["VOCAB_QUIZ_STUDENT_ENABLED"] = True
    r = client2.get("/practice/vocab-quiz/")
    check(r.status_code == 200, f"기능 플래그를 켜면 학생에게 정상 응답(실제 {r.status_code})")
    app.config["VOCAB_QUIZ_STUDENT_ENABLED"] = False
    r = client2.get("/practice/vocab-quiz/")
    check(r.status_code == 404, f"기능 플래그를 다시 끄면 즉시 404로 복귀(실제 {r.status_code})")

    with app.app_context():
        User.query.filter_by(user_id=student_id).delete(synchronize_session=False)
        db.session.commit()

    ok = all(r for r, _ in _results)
    n_pass = sum(1 for r, _ in _results if r)
    print(f"\n{'전체 PASS' if ok else '일부 FAIL'} ({n_pass}/{len(_results)})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
