# -*- coding: utf-8 -*-
"""독립 로컬 PostgreSQL(운영 DB 아님) 전용 - 학생용 어휘 연습 화면을
수동으로 확인하기 위한 가상 공개 문항 10개 표제어(20문항, 공개 가능) +
게이트가 걸러내야 하는 REVIEW_BOUNDARY 비공개 문항 1건, 데모 학생
계정 1개를 심는다. 실제 학생 데이터를 전혀 쓰지 않는다. DATABASE_URL에
'test'가 없으면 즉시 중단한다(운영 DB 오염 방지).

실행:
    set DATABASE_URL=postgresql://postgres@localhost:55433/momolib_vocab_student_test
    set FLASK_ENV=development
    python tests/seed_vocab_quiz_student_demo.py
"""
from __future__ import annotations

import io
import json
import os
import sys

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

app = create_app("development")

WORDS = [
    ("가상어휘일", "명사", "테스트로 만든 가상 어휘 뜻풀이 일번", "이것은 가상어휘일 예문입니다.", "가상어휘일", 4),
    ("가상어휘이", "명사", "테스트로 만든 가상 어휘 뜻풀이 이번", "이것은 가상어휘이 예문입니다.", "가상어휘이", 4),
    ("가상어휘삼", "명사", "테스트로 만든 가상 어휘 뜻풀이 삼번", "이것은 가상어휘삼 예문입니다.", "가상어휘삼", 4),
    ("가상어휘사", "명사", "테스트로 만든 가상 어휘 뜻풀이 사번", "이것은 가상어휘사 예문입니다.", "가상어휘사", 5),
    ("가상어휘오", "명사", "테스트로 만든 가상 어휘 뜻풀이 오번", "이것은 가상어휘오 예문입니다.", "가상어휘오", 5),
    ("가상어휘육", "명사", "테스트로 만든 가상 어휘 뜻풀이 육번", "이것은 가상어휘육 예문입니다.", "가상어휘육", 5),
    ("가상어휘칠", "명사", "테스트로 만든 가상 어휘 뜻풀이 칠번", "이것은 가상어휘칠 예문입니다.", "가상어휘칠", 6),
    ("가상어휘팔", "명사", "테스트로 만든 가상 어휘 뜻풀이 팔번", "이것은 가상어휘팔 예문입니다.", "가상어휘팔", 6),
    ("가상어휘구", "명사", "테스트로 만든 가상 어휘 뜻풀이 구번", "이것은 가상어휘구 예문입니다.", "가상어휘구", 6),
    ("가상어휘십", "명사", "테스트로 만든 가상 어휘 뜻풀이 십번", "이것은 가상어휘십 예문입니다.", "가상어휘십", 6),
]


