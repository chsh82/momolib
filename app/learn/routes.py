# -*- coding: utf-8 -*-
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.learn import learn_bp
from app.models import db
from app.models.lms import (StudentPackageAssignment, StudentItemProgress,
                              CurriculumItem)
from app.models.content_bank import BankQuestion, LectureVideo


def _student_only():
    return current_user.role == 'student'


@learn_bp.route('/')
@login_required
def index():
    if not _student_only(): abort(403)
    assignments = StudentPackageAssignment.query.filter_by(
        student_id=current_user.user_id, is_active=True
    ).order_by(StudentPackageAssignment.assigned_at.desc()).all()

    # 각 assignment 진도율 계산
    progress_map = {}
    for a in assignments:
        total = sum(len(pc.curriculum.items) for pc in a.package.curricula)
        if total == 0:
            progress_map[a.id] = None
            continue
        done = StudentItemProgress.query.filter_by(
            student_id=current_user.user_id,
            assignment_id=a.id,
            status='completed'
        ).count()
        progress_map[a.id] = round(done / total * 100)

    return render_template('learn/index.html',
                           assignments=assignments,
                           progress_map=progress_map)


@learn_bp.route('/<int:assignment_id>/')
@login_required
def package_view(assignment_id):
    if not _student_only(): abort(403)
    a = StudentPackageAssignment.query.filter_by(
        id=assignment_id,
        student_id=current_user.user_id,
        is_active=True
    ).first_or_404()

    # 커리큘럼별 진도율
    curriculum_progress = {}
    for pc in a.package.curricula:
        c = pc.curriculum
        total = len(c.items)
        if total == 0:
            curriculum_progress[c.curriculum_id] = None
            continue
        item_ids = [i.item_id for i in c.items]
        done = StudentItemProgress.query.filter(
            StudentItemProgress.student_id == current_user.user_id,
            StudentItemProgress.assignment_id == assignment_id,
            StudentItemProgress.item_id.in_(item_ids),
            StudentItemProgress.status == 'completed'
        ).count()
        curriculum_progress[c.curriculum_id] = (done, total)

    return render_template('learn/package.html',
                           assignment=a,
                           curriculum_progress=curriculum_progress)


@learn_bp.route('/<int:assignment_id>/<curriculum_id>/')
@login_required
def curriculum_view(assignment_id, curriculum_id):
    if not _student_only(): abort(403)
    a = StudentPackageAssignment.query.filter_by(
        id=assignment_id,
        student_id=current_user.user_id,
        is_active=True
    ).first_or_404()

    # 해당 curriculum이 패키지에 포함되어 있는지 확인
    curriculum = next(
        (pc.curriculum for pc in a.package.curricula
         if pc.curriculum_id == curriculum_id), None
    )
    if curriculum is None:
        abort(404)

    # 아이템별 진도 조회
    item_ids = [item.item_id for item in curriculum.items]
    progresses = {
        p.item_id: p
        for p in StudentItemProgress.query.filter(
            StudentItemProgress.student_id == current_user.user_id,
            StudentItemProgress.assignment_id == assignment_id,
            StudentItemProgress.item_id.in_(item_ids)
        ).all()
    }

    return render_template('learn/curriculum.html',
                           assignment=a,
                           curriculum=curriculum,
                           progresses=progresses)


