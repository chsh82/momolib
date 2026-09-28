# -*- coding: utf-8 -*-
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.lms import lms_bp
from app.models import db
from app.models.lms import (Curriculum, CurriculumItem, Package, PackageCurriculum,
                             BranchPackageAssignment, StudentPackageAssignment,
                             StudentItemProgress)
from app.models.content_bank import BankQuestion, LectureVideo
from app.models.branch import Branch
from app.models.member import StudentProfile

CONTENT_TYPES = ['vocab_quiz', 'book_quiz', 'reading_quiz', 'video', 'essay', 'b2b_workbook']
DEFAULT_ORDER = ['vocab_quiz', 'book_quiz', 'reading_quiz', 'video', 'essay', 'b2b_workbook']


def _hq_only():
    return current_user.is_hq


# ═══════════════════════════════════════════════
# 커리큘럼 관리
# ═══════════════════════════════════════════════

@lms_bp.route('/')
@login_required
def index():
    if not _hq_only(): abort(403)
    return redirect(url_for('lms.hq_dashboard'))


# ═══════════════════════════════════════════════
# HQ 전체 현황 대시보드
# ═══════════════════════════════════════════════

@lms_bp.route('/dashboard')
@login_required
def hq_dashboard():
    if not _hq_only(): abort(403)

    # ── 전체 요약 ──
    total_packages = Package.query.filter_by(is_active=True).count()
    total_branch_assignments = BranchPackageAssignment.query.filter_by(is_active=True).count()
    total_student_assignments = StudentPackageAssignment.query.filter_by(is_active=True).count()
    total_completed = StudentItemProgress.query.filter_by(status='completed').count()

    # ── 패키지별 현황 ──
    packages = Package.query.filter_by(is_active=True).order_by(Package.created_at.desc()).all()
    package_stats = []
    for p in packages:
        branch_cnt = BranchPackageAssignment.query.filter_by(
            package_id=p.package_id, is_active=True).count()
        student_assignments = StudentPackageAssignment.query.filter_by(
            package_id=p.package_id, is_active=True).all()
        student_cnt = len(student_assignments)

        total_items = sum(len(pc.curriculum.items) for pc in p.curricula)
        avg_pct = None
        if student_assignments and total_items > 0:
            pct_list = []
            for sa in student_assignments:
                done = StudentItemProgress.query.filter_by(
                    assignment_id=sa.id, status='completed').count()
                pct_list.append(done / total_items * 100)
            avg_pct = round(sum(pct_list) / len(pct_list))

        package_stats.append({
            'package': p,
            'branch_cnt': branch_cnt,
            'student_cnt': student_cnt,
            'avg_pct': avg_pct,
        })

    # ── 지점별 현황 ──
    branches = Branch.query.filter_by(status='active').order_by(Branch.name).all()
    branch_stats = []
    for b in branches:
        pkg_cnt = BranchPackageAssignment.query.filter_by(
            branch_id=b.branch_id, is_active=True).count()
        if pkg_cnt == 0:
            continue
        s_assignments = StudentPackageAssignment.query.filter_by(
            branch_id=b.branch_id, is_active=True).all()
        s_cnt = len(s_assignments)

        avg_pct = None
        if s_assignments:
            pct_list = []
            for sa in s_assignments:
                total_items = sum(len(pc.curriculum.items) for pc in sa.package.curricula)
                if total_items == 0:
                    continue
                done = StudentItemProgress.query.filter_by(
                    assignment_id=sa.id, status='completed').count()
                pct_list.append(done / total_items * 100)
            if pct_list:
                avg_pct = round(sum(pct_list) / len(pct_list))

        branch_stats.append({
            'branch': b,
            'pkg_cnt': pkg_cnt,
            'student_cnt': s_cnt,
            'avg_pct': avg_pct,
        })

    branch_stats.sort(key=lambda x: (x['avg_pct'] or 0), reverse=True)

    return render_template('lms/dashboard.html',
                           total_packages=total_packages,
                           total_branch_assignments=total_branch_assignments,
                           total_student_assignments=total_student_assignments,
                           total_completed=total_completed,
                           package_stats=package_stats,
                           branch_stats=branch_stats)


