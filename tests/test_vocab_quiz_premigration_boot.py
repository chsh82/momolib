# -*- coding: utf-8 -*-
"""배포 전 차단 조건 1번: "신규 테이블이 없는 상태에서 새 코드가 시작될
때" 앱 전체 기동과 기존 기능에 영향이 있는지, 새 라우트를 열 때만
실패하는지 정확히 구분한다. 독립 로컬 PostgreSQL(운영 아님)에서만
실행 - DATABASE_URL에 'test'/'premigration'이 없으면 중단한다.

전제: 이 DB는 vocab_quiz_* 마이그레이션을 적용하지 않은 상태(구 코드로
만든 베이스라인을 c3d4e5f6a7b8에 stamp)여야 한다 - 신규 코드가 참조하는
5개 테이블이 실제로 없어야 이 테스트가 의미가 있다.

실행:
    set DATABASE_URL=postgresql://postgres:...@localhost:55432/momolib_vocab_premigration
    set FLASK_ENV=development
    python tests/test_vocab_quiz_premigration_boot.py
"""
from __future__ import annotations

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

DB_URL = os.environ.get("DATABASE_URL", "")
if "test" not in DB_URL.lower() and "premigration" not in DB_URL.lower():
    print(f"거부: DATABASE_URL에 'test'/'premigration'이 없습니다({DB_URL!r}) - 중단합니다.")
    sys.exit(1)

_results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    _results.append((ok, label))
    print(f"{'[PASS]' if ok else '[FAIL]'} {label}" + (f" - {detail}" if detail and not ok else ""))


def main() -> bool:
    from app import create_app
    from app.models import db

    # ---- 0. 사전 조건: vocab_quiz_* 테이블이 실제로 없는지 확인 ----
    app = create_app("development")
    with app.app_context():
        rows = db.session.execute(db.text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name LIKE 'vocab_quiz%'"
        )).fetchall()
        vocab_tables = [r[0] for r in rows]
    check(len(vocab_tables) == 0, f"사전조건: vocab_quiz_* 테이블 0개(실제 {vocab_tables})")
    if vocab_tables:
        print("사전조건 실패 - 이 DB에는 이미 마이그레이션이 적용돼 있습니다. 중단.")
        return False

    # ---- 1. 앱 자체 기동(create_app) - 신규 모델 import가 여기서 터지지 않는지 ----
    try:
        app2 = create_app("development")
        boot_ok = True
        boot_err = ""
    except Exception as exc:  # noqa: BLE001
        boot_ok = False
        boot_err = repr(exc)
    check(boot_ok, "create_app() 자체는 예외 없이 성공(모델 import가 DB 스키마를 요구하지 않음)", boot_err)

    client = app2.test_client()

    # ---- 2. 기존 기능(로그인 화면, 랜딩 페이지)은 정상 ----
    r = client.get("/", follow_redirects=False)
    check(r.status_code in (200, 302), f"기존 라우트 GET / 정상 응답(실제 {r.status_code})")

    r = client.get("/auth/login")
    check(r.status_code == 200, f"기존 라우트 GET /auth/login 200(실제 {r.status_code})")

    # ---- 3. 신규 라우트만 실패(500) - 관리자 인증 우회를 위해 세션 없이 302/401 케이스도 구분 ----
    r = client.get("/vocab-quiz/", follow_redirects=False)
    check(r.status_code in (302, 401),
          f"비로그인 상태 GET /vocab-quiz/ - 인증 게이트가 DB 쿼리보다 먼저 걸려 302/401(실제 {r.status_code})")

    # 인증을 통과해야 실제 DB 쿼리(테이블 없음 -> 500)에 도달하는지 확인하기 위해
    # 관리자 계정을 만들어 로그인한다.
    from app.models.user import User
    import uuid
    with app.app_context():
        email = f"premigtest_{uuid.uuid4().hex[:8]}@test.local"
        u = User(email=email, name="premig", role="super_admin", is_active=True, is_verified=True)
        u.set_password("testpass123")
        db.session.add(u)
        db.session.commit()

    client.post("/auth/login", data={"email": email, "password": "testpass123"})

    # development 설정(DEBUG=True)에서는 Flask가 미처리 예외를 그대로
    # 전파한다(TESTING/DEBUG 시 propagate_exceptions 기본값) - 이는 "앱이
    # 죽는다"는 뜻이 아니라 "이 요청 하나가 예외로 끝난다"는 뜻이다. 실제
    # 운영 설정(ProductionConfig, DEBUG=False 상속)에서는 Flask가 이 예외를
    # 잡아 깨끗한 500 응답으로 바꾼다 - 아래에서 둘 다 구분해서 확인한다.
    try:
        r = client.get("/vocab-quiz/", follow_redirects=False)
        dev_mode_raised = False
        dev_mode_status = r.status_code
    except Exception as exc:  # noqa: BLE001
        dev_mode_raised = True
        dev_mode_status = None
        dev_mode_exc_type = type(exc).__name__
    if dev_mode_raised:
        check(True, f"development(DEBUG=True) 설정에서는 미처리 DB 예외가 요청 단위로 전파됨"
                     f"(테스트 클라이언트에 예외로 노출, 실제 서버 프로세스는 죽지 않음) - {dev_mode_exc_type}")
    else:
        check(dev_mode_status == 500, f"development 설정 GET /vocab-quiz/ 500(실제 {dev_mode_status})")

    # ---- 4. 신규 라우트가 실패해도 그 이후 기존 라우트는 여전히 정상(앱 전체가 죽지 않음) ----
    # (이미 로그인된 상태라 /auth/login은 302로 index로 리다이렉트되는 것이 정상 동작이다 -
    #  이는 "고장"이 아니라 Flask-Login의 정상적인 already-authenticated 처리다.)
    r = client.get("/auth/login", follow_redirects=False)
    check(r.status_code == 302, f"신규 라우트 실패 이후에도 기존 라우트 정상 동작(이미 로그인 상태라 index로 리다이렉트, 실제 {r.status_code})")

    r = client.get("/", follow_redirects=False)
    check(r.status_code in (200, 302), f"신규 라우트 실패 이후 랜딩 페이지도 계속 정상(실제 {r.status_code})")

    # ---- 5. production 설정(DEBUG=False)에서는 동일 상황이 깨끗한 500으로 응답됨을 별도 확인 ----
    prod_app = create_app("production")
    prod_app.testing = False  # Flask 테스트 클라이언트가 예외를 전파하지 않고 정식 500 응답을 만들게 강제
    prod_client = prod_app.test_client()
    with app.app_context():
        prod_client.post("/auth/login", data={"email": email, "password": "testpass123"})
    r = prod_client.get("/vocab-quiz/", follow_redirects=False)
    check(r.status_code == 500,
          f"production(DEBUG=False) 설정에서는 동일 상황이 깨끗한 500 응답(실제 {r.status_code}) - "
          "실제 배포 환경에서 기대할 동작")

    n_pass = sum(1 for ok, _ in _results if ok)
    print(f"\n총 {len(_results)}건 중 {n_pass}건 통과")
    return n_pass == len(_results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
