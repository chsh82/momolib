# -*- coding: utf-8 -*-
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.lms import lms_bp
from app.models import db
from app.models.lms import Curriculum, CurriculumItem, Package, PackageCurriculum
from app.models.content_bank import BankQuestion, LectureVideo

CONTENT_TYPES = ['vocab_quiz', 'book_quiz', 'reading_quiz', 'video', 'essay']
DEFAULT_ORDER = ['vocab_quiz', 'book_quiz', 'reading_quiz', 'video', 'essay']


def _hq_only():
    return current_user.is_hq


# ═══════════════════════════════════════════════
# 커리큘럼 관리
# ═══════════════════════════════════════════════

@lms_bp.route('/')
@login_required
def index():
    return redirect(url_for('lms.curriculum_list'))


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


# ── 아이템 추가/삭제/이동 ──────────────────────────

@lms_bp.route('/curricula/<curriculum_id>/items/add', methods=['POST'])
@login_required
def curriculum_item_add(curriculum_id):
    if not _hq_only(): abort(403)
    c = Curriculum.query.filter_by(curriculum_id=curriculum_id, is_active=True).first_or_404()

    content_type = request.form.get('content_type')
    content_id   = request.form.get('content_id')
    option_group = request.form.get('option_group') or None

    if content_type not in CONTENT_TYPES or not content_id:
        flash('콘텐츠를 선택해주세요.', 'error')
        return redirect(url_for('lms.curriculum_detail', curriculum_id=curriculum_id))

    max_order = max((i.order_num for i in c.items), default=-1)
    item = CurriculumItem(
        curriculum_id=curriculum_id,
        order_num=max_order + 1,
        content_type=content_type,
        content_id=content_id,
        option_group=option_group,
    )
    db.session.add(item)
    # 커리큘럼 버전 증가
    c.version   += 1
    c.updated_at = datetime.utcnow()
    db.session.commit()
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
    return render_template('lms/package/detail.html', package=p)


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


# ── 패키지 커리큘럼 추가/삭제/이동 ──────────────────

@lms_bp.route('/packages/<package_id>/curricula/add', methods=['POST'])
@login_required
def package_curriculum_add(package_id):
    if not _hq_only(): abort(403)
    p = Package.query.filter_by(package_id=package_id, is_active=True).first_or_404()
    curriculum_id = request.form.get('curriculum_id')
    c = Curriculum.query.filter_by(curriculum_id=curriculum_id, is_active=True).first_or_404()

    max_order = max((pc.order_num for pc in p.curricula), default=-1)
    pc = PackageCurriculum(
        package_id=package_id,
        curriculum_id=curriculum_id,
        curriculum_version=c.version,
        order_num=max_order + 1,
    )
    db.session.add(pc)
    p.version   += 1
    p.updated_at = datetime.utcnow()
    db.session.commit()
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
