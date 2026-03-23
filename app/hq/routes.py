# -*- coding: utf-8 -*-
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.hq import hq_bp
from app.models import db
from app.models.user import User
from app.models.branch import Branch, BranchContract
from app.utils.decorators import requires_role


@hq_bp.route('/')
@login_required
@requires_role('super_admin', 'hq_manager', 'hq_essay_manager')
def dashboard():
    """본사 대시보드"""
    total_branches = Branch.query.filter_by(status='active').count()
    total_users = User.query.filter(User.branch_id.isnot(None)).count()

    branches = Branch.query.order_by(Branch.created_at.desc()).limit(10).all()

    return render_template('hq/dashboard.html',
                           total_branches=total_branches,
                           total_users=total_users,
                           branches=branches)


@hq_bp.route('/branches')
@login_required
@requires_role('super_admin', 'hq_manager')
def branches():
    """지점 목록"""
    branches = Branch.query.order_by(Branch.code).all()
    return render_template('hq/branches.html', branches=branches)


@hq_bp.route('/branches/new', methods=['GET', 'POST'])
@login_required
@requires_role('super_admin', 'hq_manager')
def new_branch():
    """지점 생성"""
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        royalty_rate = float(request.form.get('royalty_rate', 20))
        monthly_fee = int(request.form.get('monthly_fee', 0) or 0)
        contract_start = request.form.get('contract_start')

        if not code or not name:
            flash('지점 코드와 이름은 필수입니다.', 'error')
            return render_template('hq/new_branch.html')

        if Branch.query.filter_by(code=code).first():
            flash('이미 사용 중인 지점 코드입니다.', 'error')
            return render_template('hq/new_branch.html')

        branch = Branch(code=code, name=name, address=address,
                        phone=phone, email=email)
        db.session.add(branch)
        db.session.flush()

        from datetime import date
        contract = BranchContract(
            branch_id=branch.branch_id,
            contract_start=date.fromisoformat(contract_start) if contract_start else date.today(),
            royalty_rate=royalty_rate,
            revenue_share=100 - royalty_rate,
            monthly_fee=monthly_fee
        )
        db.session.add(contract)
        db.session.commit()

        flash(f'지점 "{name}" (#{code})이 생성되었습니다.', 'success')
        return redirect(url_for('hq.branches'))

    return render_template('hq/new_branch.html')


@hq_bp.route('/branches/<branch_id>')
@login_required
@requires_role('super_admin', 'hq_manager')
def branch_detail(branch_id):
    """지점 상세"""
    branch = Branch.query.get_or_404(branch_id)
    users = User.query.filter_by(branch_id=branch_id).order_by(User.role_level).all()
    return render_template('hq/branch_detail.html', branch=branch, users=users)


@hq_bp.route('/branches/<branch_id>/create-user', methods=['GET', 'POST'])
@login_required
@requires_role('super_admin', 'hq_manager')
def create_branch_user(branch_id):
    """지점 계정 생성"""
    branch = Branch.query.get_or_404(branch_id)

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        role = request.form.get('role', 'teacher')
        password = request.form.get('password', '').strip()

        allowed_roles = ['branch_owner', 'branch_manager', 'teacher', 'parent', 'student']
        if role not in allowed_roles:
            flash('올바르지 않은 역할입니다.', 'error')
            return render_template('hq/create_branch_user.html', branch=branch)

        if User.query.filter_by(email=email).first():
            flash('이미 사용 중인 이메일입니다.', 'error')
            return render_template('hq/create_branch_user.html', branch=branch)

        user = User(email=email, name=name, role=role,
                    branch_id=branch_id, is_active=True, is_verified=True)
        user.set_password(password)
        db.session.add(user)

        # 지점장으로 지정
        if role == 'branch_owner' and not branch.owner_id:
            branch.owner_id = user.user_id

        db.session.commit()
        flash(f'{user.display_role} "{name}" 계정이 생성되었습니다.', 'success')
        return redirect(url_for('hq.branch_detail', branch_id=branch_id))

    return render_template('hq/create_branch_user.html', branch=branch)
