# -*- coding: utf-8 -*-
"""aprolabs(momo_b2b_tablet) 태블릿 교재 연동 - 2026-09-28 설계 문서 기준.

역할 분담: momolib은 학생 인증·교재 배정·진행 요약만 갖고, 교재 내용(제목 등
메타데이터 포함)은 절대 로컬에 복사·저장하지 않는다("같은 데이터를 두 곳에
쌓지 않는다") - 그래서 여기 함수들은 매번 aprolabs에 직접 물어보고, 그 결과를
디스크/DB에 캐싱하지 않는다(호출 빈도가 낮은 화면들이라 매번 조회해도 무리
없음 - 부담되면 나중에 짧은 TTL 캐시를 추가할 자리로 남겨둠).

서버 간 통신만 쓴다(브라우저를 거치지 않음) - APROLABS_PARTNER_API_KEY는
여기서만 쓰고 템플릿/JS로 절대 안 내려보낸다.
"""
import os
import requests

_TIMEOUT = 5


class AprolabsError(Exception):
    """aprolabs 호출 실패(네트워크·4xx/5xx) - 호출자가 사용자에게 보여줄 메시지를 판단"""


def _base_url() -> str:
    """서버 간 통신용(같은 서버 내부 또는 사설망) 주소."""
    return os.environ.get('APROLABS_BASE_URL', '').rstrip('/')


def _public_base_url() -> str:
    """학생 브라우저가 직접 여는 공개 주소 - _base_url()과 다를 수 있다
    (예: 내부는 http://127.0.0.1:8010, 공개는 https://momolib.com/tablet).
    미설정 시 _base_url()로 대체(로컬 개발 환경처럼 둘이 같은 경우)."""
    return os.environ.get('APROLABS_PUBLIC_BASE_URL', '').rstrip('/') or _base_url()


def _partner_key() -> str:
    return os.environ.get('APROLABS_PARTNER_API_KEY', '')


def get_edition_meta(edition_id: str | int) -> dict | None:
    """{doc_id, title, week, band, status} 또는 None(없음/오류 - 화면에서
    "(교재 정보를 불러올 수 없음)"으로 처리). /meta는 aprolabs 쪽에서 인증
    없이 열려 있는 전용 공개 엔드포인트(2026-09-28) - 전문·정답 등 민감한
    내용이 있는 전체 조회(/api/editions/{id})는 이제 로그인이 필요해져서
    momolib은 그 대신 이 메타데이터 전용 경로를 쓴다."""
    try:
        res = requests.get(f'{_base_url()}/api/editions/{edition_id}/meta', timeout=_TIMEOUT)
        if res.status_code != 200:
            return None
        data = res.json()
        return {
            'doc_id': data.get('doc_id'), 'title': data.get('title', ''),
            'week': data.get('week', ''), 'band': data.get('band', ''),
            'status': data.get('status'),
        }
    except requests.RequestException:
        return None


def list_approved_editions(query: str = '') -> list[dict]:
    """관리 화면 "교재 고르기" 목록 - 승인/발행된 교재만. query로 제목/문서ID
    간단 필터(서버가 목록 자체는 필터링 안 해주므로 여기서 부분일치)."""
    try:
        res = requests.get(
            f'{_base_url()}/api/partner/editions',
            headers={'X-Partner-Key': _partner_key()}, timeout=_TIMEOUT,
        )
        res.raise_for_status()
        editions = res.json().get('editions', [])
    except requests.RequestException as e:
        raise AprolabsError(f'aprolabs 교재 목록 조회 실패: {e}') from e

    if query:
        q = query.strip().lower()
        editions = [e for e in editions
                    if q in (e.get('title') or '').lower() or q in (e.get('doc_id') or '').lower()]
    return editions


def create_launch_session(partner_student_id: str, edition_id: str | int, return_url: str) -> dict:
    """{launch_token, expires_in} - 실패하면 AprolabsError."""
    try:
        res = requests.post(
            f'{_base_url()}/api/partner/sessions',
            headers={'X-Partner-Key': _partner_key()},
            json={'partner_student_id': partner_student_id, 'edition_id': int(edition_id),
                  'return_url': return_url},
            timeout=_TIMEOUT,
        )
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        raise AprolabsError(f'aprolabs 세션 발급 실패: {e}') from e


def launch_viewer_url(launch_token: str, edition_id: str | int) -> str:
    """학생이 새 창으로 열 최종 주소(mode=student, adapter=api) - 학생 브라우저가
    직접 접속하므로 공개 주소(_public_base_url)를 써야 한다."""
    return (f'{_public_base_url()}/renderer/viewer.html'
            f'?mode=student&adapter=api&edition={edition_id}&launch={launch_token}')
