# -*- coding: utf-8 -*-
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.hq import hq_bp
from app.models import db
from app.models.user import User
from app.models.branch import Branch, BranchContract
from app.models.revenue import RevenueRecord
from app.models.notification import Notification
from app.models.lms import BranchPackageAssignment
from app.utils.decorators import requires_role
from datetime import datetime


# ─── 대시보드 ────────────────────────────────────────────────

@hq_bp.route('/')
@login_required
@requires_role('super_admin', 'hq_manager', 'hq_essay_manager')
def dashboard():
    from app.models.essay import Essay
    now = datetime.utcnow()

    # 전체 지표
    total_branches = Branch.query.filter_by(status='active').count()
    total_students = User.query.filter(
        User.branch_id.isnot(None), User.role == 'student').count()
    total_essays = Essay.query.count()

    # 첨삭 상태별 건수
    essay_counts = {}
    for s in ('draft', 'processing', 'reviewing', 'completed', 'failed'):
        essay_counts[s] = Essay.query.filter(Essay.status == s).count()

    # 이번 달 매출
    monthly_records = RevenueRecord.query.filter_by(
        period_year=now.year, period_month=now.month).all()
    total_gross = sum(r.gross_amount for r in monthly_records)
    total_royalty = sum(r.royalty_amount for r in monthly_records)
    pending_count = RevenueRecord.query.filter_by(status='pending').count()

    # 지점별 KPI
    branches = Branch.query.filter_by(status='active').order_by(Branch.code).all()
    branch_kpi = []
    for b in branches:
        students = User.query.filter_by(branch_id=b.branch_id, role='student').count()
        b_essays = Essay.query.filter_by(branch_id=b.branch_id).count()
        b_completed = Essay.query.filter_by(
            branch_id=b.branch_id, status='completed').count()
        b_pending = Essay.query.filter_by(
            branch_id=b.branch_id, status='draft').count()
        this_month = RevenueRecord.query.filter_by(
            branch_id=b.branch_id,
            period_year=now.year, period_month=now.month).first()
        branch_kpi.append({
            'branch': b,
            'students': students,
            'essays': b_essays,
            'completed': b_completed,
            'pending': b_pending,
            'gross': this_month.gross_amount if this_month else 0,
            'royalty': this_month.royalty_amount if this_month else 0,
        })

    # 최근 첨삭 (전체)
    recent_essays = Essay.query.order_by(Essay.created_at.desc()).limit(8).all()

    return render_template('hq/dashboard.html',
                           total_branches=total_branches,
                           total_students=total_students,
                           total_essays=total_essays,
                           essay_counts=essay_counts,
                           total_gross=total_gross,
                           total_royalty=total_royalty,
                           pending_count=pending_count,
                           branch_kpi=branch_kpi,
                           recent_essays=recent_essays,
                           now=now)


# ─── 지점 관리 ───────────────────────────────────────────────

@hq_bp.route('/branches')
@login_required
@requires_role('super_admin', 'hq_manager')
def branches():
    branches = Branch.query.order_by(Branch.code).all()
    return render_template('hq/branches.html', branches=branches)


