# -*- coding: utf-8 -*-
import os
import threading
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.essays import essays_bp
from app.models import db
from app.models.essay import Essay, EssayVersion, EssayResult
from app.models.notification import Notification
from app.models.member import GRADE_CHOICES


def _can_access(essay):
    """현재 사용자가 해당 에세이에 접근 가능한지 확인"""
    if current_user.is_hq:
        return True
    if current_user.role == 'student':
        return essay.student_id == current_user.user_id
    if current_user.role in ('teacher', 'branch_owner', 'branch_manager'):
        return essay.branch_id == current_user.branch_id
    return False


# ─── 학생: 과제 제출 ──────────────────────────────────────────

@essays_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if current_user.role != 'student':
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        original_text = request.form.get('original_text', '').strip()
        correction_model = request.form.get('correction_model', 'standard')
        teacher_guide = request.form.get('teacher_guide', '').strip()

        if not title or not original_text:
            flash('제목과 본문을 입력해주세요.', 'error')
            return render_template('essays/submit.html', grade_choices=GRADE_CHOICES)

        grade = ''
        if current_user.student_profile:
            grade = current_user.student_profile.grade or ''

        essay = Essay(
            branch_id=current_user.branch_id,
            student_id=current_user.user_id,
            title=title,
            original_text=original_text,
            grade=grade,
            correction_model=correction_model,
            teacher_guide=teacher_guide or None,
            status='draft',
        )
        db.session.add(essay)
        db.session.commit()

        flash('과제가 제출되었습니다.', 'success')
        return redirect(url_for('essays.student_essays'))

    return render_template('essays/submit.html', grade_choices=GRADE_CHOICES)


@essays_bp.route('/my')
@login_required
def student_essays():
    if current_user.role != 'student':
        return redirect(url_for('index'))

    essays = Essay.query.filter_by(student_id=current_user.user_id)\
        .order_by(Essay.created_at.desc()).all()
    return render_template('essays/student_list.html', essays=essays)


@essays_bp.route('/my/<essay_id>')
@login_required
def student_view(essay_id):
    essay = Essay.query.get_or_404(essay_id)
    if essay.student_id != current_user.user_id:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.student_essays'))

    html_content = None
    if essay.latest_version:
        html_content = essay.latest_version.html_content

    return render_template('essays/student_view.html', essay=essay,
                           html_content=html_content)


# ─── 강사/지점: 첨삭 관리 ────────────────────────────────────

@essays_bp.route('/manage')
@login_required
def manage():
    if current_user.role == 'student':
        return redirect(url_for('index'))

    status_filter = request.args.get('status', '')
    search = request.args.get('q', '').strip()

    if current_user.is_hq:
        query = Essay.query
    else:
        query = Essay.query.filter_by(branch_id=current_user.branch_id)

    if status_filter:
        query = query.filter(Essay.status == status_filter)
    if search:
        from app.models.user import User
        student_ids = [u.user_id for u in
                       User.query.filter(User.name.ilike(f'%{search}%')).all()]
        query = query.filter(
            (Essay.title.ilike(f'%{search}%')) |
            (Essay.student_id.in_(student_ids))
        )

    essays = query.order_by(Essay.created_at.desc()).all()

    counts = {}
    for s in ('draft', 'processing', 'reviewing', 'completed', 'failed'):
        q = Essay.query
        if not current_user.is_hq:
            q = q.filter_by(branch_id=current_user.branch_id)
        counts[s] = q.filter(Essay.status == s).count()

    return render_template('essays/manage.html', essays=essays, counts=counts,
                           status_filter=status_filter, search=search)