@lms_bp.route('/curricula')
@login_required
def curriculum_list():
    if not _hq_only(): abort(403)
    q = request.args.get('q', '').strip()
    query = Curriculum.query.filter_by(is_active=True)
    if q:
        query = query.filter(Curriculum.title.ilike(f'%{q}%'))
    curricula = query.order_by(Curriculum.created_at.desc()).all()
    return render_template('lms/curriculum/list.html', curricula=curricula, q=q)


@lms_bp.route('/curricula/new', methods=['GET', 'POST'])
@login_required
def curriculum_new():
    if not _hq_only(): abort(403)
    if request.method == 'POST':
        c = Curriculum(
            title=request.form['title'],
            description=request.form.get('description', ''),
            created_by=current_user.user_id,
        )
        db.session.add(c)
        db.session.commit()
        flash('커리큘럼이 생성되었습니다.', 'success')
        return redirect(url_for('lms.curriculum_detail', curriculum_id=c.curriculum_id))
    return render_template('lms/curriculum/form.html')


@lms_bp.route('/curricula/<curriculum_id>')
@login_required
def curriculum_detail(curriculum_id):
    if not _hq_only(): abort(403)
    c = Curriculum.query.filter_by(curriculum_id=curriculum_id, is_active=True).first_or_404()
    return render_template('lms/curriculum/detail.html', curriculum=c,
                           content_types=CONTENT_TYPES)


@lms_bp.route('/curricula/<curriculum_id>/edit', methods=['POST'])
@login_required
def curriculum_edit(curriculum_id):
    if not _hq_only(): abort(403)
    c = Curriculum.query.filter_by(curriculum_id=curriculum_id, is_active=True).first_or_404()
    c.title       = request.form['title']
    c.description = request.form.get('description', '')
    c.version    += 1
    c.updated_at  = datetime.utcnow()
    db.session.commit()
    flash('수정되었습니다. (버전 업)' , 'success')
    return redirect(url_for('lms.curriculum_detail', curriculum_id=curriculum_id))


@lms_bp.route('/curricula/<curriculum_id>/delete', methods=['POST'])
@login_required
def curriculum_delete(curriculum_id):
    if not _hq_only(): abort(403)
    c = Curriculum.query.filter_by(curriculum_id=curriculum_id).first_or_404()
    c.is_active = False
    db.session.commit()
    flash('삭제되었습니다.', 'success')
    return redirect(url_for('lms.curriculum_list'))


@lms_bp.route('/curricula/<curriculum_id>/clone', methods=['POST'])
@login_required
def curriculum_clone(curriculum_id):
    """2026-09-28: 매주 비슷한 구조의 커리큘럼을 매번 빈 화면에서 새로
    만드는 게 반복 작업 시간을 많이 잡아먹어서 - 콘텐츠 아이템까지 통째로
    복사한 새 커리큘럼을 만든다(원본은 그대로 둠)."""
    if not _hq_only(): abort(403)
    src = Curriculum.query.filter_by(curriculum_id=curriculum_id, is_active=True).first_or_404()

    clone = Curriculum(
        title=f'{src.title} (복사본)',
        description=src.description,
        created_by=current_user.user_id,
    )
    db.session.add(clone)
    db.session.flush()

    for item in src.items:
        db.session.add(CurriculumItem(
            curriculum_id=clone.curriculum_id,
            order_num=item.order_num,
            content_type=item.content_type,
            content_id=item.content_id,
            option_group=item.option_group,
        ))
    db.session.commit()
    flash(f'"{src.title}"을(를) 복제했습니다.', 'success')
    return redirect(url_for('lms.curriculum_detail', curriculum_id=clone.curriculum_id))


# ── 아이템 추가/삭제/이동 ──────────────────────────

