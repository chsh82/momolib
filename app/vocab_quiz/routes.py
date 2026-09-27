# -*- coding: utf-8 -*-
"""schema_reading L4~L6 어휘 퀴즈 1차 이식 - 관리자 전용 미리보기 + 파일럿
응시·채점. 전 라우트 @login_required + @requires_role('super_admin',
'hq_manager') - 비로그인은 401, 비관리자는 403(app/utils/decorators.py의
기존 구현 그대로, 새 인증 계층을 만들지 않음).

절대 하지 않는 것: student_exposure/public_ready를 바꾸는 라우트, 기존
BankQuestion/QuizQuestion/LMS 라우트·모델 참조, GET 응답에 correct_option/
answer_payload_json 포함(제출 전 정답 비노출)."""
from __future__ import annotations

import json
from datetime import datetime

from flask import abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app.models import db
from app.models.vocab_quiz import (VocabQuizContent, VocabQuizContentLevel,
                                    VocabQuizPilotAttempt, VocabQuizPilotItem,
                                    VocabQuizPilotSession)
from app.utils.decorators import requires_role
from app.vocab_quiz import vocab_quiz_bp
from app.vocab_quiz.manifests import PilotManifestError, expected_item_ids

_ADMIN_ROLES = ('super_admin', 'hq_manager')


@vocab_quiz_bp.route('/')
@login_required
@requires_role(*_ADMIN_ROLES)
def index():
    total = VocabQuizContent.query.filter_by(is_active=True).count()
    by_source = (
        db.session.query(VocabQuizContent.source_version, db.func.count(VocabQuizContent.id))
        .filter(VocabQuizContent.is_active.is_(True))
        .group_by(VocabQuizContent.source_version)
        .all()
    )
    pilot_status = {}
    for key in ('l4l5', 'l6'):
        try:
            expected = expected_item_ids(key)
            db_ids = {
                r[0] for r in db.session.query(VocabQuizPilotItem.item_id)
                .filter_by(pilot_key=key, is_active=True).all()
            }
            pilot_status[key] = {
                'ok': db_ids == expected,
                'db_count': len(db_ids),
                'expected_count': len(expected),
            }
        except PilotManifestError as exc:
            pilot_status[key] = {'ok': False, 'error': str(exc)}
    return render_template('vocab_quiz/index.html', total=total, by_source=by_source,
                            pilot_status=pilot_status)


@vocab_quiz_bp.route('/contents')
@login_required
@requires_role(*_ADMIN_ROLES)
def content_list():
    source_version = request.args.get('source_version', '')
    q = VocabQuizContent.query.filter_by(is_active=True)
    if source_version:
        q = q.filter_by(source_version=source_version)
    contents = q.order_by(VocabQuizContent.lemma).all()
    all_versions = [r[0] for r in db.session.query(VocabQuizContent.source_version).distinct().all()]
    return render_template('vocab_quiz/content_list.html', contents=contents,
                            source_version=source_version, all_versions=sorted(all_versions))


@vocab_quiz_bp.route('/contents/<content_id>')
@login_required
@requires_role(*_ADMIN_ROLES)
def content_preview(content_id):
    content = VocabQuizContent.query.filter_by(content_id=content_id).first_or_404()
    levels = VocabQuizContentLevel.query.filter_by(content_id=content_id).all()
    return render_template('vocab_quiz/content_preview.html', content=content, levels=levels)


def _pilot_or_404(pilot_key: str) -> None:
    if pilot_key not in ('l4l5', 'l6'):
        abort(404)


@vocab_quiz_bp.route('/pilot/<pilot_key>')
@login_required
@requires_role(*_ADMIN_ROLES)
def pilot_info(pilot_key):
    _pilot_or_404(pilot_key)
    try:
        expected = expected_item_ids(pilot_key)
    except PilotManifestError as exc:
        return render_template('vocab_quiz/pilot_error.html', pilot_key=pilot_key, error=str(exc)), 500
    db_ids = {
        r[0] for r in db.session.query(VocabQuizPilotItem.item_id)
        .filter_by(pilot_key=pilot_key, is_active=True).all()
    }
    ok = db_ids == expected
    my_sessions = (
        VocabQuizPilotSession.query
        .filter_by(pilot_key=pilot_key, user_id=current_user.user_id)
        .order_by(VocabQuizPilotSession.started_at.desc())
        .limit(10).all()
    )
    return render_template('vocab_quiz/pilot_info.html', pilot_key=pilot_key, ok=ok,
                            db_count=len(db_ids), expected_count=len(expected), my_sessions=my_sessions)


@vocab_quiz_bp.route('/pilot/<pilot_key>/start', methods=['POST'])
@login_required
@requires_role(*_ADMIN_ROLES)
def pilot_start(pilot_key):
    _pilot_or_404(pilot_key)
    try:
        expected = expected_item_ids(pilot_key)
    except PilotManifestError as exc:
        return jsonify({'error': str(exc)}), 500

    items = (
        VocabQuizPilotItem.query
        .filter_by(pilot_key=pilot_key, is_active=True)
        .order_by(VocabQuizPilotItem.item_id)
        .all()
    )
    db_ids = {it.item_id for it in items}
    if db_ids != expected:
        missing = expected - db_ids
        unexpected = db_ids - expected
        return jsonify({
            'error': 'PILOT_BATCH_INTEGRITY_ERROR',
            'detail': f'매니페스트({len(expected)}건)와 DB({len(db_ids)}건)가 다릅니다',
            'missing': sorted(missing)[:5],
            'unexpected': sorted(unexpected)[:5],
        }), 500

    order = [it.item_id for it in items]
    session = VocabQuizPilotSession(
        pilot_key=pilot_key,
        user_id=current_user.user_id,
        question_count=len(order),
        item_order_json=json.dumps(order),
        status='in_progress',
    )
    db.session.add(session)
    db.session.commit()
    return jsonify({'session_id': session.id, 'question_count': len(order)})


