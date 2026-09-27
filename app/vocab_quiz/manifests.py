# -*- coding: utf-8 -*-
"""파일럿 매니페스트 로딩·정합성 검사 - aprolabs
app/vocabulary_quiz/routers/multiformat.py의 _load_pilot_manifest_rows/
_load_l6_pilot_manifest_rows와 동일한 방어 논리를 그대로 옮긴다: 매니페스트
파일이 없거나, 건수가 40이 아니거나, item_id가 중복이면 조용히 일부만
내놓지 않고 즉시 예외로 막는다. DB의 vocab_quiz_pilot_items와 매니페스트
파일이 정확히 같은 40개 item_id 집합인지도 매 세션 생성 시 다시 대조한다
(가져온 뒤 누가 실수로 데이터를 바꿔도 즉시 잡아낸다)."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

MANIFEST_PATHS = {
    'l4l5': REPO_ROOT / 'data' / 'vocab_quiz' / 'pilot_l4l5_manifest_v1.json',
    'l6': REPO_ROOT / 'data' / 'vocab_quiz' / 'pilot_l6_manifest_v1.json',
}
EXPECTED_ITEM_COUNT = 40

_cache: dict[str, list[dict]] = {}


class PilotManifestError(Exception):
    """매니페스트 파일 자체가 없거나/형식이 깨졌거나/DB와 불일치할 때."""


def load_manifest_rows(pilot_key: str) -> list[dict]:
    if pilot_key not in MANIFEST_PATHS:
        raise ValueError(f"알 수 없는 pilot_key: {pilot_key!r}")
    if pilot_key in _cache:
        return _cache[pilot_key]

    path = MANIFEST_PATHS[pilot_key]
    if not path.exists():
        raise PilotManifestError(
            f"[배포 오류] 파일럿 매니페스트 파일이 없습니다: {path} - 이 파일은 git으로 "
            "버전 관리되므로 정상 배포됐다면 항상 존재해야 합니다."
        )
    try:
        rows = json.loads(path.read_text(encoding='utf-8'))
        ids = [row['item_id'] for row in rows]
    except Exception as exc:  # noqa: BLE001 - 어떤 파싱 실패든 즉시 표면화
        raise PilotManifestError(f"매니페스트 파일을 읽을 수 없습니다: {path} ({exc})") from exc

    if len(ids) != EXPECTED_ITEM_COUNT or len(set(ids)) != len(ids):
        raise PilotManifestError(
            f"매니페스트가 예상({EXPECTED_ITEM_COUNT}건, 중복 0)과 다릅니다"
            f"(실제 {len(ids)}건, distinct {len(set(ids))}건): {path}"
        )

    _cache[pilot_key] = rows
    return rows


def expected_item_ids(pilot_key: str) -> frozenset[str]:
    return frozenset(row['item_id'] for row in load_manifest_rows(pilot_key))


def verify_db_matches_manifest(pilot_key: str, db_item_ids: set[str]) -> None:
    """DB에 실제로 들어있는 item_id 집합이 매니페스트와 정확히 같은지 확인.
    다르면(오염/누락) 즉시 예외 - 파일럿을 절대 일부만 내놓지 않는다."""
    expected = expected_item_ids(pilot_key)
    if db_item_ids != expected:
        missing = expected - db_item_ids
        unexpected = db_item_ids - expected
        raise PilotManifestError(
            f"파일럿({pilot_key}) DB 상태가 매니페스트와 다릅니다 - "
            f"누락 {len(missing)}건({sorted(missing)[:5]}...), "
            f"예상 밖 {len(unexpected)}건({sorted(unexpected)[:5]}...)"
        )
