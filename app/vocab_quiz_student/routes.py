# -*- coding: utf-8 -*-
"""학생용 어휘 퀴즈 연습 - 관리자 파일럿(app/vocab_quiz/routes.py)과 같은
문항 원본(vocab_quiz_pilot_items)을 읽지만, 문항을 고를 때는 반드시
app/vocab_quiz/eligibility.py의 단일 게이트를 거친다. 관리자 라우트의
인증 데코레이터(@requires_role('super_admin','hq_manager'))는 이 파일이
전혀 건드리지 않는다 - 학생용은 별도 블루프린트·별도 접근조건
(role == 'student')으로 완전히 분리한다.

채점·정답 비노출 로직은 관리자 파일럿 라우트와 동일한 패턴을 그대로
재사용한다(제출 전 GET 응답에 correct_option/answer_payload_json을
절대 포함하지 않고, POST 채점 이후에만 그 문항의 결과만 돌려준다)."""
from __future__ import annotations

import json
import random
from datetime import datetime

from flask import abort, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.models import db
from app.models.vocab_quiz import VocabQuizPilotItem
from app.models.vocab_quiz_student import VocabQuizStudentAttempt, VocabQuizStudentSession
from app.vocab_quiz.eligibility import (GATE_VERSION, VOCAB_LEVEL_LABELS, VOCAB_LEVELS,
                                         eligible_pilot_items, eligible_pilot_items_by_level,
                                         student_allowed_levels)
from app.vocab_quiz_student import vocab_quiz_student_bp

SESSION_ITEM_COUNT = 10


def _student_only() -> bool:
    return current_user.role == 'student'


def _log_event(event: str, **fields) -> None:
    """운영 중 집계할 최소 항목(시작/완료/오류 - 정답은 절대 포함하지
    않음)만 표준 형식으로 남긴다. 문항별 정오답·item_id는 이미
    vocab_quiz_student_attempts 테이블에 전부 기록되므로 로그에
    중복해서 남기지 않는다 - 집계는 그 테이블을 직접 조회한다."""
    parts = ' '.join(f'{k}={v}' for k, v in fields.items())
    current_app.logger.info(f'[vocab_quiz_student] event={event} {parts}')


@vocab_quiz_student_bp.route('/')
@login_required
def index():
    if not _student_only():
        abort(403)
    allowed_levels = student_allowed_levels(current_user.user_id)
    pool_counts_by_level = {lv: len(eligible_pilot_items_by_level(lv)) for lv in VOCAB_LEVELS if lv in allowed_levels}
    my_sessions = (
        VocabQuizStudentSession.query
        .filter_by(user_id=current_user.user_id)
        .order_by(VocabQuizStudentSession.started_at.desc())
        .limit(10).all()
    )
    return render_template('vocab_quiz_student/index.html',
                            pool_count=sum(pool_counts_by_level.values()),
                            pool_counts_by_level=pool_counts_by_level,
                            vocab_level_labels=VOCAB_LEVEL_LABELS,
                            session_item_count=SESSION_ITEM_COUNT,
                            my_sessions=my_sessions)