@essays_bp.route('/<essay_id>')
@login_required
def view_submission(essay_id):
    essay = Essay.query.get_or_404(essay_id)
    if not _can_access(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.manage'))

    return render_template('essays/view_submission.html', essay=essay)


@essays_bp.route('/<essay_id>/start', methods=['POST'])
@login_required
def start_correction(essay_id):
    """AI 첨삭 시작"""
    essay = Essay.query.get_or_404(essay_id)
    if not _can_access(essay):
        return jsonify({'error': '권한 없음'}), 403

    if essay.status == 'processing':
        return jsonify({'error': '이미 처리 중입니다.'}), 400

    # 선택적: 강사 가이드 업데이트
    guide = request.form.get('teacher_guide', '').strip()
    if guide:
        essay.teacher_guide = guide

    # 담당 강사 지정
    if current_user.role == 'teacher' and not essay.teacher_id:
        essay.teacher_id = current_user.user_id

    essay.status = 'processing'
    db.session.commit()

    # 백그라운드 스레드로 AI 첨삭 실행
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    t = threading.Thread(
        target=_correction_worker,
        args=(essay_id, api_key),
        daemon=True,
    )
    t.start()

    flash('첨삭을 시작했습니다. 처리 완료 후 알림을 받으실 수 있습니다.', 'success')
    return redirect(url_for('essays.view_submission', essay_id=essay_id))


def _correction_worker(essay_id, api_key):
    """백그라운드 첨삭 처리 + 완료 알림"""
    from app.services.correction_service import correct_essay
    correct_essay(essay_id, api_key)

    # 완료 후 알림 발송
    from app import create_app
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        essay = Essay.query.get(essay_id)
        if not essay or essay.status != 'reviewing':
            return

        # 학생 알림
        Notification.create(
            user_id=essay.student_id,
            title=f'"{essay.title}" 첨삭이 완료되었습니다',
            notif_type='essay_completed',
            message='선생님의 첨삭을 확인해보세요!',
            link_url=url_for('essays.student_view', essay_id=essay_id),
        )

        # 학부모 알림
        from app.models.member import ParentStudent
        for link in ParentStudent.query.filter_by(
                student_id=essay.student_id, is_active=True).all():
            Notification.create(
                user_id=link.parent_id,
                title=f'{essay.student.name} 학생의 첨삭이 완료되었습니다',
                notif_type='essay_completed',
                message=f'"{essay.title}"',
                link_url=url_for('essays.parent_view',
                                 essay_id=essay_id,
                                 student_id=essay.student_id),
            )
        db.session.commit()


@essays_bp.route('/<essay_id>/status')
@login_required
def status(essay_id):
    """AJAX 상태 조회"""
    essay = Essay.query.get_or_404(essay_id)
    if not _can_access(essay):
        return jsonify({'error': '권한 없음'}), 403
    return jsonify({
        'status': essay.status,
        'status_display': essay.status_display,
        'is_finalized': essay.is_finalized,
        'has_result': essay.result is not None,
    })


@essays_bp.route('/<essay_id>/result')
@login_required
def result(essay_id):
    """첨삭 결과 뷰어"""
    essay = Essay.query.get_or_404(essay_id)
    if not _can_access(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.manage'))

    html_content = None
    if essay.latest_version:
        html_content = essay.latest_version.html_content

    return render_template('essays/result.html', essay=essay, html_content=html_content)


@essays_bp.route('/<essay_id>/finalize', methods=['POST'])
@login_required
def finalize(essay_id):
    """최종 확정 → 학생/학부모 알림"""
    essay = Essay.query.get_or_404(essay_id)
    if not _can_access(essay):
        return jsonify({'error': '권한 없음'}), 403

    if essay.status not in ('reviewing', 'completed'):
        flash('검토 중 상태의 첨삭만 확정할 수 있습니다.', 'error')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    essay.is_finalized = True
    essay.status = 'completed'
    essay.finalized_at = datetime.utcnow()

    # 학생 알림
    Notification.create(
        user_id=essay.student_id,
        title=f'"{essay.title}" 첨삭이 최종 확정되었습니다',
        notif_type='essay_finalized',
        message='첨삭 결과를 확인해보세요!',
        link_url=url_for('essays.student_view', essay_id=essay_id),
    )

    # 학부모 알림
    from app.models.member import ParentStudent
    for link in ParentStudent.query.filter_by(
            student_id=essay.student_id, is_active=True).all():
        Notification.create(
            user_id=link.parent_id,
            title=f'{essay.student.name} 학생 첨삭이 확정되었습니다',
            notif_type='essay_finalized',
            message=f'"{essay.title}"',
        )

    db.session.commit()
    flash('첨삭이 최종 확정되었습니다. 학생과 학부모에게 알림을 보냈습니다.', 'success')
    return redirect(url_for('essays.result', essay_id=essay_id))


@essays_bp.route('/<essay_id>/regenerate', methods=['POST'])
@login_required
def regenerate(essay_id):
    """첨삭 재생성"""
    essay = Essay.query.get_or_404(essay_id)
    if not _can_access(essay):
        return jsonify({'error': '권한 없음'}), 403

    if essay.status == 'processing':
        flash('이미 처리 중입니다.', 'error')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    essay.status = 'processing'
    essay.is_finalized = False
    db.session.commit()

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    t = threading.Thread(
        target=_correction_worker,
        args=(essay_id, api_key),
        daemon=True,
    )
    t.start()

    flash('첨삭을 재생성합니다.', 'info')
    return redirect(url_for('essays.view_submission', essay_id=essay_id))


@essays_bp.route('/<essay_id>/delete', methods=['POST'])
@login_required
def delete(essay_id):
    """에세이 삭제 (관리자/강사/학생 본인)"""
    essay = Essay.query.get_or_404(essay_id)
    if not _can_access(essay):
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('essays.manage'))

    db.session.delete(essay)
    db.session.commit()
    flash('삭제되었습니다.', 'success')

    if current_user.role == 'student':
        return redirect(url_for('essays.student_essays'))
    return redirect(url_for('essays.manage'))


# ─── 학부모 뷰 ───────────────────────────────────────────────

@essays_bp.route('/parent/<student_id>')
@login_required
def parent_essays(student_id):
    if current_user.role != 'parent':
        return redirect(url_for('index'))

    from app.models.member import ParentStudent
    link = ParentStudent.query.filter_by(
        parent_id=current_user.user_id, student_id=student_id,
        is_active=True).first_or_404()

    essays = Essay.query.filter_by(student_id=student_id)\
        .order_by(Essay.created_at.desc()).all()

    from app.models.user import User
    student = User.query.get_or_404(student_id)

    return render_template('essays/parent_list.html', essays=essays, student=student)


@essays_bp.route('/parent/<student_id>/<essay_id>')
@login_required
def parent_view(student_id, essay_id):
    if current_user.role != 'parent':
        return redirect(url_for('index'))

    from app.models.member import ParentStudent
    ParentStudent.query.filter_by(
        parent_id=current_user.user_id, student_id=student_id,
        is_active=True).first_or_404()

    essay = Essay.query.filter_by(
        essay_id=essay_id, student_id=student_id).first_or_404()

    html_content = None
    if essay.is_finalized and essay.latest_version:
        html_content = essay.latest_version.html_content

    return render_template('essays/parent_view.html', essay=essay,
                           html_content=html_content)
