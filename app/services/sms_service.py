# -*- coding: utf-8 -*-
"""coolsms SMS 발송 서비스"""
import hmac
import hashlib
import time
import uuid
import requests
from flask import current_app


def _make_signature(api_key: str, api_secret: str) -> dict:
    """coolsms HMAC-SHA256 인증 헤더 생성"""
    date = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    salt = str(uuid.uuid4()).replace('-', '')
    data = f'{date}{salt}'
    signature = hmac.new(
        api_secret.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return {
        'Authorization': f'HMAC-SHA256 apiKey={api_key}, date={date}, salt={salt}, signature={signature}',
        'Content-Type': 'application/json',
    }


def send_sms(to: str, text: str) -> bool:
    """단문 SMS 발송. 성공 시 True, 실패 시 False"""
    api_key = current_app.config.get('SMS_API_KEY', '')
    api_secret = current_app.config.get('SMS_USER_ID', '')   # coolsms uses USER_ID as secret
    sender = current_app.config.get('SMS_SENDER', '')

    if not all([api_key, api_secret, sender]):
        current_app.logger.warning('SMS 설정 없음 — 발송 건너뜀')
        return False

    # 수신 번호 정규화 (하이픈 제거)
    to_clean = to.replace('-', '').replace(' ', '')
    if not to_clean.startswith('0'):
        current_app.logger.warning(f'잘못된 수신 번호: {to}')
        return False

    headers = _make_signature(api_key, api_secret)
    payload = {
        'message': {
            'to': to_clean,
            'from': sender.replace('-', ''),
            'text': text,
        }
    }

    try:
        resp = requests.post(
            'https://api.coolsms.co.kr/messages/v4/send',
            json=payload,
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        current_app.logger.error(f'SMS 발송 실패 {resp.status_code}: {resp.text[:200]}')
        return False
    except Exception as e:
        current_app.logger.error(f'SMS 발송 예외: {e}')
        return False


def send_correction_done(phone: str, student_name: str, book_title: str) -> bool:
    """첨삭 완료 알림 SMS"""
    text = f'[모모립] {student_name} 학생의 "{book_title}" 독서 서술형 첨삭이 완료되었습니다. 모모립에서 확인하세요.'
    return send_sms(phone, text)


def send_correction_finalized(phone: str, student_name: str, book_title: str) -> bool:
    """첨삭 최종 확정 알림 SMS"""
    text = f'[모모립] {student_name} 학생의 "{book_title}" 첨삭 결과가 최종 확정되었습니다. 모모립에서 확인하세요.'
    return send_sms(phone, text)
