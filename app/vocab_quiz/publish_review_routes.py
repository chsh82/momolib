# -*- coding: utf-8 -*-
"""관리자 공개검토 화면 - 같은 블루프린트(app/vocab_quiz)의 기존
routes.py와 동일하게 @login_required + @requires_role('super_admin',
'hq_manager')만 허용한다(이 파일은 routes.py를 한 글자도 건드리지
않는다 - 완전히 별도 모듈로 추가).

이 화면의 판정 저장(POST .../verdict)은 vocab_quiz_admin_reviews 테이블
에만 쓴다 - student_exposure/public_ready/level_status/boundary_flag는
어떤 라우트에서도 바꾸지 않는다. 실제 공개 전환(그 값들을 바꾸는 것)은
이 파일에 아예 구현하지 않았다 - promote_dry_run()은 "무엇이 바뀔
예정인지"만 읽기 전용으로 계산해서 보여준다."""
from __future__ import annotations

import json

from flask import abort, render_template, request
from flask_login import current_user, login_required

from app.models.vocab_quiz import VocabQuizContent, VocabQuizContentLevel, VocabQuizPilotItem
from app.utils.decorators import requires_role
from app.vocab_quiz import vocab_quiz_bp
from app.vocab_quiz import publish_review as pr
from app.vocab_quiz.eligibility import content_is_eligible
from app.models.vocab_quiz_review import VERDICT_CHOICES, VERDICT_LABELS

_ADMIN_ROLES = ('super_admin', 'hq_manager')


@vocab_quiz_bp.route('/publish-review/')
@login_required
@requires_role(*_ADMIN_ROLES)
def publish_review_index():
    t1_ids = pr.tier1_content_ids()
    tier1 = VocabQuizContent.query.filter(VocabQuizContent.content_id.in_(t1_ids)).order_by(
        VocabQuizContent.lemma).all()

    tier1_rows = []
    for c in tier1:
        review = pr.latest_review(c.content_id)
        stale = pr.review_is_stale(review, c) if review else None
        tier1_rows.append({'content': c, 'review': review, 'stale': stale})

    tier2 = (
        VocabQuizContent.query
        .filter(VocabQuizContent.source_version == pr.TIER2_SOURCE_VERSION)
        .filter(~VocabQuizContent.content_id.in_(t1_ids))
        .order_by(VocabQuizContent.lemma).all()
    )
    tier3_count = (
        VocabQuizContent.query
        .filter(~VocabQuizContent.content_id.in_(t1_ids))
        .filter(VocabQuizContent.source_version != pr.TIER2_SOURCE_VERSION)
        .count()
    )

    return render_template(
        'vocab_quiz/publish_review_index.html',
        tier1_rows=tier1_rows, tier2=tier2, tier3_count=tier3_count,
        verdict_labels=VERDICT_LABELS,
    )


@vocab_quiz_bp.route('/publish-review/<content_id>')
@login_required
@requires_role(*_ADMIN_ROLES)
def publish_review_detail(content_id):
    content = VocabQuizContent.query.filter_by(content_id=content_id).first_or_404()
    levels = VocabQuizContentLevel.query.filter_by(content_id=content_id).all()
    items = pr.linked_items(content_id)
    items_with_notes = [
        {'item': it, 'note': pr.online_qa_note(it),
         'options': json.loads(it.options_json) if it.options_json else []}
        for it in items
    ]
    t1_ids = pr.tier1_content_ids()
    tier = pr.tier_of(content, t1_ids)
    history = pr.review_history(content_id)
    latest = history[0] if history else None
    stale = pr.review_is_stale(latest, content) if latest else None

    return render_template(
        'vocab_quiz/publish_review_detail.html',
        content=content, levels=levels, items_with_notes=items_with_notes,
        tier=tier, history=history, latest=latest, stale=stale,
        verdict_choices=VERDICT_CHOICES, verdict_labels=VERDICT_LABELS,
    )


@vocab_quiz_bp.route('/publish-review/<content_id>/verdict', methods=['POST'])
@login_required
@requires_role(*_ADMIN_ROLES)
def publish_review_save_verdict(content_id):
    VocabQuizContent.query.filter_by(content_id=content_id).first_or_404()
    verdict = request.form.get('verdict', '')
    rationale = request.form.get('rationale', '').strip()
    if verdict not in VERDICT_CHOICES:
        abort(400)
    if not rationale:
        abort(400, description='근거를 입력해야 합니다.')
    pr.save_review(content_id, verdict, rationale, current_user.user_id)
    return publish_review_detail(content_id)


@vocab_quiz_bp.route('/publish-review/promote-dry-run')
@login_required
@requires_role(*_ADMIN_ROLES)
def promote_dry_run():
    """읽기 전용. 실제로 아무것도 바꾸지 않는다 - '승격하면 무엇이
    바뀔지'만 계산해서 보여준다. POST/실행 경로 자체가 없다."""
    t1_ids = pr.tier1_content_ids()
    tier1 = VocabQuizContent.query.filter(VocabQuizContent.content_id.in_(t1_ids)).order_by(
        VocabQuizContent.lemma).all()

    rows = []
    for c in tier1:
        review = pr.latest_review(c.content_id)
        reasons_blocking = []

        if review is None:
            reasons_blocking.append('관리자 판정 없음')
        elif review.verdict != 'APPROVED_CANDIDATE':
            reasons_blocking.append(f"판정이 승인후보 아님({VERDICT_LABELS.get(review.verdict, review.verdict)})")
        elif pr.review_is_stale(review, c):
            reasons_blocking.append('판정 이후 콘텐츠/문항이 변경되어 판정이 최신 버전에 유효하지 않음')

        if c.hold_reason and c.hold_reason.strip():
            reasons_blocking.append(f'HOLD 사유 있음: {c.hold_reason}')
        if not c.is_active:
            reasons_blocking.append('콘텐츠 is_active=False')

        items = pr.linked_items(c.content_id)
        if not items:
            reasons_blocking.append('연결된 문항 없음')
        for it in items:
            if not it.is_active:
                reasons_blocking.append(f'문항 {it.item_id} is_active=False')
            if not it.options_json or not it.correct_option:
                reasons_blocking.append(f'문항 {it.item_id} 구조 불완전(선택지/정답 없음)')

        levels = VocabQuizContentLevel.query.filter_by(content_id=c.content_id).all()
        if not levels:
            reasons_blocking.append('연결된 레벨 없음')
        boundary_levels = [lv for lv in levels if lv.boundary_flag or lv.level_status == 'REVIEW_BOUNDARY']

        already_eligible = content_is_eligible(c)

        planned_changes = []
        if not reasons_blocking:
            if not c.student_exposure:
                planned_changes.append('student_exposure: False -> True')
            if not c.public_ready:
                planned_changes.append('public_ready: False -> True')
            for lv in boundary_levels:
                planned_changes.append(
                    f'레벨 L{lv.vocab_level}({lv.level_version}): '
                    f'level_status {lv.level_status} -> PROVISIONAL_AUTO, boundary_flag True -> False'
                )
            if not planned_changes:
                reasons_blocking.append('이미 공개 자격을 전부 충족한 상태(변경 불필요)')

        rows.append({
            'content': c,
            'review': review,
            'blocking': reasons_blocking,
            'planned_changes': planned_changes,
            'would_promote': bool(planned_changes) and not reasons_blocking,
            'already_eligible': already_eligible,
        })

    would_promote_count = sum(1 for r in rows if r['would_promote'])

    return render_template(
        'vocab_quiz/promote_dry_run.html',
        rows=rows, would_promote_count=would_promote_count, total=len(rows),
    )
