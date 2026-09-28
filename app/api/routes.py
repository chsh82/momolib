# -*- coding: utf-8 -*-
"""외부 파트너(aprolabs 등)가 momolib에 보내는 서버 간 알림 수신 - 2026-09-28
설계 문서 §[2]. 브라우저를 거치지 않는 서버-서버 호출이라 @login_required
대신 공유 비밀키(X-Aprolabs-Notify-Key)로 인증한다."""
import os
from datetime import datetime
from flask import request, jsonify
from app.api import api_bp
from app.models import db
from app.models.lms import CurriculumItem, StudentPackageAssignment, StudentItemProgress
from app.models.avatar import MileageReason
from app.utils.mileage import award_mileage


@api_bp.route('/aprolabs/progress', methods=['POST'])
def aprolabs_progress():
    if request.headers.get('X-Aprolabs-Notify-Key') != os.environ.get('APROLABS_NOTIFY_SECRET'):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    partner_student_id = data.get('partner_student_id')
    edition_id = data.get('edition_id')
    if not partner_student_id or edition_id is None:
        return jsonify({'ok': False, 'error': 'missing_fields'}), 400

    # partner_student_id는 momolib이 발급한 학생 가명(=momolib student_id 그대로)
    item = CurriculumItem.query.filter_by(
        content_type='b2b_workbook', content_id=str(edition_id)
    ).first()
    if item is None:
        return jsonify({'ok': False, 'error': 'item_not_found'}), 404

    # 이 교재가 들어있는 커리큘럼을 배정받은, 그 학생의 활성 배정을 찾는다
    assignments = StudentPackageAssignment.query.filter_by(
        student_id=partner_student_id, is_active=True
    ).all()
    assignment = next(
        (a for a in assignments
         if any(pc.curriculum_id == item.curriculum_id for pc in a.package.curricula)),
        None,
    )
    if assignment is None:
        return jsonify({'ok': False, 'error': 'assignment_not_found'}), 404

    row = StudentItemProgress.query.filter_by(
        student_id=partner_student_id, assignment_id=assignment.id, item_id=item.item_id
    ).first()
    if row is None:
        row = StudentItemProgress(
            student_id=partner_student_id, assignment_id=assignment.id, item_id=item.item_id,
            status='in_progress', started_at=datetime.utcnow(),
        )
        db.session.add(row)
    elif row.status == 'not_started':
        row.status = 'in_progress'
        row.started_at = row.started_at or datetime.utcnow()

    row.response_data = {
        'progress': data.get('progress'),
        'last_activity_at': data.get('last_activity_at'),
    }
    if data.get('completed'):
        row.status = 'completed'
        row.completed_at = row.completed_at or datetime.utcnow()

    db.session.commit()

    # 2026-09-28: 완료 통지를 받는 시점(=aprolabs가 "학생이 학습 목록으로
    # 돌아갔다"고 알려주는 시점)에 다른 콘텐츠 타입과 같은 방식으로 마일리지
    # 지급. award_mileage가 ref_type+ref_id로 중복 지급을 막아주므로,
    # 통지가 여러 번 와도(재시도 등) 안전하게 한 번만 지급된다.
    if data.get('completed'):
        award_mileage(
            partner_student_id, MileageReason.LMS_WORKBOOK,
            description='태블릿 교재 완료',
            ref_type='lms_item', ref_id=f'lms_item_{item.item_id}',
        )

    return jsonify({'ok': True})
