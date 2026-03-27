# -*- coding: utf-8 -*-
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.avatar import avatar_bp
from app.models import db
from app.models.avatar import AvatarItem, StudentAvatar, StudentAvatarInventory, MileageLog
from app.models.member import StudentProfile
from app.utils.mileage import deduct_mileage, get_or_create_avatar

# 선택 가능한 기본 캐릭터 목록
CHARACTERS = [
    {'file': 'momo_girl_nobg.png',     'name': '모모',          'desc': '이야기 속 시간의 수호자'},
    {'file': 'old_man_broom_nobg.png', 'name': '베포',          'desc': '느리지만 꾸준한 청소부'},
    {'file': 'purple_boy_nobg.png',    'name': '기기',          'desc': '호기심 많은 모험가'},
    {'file': 'scientist_nobg.png',     'name': '호라박사',      'desc': '지혜로운 시간 관리자'},
    {'file': 'turtle_nobg.png',        'name': '카시오페이아',  'desc': '미래를 아는 거북이'},
    {'file': 'captain_nemo_nobg.png',  'name': '네모선장',      'desc': '바다 깊은 곳의 탐험가'},
    {'file': 'nature_boy_nobg.png',    'name': '콩세유',        'desc': '박식한 자연 관찰자'},
    {'file': 'traveler_nobg.png',      'name': '파스파르투',    'desc': '세계를 누비는 모험가'},
    {'file': 'indian_girl_nobg.png',   'name': '아우다부인',    'desc': '용감하고 우아한 여행자'},
]


def _student_only():
    return current_user.role == 'student'


@avatar_bp.route('/')
@login_required
def index():
    if not _student_only():
        abort(403)

    profile = StudentProfile.query.filter_by(user_id=current_user.user_id).first_or_404()
    avatar = get_or_create_avatar(current_user.user_id)
    db.session.commit()

    # 보유 아이템 ID 집합
    owned_ids = {inv.item_id for inv in StudentAvatarInventory.query.filter_by(
        student_id=current_user.user_id).all()}

    # 상점 아이템 (카테고리별 분류)
    shop_items = AvatarItem.query.filter_by(is_active=True).order_by(
        AvatarItem.category, AvatarItem.sort_order, AvatarItem.price).all()

    # 최근 마일리지 내역
    logs = MileageLog.query.filter_by(student_id=current_user.user_id)\
        .order_by(MileageLog.created_at.desc()).limit(10).all()

    return render_template('avatar/index.html',
                           profile=profile,
                           avatar=avatar,
                           characters=CHARACTERS,
                           shop_items=shop_items,
                           owned_ids=owned_ids,
                           mileage_logs=logs)


@avatar_bp.route('/character', methods=['POST'])
@login_required
def set_character():
    if not _student_only():
        abort(403)
    char_file = request.form.get('character', '')
    valid_files = {c['file'] for c in CHARACTERS}
    if char_file not in valid_files:
        flash('올바른 캐릭터가 아닙니다.', 'error')
        return redirect(url_for('avatar.index'))

    avatar = get_or_create_avatar(current_user.user_id)
    avatar.character = char_file
    db.session.commit()
    flash('캐릭터가 변경됐어요! 🎉', 'success')
    return redirect(url_for('avatar.index'))


@avatar_bp.route('/buy/<item_id>', methods=['POST'])
@login_required
def buy_item(item_id):
    if not _student_only():
        abort(403)

    item = AvatarItem.query.filter_by(item_id=item_id, is_active=True).first_or_404()

    # 이미 보유 중인지 확인
    already = StudentAvatarInventory.query.filter_by(
        student_id=current_user.user_id, item_id=item_id).first()
    if already:
        flash('이미 보유한 아이템이에요!', 'warning')
        return redirect(url_for('avatar.index'))

    # 마일리지 차감
    ok = deduct_mileage(
        student_id=current_user.user_id,
        amount=item.price,
        description=f'{item.name} 구매',
        ref_type='item_purchase',
        ref_id=item_id,
    )
    if not ok:
        flash('마일리지가 부족해요. 더 열심히 학습해보세요! 💪', 'error')
        return redirect(url_for('avatar.index'))

    # 인벤토리에 추가
    inv = StudentAvatarInventory(student_id=current_user.user_id, item_id=item_id)
    db.session.add(inv)
    db.session.commit()
    flash(f'{item.name}을(를) 구매했어요! 🎁', 'success')
    return redirect(url_for('avatar.index'))


@avatar_bp.route('/equip/<item_id>', methods=['POST'])
@login_required
def equip_item(item_id):
    if not _student_only():
        abort(403)

    # 보유 중인지 확인
    inv = StudentAvatarInventory.query.filter_by(
        student_id=current_user.user_id, item_id=item_id).first_or_404()

    avatar = get_or_create_avatar(current_user.user_id)
    equipped = dict(avatar.equipped or {})
    category = inv.item.category

    # 같은 카테고리에 이미 장착 중이면 해제, 아니면 장착
    if equipped.get(category) == item_id:
        equipped.pop(category, None)
        msg = '아이템을 해제했어요.'
    else:
        equipped[category] = item_id
        msg = f'{inv.item.name}을(를) 장착했어요! ✨'

    avatar.equipped = equipped
    db.session.commit()
    flash(msg, 'success')
    return redirect(url_for('avatar.index'))
