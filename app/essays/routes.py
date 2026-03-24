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


# ─── 권한 헬퍼 ───────────────────────────────────────────────

def _can_view(essay):
    """조회 가능: HQ 전체 + 같은 지점 강사/운영진 + 본인 학생"""
    if current_user.is_hq:
        return True
    if current_user.role == 'student':
        return essay.student_id == current_user.user_id
    if current_user.role in ('teacher', 'branch_owner', 'branch_manager'):
        return essay.branch_id == current_user.branch_id
    return False


def _can_ai_correct(essay):
    """AI 첨삭 시작: 본사(HQ)만 가능"""
    return current_user.is_hq  # super_admin, hq_manager, hq_essay_manager


def _can_manual_correct(essay):
    """수동 첨삭: 강사(같은 지점) + 본사 모든 계정"""
    if current_user.is_hq:
        return True
    return (current_user.role == 'teacher' and
            essay.branch_id == current_user.branch_id)


def _can_finalize(essay):
    """확정: HQ + 지점 운영진 + 강사"""
    if current_user.is_hq:
        return True
    if current_user.role in ('branch_owner', 'branch_manager'):
        return essay.branch_id == current_user.branch_id
    if current_user.role == 'teacher':
        return essay.branch_id == current_user.branch_id
    return False


def _can_delete(essay):
    """삭제: HQ + 지점장/매니저 + 강사"""
    if current_user.is_hq:
        return True
    if current_user.role in ('branch_owner', 'branch_manager', 'teacher'):
        return essay.branch_id == current_user.branch_id
    return False


# ─── 알림 발송 공통 ──────────────────────────────────────────

def _notify_student_and_parents(essay, title, message=''):
    Notification.create(
        user_id=essay.student_id,
        title=title,
        notif_type='essay_finalized',
        message=message,
        link_url=url_for('essays.student_view', essay_id=essay.essay_id),
    )
    from app.models.member import ParentStudent
    for link in ParentStudent.query.filter_by(
            student_id=essay.student_id, is_active=True).all():
        Notification.create(
            user_id=link.parent_id,
            title=f'{essay.student.name} 학생: {title}',
            notif_type='essay_finalized',
            message=message,
        )


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

        # 이용권 체크 (크레딧이 설정된 학생만)
        from app.models.credit import EssayCredit
        credit = EssayCredit.query.filter_by(
            student_id=current_user.user_id).first()
        if credit and credit.remaining <= 0:
            flash('이용권이 부족합니다. 지점에 문의해주세요.', 'error')
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
        db.session.flush()

        # 크레딧 차감
        if credit and credit.remaining > 0:
            credit.deduct(1, note=f'제출: {title[:30]}')

        db.session.commit()
        flash('과제가 제출되었습니다.', 'success')
        return redirect(url_for('essays.student_essays'))

    return render_template('essays/submit.html', grade_choices=GRADE_CHOICES)