@lms_bp.route('/curricula/<curriculum_id>/items/add', methods=['POST'])
@login_required
def curriculum_item_add(curriculum_id):
    if not _hq_only(): abort(403)
    c = Curriculum.query.filter_by(curriculum_id=curriculum_id, is_active=True).first_or_404()

    content_type = request.form.get('content_type')
    content_ids  = request.form.getlist('content_ids')  # 여러 개
    option_group = request.form.get('option_group') or None

    if content_type not in CONTENT_TYPES or not content_ids:
        flash('콘텐츠를 하나 이상 선택해주세요.', 'error')
        return redirect(url_for('lms.curriculum_detail', curriculum_id=curriculum_id))

    max_order = max((i.order_num for i in c.items), default=-1)
    for idx, content_id in enumerate(content_ids):
        item = CurriculumItem(
            curriculum_id=curriculum_id,
            order_num=max_order + 1 + idx,
            content_type=content_type,
            content_id=content_id,
            option_group=option_group,
        )
        db.session.add(item)
    c.version   += 1
    c.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'{len(content_ids)}개 추가되었습니다.', 'success')
    return redirect(url_for('lms.curriculum_detail', curriculum_id=curriculum_id))


@lms_bp.route('/curricula/<curriculum_id>/items/<int:item_id>/delete', methods=['POST'])
@login_required
def curriculum_item_delete(curriculum_id, item_id):
    if not _hq_only(): abort(403)
    item = CurriculumItem.query.filter_by(item_id=item_id,
                                          curriculum_id=curriculum_id).first_or_404()
    c = item.curriculum
    db.session.delete(item)
    # 순서 재정렬
    remaining = CurriculumItem.query.filter_by(curriculum_id=curriculum_id)\
                    .order_by(CurriculumItem.order_num).all()
    for i, r in enumerate(remaining):
        r.order_num = i
    c.version   += 1
    c.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('lms.curriculum_detail', curriculum_id=curriculum_id))


@lms_bp.route('/curricula/<curriculum_id>/items/<int:item_id>/move', methods=['POST'])
@login_required
def curriculum_item_move(curriculum_id, item_id):
    if not _hq_only(): abort(403)
    direction = request.form.get('direction')  # 'up' or 'down'
    items = CurriculumItem.query.filter_by(curriculum_id=curriculum_id)\
                .order_by(CurriculumItem.order_num).all()
    idx = next((i for i, x in enumerate(items) if x.item_id == item_id), None)
    if idx is None:
        abort(404)
    swap = idx - 1 if direction == 'up' else idx + 1
    if 0 <= swap < len(items):
        items[idx].order_num, items[swap].order_num = items[swap].order_num, items[idx].order_num
        c = items[idx].curriculum
        c.version   += 1
        c.updated_at = datetime.utcnow()
        db.session.commit()
    return redirect(url_for('lms.curriculum_detail', curriculum_id=curriculum_id))


# ── 콘텐츠 검색 API (AJAX) ─────────────────────────

@lms_bp.route('/content-search')
@login_required
def content_search():
    if not _hq_only(): abort(403)
    content_type = request.args.get('type', '')
    q = request.args.get('q', '').strip()

    results = []
    if content_type == 'video':
        query = LectureVideo.query.filter_by(is_published=True)
        if q:
            query = query.filter(LectureVideo.title.ilike(f'%{q}%'))
        for v in query.order_by(LectureVideo.title).limit(30).all():
            results.append({'id': v.video_id, 'title': v.title,
                            'sub': v.duration_display})
    elif content_type == 'b2b_workbook':
        # 2026-09-28: aprolabs가 진짜 목록을 갖고 있다 - momolib DB에는 없음.
        from app.services.aprolabs_client import list_approved_editions, AprolabsError
        try:
            for e in list_approved_editions(q)[:30]:
                sub = e.get('band', '')
                if e.get('week'):
                    sub += f" {e['week']}"
                results.append({'id': str(e['edition_id']),
                                 'title': f"{e.get('title', '')} ({e.get('doc_id', '')})",
                                 'sub': sub.strip()})
        except AprolabsError:
            pass  # 목록 API 자체가 [] 반환 - 화면에 "검색 결과 없음"으로만 보임
    elif content_type in CONTENT_TYPES:
        query = BankQuestion.query.filter_by(type=content_type, is_active=True)
        if q:
            query = query.filter(BankQuestion.title.ilike(f'%{q}%'))
        for bq in query.order_by(BankQuestion.title).limit(30).all():
            sub = bq.book.title if bq.book else ''
            if bq.week_num:
                sub += f' {bq.week_num}주차'
            results.append({'id': bq.question_id, 'title': bq.title, 'sub': sub.strip()})

    return jsonify(results)


