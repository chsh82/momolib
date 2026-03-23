# -*- coding: utf-8 -*-
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.branch_portal import branch_bp
from app.models import db
from app.models.user import User
from app.models.branch import Branch
from app.models.content import ContentItem, ContentView
from app.models.member import StudentProfile, ParentStudent, GRADE_CHOICES
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

    return render_template('branch/member_detail.html',
                           member=user,
                           parents=parents, children=children,
                           all_students=all_students,
                           all_parents=all_parents,
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

    db.session.commit()
    flash('정보가 수정되었습니다.', 'success')
    return redirect(url_for('branch.member_detail', user_id=user_id))


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


@branch_bp.route('/members/unlink/<link_id>', methods=['POST'])
@login_required
@requires_role('branch_owner', 'branch_manager')
def unlink_parent_student(link_id):
    """학부모-학생 연결 해제"""
    link = ParentStudent.query.get_or_404(link_id)

    # 같은 지점인지 확인
    if link.branch_id != current_user.branch_id:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('branch.members'))

    link.is_active = False
    db.session.commit()
    flash('연결이 해제되었습니다.', 'success')
    return redirect(request.referrer or url_for('branch.members'))