@learn_bp.route('/<int:assignment_id>/item/<int:item_id>/')
@login_required
def item_view(assignment_id, item_id):
    if not _student_only(): abort(403)
    a = StudentPackageAssignment.query.filter_by(
        id=assignment_id,
        student_id=current_user.user_id,
        is_active=True
    ).first_or_404()

    item = CurriculumItem.query.get_or_404(item_id)

    # 해당 아이템이 배정된 패키지에 포함되어 있는지 확인
    valid = any(
        item.curriculum_id == pc.curriculum_id
        for pc in a.package.curricula
    )
    if not valid:
        abort(404)

    # 진도 레코드 가져오기 (없으면 생성)
    progress = StudentItemProgress.query.filter_by(
        student_id=current_user.user_id,
        assignment_id=assignment_id,
        item_id=item_id
    ).first()
    if progress is None:
        progress = StudentItemProgress(
            student_id=current_user.user_id,
            assignment_id=assignment_id,
            item_id=item_id,
            status='in_progress',
            started_at=datetime.utcnow(),
        )
        db.session.add(progress)
        db.session.commit()
    elif progress.status == 'not_started':
        progress.status = 'in_progress'
        progress.started_at = datetime.utcnow()
        db.session.commit()

    # 콘텐츠 객체 로드
    content = item.content_object

    # 이전/다음 아이템 계산
    all_items = item.curriculum.items
    idx = next((i for i, x in enumerate(all_items) if x.item_id == item_id), None)
    prev_item = all_items[idx - 1] if idx and idx > 0 else None
    next_item = all_items[idx + 1] if idx is not None and idx < len(all_items) - 1 else None

    return render_template('learn/item.html',
                           assignment=a,
                           item=item,
                           content=content,
                           progress=progress,
                           prev_item=prev_item,
                           next_item=next_item)


@learn_bp.route('/<int:assignment_id>/item/<int:item_id>/submit', methods=['POST'])
@login_required
def item_submit(assignment_id, item_id):
    if not _student_only(): abort(403)
    a = StudentPackageAssignment.query.filter_by(
        id=assignment_id,
        student_id=current_user.user_id,
        is_active=True
    ).first_or_404()

    item = CurriculumItem.query.get_or_404(item_id)
    progress = StudentItemProgress.query.filter_by(
        student_id=current_user.user_id,
        assignment_id=assignment_id,
        item_id=item_id
    ).first_or_404()

    content = item.content_object
    score = None
    response_data = {}

    if item.content_type == 'vocab_quiz':
        chosen = request.form.get('answer')
        correct_idx = str(content.data.get('correct_idx', ''))
        score = 1.0 if chosen == correct_idx else 0.0
        response_data = {'chosen': chosen, 'correct_idx': correct_idx}

    elif item.content_type == 'book_quiz':
        fmt = content.data.get('format', 'multiple')
        if fmt == 'ox':
            chosen = request.form.get('answer')
            correct = content.data.get('correct', '')
            score = 1.0 if chosen == correct else 0.0
            response_data = {'chosen': chosen, 'correct': correct}
        elif fmt == 'multiple':
            chosen = request.form.get('answer')
            correct_idx = str(content.data.get('correct_idx', ''))
            score = 1.0 if chosen == correct_idx else 0.0
            response_data = {'chosen': chosen, 'correct_idx': correct_idx}
        else:  # short
            answer = request.form.get('answer', '').strip()
            correct = content.data.get('correct_answer', '').strip()
            score = 1.0 if answer.lower() == correct.lower() else 0.0
            response_data = {'answer': answer, 'correct_answer': correct}

    elif item.content_type == 'reading_quiz':
        # 토론질문: 답변 텍스트 저장, 점수 없음
        answer = request.form.get('answer', '').strip()
        response_data = {'answer': answer}

    elif item.content_type == 'video':
        # 영상: 완료 처리
        response_data = {}

    elif item.content_type == 'essay':
        essay_text = request.form.get('essay_text', '').strip()
        response_data = {'essay_text': essay_text}

    progress.status = 'completed'
    progress.score = score
    progress.response_data = response_data
    progress.completed_at = datetime.utcnow()
    db.session.commit()

    flash('제출 완료!', 'success')
    # 다음 아이템으로 이동
    all_items = item.curriculum.items
    idx = next((i for i, x in enumerate(all_items) if x.item_id == item_id), None)
    if idx is not None and idx < len(all_items) - 1:
        next_id = all_items[idx + 1].item_id
        return redirect(url_for('learn.item_view',
                                assignment_id=assignment_id, item_id=next_id))
    return redirect(url_for('learn.curriculum_view',
                            assignment_id=assignment_id,
                            curriculum_id=item.curriculum_id))
