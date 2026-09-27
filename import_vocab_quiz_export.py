# -*- coding: utf-8 -*-
"""aprolabs 연구 사이트 export 패키지(data/vocab_quiz_import/,
data/vocab_quiz/pilot_*_manifest_v1.json)를 vocab_quiz_* 테이블로
가져온다. 기존 bank_questions/quiz_questions/curriculum* 등 어떤 기존
테이블도 건드리지 않는다.

기본은 항상 dry-run(SAVEPOINT 후 항상 ROLLBACK) - --apply를 줘야 실제
COMMIT한다. 자연키(content_id/item_id) 충돌 규칙:
  - DB에 없음               -> 신규 삽입
  - DB에 있고 내용 해시 동일 -> SKIP(멱등 재실행)
  - DB에 있고 내용 해시 다름 -> FAIL(그 건만 조용히 덮어쓰지 않고 즉시 중단,
                                 --apply 여부와 무관하게 dry-run에서도 검출)

사용(항상 먼저 dry-run):
    python import_vocab_quiz_export.py
    (검토 후) python import_vocab_quiz_export.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from app import create_app
from app.models import db
from app.models.vocab_quiz import VocabQuizContent, VocabQuizContentLevel, VocabQuizPilotItem

REPO_ROOT = Path(__file__).resolve().parent
EXPORT_DIR = REPO_ROOT / "data" / "vocab_quiz_import" / "vocab_quiz_momolib_export_v1"
MANIFEST_DIR = REPO_ROOT / "data" / "vocab_quiz"

CONTENT_NATURAL_FIELDS = [
    "content_id", "lemma", "pos", "canonical_definition", "student_definition",
    "example_sentence", "example_target_form", "batch_id", "source_version",
    "student_exposure", "public_ready", "hold_reason", "is_active",
]
LEVEL_NATURAL_FIELDS = [
    "content_id", "vocab_level", "target_grade_band", "level_status",
    "boundary_flag", "level_source", "level_version", "level_reason_json",
]
ITEM_NATURAL_FIELDS = [
    "item_id", "item_type", "source_content_id", "source_content_ids_json",
    "lemma", "pos", "prompt", "options_json", "correct_option",
    "public_payload_json", "answer_payload_json", "explanation", "source_version",
]


BOOL_FIELDS = {"student_exposure", "public_ready", "is_active", "boundary_flag"}


def _normalize_value(field: str, value):
    """SQLite export(0/1 정수)와 Postgres/SQLAlchemy(True/False)의 표현
    차이로 인한 거짓 충돌을 막기 위해, 불리언 필드는 항상 bool()로
    정규화한 뒤 해시한다 - 실제 값이 아니라 타입 표현 차이 때문에
    ConflictError가 발생하면 안 된다."""
    if field in BOOL_FIELDS and value is not None:
        return bool(value)
    return value


def row_hash(row: dict, fields: list[str]) -> str:
    blob = json.dumps(
        {f: _normalize_value(f, row.get(f)) for f in fields},
        ensure_ascii=False, sort_keys=True, default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ConflictError(Exception):
    """자연키는 같은데 내용 해시가 다름 - 조용히 덮어쓰지 않고 즉시 중단."""


def _content_row_current_hash(c: VocabQuizContent) -> str:
    """cur.content_hash 컬럼(캐시)을 믿지 않고, DB에 지금 실제로 들어있는
    값으로 해시를 다시 계산한다 - 캐시 컬럼만 비교하면 누가 UPDATE로 값을
    직접 바꿔도(캐시는 그대로) 충돌을 놓친다."""
    return row_hash({
        "content_id": c.content_id, "lemma": c.lemma, "pos": c.pos,
        "canonical_definition": c.canonical_definition, "student_definition": c.student_definition,
        "example_sentence": c.example_sentence, "example_target_form": c.example_target_form,
        "batch_id": c.batch_id, "source_version": c.source_version,
        "student_exposure": c.student_exposure, "public_ready": c.public_ready,
        "hold_reason": c.hold_reason, "is_active": c.is_active,
    }, CONTENT_NATURAL_FIELDS)


def _level_row_current_hash(lv: VocabQuizContentLevel) -> str:
    return row_hash({
        "content_id": lv.content_id, "vocab_level": lv.vocab_level,
        "target_grade_band": lv.target_grade_band, "level_status": lv.level_status,
        "boundary_flag": lv.boundary_flag, "level_source": lv.level_source,
        "level_version": lv.level_version, "level_reason_json": lv.level_reason_json,
    }, LEVEL_NATURAL_FIELDS)


def _item_row_current_hash(it: VocabQuizPilotItem) -> str:
    return row_hash({
        "item_id": it.item_id, "item_type": it.item_type,
        "source_content_id": it.source_content_id, "source_content_ids_json": it.source_content_ids_json,
        "lemma": it.lemma, "pos": it.pos, "prompt": it.prompt,
        "options_json": it.options_json, "correct_option": it.correct_option,
        "public_payload_json": it.public_payload_json, "answer_payload_json": it.answer_payload_json,
        "explanation": it.explanation, "source_version": it.source_version,
    }, ITEM_NATURAL_FIELDS)


def _sync_contents(export_contents: list[dict]) -> tuple[int, int]:
    inserted = skipped = 0
    existing = {c.content_id: c for c in VocabQuizContent.query.all()}
    for row in export_contents:
        h = row_hash(row, CONTENT_NATURAL_FIELDS)
        cur = existing.get(row["content_id"])
        if cur is None:
            db.session.add(VocabQuizContent(
                content_id=row["content_id"], lemma=row["lemma"], pos=row.get("pos"),
                canonical_definition=row.get("canonical_definition"),
                student_definition=row.get("student_definition"),
                example_sentence=row.get("example_sentence"),
                example_target_form=row.get("example_target_form"),
                batch_id=row.get("batch_id"), source_version=row["source_version"],
                student_exposure=bool(row.get("student_exposure")),
                public_ready=bool(row.get("public_ready")),
                hold_reason=row.get("hold_reason"),
                is_active=bool(row.get("is_active", True)),
                content_hash=h,
            ))
            inserted += 1
        elif _content_row_current_hash(cur) == h:
            skipped += 1
        else:
            raise ConflictError(
                f"content_id={row['content_id']!r} 자연키는 같지만 내용이 다릅니다 "
                f"(DB 현재 hash={_content_row_current_hash(cur)}, 신규 hash={h}) - 덮어쓰지 않고 중단합니다."
            )
    return inserted, skipped


def _sync_levels(export_levels: list[dict]) -> tuple[int, int]:
    inserted = skipped = 0
    existing = {
        (lv.content_id, lv.level_version): lv for lv in VocabQuizContentLevel.query.all()
    }
    for row in export_levels:
        h = row_hash(row, LEVEL_NATURAL_FIELDS)
        key = (row["content_id"], row["level_version"])
        cur = existing.get(key)
        if cur is None:
            db.session.add(VocabQuizContentLevel(
                content_id=row["content_id"], vocab_level=row["vocab_level"],
                target_grade_band=row.get("target_grade_band"),
                level_status=row["level_status"], boundary_flag=bool(row.get("boundary_flag")),
                level_source=row.get("level_source"), level_version=row["level_version"],
                level_reason_json=row.get("level_reason_json"), content_hash=h,
            ))
            inserted += 1
        elif _level_row_current_hash(cur) == h:
            skipped += 1
        else:
            raise ConflictError(
                f"(content_id={key[0]!r}, level_version={key[1]!r}) 자연키는 같지만 "
                f"내용이 다릅니다 - 덮어쓰지 않고 중단합니다."
            )
    return inserted, skipped


def _sync_pilot_items(pilot_key: str, rows: list[dict]) -> tuple[int, int]:
    inserted = skipped = 0
    existing = {
        it.item_id: it for it in VocabQuizPilotItem.query.filter_by(pilot_key=pilot_key).all()
    }
    for row in rows:
        h = row_hash(row, ITEM_NATURAL_FIELDS)
        cur = existing.get(row["item_id"])
        if cur is None:
            db.session.add(VocabQuizPilotItem(
                item_id=row["item_id"], pilot_key=pilot_key, item_type=row["item_type"],
                source_content_id=row.get("source_content_id"),
                source_content_ids_json=row.get("source_content_ids_json"),
                lemma=row.get("lemma"), pos=row.get("pos"), prompt=row["prompt"],
                options_json=row.get("options_json"), correct_option=row.get("correct_option"),
                public_payload_json=row.get("public_payload_json"),
                answer_payload_json=row["answer_payload_json"],
                explanation=row.get("explanation"), source_version=row["source_version"],
                is_active=True, item_hash=h,
            ))
            inserted += 1
        elif _item_row_current_hash(cur) == h:
            skipped += 1
        else:
            raise ConflictError(
                f"item_id={row['item_id']!r} 자연키는 같지만 내용이 다릅니다 - 중단합니다."
            )
    return inserted, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="기본은 dry-run. 이 플래그가 있어야 실제 COMMIT.")
    args = ap.parse_args()

    manifest_path = EXPORT_DIR / "export_manifest.json"
    if not manifest_path.exists():
        print(f"FAIL: export 패키지가 없습니다: {EXPORT_DIR}")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contents = json.loads((EXPORT_DIR / "contents.json").read_text(encoding="utf-8"))
    levels = json.loads((EXPORT_DIR / "content_levels.json").read_text(encoding="utf-8"))
    pilot_l4l5 = json.loads((MANIFEST_DIR / "pilot_l4l5_manifest_v1.json").read_text(encoding="utf-8"))
    pilot_l6 = json.loads((MANIFEST_DIR / "pilot_l6_manifest_v1.json").read_text(encoding="utf-8"))

    payload = manifest["exported_payload"]
    if len(contents) != payload["contents_count"] or len(levels) != payload["content_levels_count"]:
        print("FAIL: 로컬 파일 건수가 export_manifest.json과 다릅니다 - 파일이 손상됐거나 바뀌었습니다.")
        return 1
    if len(pilot_l4l5) != 40 or len(pilot_l6) != 40:
        print("FAIL: 파일럿 매니페스트가 40건이 아닙니다 - 중단.")
        return 1

    app = create_app("development")
    with app.app_context():
        try:
            n_c_ins, n_c_skip = _sync_contents(contents)
            n_l_ins, n_l_skip = _sync_levels(levels)
            n_p1_ins, n_p1_skip = _sync_pilot_items("l4l5", pilot_l4l5)
            n_p2_ins, n_p2_skip = _sync_pilot_items("l6", pilot_l6)
        except ConflictError as exc:
            db.session.rollback()
            print(f"FAIL(CONFLICT): {exc}")
            return 2

        print(f"contents: 신규 {n_c_ins}건, 스킵(동일) {n_c_skip}건")
        print(f"content_levels: 신규 {n_l_ins}건, 스킵(동일) {n_l_skip}건")
        print(f"pilot_items(l4l5): 신규 {n_p1_ins}건, 스킵(동일) {n_p1_skip}건")
        print(f"pilot_items(l6): 신규 {n_p2_ins}건, 스킵(동일) {n_p2_skip}건")

        if args.apply:
            db.session.commit()
            print("MODE=APPLY - 커밋 완료")
        else:
            db.session.rollback()
            print("MODE=DRY_RUN - 전부 롤백함(실제 반영 없음)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
