# -*- coding: utf-8 -*-
"""import_vocab_quiz_export.py 자체의 멱등성·부분적재 복구·충돌 감지를
검증한다. 독립 로컬 PostgreSQL(운영 아님)에서만 실행 - DATABASE_URL에
'test'가 없으면 즉시 중단한다.

실행:
    set DATABASE_URL=postgresql://postgres:...@localhost:55432/momolib_vocab_test
    set FLASK_ENV=development
    python tests/test_vocab_quiz_import.py
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

DB_URL = os.environ.get("DATABASE_URL", "")
if "test" not in DB_URL.lower():
    print(f"거부: DATABASE_URL에 'test'가 없습니다({DB_URL!r}) - 중단합니다.")
    sys.exit(1)

from app import create_app  # noqa: E402
from app.models import db  # noqa: E402
from app.models.vocab_quiz import VocabQuizContent, VocabQuizContentLevel, VocabQuizPilotItem  # noqa: E402

_results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    _results.append((ok, label))
    print(f"{'[PASS]' if ok else '[FAIL]'} {label}" + (f" - {detail}" if detail and not ok else ""))


def run_import(apply: bool) -> int:
    """importer를 실제 운영 방식과 동일하게 별도 프로세스로 실행한다(모듈로
    import해서 같은 app context 안에서 부르면 Flask-SQLAlchemy 컨텍스트가
    중첩돼 부작용이 생길 수 있음 - 실제 사용 방식을 그대로 재현하는 것이
    더 안전하고 현실적이다)."""
    cmd = [sys.executable, os.path.join(REPO_ROOT, "import_vocab_quiz_export.py")]
    if apply:
        cmd.append("--apply")
    result = subprocess.run(cmd, cwd=REPO_ROOT, env=os.environ.copy(),
                             capture_output=True, timeout=60)
    print(result.stdout.decode("utf-8", errors="replace"))
    if result.returncode not in (0, 1, 2):
        print(result.stderr.decode("utf-8", errors="replace"))
    return result.returncode


def main() -> bool:
    app = create_app("development")
    with app.app_context():
        # 시작 전 클린 상태 보장
        VocabQuizContentLevel.query.delete()
        VocabQuizPilotItem.query.delete()
        VocabQuizContent.query.delete()
        db.session.commit()

        # ---- 1. dry-run: 전부 신규, 커밋 후에도 DB는 비어 있어야 함 ----
        code = run_import(apply=False)
        check(code == 0, f"dry-run 종료 코드 0(실제 {code})")
        check(VocabQuizContent.query.count() == 0, "dry-run 후 vocab_quiz_contents 여전히 0건(ROLLBACK 확인)")

        # ---- 2. --apply: 227/227/40/40 삽입 ----
        code = run_import(apply=True)
        check(code == 0, f"apply 종료 코드 0(실제 {code})")
        check(VocabQuizContent.query.count() == 227, f"contents 227건(실제 {VocabQuizContent.query.count()})")
        check(VocabQuizContentLevel.query.count() == 227, "content_levels 227건")
        check(VocabQuizPilotItem.query.filter_by(pilot_key="l4l5").count() == 40, "pilot l4l5 40건")
        check(VocabQuizPilotItem.query.filter_by(pilot_key="l6").count() == 40, "pilot l6 40건")

        # ---- 3. 멱등성: 재실행해도 신규 0건 ----
        code = run_import(apply=True)
        check(code == 0, "재실행 종료 코드 0")
        check(VocabQuizContent.query.count() == 227, "재실행 후에도 여전히 227건(중복 삽입 없음)")

        # ---- 4. 부분적재 복구: 몇 건 삭제 후 재실행하면 정확히 그만큼만 채워짐 ----
        victims = VocabQuizContent.query.order_by(VocabQuizContent.content_id).limit(4).all()
        victim_ids = [v.content_id for v in victims]
        VocabQuizContentLevel.query.filter(VocabQuizContentLevel.content_id.in_(victim_ids)).delete(
            synchronize_session=False)
        VocabQuizContent.query.filter(VocabQuizContent.content_id.in_(victim_ids)).delete(synchronize_session=False)
        db.session.commit()
        check(VocabQuizContent.query.count() == 223, "4건 삭제 후 223건")

        code = run_import(apply=True)
        check(code == 0, "부분적재 복구 실행 종료 코드 0")
        check(VocabQuizContent.query.count() == 227, "복구 후 다시 227건(정확히 누락분만 채움)")

        # ---- 5. 충돌 감지: 1건을 실제로 다른 내용으로 바꾸면 즉시 FAIL, 나머지는 안 건드림 ----
        target = VocabQuizContent.query.first()
        target_id = target.content_id
        original_def = target.student_definition
        target.student_definition = "TAMPERED_FOR_TEST"
        db.session.commit()

        code = run_import(apply=True)
        check(code == 2, f"내용 충돌 시 종료 코드 2(실제 {code})")
        after = VocabQuizContent.query.filter_by(content_id=target_id).first()
        check(after.student_definition == "TAMPERED_FOR_TEST",
              "충돌 감지 후에도 변조된 값이 조용히 덮어써지지 않음(그대로 유지)")

        # 원복
        after.student_definition = original_def
        db.session.commit()
        code = run_import(apply=True)
        check(code == 0, "원복 후 재실행 다시 성공")
        check(VocabQuizContent.query.count() == 227, "최종 227건 유지")

    n_pass = sum(1 for ok, _ in _results if ok)
    print(f"\n총 {len(_results)}건 중 {n_pass}건 통과")
    return n_pass == len(_results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