@essays_bp.route('/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return redirect(url_for('index'))
    total = Essay.query.filter_by(student_id=current_user.user_id).count()
    completed = Essay.query.filter_by(
        student_id=current_user.user_id, status='completed').count()
    reviewing = Essay.query.filter_by(
        student_id=current_user.user_id, status='reviewing').count()
    draft = Essay.query.filter_by(
        student_id=current_user.user_id, status='draft').count()
    recent = Essay.query.filter_by(student_id=current_user.user_id)\
        .order_by(Essay.created_at.desc()).limit(5).all()
    from app.models.credit import EssayCredit
    credit = EssayCredit.query.filter_by(
        student_id=current_user.user_id).first()
    return render_template('essays/student_dashboard.html',
                           total=total, completed=completed,
                           reviewing=reviewing, draft=draft,
                           recent=recent, credit=credit)


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
    if essay.is_finalized and essay.latest_version:
        html_content = essay.latest_version.html_content

    return render_template('essays/student_view.html', essay=essay,
                           html_content=html_content)


# ─── 관리자/강사: 첨삭 관리 ──────────────────────────────────

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
    if not _can_view(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.manage'))

    return render_template('essays/view_submission.html', essay=essay,
                           can_ai_correct=_can_ai_correct(essay),
                           can_manual_correct=_can_manual_correct(essay),
                           can_finalize=_can_finalize(essay),
                           can_delete=_can_delete(essay))


# ─── AI 첨삭 (본사 전용) ─────────────────────────────────────

@essays_bp.route('/<essay_id>/start', methods=['POST'])
@login_required
def start_correction(essay_id):
    essay = Essay.query.get_or_404(essay_id)
    if not _can_ai_correct(essay):
        flash('AI 첨삭은 본사 계정만 실행할 수 있습니다.', 'error')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    if essay.status == 'processing':
        flash('이미 처리 중입니다.', 'error')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    guide = request.form.get('teacher_guide', '').strip()
    if guide:
        essay.teacher_guide = guide

    essay.teacher_id = current_user.user_id
    essay.status = 'processing'
    db.session.commit()

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    t = threading.Thread(
        target=_correction_worker, args=(essay_id, api_key), daemon=True)
    t.start()

    flash('AI 첨삭을 시작했습니다. 처리 완료 후 알림이 전송됩니다.', 'success')
    return redirect(url_for('essays.view_submission', essay_id=essay_id))


def _correction_worker(essay_id, api_key):
    from app.services.correction_service import correct_essay
    correct_essay(essay_id, api_key)

    from app import create_app
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        essay = Essay.query.get(essay_id)
        if not essay or essay.status != 'reviewing':
            return
        _notify_student_and_parents(
            essay,
            title=f'"{essay.title}" AI 첨삭이 완료되었습니다',
            message='선생님의 검토 후 최종 확정됩니다.',
        )
        # SMS 알림: 학부모에게 발송
        from app.services.sms_service import send_correction_done
        from app.models.member import ParentStudent
        from app.models.user import User
        student = essay.student
        for link in ParentStudent.query.filter_by(
                student_id=essay.student_id, is_active=True).all():
            parent = User.query.get(link.parent_id)
            if parent and parent.phone:
                send_correction_done(
                    parent.phone,
                    student.name if student else '학생',
                    essay.title,
                )
        db.session.commit()


# ─── 수동 첨삭 (강사 전용) ────────────────────────────────────

@essays_bp.route('/<essay_id>/manual', methods=['GET', 'POST'])
@login_required
def manual_correction(essay_id):
    essay = Essay.query.get_or_404(essay_id)
    if not _can_manual_correct(essay):
        flash('수동 첨삭은 담당 강사만 작성할 수 있습니다.', 'error')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    if request.method == 'POST':
        html_content = request.form.get('html_content', '').strip()
        if not html_content:
            flash('첨삭 내용을 입력해주세요.', 'error')
            return render_template('essays/manual_correction.html', essay=essay)

        version_number = (essay.current_version or 0) + 1
        version = EssayVersion(
            essay_id=essay_id,
            version_number=version_number,
            html_content=html_content,
            revision_note='수동 첨삭',
        )
        db.session.add(version)
        db.session.flush()

        # 결과 업데이트
        total_score_str = request.form.get('total_score', '').strip()
        final_grade = request.form.get('final_grade', '').strip()
        total_score = float(total_score_str) if total_score_str else None

        if essay.result:
            essay.result.version_id = version.version_id
            essay.result.total_score = total_score
            essay.result.final_grade = final_grade or None
        else:
            result = EssayResult(
                essay_id=essay_id,
                version_id=version.version_id,
                total_score=total_score,
                final_grade=final_grade or None,
            )
            db.session.add(result)

        essay.current_version = version_number
        essay.teacher_id = current_user.user_id
        essay.status = 'reviewing'
        essay.completed_at = datetime.utcnow()
        db.session.commit()

        flash('수동 첨삭이 저장되었습니다. 확정 후 학생에게 전달됩니다.', 'success')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    # 기존 버전이 있으면 불러오기
    existing_content = ''
    if essay.latest_version:
        existing_content = essay.latest_version.html_content or ''

    return render_template('essays/manual_correction.html', essay=essay,
                           existing_content=existing_content)


# ─── 공통: 상태/확정/재생성/삭제 ─────────────────────────────

@essays_bp.route('/<essay_id>/status')
@login_required
def status(essay_id):
    essay = Essay.query.get_or_404(essay_id)
    if not _can_view(essay):
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
    essay = Essay.query.get_or_404(essay_id)
    if not _can_view(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.manage'))

    html_content = None
    if essay.latest_version:
        html_content = essay.latest_version.html_content

    return render_template('essays/result.html', essay=essay,
                           html_content=html_content,
                           can_finalize=_can_finalize(essay))


@essays_bp.route('/<essay_id>/finalize', methods=['POST'])
@login_required
def finalize(essay_id):
    essay = Essay.query.get_or_404(essay_id)
    if not _can_finalize(essay):
        flash('확정 권한이 없습니다.', 'error')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    if essay.status not in ('reviewing', 'completed'):
        flash('검토 중 상태의 첨삭만 확정할 수 있습니다.', 'error')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    essay.is_finalized = True
    essay.status = 'completed'
    essay.finalized_at = datetime.utcnow()

    _notify_student_and_parents(
        essay,
        title=f'"{essay.title}" 첨삭이 최종 확정되었습니다',
        message='첨삭 결과를 확인해보세요!',
    )
    # SMS 알림: 학생 + 학부모
    from app.services.sms_service import send_correction_finalized
    from app.models.member import ParentStudent
    from app.models.user import User
    if essay.student and essay.student.phone:
        send_correction_finalized(essay.student.phone, essay.student.name, essay.title)
    for link in ParentStudent.query.filter_by(
            student_id=essay.student_id, is_active=True).all():
        parent = User.query.get(link.parent_id)
        if parent and parent.phone:
            send_correction_finalized(parent.phone, essay.student.name, essay.title)
    db.session.commit()

    flash('최종 확정되었습니다. 학생과 학부모에게 알림을 보냈습니다.', 'success')
    return redirect(url_for('essays.result', essay_id=essay_id))


@essays_bp.route('/<essay_id>/regenerate', methods=['POST'])
@login_required
def regenerate(essay_id):
    essay = Essay.query.get_or_404(essay_id)
    if not _can_ai_correct(essay):
        flash('AI 첨삭 재생성은 본사 계정만 가능합니다.', 'error')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    if essay.status == 'processing':
        flash('이미 처리 중입니다.', 'error')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    essay.status = 'processing'
    essay.is_finalized = False
    db.session.commit()

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    t = threading.Thread(
        target=_correction_worker, args=(essay_id, api_key), daemon=True)
    t.start()

    flash('첨삭을 재생성합니다.', 'info')
    return redirect(url_for('essays.view_submission', essay_id=essay_id))


@essays_bp.route('/<essay_id>/delete', methods=['POST'])
@login_required
def delete(essay_id):
    essay = Essay.query.get_or_404(essay_id)
    if not _can_delete(essay):
        flash('삭제 권한이 없습니다.', 'error')
        return redirect(url_for('essays.manage'))

    db.session.delete(essay)
    db.session.commit()
    flash('삭제되었습니다.', 'success')

    if current_user.role == 'student':
        return redirect(url_for('essays.student_essays'))
    return redirect(url_for('essays.manage'))


# ─── 학부모 대시보드 ──────────────────────────────────────────

@essays_bp.route('/parent/dashboard')
@login_required
def parent_dashboard():
    if current_user.role != 'parent':
        return redirect(url_for('index'))
    from app.models.member import ParentStudent
    from app.models.user import User
    links = ParentStudent.query.filter_by(
        parent_id=current_user.user_id, is_active=True).all()
    children = []
    for link in links:
        student = User.query.get(link.student_id)
        if not student:
            continue
        total = Essay.query.filter_by(student_id=student.user_id).count()
        completed = Essay.query.filter_by(
            student_id=student.user_id, status='completed').count()
        pending = Essay.query.filter_by(
            student_id=student.user_id, status='draft').count()
        recent = Essay.query.filter_by(student_id=student.user_id)\
            .order_by(Essay.created_at.desc()).limit(3).all()
        children.append({
            'student': student,
            'relation': link.relation,
            'total': total,
            'completed': completed,
            'pending': pending,
            'recent': recent,
        })
    return render_template('essays/parent_dashboard.html', children=children)


# ─── 학부모 뷰 ───────────────────────────────────────────────

@essays_bp.route('/parent/<student_id>')
@login_required
def parent_essays(student_id):
    if current_user.role != 'parent':
        return redirect(url_for('index'))
    from app.models.member import ParentStudent
    ParentStudent.query.filter_by(
        parent_id=current_user.user_id, student_id=student_id,
        is_active=True).first_or_404()
    from app.models.user import User
    student = User.query.get_or_404(student_id)
    essays = Essay.query.filter_by(student_id=student_id)\
        .order_by(Essay.created_at.desc()).all()
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


# ─── 학생: 성적 분석 ──────────────────────────────────────────

@essays_bp.route('/my/scores')
@login_required
def student_scores():
    if current_user.role != 'student':
        return redirect(url_for('index'))

    essays = (Essay.query
        .filter_by(student_id=current_user.user_id, status='completed')
        .order_by(Essay.created_at.asc()).all())

    chart_labels = []
    chart_scores = []
    score_list = []
    for e in essays:
        if e.result and e.result.total_score is not None:
            chart_labels.append(e.created_at.strftime('%m/%d'))
            chart_scores.append(e.result.total_score)
            score_list.append({
                'essay': e,
                'score': e.result.total_score,
                'grade': e.result.final_grade,
            })

    avg = round(sum(chart_scores) / len(chart_scores), 1) if chart_scores else None
    best = max(chart_scores) if chart_scores else None
    latest = chart_scores[-1] if chart_scores else None

    return render_template('essays/student_scores.html',
                           score_list=score_list,
                           chart_labels=chart_labels,
                           chart_scores=chart_scores,
                           avg=avg, best=best, latest=latest)


# ─── 학부모: 자녀 성적 리포트 ────────────────────────────────

@essays_bp.route('/parent/<student_id>/scores')
@login_required
def parent_scores(student_id):
    if current_user.role != 'parent':
        return redirect(url_for('index'))
    from app.models.member import ParentStudent
    from app.models.user import User
    ParentStudent.query.filter_by(
        parent_id=current_user.user_id, student_id=student_id,
        is_active=True).first_or_404()
    student = User.query.get_or_404(student_id)

    essays = (Essay.query
        .filter_by(student_id=student_id, status='completed')
        .order_by(Essay.created_at.asc()).all())

    chart_labels = []
    chart_scores = []
    score_list = []
    for e in essays:
        if e.result and e.result.total_score is not None:
            chart_labels.append(e.created_at.strftime('%m/%d'))
            chart_scores.append(e.result.total_score)
            score_list.append({
                'essay': e,
                'score': e.result.total_score,
                'grade': e.result.final_grade,
            })

    avg = round(sum(chart_scores) / len(chart_scores), 1) if chart_scores else None
    best = max(chart_scores) if chart_scores else None
    latest = chart_scores[-1] if chart_scores else None

    return render_template('essays/parent_scores.html',
                           student=student, score_list=score_list,
                           chart_labels=chart_labels,
                           chart_scores=chart_scores,
                           avg=avg, best=best, latest=latest)


# ─── 지점 공지 (학생/학부모 수신) ────────────────────────────

@essays_bp.route('/notices')
@login_required
def member_notices():
    """학생/학부모가 보는 지점 공지"""
    if current_user.role not in ('student', 'parent'):
        return redirect(url_for('index'))
    from app.models.branch_post import BranchPost, BranchPostRead

    posts = (BranchPost.query
        .filter_by(branch_id=current_user.branch_id, is_published=True)
        .order_by(BranchPost.is_pinned.desc(), BranchPost.created_at.desc())
        .all())
    visible = [p for p in posts if p.is_visible_to(current_user.role)]

    read_ids = {r.post_id for r in BranchPostRead.query.filter_by(
        user_id=current_user.user_id).all()}

    return render_template('essays/member_notices.html',
                           posts=visible, read_ids=read_ids)


@essays_bp.route('/notices/<post_id>')
@login_required
def member_notice_detail(post_id):
    """학생/학부모 공지 상세"""
    if current_user.role not in ('student', 'parent'):
        return redirect(url_for('index'))
    from app.models.branch_post import BranchPost, BranchPostRead

    post = BranchPost.query.filter_by(
        post_id=post_id, branch_id=current_user.branch_id).first_or_404()

    existing = BranchPostRead.query.filter_by(
        post_id=post_id, user_id=current_user.user_id).first()
    if not existing:
        db.session.add(BranchPostRead(
            post_id=post_id, user_id=current_user.user_id))
        db.session.commit()

    return render_template('essays/member_notice_detail.html', post=post)