# ═══════════════════════════════════════════════
# 패키지 관리
# ═══════════════════════════════════════════════

@lms_bp.route('/packages')
@login_required
def package_list():
    if not _hq_only(): abort(403)
    q = request.args.get('q', '').strip()
    query = Package.query.filter_by(is_active=True)
    if q:
        query = query.filter(Package.title.ilike(f'%{q}%'))
    packages = query.order_by(Package.created_at.desc()).all()
    return render_template('lms/package/list.html', packages=packages, q=q)


@lms_bp.route('/packages/new', methods=['GET', 'POST'])
@login_required
def package_new():
    if not _hq_only(): abort(403)
    if request.method == 'POST':
        p = Package(
            title=request.form['title'],
            description=request.form.get('description', ''),
            is_ordered=request.form.get('is_ordered') == '1',
            created_by=current_user.user_id,
        )
        db.session.add(p)
        db.session.commit()
        flash('패키지가 생성되었습니다.', 'success')
        return redirect(url_for('lms.package_detail', package_id=p.package_id))
    return render_template('lms/package/form.html')


@lms_bp.route('/packages/<package_id>')
@login_required
def package_detail(package_id):
    if not _hq_only(): abort(403)
    p = Package.query.filter_by(package_id=package_id, is_active=True).first_or_404()
    branches = Branch.query.filter_by(status='active').order_by(Branch.name).all()
    assigned_branch_ids = {a.branch_id for a in p.branch_assignments if a.is_active}
    return render_template('lms/package/detail.html', package=p,
                           branches=branches, assigned_branch_ids=assigned_branch_ids)


@lms_bp.route('/packages/<package_id>/edit', methods=['POST'])
@login_required
def package_edit(package_id):
    if not _hq_only(): abort(403)
    p = Package.query.filter_by(package_id=package_id, is_active=True).first_or_404()
    p.title       = request.form['title']
    p.description = request.form.get('description', '')
    p.is_ordered  = request.form.get('is_ordered') == '1'
    p.version    += 1
    p.updated_at  = datetime.utcnow()
    db.session.commit()
    flash('수정되었습니다.', 'success')
    return redirect(url_for('lms.package_detail', package_id=package_id))


@lms_bp.route('/packages/<package_id>/delete', methods=['POST'])
@login_required
def package_delete(package_id):
    if not _hq_only(): abort(403)
    p = Package.query.filter_by(package_id=package_id).first_or_404()
    p.is_active = False
    db.session.commit()
    flash('삭제되었습니다.', 'success')
    return redirect(url_for('lms.package_list'))


@lms_bp.route('/packages/<package_id>/clone', methods=['POST'])
@login_required
def package_clone(package_id):
    """2026-09-28: 커리큘럼 구성만 복사 - 지점 배정은 일부러 복사하지
    않는다(어느 지점에 내려줄지는 매번 새로 판단해야 하는 배포 결정이라,
    구조 복제와 섞으면 실수로 잘못된 지점에 배정될 위험이 있음)."""
    if not _hq_only(): abort(403)
    src = Package.query.filter_by(package_id=package_id, is_active=True).first_or_404()

    clone = Package(
        title=f'{src.title} (복사본)',
        description=src.description,
        is_ordered=src.is_ordered,
        created_by=current_user.user_id,
    )
    db.session.add(clone)
    db.session.flush()

    for pc in src.curricula:
        db.session.add(PackageCurriculum(
            package_id=clone.package_id,
            curriculum_id=pc.curriculum_id,
            curriculum_version=pc.curriculum_version,
            order_num=pc.order_num,
        ))
    db.session.commit()
    flash(f'"{src.title}"을(를) 복제했습니다. 지점 배정은 새로 해주세요.', 'success')
    return redirect(url_for('lms.package_detail', package_id=clone.package_id))