@hq_bp.route('/branches/new', methods=['GET', 'POST'])
@login_required
@requires_role('super_admin', 'hq_manager')
def new_branch():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        short_code = request.form.get('short_code', '').strip().upper() or None
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

        branch = Branch(code=code, short_code=short_code, name=name, address=address,
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
    branch = Branch.query.get_or_404(branch_id)
    users = User.query.filter_by(branch_id=branch_id).order_by(User.role_level).all()
    recent_revenue = RevenueRecord.query.filter_by(branch_id=branch_id)\
        .order_by(RevenueRecord.period_year.desc(), RevenueRecord.period_month.desc())\
        .limit(6).all()
    pkg_assignments = BranchPackageAssignment.query.filter_by(
        branch_id=branch_id, is_active=True).all()
    return render_template('hq/branch_detail.html', branch=branch, users=users,
                           recent_revenue=recent_revenue,
                           pkg_assignments=pkg_assignments)


@hq_bp.route('/branches/<branch_id>/create-user', methods=['GET', 'POST'])
@login_required
@requires_role('super_admin', 'hq_manager')
def create_branch_user(branch_id):
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

        if role == 'branch_owner' and not branch.owner_id:
            db.session.flush()
            branch.owner_id = user.user_id

        db.session.commit()
        flash(f'{user.display_role} "{name}" 계정이 생성되었습니다.', 'success')
        return redirect(url_for('hq.branch_detail', branch_id=branch_id))

    return render_template('hq/create_branch_user.html', branch=branch)


# ─── 정산 관리 ───────────────────────────────────────────────

@hq_bp.route('/revenue')
@login_required
@requires_role('super_admin', 'hq_manager')
def revenue():
    """전체 정산 현황"""
    now = datetime.utcnow()
    year = int(request.args.get('year', now.year))
    month = int(request.args.get('month', now.month))

    records = RevenueRecord.query.filter_by(period_year=year, period_month=month)\
        .join(Branch, RevenueRecord.branch_id == Branch.branch_id)\
        .order_by(Branch.code).all()

    # 전체 합계
    total_gross = sum(r.gross_amount for r in records)
    total_royalty = sum(r.royalty_amount for r in records)
    total_fee = sum(r.monthly_fee for r in records)
    total_net = sum(r.net_amount for r in records)

    # 정산 입력되지 않은 지점 목록
    recorded_branch_ids = {r.branch_id for r in records}
    unrecorded_branches = Branch.query.filter_by(status='active')\
        .filter(~Branch.branch_id.in_(recorded_branch_ids)).all()

    # 연월 선택용 범위
    years = list(range(now.year - 2, now.year + 1))
    months = list(range(1, 13))

    return render_template('hq/revenue.html',
                           records=records,
                           year=year, month=month,
                           total_gross=total_gross,
                           total_royalty=total_royalty,
                           total_fee=total_fee,
                           total_net=total_net,
                           unrecorded_branches=unrecorded_branches,
                           years=years, months=months)


@hq_bp.route('/revenue/input', methods=['GET', 'POST'])
@login_required
@requires_role('super_admin', 'hq_manager')
def revenue_input():
    """정산 데이터 입력"""
    now = datetime.utcnow()
    branches = Branch.query.filter_by(status='active').order_by(Branch.code).all()

    if request.method == 'POST':
        branch_id = request.form.get('branch_id')
        year = int(request.form.get('year', now.year))
        month = int(request.form.get('month', now.month))
        gross_amount = int(request.form.get('gross_amount', 0) or 0)
        notes = request.form.get('notes', '').strip()

        branch = Branch.query.get_or_404(branch_id)

        # 계약 기준 로열티 자동 계산
        royalty_rate = float(branch.contract.royalty_rate) if branch.contract else 20.0
        monthly_fee = int(branch.contract.monthly_fee or 0) if branch.contract else 0
        royalty_amount = int(gross_amount * royalty_rate / 100)
        net_amount = gross_amount - royalty_amount - monthly_fee

        # 이미 있으면 업데이트, 없으면 생성
        record = RevenueRecord.query.filter_by(
            branch_id=branch_id, period_year=year, period_month=month).first()

        if record:
            record.gross_amount = gross_amount
            record.royalty_amount = royalty_amount
            record.monthly_fee = monthly_fee
            record.net_amount = net_amount
            record.notes = notes or record.notes
            flash(f'{branch.name} {year}년 {month}월 정산이 수정되었습니다.', 'success')
        else:
            record = RevenueRecord(
                branch_id=branch_id,
                period_year=year,
                period_month=month,
                gross_amount=gross_amount,
                royalty_amount=royalty_amount,
                monthly_fee=monthly_fee,
                net_amount=net_amount,
                notes=notes or None,
            )
            db.session.add(record)
            flash(f'{branch.name} {year}년 {month}월 정산이 등록되었습니다.', 'success')

        db.session.commit()
        return redirect(url_for('hq.revenue', year=year, month=month))

    # 선택된 지점의 계약 정보 (AJAX용)
    branch_id = request.args.get('branch_id')
    selected_branch = Branch.query.get(branch_id) if branch_id else None

    return render_template('hq/revenue_input.html',
                           branches=branches,
                           selected_branch=selected_branch,
                           now=now)


@hq_bp.route('/revenue/<record_id>/confirm', methods=['POST'])
@login_required
@requires_role('super_admin', 'hq_manager')
def revenue_confirm(record_id):
    """정산 확정"""
    record = RevenueRecord.query.get_or_404(record_id)
    if record.status == 'pending':
        record.status = 'confirmed'
        db.session.flush()
        # 지점 운영진에게 알림 발송
        Notification.send_to_branch(
            branch_id=record.branch_id,
            title=f'{record.period_label} 정산이 확정되었습니다',
            notif_type='revenue_confirmed',
            message=f'수금액 {record.gross_amount:,}원 / 로열티 {record.royalty_amount:,}원 / 지급액 {record.net_amount:,}원',
            link_url='/branch/revenue',
            roles=['branch_owner', 'branch_manager'],
        )
        db.session.commit()
        return jsonify({'success': True, 'status': 'confirmed', 'label': '확정'})
    return jsonify({'success': False, 'message': '이미 처리된 정산입니다.'})


@hq_bp.route('/revenue/<record_id>/pay', methods=['POST'])
@login_required
@requires_role('super_admin')
def revenue_pay(record_id):
    """지급 완료 처리"""
    record = RevenueRecord.query.get_or_404(record_id)
    if record.status == 'confirmed':
        record.status = 'paid'
        record.paid_at = datetime.utcnow()
        db.session.flush()
        # 지급 알림
        Notification.send_to_branch(
            branch_id=record.branch_id,
            title=f'{record.period_label} 정산금이 지급 처리되었습니다',
            notif_type='revenue_paid',
            message=f'지급액 {record.net_amount:,}원',
            link_url='/branch/revenue',
            roles=['branch_owner', 'branch_manager'],
        )
        db.session.commit()
        return jsonify({'success': True, 'status': 'paid', 'label': '지급 완료'})
    return jsonify({'success': False, 'message': '확정된 정산만 지급 처리할 수 있습니다.'})


@hq_bp.route('/revenue/summary')
@login_required
@requires_role('super_admin', 'hq_manager')
def revenue_summary():
    """연간 정산 요약"""
    now = datetime.utcnow()
    year = int(request.args.get('year', now.year))

    # 지점별 연간 합계
    from sqlalchemy import func
    results = db.session.query(
        Branch.branch_id,
        Branch.code,
        Branch.name,
        func.sum(RevenueRecord.gross_amount).label('total_gross'),
        func.sum(RevenueRecord.royalty_amount).label('total_royalty'),
        func.sum(RevenueRecord.net_amount).label('total_net'),
        func.count(RevenueRecord.record_id).label('months_recorded'),
    ).join(RevenueRecord, Branch.branch_id == RevenueRecord.branch_id)\
     .filter(RevenueRecord.period_year == year)\
     .group_by(Branch.branch_id, Branch.code, Branch.name)\
     .order_by(func.sum(RevenueRecord.gross_amount).desc())\
     .all()

    grand_gross = sum(r.total_gross or 0 for r in results)
    grand_royalty = sum(r.total_royalty or 0 for r in results)

    years = list(range(now.year - 2, now.year + 1))

    return render_template('hq/revenue_summary.html',
                           results=results,
                           year=year, years=years,
                           grand_gross=grand_gross,
                           grand_royalty=grand_royalty)