@vocab_quiz_student_bp.route('/start', methods=['POST'])
@login_required
def start():
    """vocab_level(4/5/6)을 명시적으로 받는다 - 요청에 실려 오는 값은
    화이트리스트(VOCAB_LEVELS)로만 검증하고, 실제 문항 선택은 항상
    eligible_pilot_items_by_level()을 거친다. 학생이 vocab_level 값을
    조작해도(범위 밖 숫자, 문자열, 생략 등) 게이트를 통과하지 못한
    콘텐츠나 다른 레벨의 문항은 절대 나올 수 없다."""
    if not _student_only():
        abort(403)

    body = request.get_json(silent=True) or {}
    raw_level = body.get('vocab_level', request.form.get('vocab_level'))
    if raw_level is None:
        _log_event('start_error', user_id=current_user.user_id, error='VOCAB_LEVEL_REQUIRED')
        return jsonify({'error': 'VOCAB_LEVEL_REQUIRED',
                         'detail': 'vocab_level(4/5/6)을 지정해야 합니다.'}), 400
    try:
        vocab_level = int(raw_level)
    except (TypeError, ValueError):
        _log_event('start_error', user_id=current_user.user_id, error='INVALID_VOCAB_LEVEL', raw_level=raw_level)
        return jsonify({'error': 'INVALID_VOCAB_LEVEL',
                         'detail': f'vocab_level은 {list(VOCAB_LEVELS)} 중 하나여야 합니다.'}), 400
    if vocab_level not in VOCAB_LEVELS:
        _log_event('start_error', user_id=current_user.user_id, error='INVALID_VOCAB_LEVEL', vocab_level=vocab_level)
        return jsonify({'error': 'INVALID_VOCAB_LEVEL',
                         'detail': f'vocab_level은 {list(VOCAB_LEVELS)} 중 하나여야 합니다.'}), 400

    if vocab_level not in student_allowed_levels(current_user.user_id):
        _log_event('start_error', user_id=current_user.user_id, error='LEVEL_NOT_ALLOWED', vocab_level=vocab_level)
        return jsonify({'error': 'LEVEL_NOT_ALLOWED',
                         'detail': '이 레벨은 파일럿 대상으로 허용되지 않았습니다.'}), 403

    pool = eligible_pilot_items_by_level(vocab_level)
    if not pool:
        _log_event('start_error', user_id=current_user.user_id, error='NO_ELIGIBLE_ITEMS', vocab_level=vocab_level)
        return jsonify({'error': 'NO_ELIGIBLE_ITEMS',
                         'detail': f'{VOCAB_LEVEL_LABELS[vocab_level]}(L{vocab_level})에 아직 공개된 문항이 없습니다.'}), 409

    n = min(SESSION_ITEM_COUNT, len(pool))
    chosen = random.sample(pool, n)
    order = [it.item_id for it in chosen]

    session = VocabQuizStudentSession(
        user_id=current_user.user_id,
        item_count=len(order),
        item_order_json=json.dumps(order),
        gate_version=GATE_VERSION,
        vocab_level=vocab_level,
        status='in_progress',
    )
    db.session.add(session)
    db.session.commit()
    _log_event('session_start', user_id=current_user.user_id, session_id=session.id,
               vocab_level=vocab_level, item_count=len(order))
    return jsonify({'session_id': session.id, 'item_count': len(order), 'vocab_level': vocab_level})


def _get_session_or_404(session_id: str) -> VocabQuizStudentSession:
    session = VocabQuizStudentSession.query.get_or_404(session_id)
    if session.user_id != current_user.user_id:
        abort(403)
    return session


@vocab_quiz_student_bp.route('/session/<session_id>')
@login_required
def take(session_id):
    if not _student_only():
        abort(403)
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
    return render_template('vocab_quiz_student/take.html', session=session, questions=questions)


@vocab_quiz_student_bp.route('/session/<session_id>/answer', methods=['POST'])
@login_required
def answer(session_id):
    if not _student_only():
        abort(403)
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

    existing = VocabQuizStudentAttempt.query.filter_by(session_id=session.id, item_id=item_id).first()
    is_correct = bool(int(selected_option) == item.correct_option)
    if existing:
        existing.selected_option = selected_option
        existing.correct_option = item.correct_option
        existing.is_correct = is_correct
        existing.answered_at = datetime.utcnow()
    else:
        db.session.add(VocabQuizStudentAttempt(
            session_id=session.id, item_id=item_id, order_index=order.index(item_id),
            selected_option=selected_option, correct_option=item.correct_option,
            is_correct=is_correct, answered_at=datetime.utcnow(),
        ))
        if is_correct:
            session.correct_count += 1
    db.session.commit()

    return jsonify({
        'item_id': item_id,
        'is_correct': is_correct,
        'correct_option': item.correct_option,
        'explanation': item.explanation,
    })


@vocab_quiz_student_bp.route('/session/<session_id>/complete', methods=['POST'])
@login_required
def complete(session_id):
    if not _student_only():
        abort(403)
    session = _get_session_or_404(session_id)
    if session.status == 'in_progress':
        session.status = 'completed'
        session.completed_at = datetime.utcnow()
        session.correct_count = VocabQuizStudentAttempt.query.filter_by(
            session_id=session.id, is_correct=True
        ).count()
        db.session.commit()
        _log_event('session_complete', user_id=current_user.user_id, session_id=session.id,
                   vocab_level=session.vocab_level, correct_count=session.correct_count,
                   item_count=session.item_count)
    return jsonify({'session_id': session.id, 'status': session.status,
                    'correct_count': session.correct_count, 'item_count': session.item_count})


@vocab_quiz_student_bp.route('/session/<session_id>/result')
@login_required
def result(session_id):
    if not _student_only():
        abort(403)
    session = _get_session_or_404(session_id)
    if session.status != 'completed':
        abort(400)
    attempts = (
        VocabQuizStudentAttempt.query.filter_by(session_id=session.id)
        .order_by(VocabQuizStudentAttempt.order_index).all()
    )
    items_by_id = {
        it.item_id: it for it in VocabQuizPilotItem.query
        .filter(VocabQuizPilotItem.item_id.in_([a.item_id for a in attempts])).all()
    }
    rows = [{
        'item': items_by_id.get(a.item_id),
        'attempt': a,
    } for a in attempts]
    return render_template('vocab_quiz_student/result.html', session=session, rows=rows)