# ── 패키지 커리큘럼 추가/삭제/이동 ──────────────────

@lms_bp.route('/packages/<package_id>/curricula/add', methods=['POST'])
@login_required
def package_curriculum_add(package_id):
    if not _hq_only(): abort(403)
    p = Package.query.filter_by(package_id=package_id, is_active=True).first_or_404()
    # 2026-09-28: 예전엔 curriculum_id 하나만 받았음 - getlist로 바꿔서
    # 여러 커리큘럼을 한 번에 추가(체크박스 다중선택). 단일값으로 와도
    # getlist가 [값] 하나짜리 리스트를 주므로 그대로 동작한다.
    curriculum_ids = request.form.getlist('curriculum_ids') or \
        ([request.form['curriculum_id']] if request.form.get('curriculum_id') else [])
    if not curriculum_ids:
        flash('커리큘럼을 하나 이상 선택해주세요.', 'error')
        return redirect(url_for('lms.package_detail', package_id=package_id))

    already_in = {pc.curriculum_id for pc in p.curricula}
    max_order = max((pc.order_num for pc in p.curricula), default=-1)
    added = 0
    for idx, curriculum_id in enumerate(curriculum_ids):
        if curriculum_id in already_in:
            continue
        c = Curriculum.query.filter_by(curriculum_id=curriculum_id, is_active=True).first()
        if c is None:
            continue
        db.session.add(PackageCurriculum(
            package_id=package_id,
            curriculum_id=curriculum_id,
            curriculum_version=c.version,
            order_num=max_order + 1 + added,
        ))
        already_in.add(curriculum_id)
        added += 1

    if added:
        p.version   += 1
        p.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'{added}개 커리큘럼을 추가했습니다.', 'success')
    else:
        flash('이미 포함되어 있거나 유효하지 않은 커리큘럼입니다.', 'warning')
    return redirect(url_for('lms.package_detail', package_id=package_id))


@lms_bp.route('/packages/<package_id>/curricula/<int:pc_id>/delete', methods=['POST'])
@login_required
def package_curriculum_delete(package_id, pc_id):
    if not _hq_only(): abort(403)
    pc = PackageCurriculum.query.filter_by(id=pc_id, package_id=package_id).first_or_404()
    p = pc.package
    db.session.delete(pc)
    remaining = PackageCurriculum.query.filter_by(package_id=package_id)\
                    .order_by(PackageCurriculum.order_num).all()
    for i, r in enumerate(remaining):
        r.order_num = i
    p.version   += 1
    p.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('lms.package_detail', package_id=package_id))


@lms_bp.route('/packages/<package_id>/curricula/<int:pc_id>/move', methods=['POST'])
@login_required
def package_curriculum_move(package_id, pc_id):
    if not _hq_only(): abort(403)
    direction = request.form.get('direction')
    pcs = PackageCurriculum.query.filter_by(package_id=package_id)\
              .order_by(PackageCurriculum.order_num).all()
    idx = next((i for i, x in enumerate(pcs) if x.id == pc_id), None)
    if idx is None:
        abort(404)
    swap = idx - 1 if direction == 'up' else idx + 1
    if 0 <= swap < len(pcs):
        pcs[idx].order_num, pcs[swap].order_num = pcs[swap].order_num, pcs[idx].order_num
        p = pcs[idx].package
        p.version   += 1
        p.updated_at = datetime.utcnow()
        db.session.commit()
    return redirect(url_for('lms.package_detail', package_id=package_id))


# ═══════════════════════════════════════════════
# 지점 패키지 배정 (HQ 전용)
# ═══════════════════════════════════════════════

