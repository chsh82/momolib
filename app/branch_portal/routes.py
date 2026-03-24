# -*- coding: utf-8 -*-
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.branch_portal import branch_bp
from app.models import db
from app.models.user import User
from app.models.branch import Branch
from app.models.content import ContentItem, ContentView
from app.models.member import StudentProfile, ParentStudent, GRADE_CHOICES
from app.models.revenue import RevenueRecord
from app.models.branch_post import BranchPost, BranchPostRead
from app.models.essay import Essay, EssayResult
from app.models.credit import EssayCredit, EssayCreditLog
from datetime import datetime
from app.utils.decorators import requires_role


# ─── 대시보드 ────────────────────────────────────────────────

@branch_bp.route('/')
@login_required
@requires_role('branch_owner', 'branch_manager', 'teacher')
def dashboard():
    branch = Branch.query.get(current_user.branch_id)
    if not branch:
        flash('소속 지점 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('auth.logout'))

    total_users = User.query.filter_by(branch_id=branch.branch_id).count()
    teachers = User.query.filter_by(branch_id=branch.branch_id, role='teacher').count()
    students = User.query.filter_by(branch_id=branch.branch_id, role='student').count()
    parents = User.query.filter_by(branch_id=branch.branch_id, role='parent').count()

    from sqlalchemy import or_
    unread_notices = ContentItem.query.filter(
        ContentItem.is_published == True,
        ContentItem.content_type == 'notice',
        or_(ContentItem.is_global == True,
            ContentItem.permissions.any(branch_id=branch.branch_id))
    ).filter(
        ~ContentItem.views.any(user_id=current_user.user_id)
    ).count()

    return render_template('branch/dashboard.html',
                           branch=branch,
                           total_users=total_users,
                           teachers=teachers,
                           students=students,
                           parents=parents,
                           unread_notices=unread_notices)


# ─── 공지 수신함 ─────────────────────────────────────────────

@branch_bp.route('/notices')
@login_required
@requires_role('branch_owner', 'branch_manager', 'teacher')
def notices():
    from sqlalchemy import or_
    branch_id = current_user.branch_id

    items = ContentItem.query.filter(
        ContentItem.is_published == True,
        or_(ContentItem.is_global == True,
            ContentItem.permissions.any(branch_id=branch_id))
    ).order_by(ContentItem.created_at.desc()).all()

    read_ids = {v.content_id for v in ContentView.query.filter_by(
        user_id=current_user.user_id).all()}

    return render_template('branch/notices.html', items=items, read_ids=read_ids)


@branch_bp.route('/notices/<content_id>')
@login_required
@requires_role('branch_owner', 'branch_manager', 'teacher')
def notice_detail(content_id):
    item = ContentItem.query.get_or_404(content_id)

    existing = ContentView.query.filter_by(
        content_id=content_id, user_id=current_user.user_id).first()
    if not existing:
        view = ContentView(content_id=content_id,
                           user_id=current_user.user_id,
                           branch_id=current_user.branch_id)
        db.session.add(view)
        db.session.commit()

    return render_template('branch/notice_detail.html', item=item)


# ─── 회원 관리 ───────────────────────────────────────────────

@branch_bp.route('/members')
@login_required
@requires_role('branch_owner', 'branch_manager')
def members():
    """회원 목록"""
    branch_id = current_user.branch_id
    role_filter = request.args.get('role', '')
    search = request.args.get('q', '').strip()

    query = User.query.filter_by(branch_id=branch_id)
    if role_filter:
        query = query.filter_by(role=role_filter)
    if search:
        query = query.filter(
            (User.name.ilike(f'%{search}%')) | (User.email.ilike(f'%{search}%'))
        )

    users = query.order_by(User.role_level, User.name).all()

    counts = {
        'teacher': User.query.filter_by(branch_id=branch_id, role='teacher').count(),
        'student': User.query.filter_by(branch_id=branch_id, role='student').count(),
        'parent': User.query.filter_by(branch_id=branch_id, role='parent').count(),
    }

    return render_template('branch/members.html',
                           users=users, counts=counts,
                           role_filter=role_filter, search=search)


@branch_bp.route('/members/add', methods=['GET', 'POST'])
@login_required
@requires_role('branch_owner', 'branch_manager')
def add_member():
    """회원 추가"""
    branch_id = current_user.branch_id
    role_default = request.args.get('role', 'student')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        role = request.form.get('role', 'student')
        password = request.form.get('password', '').strip()

        allowed = ['teacher', 'parent', 'student']
        if role not in allowed:
            flash('올바르지 않은 역할입니다.', 'error')
            return render_template('branch/add_member.html',
                                   role_default=role_default, grade_choices=GRADE_CHOICES)

        if not email or not name or not password:
            flash('이메일, 이름, 비밀번호는 필수입니다.', 'error')
            return render_template('branch/add_member.html',
                                   role_default=role_default, grade_choices=GRADE_CHOICES)

        if User.query.filter_by(email=email).first():
            flash('이미 사용 중인 이메일입니다.', 'error')
            return render_template('branch/add_member.html',
                                   role_default=role_default, grade_choices=GRADE_CHOICES)

        user = User(email=email, name=name, phone=phone or None,
                    role=role, branch_id=branch_id,
                    is_active=True, is_verified=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # 학생이면 StudentProfile 생성
        if role == 'student':
            grade = request.form.get('grade', '')
            school = request.form.get('school', '').strip()
            student_code = request.form.get('student_code', '').strip()
            birth_date_str = request.form.get('birth_date', '')
            notes = request.form.get('notes', '').strip()

            from datetime import date
            birth_date = None
            if birth_date_str:
                try:
                    birth_date = date.fromisoformat(birth_date_str)
                except ValueError:
                    pass

            profile = StudentProfile(
                user_id=user.user_id,
                branch_id=branch_id,
                grade=grade or None,
                school=school or None,
                student_code=student_code or None,
                birth_date=birth_date,
                notes=notes or None,
                enrolled_at=date.today(),
            )
            db.session.add(profile)

        db.session.commit()
        flash(f'{user.display_role} "{name}" 등록이 완료되었습니다.', 'success')
        return redirect(url_for('branch.members', role=role))

    return render_template('branch/add_member.html',
                           role_default=role_default, grade_choices=GRADE_CHOICES)


@branch_bp.route('/members/<user_id>')
@login_required
@requires_role('branch_owner', 'branch_manager')
def member_detail(user_id):
    """회원 상세"""
    branch_id = current_user.branch_id
    user = User.query.filter_by(user_id=user_id, branch_id=branch_id).first_or_404()

    parents = []
    children = []
    if user.role == 'student':
        parents = ParentStudent.query.filter_by(
            student_id=user_id, is_active=True).all()
    elif user.role == 'parent':
        children = ParentStudent.query.filter_by(
            parent_id=user_id, is_active=True).all()

    # 연결 가능한 학생/학부모 목록 (같은 지점)
    all_students = User.query.filter_by(branch_id=branch_id, role='student',
                                        is_active=True).order_by(User.name).all()
    all_parents = User.query.filter_by(branch_id=branch_id, role='parent',
                                       is_active=True).order_by(User.name).all()
    all_teachers = User.query.filter_by(branch_id=branch_id, role='teacher',
                                        is_active=True).order_by(User.name).all()

    return render_template('branch/member_detail.html',
                           member=user,
                           parents=parents, children=children,
                           all_students=all_students,
                           all_parents=all_parents,
                           all_teachers=all_teachers,
                           grade_choices=GRADE_CHOICES)


@branch_bp.route('/members/<user_id>/edit', methods=['POST'])
@login_required
@requires_role('branch_owner', 'branch_manager')
def edit_member(user_id):
    """회원 정보 수정"""
    branch_id = current_user.branch_id
    user = User.query.filter_by(user_id=user_id, branch_id=branch_id).first_or_404()

    user.name = request.form.get('name', user.name).strip()
    user.phone = request.form.get('phone', '').strip() or None

    new_password = request.form.get('new_password', '').strip()
    if new_password:
        user.set_password(new_password)

    if user.role == 'student' and user.student_profile:
        p = user.student_profile
        p.grade = request.form.get('grade') or None
        p.school = request.form.get('school', '').strip() or None
        p.student_code = request.form.get('student_code', '').strip() or None
        p.notes = request.form.get('notes', '').strip() or None
        # 담당 강사 배정
        teacher_id = request.form.get('assigned_teacher_id', '').strip()
        if teacher_id:
            teacher = User.query.filter_by(user_id=teacher_id,
                branch_id=branch_id, role='teacher').first()
            p.assigned_teacher_id = teacher.user_id if teacher else None
        else:
            p.assigned_teacher_id = None

    db.session.commit()
    flash('정보가 수정되었습니다.', 'success')
    return redirect(url_for('branch.member_detail', user_id=user_id))


@branch_bp.route('/members/<user_id>/delete', methods=['POST'])
@login_required
@requires_role('branch_owner')
def delete_member(user_id):
    """회원 완전 삭제 (지점장 전용)"""
    user = User.query.filter_by(user_id=user_id, branch_id=current_user.branch_id).first_or_404()
    if user.role == 'branch_owner':
        flash('지점장 계정은 삭제할 수 없습니다.', 'error')
        return redirect(url_for('branch.member_detail', user_id=user_id))
    db.session.delete(user)
    db.session.commit()
    flash(f'{user.name} 계정이 삭제되었습니다.', 'success')
    return redirect(url_for('branch.members'))


@branch_bp.route('/members/<user_id>/reset-password', methods=['POST'])
@login_required
@requires_role('branch_owner', 'branch_manager')
def reset_member_password(user_id):
    """비밀번호 임시 초기화"""
    import random, string
    user = User.query.filter_by(user_id=user_id, branch_id=current_user.branch_id).first_or_404()
    if user.role == 'branch_owner':
        return jsonify({'error': '지점장 계정은 초기화할 수 없습니다.'}), 403
    temp_pw = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    user.set_password(temp_pw)
    db.session.commit()
    return jsonify({'success': True, 'temp_password': temp_pw, 'name': user.name})


@branch_bp.route('/members/<user_id>/toggle-active', methods=['POST'])
@login_required
@requires_role('branch_owner', 'branch_manager')
def toggle_member_active(user_id):
    """계정 활성/비활성 토글"""
    branch_id = current_user.branch_id
    user = User.query.filter_by(user_id=user_id, branch_id=branch_id).first_or_404()

    # 지점장은 비활성화 불가
    if user.role == 'branch_owner':
        return jsonify({'error': '지점장 계정은 변경할 수 없습니다.'}), 403

    user.is_active = not user.is_active
    db.session.commit()
    status = '활성화' if user.is_active else '비활성화'
    return jsonify({'success': True, 'is_active': user.is_active,
                    'message': f'{user.name} 계정이 {status}되었습니다.'})


# ─── 학부모-학생 연결 ─────────────────────────────────────────

@branch_bp.route('/members/link', methods=['POST'])
@login_required
@requires_role('branch_owner', 'branch_manager')
def link_parent_student():
    """학부모-학생 연결"""
    branch_id = current_user.branch_id
    parent_id = request.form.get('parent_id')
    student_id = request.form.get('student_id')

    if not parent_id or not student_id:
        flash('학부모와 학생을 모두 선택해주세요.', 'error')
        return redirect(request.referrer or url_for('branch.members'))

    # 검증
    parent = User.query.filter_by(user_id=parent_id, branch_id=branch_id,
                                   role='parent').first()
    student = User.query.filter_by(user_id=student_id, branch_id=branch_id,
                                    role='student').first()
    if not parent or not student:
        flash('올바르지 않은 요청입니다.', 'error')
        return redirect(request.referrer or url_for('branch.members'))

    existing = ParentStudent.query.filter_by(
        parent_id=parent_id, student_id=student_id).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.session.commit()
            flash('연결이 복원되었습니다.', 'success')
        else:
            flash('이미 연결되어 있습니다.', 'warning')
        return redirect(request.referrer or url_for('branch.members'))

    link = ParentStudent(
        branch_id=branch_id,
        parent_id=parent_id,
        student_id=student_id,
        linked_by=current_user.user_id,
    )
    db.session.add(link)
    db.session.commit()
    flash(f'{parent.name} ↔ {student.name} 연결이 완료되었습니다.', 'success')
    return redirect(request.referrer or url_for('branch.members'))


@branch_bp.route('/revenue')
@login_required
@requires_role('branch_owner', 'branch_manager')
def my_revenue():
    """지점 정산 내역 확인"""
    branch_id = current_user.branch_id
    now = datetime.utcnow()
    year = int(request.args.get('year', now.year))

    records = RevenueRecord.query.filter_by(branch_id=branch_id)\
        .filter_by(period_year=year)\
        .order_by(RevenueRecord.period_month.desc()).all()

    total_gross = sum(r.gross_amount for r in records)
    total_royalty = sum(r.royalty_amount for r in records)
    total_net = sum(r.net_amount for r in records)

    years = list(range(now.year - 2, now.year + 1))

    return render_template('branch/revenue.html',
                           records=records,
                           year=year, years=years,
                           total_gross=total_gross,
                           total_royalty=total_royalty,
                           total_net=total_net)


@branch_bp.route('/members/unlink/<link_id>', methods=['POST'])
@login_required
@requires_role('branch_owner', 'branch_manager')
def unlink_parent_student(link_id):
    """학부모-학생 연결 해제"""
    link = ParentStudent.query.get_or_404(link_id)

    if link.branch_id != current_user.branch_id:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('branch.members'))

    link.is_active = False
    db.session.commit()
    flash('연결이 해제되었습니다.', 'success')
    return redirect(request.referrer or url_for('branch.members'))


# ─── 강사 전용 메뉴 ──────────────────────────────────────────

@branch_bp.route('/teacher/students')
@login_required
@requires_role('teacher')
def teacher_students():
    """강사: 지점 학생 목록 + 과제 현황"""
    branch_id = current_user.branch_id
    search = request.args.get('q', '').strip()

    assigned_only = request.args.get('assigned') == '1'
    query = User.query.filter_by(branch_id=branch_id, role='student', is_active=True)
    if search:
        query = query.filter(User.name.ilike(f'%{search}%'))
    if assigned_only:
        from app.models.member import StudentProfile as SP
        query = query.join(SP, SP.user_id == User.user_id).filter(
            SP.assigned_teacher_id == current_user.user_id)
    students = query.order_by(User.name).all()

    # 학생별 통계
    stats = {}
    for s in students:
        total = Essay.query.filter_by(student_id=s.user_id).count()
        completed = Essay.query.filter_by(
            student_id=s.user_id, status='completed').count()
        pending = Essay.query.filter_by(
            student_id=s.user_id, status='draft').count()
        # 최근 점수
        latest_result = (EssayResult.query
            .join(Essay, Essay.essay_id == EssayResult.essay_id)
            .filter(Essay.student_id == s.user_id,
                    Essay.status == 'completed')
            .order_by(Essay.created_at.desc()).first())
        stats[s.user_id] = {
            'total': total, 'completed': completed, 'pending': pending,
            'latest_score': latest_result.total_score if latest_result else None,
        }

    return render_template('branch/teacher_students.html',
                           students=students, stats=stats,
                           search=search, assigned_only=assigned_only)


@branch_bp.route('/teacher/queue')
@login_required
@requires_role('teacher')
def teacher_queue():
    """강사: 첨삭 대기 큐 (수동 첨삭 가능한 과제)"""
    branch_id = current_user.branch_id
    essays = (Essay.query
        .filter_by(branch_id=branch_id)
        .filter(Essay.status.in_(['draft', 'failed', 'reviewing']))
        .order_by(Essay.created_at.asc()).all())

    counts = {
        'draft': sum(1 for e in essays if e.status == 'draft'),
        'failed': sum(1 for e in essays if e.status == 'failed'),
        'reviewing': sum(1 for e in essays if e.status == 'reviewing'),
    }

    return render_template('branch/teacher_queue.html',
                           essays=essays, counts=counts)


# ─── 학생 성적 현황 (지점장/매니저) ──────────────────────────

@branch_bp.route('/scores')
@login_required
@requires_role('branch_owner', 'branch_manager', 'teacher')
def scores():
    """학생 성적 현황"""
    branch_id = current_user.branch_id
    search = request.args.get('q', '').strip()

    query = User.query.filter_by(branch_id=branch_id, role='student', is_active=True)
    if search:
        query = query.filter(User.name.ilike(f'%{search}%'))
    students = query.order_by(User.name).all()

    student_data = []
    for s in students:
        essays = (Essay.query
            .filter_by(student_id=s.user_id, status='completed')
            .order_by(Essay.created_at.asc()).all())

        scores_list = []
        for e in essays:
            if e.result and e.result.total_score is not None:
                scores_list.append({
                    'title': e.title,
                    'score': e.result.total_score,
                    'grade': e.result.final_grade,
                    'date': e.created_at.strftime('%Y-%m-%d'),
                    'essay_id': e.essay_id,
                })

        avg = (sum(x['score'] for x in scores_list) / len(scores_list)
               if scores_list else None)
        student_data.append({
            'student': s,
            'scores': scores_list,
            'avg': round(avg, 1) if avg else None,
            'count': len(scores_list),
            'total_essays': Essay.query.filter_by(student_id=s.user_id).count(),
        })

    return render_template('branch/scores.html',
                           student_data=student_data, search=search)


# ─── 지점 공지사항 ────────────────────────────────────────────

@branch_bp.route('/posts')
@login_required
@requires_role('branch_owner', 'branch_manager', 'teacher')
def branch_posts():
    """지점 공지사항 목록"""
    branch_id = current_user.branch_id
    posts = (BranchPost.query
        .filter_by(branch_id=branch_id, is_published=True)
        .filter(BranchPost.target_roles.in_(['all', current_user.role]) |
                BranchPost.target_roles.contains(current_user.role))
        .order_by(BranchPost.is_pinned.desc(), BranchPost.created_at.desc())
        .all())

    # 필터: role에 맞는 공지만
    visible = [p for p in posts if p.is_visible_to(current_user.role)]

    read_ids = {r.post_id for r in BranchPostRead.query.filter_by(
        user_id=current_user.user_id).all()}

    return render_template('branch/branch_posts.html',
                           posts=visible, read_ids=read_ids,
                           can_manage=current_user.role in ('branch_owner', 'branch_manager'))


@branch_bp.route('/posts/new', methods=['GET', 'POST'])
@login_required
@requires_role('branch_owner', 'branch_manager')
def new_branch_post():
    """지점 공지 작성"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        target_roles = request.form.get('target_roles', 'all')
        is_pinned = bool(request.form.get('is_pinned'))

        if not title or not content:
            flash('제목과 내용을 입력해주세요.', 'error')
            return render_template('branch/branch_post_form.html')

        post = BranchPost(
            branch_id=current_user.branch_id,
            author_id=current_user.user_id,
            title=title,
            content=content,
            target_roles=target_roles,
            is_pinned=is_pinned,
        )
        db.session.add(post)
        db.session.commit()

        # 알림 전송
        from app.models.notification import Notification
        roles = ['teacher', 'student', 'parent'] if target_roles == 'all' \
            else target_roles.split(',')
        recipients = User.query.filter_by(
            branch_id=current_user.branch_id, is_active=True).filter(
            User.role.in_(roles)).all()
        for r in recipients:
            Notification.create(
                user_id=r.user_id,
                notif_type='branch_post',
                title=f'[지점 공지] {title}',
                message=content[:80] + ('...' if len(content) > 80 else ''),
                link_url=f'/branch/posts/{post.post_id}',
            )
        db.session.commit()

        flash('공지사항이 등록되었습니다.', 'success')
        return redirect(url_for('branch.branch_posts'))

    return render_template('branch/branch_post_form.html')


@branch_bp.route('/posts/<post_id>')
@login_required
@requires_role('branch_owner', 'branch_manager', 'teacher')
def branch_post_detail(post_id):
    """지점 공지 상세"""
    post = BranchPost.query.filter_by(
        post_id=post_id, branch_id=current_user.branch_id).first_or_404()

    # 읽음 처리
    existing = BranchPostRead.query.filter_by(
        post_id=post_id, user_id=current_user.user_id).first()
    if not existing:
        db.session.add(BranchPostRead(
            post_id=post_id, user_id=current_user.user_id))
        db.session.commit()

    can_manage = current_user.role in ('branch_owner', 'branch_manager')
    return render_template('branch/branch_post_detail.html',
                           post=post, can_manage=can_manage)


@branch_bp.route('/posts/<post_id>/delete', methods=['POST'])
@login_required
@requires_role('branch_owner', 'branch_manager')
def delete_branch_post(post_id):
    post = BranchPost.query.filter_by(
        post_id=post_id, branch_id=current_user.branch_id).first_or_404()
    db.session.delete(post)
    db.session.commit()
    flash('공지가 삭제되었습니다.', 'success')
    return redirect(url_for('branch.branch_posts'))


# ─── 이용권/크레딧 관리 ──────────────────────────────────────

@branch_bp.route('/credits')
@login_required
@requires_role('branch_owner', 'branch_manager')
def credits():
    """학생 이용권 현황"""
    branch_id = current_user.branch_id
    search = request.args.get('q', '').strip()

    query = User.query.filter_by(branch_id=branch_id, role='student', is_active=True)
    if search:
        query = query.filter(User.name.ilike(f'%{search}%'))
    students = query.order_by(User.name).all()

    credit_map = {
        c.student_id: c for c in
        EssayCredit.query.filter_by(branch_id=branch_id).all()
    }

    return render_template('branch/credits.html',
                           students=students, credit_map=credit_map, search=search)


@branch_bp.route('/credits/<student_id>', methods=['GET', 'POST'])
@login_required
@requires_role('branch_owner', 'branch_manager')
def credit_detail(student_id):
    """학생 이용권 상세 + 충전"""
    branch_id = current_user.branch_id
    student = User.query.filter_by(
        user_id=student_id, branch_id=branch_id, role='student').first_or_404()

    credit = EssayCredit.query.filter_by(student_id=student_id).first()

    if request.method == 'POST':
        action = request.form.get('action')
        try:
            amount = int(request.form.get('amount', 0))
        except ValueError:
            amount = 0
        note = request.form.get('note', '').strip()

        if amount <= 0:
            flash('수량은 1 이상이어야 합니다.', 'error')
            return redirect(url_for('branch.credit_detail', student_id=student_id))

        if not credit:
            credit = EssayCredit(
                branch_id=branch_id, student_id=student_id)
            db.session.add(credit)
            db.session.flush()

        if action == 'add':
            credit.add(amount, note=note or f'{amount}회 충전', added_by=current_user.user_id)
            flash(f'{amount}회 충전되었습니다.', 'success')
        elif action == 'deduct':
            try:
                credit.deduct(amount, note=note or f'{amount}회 수동 차감')
                flash(f'{amount}회 차감되었습니다.', 'success')
            except ValueError as e:
                flash(str(e), 'error')
                return redirect(url_for('branch.credit_detail', student_id=student_id))

        db.session.commit()
        return redirect(url_for('branch.credit_detail', student_id=student_id))

    logs = EssayCreditLog.query.filter_by(
        student_id=student_id).order_by(
        EssayCreditLog.created_at.desc()).limit(30).all()

    return render_template('branch/credit_detail.html',
                           student=student, credit=credit, logs=logs)


# ─── 월별 정산 리포트 (인쇄용) ────────────────────────────────

@branch_bp.route('/revenue/report')
@login_required
@requires_role('branch_owner', 'branch_manager')
def revenue_report():
    """월별 정산 인쇄용 리포트"""
    branch_id = current_user.branch_id
    branch = Branch.query.get(branch_id)
    now = datetime.utcnow()
    year = int(request.args.get('year', now.year))
    month = int(request.args.get('month', now.month))

    record = RevenueRecord.query.filter_by(
        branch_id=branch_id, period_year=year, period_month=month).first()

    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    return render_template('branch/revenue_report.html',
                           branch=branch, record=record,
                           year=year, month=month, now_str=now_str)
