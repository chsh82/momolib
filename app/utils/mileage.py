# -*- coding: utf-8 -*-
from datetime import datetime, date
from app.models import db
from app.models.avatar import MileageLog, MileageReason, StudentAvatar
from app.models.member import StudentProfile


def award_mileage(student_id, reason, description=None, ref_type=None, ref_id=None, amount=None):
    """
    학생에게 마일리지를 지급하고 MileageLog에 기록한다.
    amount가 None이면 MileageReason.AMOUNTS에서 자동으로 가져온다.
    중복 지급 방지: ref_type + ref_id 조합이 이미 있으면 스킵.
    """
    if amount is None:
        amount = MileageReason.AMOUNTS.get(reason, 0)
    if amount == 0:
        return None

    # 중복 방지: 같은 ref_type + ref_id가 이미 기록된 경우 스킵
    if ref_type and ref_id:
        exists = MileageLog.query.filter_by(
            student_id=student_id,
            ref_type=ref_type,
            ref_id=str(ref_id)
        ).first()
        if exists:
            return None

    profile = StudentProfile.query.filter_by(user_id=student_id).first()
    if not profile:
        return None

    profile.mileage = (profile.mileage or 0) + amount
    log = MileageLog(
        student_id=student_id,
        amount=amount,
        balance_after=profile.mileage,
        reason=reason,
        description=description,
        ref_type=ref_type,
        ref_id=str(ref_id) if ref_id else None,
    )
    db.session.add(log)
    return log


def deduct_mileage(student_id, amount, reason=MileageReason.ITEM_PURCHASE,
                   description=None, ref_type=None, ref_id=None):
    """마일리지 차감 (잔액 부족 시 False 반환)"""
    profile = StudentProfile.query.filter_by(user_id=student_id).first()
    if not profile or (profile.mileage or 0) < amount:
        return False

    profile.mileage -= amount
    log = MileageLog(
        student_id=student_id,
        amount=-amount,
        balance_after=profile.mileage,
        reason=reason,
        description=description,
        ref_type=ref_type,
        ref_id=str(ref_id) if ref_id else None,
    )
    db.session.add(log)
    return True


def check_daily_login(student_id):
    """오늘 일일 로그인 마일리지를 아직 안 받았으면 지급"""
    today_str = date.today().isoformat()
    award_mileage(
        student_id=student_id,
        reason=MileageReason.DAILY_LOGIN,
        description='일일 로그인 보상',
        ref_type='daily_login',
        ref_id=today_str,
    )


def get_or_create_avatar(student_id):
    """StudentAvatar 레코드가 없으면 기본값으로 생성"""
    avatar = StudentAvatar.query.filter_by(student_id=student_id).first()
    if not avatar:
        avatar = StudentAvatar(student_id=student_id)
        db.session.add(avatar)
    return avatar