@lms_bp.route('/packages/<package_id>/branches/add', methods=['POST'])
@login_required
def package_branch_add(package_id):
    if not _hq_only(): abort(403)
    p = Package.query.filter_by(package_id=package_id, is_active=True).first_or_404()
    # 2026-09-28: branch_id 단일값 → branch_ids 다중선택(체크박스)으로 확장.
    # 예전 단일 select 폼이 남아있어도 getlist('branch_id')가 [값] 하나짜리
    # 리스트를 주므로 호환된다.
    branch_ids = request.form.getlist('branch_ids') or request.form.getlist('branch_id')
    if not branch_ids:
        flash('지점을 하나 이상 선택해주세요.', 'error')
        return redirect(url_for('lms.package_detail', package_id=package_id))

    expires_at = request.form.get('expires_at') or None
    if expires_at:
        from datetime import date
        expires_at = date.fromisoformat(expires_at)

    already = {a.branch_id for a in p.branch_assignments if a.is_active}
    added = 0
    for branch_id in branch_ids:
        if branch_id in already:
            continue
        db.session.add(BranchPackageAssignment(
            branch_id=branch_id,
            package_id=package_id,
            assigned_by=current_user.user_id,
            expires_at=expires_at,
        ))
        already.add(branch_id)
        added += 1

    if added:
        db.session.commit()
        flash(f'{added}개 지점에 패키지를 배정했습니다.', 'success')
    else:
        flash('이미 배정된 지점들입니다.', 'warning')
    return redirect(url_for('lms.package_detail', package_id=package_id))


@lms_bp.route('/packages/<package_id>/branches/<int:assignment_id>/delete', methods=['POST'])
@login_required
def package_branch_delete(package_id, assignment_id):
    if not _hq_only(): abort(403)
    a = BranchPackageAssignment.query.filter_by(
        id=assignment_id, package_id=package_id).first_or_404()
    a.is_active = False
    db.session.commit()
    flash('배정을 해제했습니다.', 'success')
    return redirect(url_for('lms.package_detail', package_id=package_id))


# ── 지점용 패키지 목록 API ─────────────────────────

@lms_bp.route('/branch-packages')
@login_required
def branch_packages():
    """지점에 배정된 패키지 목록 (지점 포털용 API)"""
    from app.models.user import User
    if current_user.is_hq: abort(403)
    if not (current_user.is_branch_owner or current_user.is_branch_staff): abort(403)

    branch_id = current_user.branch_id
    assignments = BranchPackageAssignment.query.filter_by(
        branch_id=branch_id, is_active=True).all()
    results = [{'id': a.package_id, 'title': a.package.title,
                'sub': f'{a.package.curriculum_count}개 커리큘럼 · v{a.package.version}'}
               for a in assignments if a.package.is_active]
    return jsonify(results)


# ═══════════════════════════════════════════════
# 학생 패키지 배정 (지점 포털용)
# ═══════════════════════════════════════════════

def _branch_staff_only():
    return current_user.is_branch_owner or current_user.is_branch_staff


@lms_bp.route('/students/<student_id>/packages/assign', methods=['POST'])
@login_required
def student_package_assign(student_id):
    if not _branch_staff_only(): abort(403)
    branch_id = current_user.branch_id

    # 해당 지점 학생인지 확인
    profile = StudentProfile.query.filter_by(
        user_id=student_id, branch_id=branch_id).first_or_404()

    package_id = request.form.get('package_id')
    if not package_id:
        flash('패키지를 선택해주세요.', 'error')
        return redirect(url_for('branch.member_detail', user_id=student_id))

    # 지점에 배정된 패키지인지 확인
    branch_assignment = BranchPackageAssignment.query.filter_by(
        branch_id=branch_id, package_id=package_id, is_active=True).first()
    if not branch_assignment:
        flash('해당 패키지를 사용할 권한이 없습니다.', 'error')
        return redirect(url_for('branch.member_detail', user_id=student_id))

    # 이미 배정됐는지 확인
    exists = StudentPackageAssignment.query.filter_by(
        student_id=student_id, package_id=package_id, is_active=True).first()
    if exists:
        flash('이미 배정된 패키지입니다.', 'warning')
        return redirect(url_for('branch.member_detail', user_id=student_id))

    from datetime import date
    start_date = request.form.get('start_date') or None
    end_date   = request.form.get('end_date') or None
    if start_date:
        start_date = date.fromisoformat(start_date)
    if end_date:
        end_date = date.fromisoformat(end_date)

    a = StudentPackageAssignment(
        student_id=student_id,
        package_id=package_id,
        branch_id=branch_id,
        assigned_by=current_user.user_id,
        start_date=start_date,
        end_date=end_date,
    )
    db.session.add(a)
    db.session.commit()
    flash('패키지를 배정했습니다.', 'success')
    return redirect(url_for('branch.member_detail', user_id=student_id))