def main() -> None:
    with app.app_context():
        created_contents = []
        created_items = []

        for i, (lemma, pos, definition, example, target, level) in enumerate(WORDS):
            cid = f"DEMO_ELIGIBLE_{i+1:03d}"
            if VocabQuizContent.query.filter_by(content_id=cid).first():
                continue
            c = VocabQuizContent(
                content_id=cid, lemma=lemma, pos=pos,
                canonical_definition=definition, student_definition=definition,
                example_sentence=example, example_target_form=target,
                batch_id="DEMO_STUDENT_SEED", source_version="vocab_quiz_student_demo_v1",
                student_exposure=True, public_ready=True, hold_reason=None,
                is_active=True, content_hash="1" * 64,
            )
            db.session.add(c)
            db.session.flush()
            db.session.add(VocabQuizContentLevel(
                content_id=cid, vocab_level=level, target_grade_band=f"L{level} 데모",
                level_status="PROVISIONAL_AUTO", boundary_flag=False,
                level_source="demo", level_version="demo_v1",
                level_reason_json=None, content_hash="1" * 64,
            ))
            db.session.flush()
            created_contents.append(cid)

            others = [w for w in WORDS if w[0] != lemma]
            distractors = [others[(i + off) % len(others)][2] for off in (1, 2, 3)]
            options = [definition] + distractors
            correct_pos = 1

            mc_id = f"DEMO_MC_{i+1:03d}"
            db.session.add(VocabQuizPilotItem(
                item_id=mc_id, pilot_key="l6" if level == 6 else "l4l5",
                item_type="MEANING_CHOICE", source_content_id=cid,
                lemma=lemma, pos=pos, prompt=f"'{lemma}'의 뜻으로 가장 알맞은 것은?",
                options_json=json.dumps(options, ensure_ascii=False),
                correct_option=correct_pos,
                public_payload_json=json.dumps({"options": options}, ensure_ascii=False),
                answer_payload_json=json.dumps({"correct_option": correct_pos}, ensure_ascii=False),
                explanation=f"'{lemma}'는 '{definition}'라는 뜻입니다.",
                source_version="vocab_quiz_student_demo_v1", is_active=True, item_hash="1" * 64,
            ))
            created_items.append(mc_id)

            cm_id = f"DEMO_CM_{i+1:03d}"
            db.session.add(VocabQuizPilotItem(
                item_id=cm_id, pilot_key="l6" if level == 6 else "l4l5",
                item_type="CONTEXT_MEANING", source_content_id=cid,
                lemma=lemma, pos=pos,
                prompt=f"다음 문장에서 표시된 낱말의 뜻으로 가장 알맞은 것은?\n\n{example}",
                options_json=json.dumps(options, ensure_ascii=False),
                correct_option=correct_pos,
                public_payload_json=json.dumps({"options": options}, ensure_ascii=False),
                answer_payload_json=json.dumps({"correct_option": correct_pos}, ensure_ascii=False),
                explanation=f"문장 속 '{target}'는 '{definition}'를 뜻합니다.",
                source_version="vocab_quiz_student_demo_v1", is_active=True, item_hash="1" * 64,
            ))
            created_items.append(cm_id)

        # 배제 확인용 비공개 문항 1건(REVIEW_BOUNDARY) - 학생 화면에 절대 보이면 안 됨
        hold_cid = "DEMO_HOLD_001"
        if not VocabQuizContent.query.filter_by(content_id=hold_cid).first():
            c = VocabQuizContent(
                content_id=hold_cid, lemma="가상비공개어휘", pos="명사",
                canonical_definition="공개되면 안 되는 가상 뜻풀이", student_definition="공개되면 안 되는 가상 뜻풀이",
                example_sentence="이것은 비공개 예문입니다.", example_target_form="가상비공개어휘",
                batch_id="DEMO_STUDENT_SEED", source_version="vocab_quiz_student_demo_v1",
                student_exposure=True, public_ready=True, hold_reason=None,
                is_active=True, content_hash="1" * 64,
            )
            db.session.add(c)
            db.session.flush()
            db.session.add(VocabQuizContentLevel(
                content_id=hold_cid, vocab_level=6, target_grade_band="L6 데모",
                level_status="REVIEW_BOUNDARY", boundary_flag=True,
                level_source="demo", level_version="demo_v1",
                level_reason_json=None, content_hash="1" * 64,
            ))
            db.session.add(VocabQuizPilotItem(
                item_id="DEMO_MC_HOLD_001", pilot_key="l6", item_type="MEANING_CHOICE",
                source_content_id=hold_cid, lemma="가상비공개어휘", pos="명사",
                prompt="'가상비공개어휘'의 뜻으로 가장 알맞은 것은?",
                options_json=json.dumps(["공개되면 안 되는 가상 뜻풀이", "x", "y", "z"], ensure_ascii=False),
                correct_option=1,
                public_payload_json=json.dumps({"options": ["공개되면 안 되는 가상 뜻풀이", "x", "y", "z"]}, ensure_ascii=False),
                answer_payload_json=json.dumps({"correct_option": 1}, ensure_ascii=False),
                explanation="이 문항은 REVIEW_BOUNDARY라 학생 화면에 보이면 안 됩니다.",
                source_version="vocab_quiz_student_demo_v1", is_active=True, item_hash="1" * 64,
            ))

        db.session.commit()
        print(f"공개 가능 콘텐츠 {len(created_contents)}건, 문항 {len(created_items)}건 생성(+ REVIEW_BOUNDARY 비공개 1건)")

        student = User.query.filter_by(email="demo-student@momolib.local").first()
        if not student:
            student = User(email="demo-student@momolib.local", name="데모학생",
                           role="student", is_active=True, is_verified=True)
            student.set_password("DemoStudent!2026")
            db.session.add(student)
            db.session.commit()
            print("데모 학생 계정 생성: demo-student@momolib.local / DemoStudent!2026")
        else:
            print("데모 학생 계정 이미 존재")


if __name__ == "__main__":
    main()