def _get_session_or_404(session_id: str) -> VocabQuizPilotSession:
    session = VocabQuizPilotSession.query.get_or_404(session_id)
    if session.user_id != current_user.user_id and not current_user.is_super_admin:
        abort(403)
    return session


@vocab_quiz_bp.route('/pilot/session/<session_id>')
@login_required
@requires_role(*_ADMIN_ROLES)
def pilot_take(session_id):
    session = _get_session_or_404(session_id)
    order = json.loads(session.item_order_json)
    answered = {a.item_id: a for a in session.attempts}

    items_by_id = {
        it.item_id: it for it in VocabQuizPilotItem.query.filter(VocabQuizPilotItem.item_id.in_(order)).all()
    }
    questions = []
    for idx, item_id in enumerate(order):
        it = items_by_id.get(item_id)
        if it is None:
            continue
        att = answered.get(item_id)
        # 제출 전 정답 비노출: correct_option/answer_payload_json은 절대 포함하지 않는다.
        questions.append({
            'order_index': idx,
            'item_id': it.item_id,
            'item_type': it.item_type,
            'lemma': it.lemma,
            'prompt': it.prompt,
            'public_payload': json.loads(it.public_payload_json) if it.public_payload_json else None,
            'answered': att is not None,
            'selected_option': att.selected_option if att else None,
            'is_correct': att.is_correct if att else None,
        })
    return render_template('vocab_quiz/pilot_take.html', session=session, questions=questions)


@vocab_quiz_bp.route('/pilot/session/<session_id>/answer', methods=['POST'])
@login_required
@requires_role(*_ADMIN_ROLES)
def pilot_answer(session_id):
    session = _get_session_or_404(session_id)
    if session.status != 'in_progress':
        return jsonify({'error': 'SESSION_ALREADY_COMPLETED'}), 400

    body = request.get_json(force=True) or {}
    item_id = body.get('item_id')
    selected_option = body.get('selected_option')
    if not item_id or selected_option is None:
        return jsonify({'error': 'item_id, selected_option 필요'}), 400

    order = json.loads(session.item_order_json)
    if item_id not in order:
        return jsonify({'error': 'ITEM_NOT_IN_SESSION'}), 400

    item = VocabQuizPilotItem.query.filter_by(item_id=item_id).first_or_404()

    existing = VocabQuizPilotAttempt.query.filter_by(session_id=session.id, item_id=item_id).first()
    is_correct = bool(int(selected_option) == item.correct_option)
    if existing:
        existing.selected_option = selected_option
        existing.correct_option = item.correct_option
        existing.is_correct = is_correct
        existing.answered_at = datetime.utcnow()
    else:
        db.session.add(VocabQuizPilotAttempt(
            session_id=session.id, item_id=item_id, order_index=order.index(item_id),
            selected_option=selected_option, correct_option=item.correct_option,
            is_correct=is_correct, answered_at=datetime.utcnow(),
        ))
        if is_correct:
            session.correct_count += 1
    db.session.commit()

    # 제출(POST) 채점 이후에만 그 문항 결과를 돌려준다 - 다른 문항의 정답은 여전히 비노출.
    return jsonify({
        'item_id': item_id,
        'is_correct': is_correct,
        'correct_option': item.correct_option,
        'explanation': item.explanation,
    })


@vocab_quiz_bp.route('/pilot/session/<session_id>/complete', methods=['POST'])
@login_required
@requires_role(*_ADMIN_ROLES)
def pilot_complete(session_id):
    session = _get_session_or_404(session_id)
    if session.status == 'in_progress':
        session.status = 'completed'
        session.completed_at = datetime.utcnow()
        session.correct_count = VocabQuizPilotAttempt.query.filter_by(
            session_id=session.id, is_correct=True
        ).count()
        db.session.commit()
    return jsonify({'session_id': session.id, 'status': session.status,
                    'correct_count': session.correct_count, 'question_count': session.question_count})


@vocab_quiz_bp.route('/pilot/session/<session_id>/result')
@login_required
@requires_role(*_ADMIN_ROLES)
def pilot_result(session_id):
    session = _get_session_or_404(session_id)
    if session.status != 'completed':
        abort(400)
    attempts = (
        VocabQuizPilotAttempt.query.filter_by(session_id=session.id)
        .order_by(VocabQuizPilotAttempt.order_index).all()
    )
    items_by_id = {
        it.item_id: it for it in VocabQuizPilotItem.query
        .filter(VocabQuizPilotItem.item_id.in_([a.item_id for a in attempts])).all()
    }
    rows = [{
        'item': items_by_id.get(a.item_id),
        'attempt': a,
    } for a in attempts]
    return render_template('vocab_quiz/pilot_result.html', session=session, rows=rows)