@lms_bp.route('/students/packages/bulk-assign', methods=['POST'])
@login_required
def student_package_bulk_assign():
    """2026-09-28: 지점 회원 목록에서 학생 여러 명을 체크해 패키지 하나를
    한 번에 배정 - 반 전체 배정처럼 매주 반복되는 작업 시간을 줄이기 위함.
    학생별 로직은 student_package_assign()과 동일(지점 소속·배정권한·
    중복배정 확인)하되 여러 명을 한 트랜잭션에서 처리한다."""
    if not _branch_staff_only(): abort(403)
    branch_id = current_user.branch_id

    student_ids = request.form.getlist('student_ids')
    package_id = request.form.get('package_id')
    if not student_ids or not package_id:
        flash('학생과 패키지를 모두 선택해주세요.', 'error')
        return redirect(url_for('branch.members'))

    branch_assignment = BranchPackageAssignment.query.filter_by(
        branch_id=branch_id, package_id=package_id, is_active=True).first()
    if not branch_assignment:
        flash('해당 패키지를 사용할 권한이 없습니다.', 'error')
        return redirect(url_for('branch.members'))

    from datetime import date
    start_date = request.form.get('start_date') or None
    end_date   = request.form.get('end_date') or None
    if start_date:
        start_date = date.fromisoformat(start_date)
    if end_date:
        end_date = date.fromisoformat(end_date)

    valid_student_ids = {
        p.user_id for p in StudentProfile.query.filter(
            StudentProfile.user_id.in_(student_ids), StudentProfile.branch_id == branch_id
        ).all()
    }
    already = {
        a.student_id for a in StudentPackageAssignment.query.filter_by(
            package_id=package_id, is_active=True
        ).filter(StudentPackageAssignment.student_id.in_(student_ids)).all()
    }

    added = 0
    for student_id in student_ids:
        if student_id not in valid_student_ids or student_id in already:
            continue
        db.session.add(StudentPackageAssignment(
            student_id=student_id, package_id=package_id, branch_id=branch_id,
            assigned_by=current_user.user_id, start_date=start_date, end_date=end_date,
        ))
        added += 1

    if added:
        db.session.commit()
        flash(f'학생 {added}명에게 패키지를 배정했습니다.', 'success')
    else:
        flash('선택한 학생 모두 이미 배정되어 있거나 유효하지 않습니다.', 'warning')
    return redirect(url_for('branch.members'))


@lms_bp.route('/students/<student_id>/packages/<int:assignment_id>/revoke', methods=['POST'])
@login_required
def student_package_revoke(student_id, assignment_id):
    if not _branch_staff_only(): abort(403)
    branch_id = current_user.branch_id
    a = StudentPackageAssignment.query.filter_by(
        id=assignment_id, student_id=student_id, branch_id=branch_id).first_or_404()
    a.is_active = False
    db.session.commit()
    flash('배정을 해제했습니다.', 'success')
    return redirect(url_for('branch.member_detail', user_id=student_id))


# ── 패키지 커리큘럼 검색 API ──────────────────────

@lms_bp.route('/curriculum-search')
@login_required
def curriculum_search():
    if not _hq_only(): abort(403)
    q = request.args.get('q', '').strip()
    query = Curriculum.query.filter_by(is_active=True)
    if q:
        query = query.filter(Curriculum.title.ilike(f'%{q}%'))
    results = [{'id': c.curriculum_id, 'title': c.title,
                'sub': f'{c.item_count}개 콘텐츠 · v{c.version}'}
               for c in query.order_by(Curriculum.title).limit(30).all()]
    return jsonify(results)
