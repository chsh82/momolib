# -*- coding: utf-8 -*-
import os
import uuid
from datetime import datetime
from flask import (render_template, redirect, url_for, flash,
                   request, jsonify, send_from_directory, abort)
from flask_login import login_required, current_user
from app.cms import cms_bp
from app.models import db
from app.models.branch import Branch
from app.models.content import ContentItem, ContentPermission, ContentView
from app.models.library import Book
from app.models.content_bank import (
    BankQuestion, LectureVideo, MockExam, MockExamQuestion, StudyMaterial,
    BANK_QUESTION_TYPES, DIFFICULTY_CHOICES, EXAM_QUESTION_TYPES, MATERIAL_TYPES,
)
from app.utils.decorators import requires_role
from app.models.notification import Notification

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'materials')
ALLOWED_EXTENSIONS = {'pdf', 'hwp', 'docx', 'pptx', 'xlsx', 'zip'}


def _ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_file(file_obj):
    """파일 저장 후 (저장경로, 원본명, 확장자, 크기) 반환"""
    _ensure_upload_dir()
    original_name = file_obj.filename
    ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else 'bin'
    saved_name = f"{uuid.uuid4().hex}.{ext}"
    full_path = os.path.join(UPLOAD_DIR, saved_name)
    file_obj.save(full_path)
    size = os.path.getsize(full_path)
    return f"uploads/materials/{saved_name}", original_name, ext, size


def _hq_only():
    return current_user.is_hq


# ═══════════════════════════════════════════════
# CMS 메인 인덱스 (공지)
# ═══════════════════════════════════════════════

@cms_bp.route('/')
@login_required
@requires_role('super_admin', 'hq_manager')
def index():
    items = ContentItem.query.order_by(ContentItem.created_at.desc()).all()
    return render_template('cms/index.html', items=items)


@cms_bp.route('/new', methods=['GET', 'POST'])
@login_required
@requires_role('super_admin', 'hq_manager')
def new_content():
    branches = Branch.query.filter_by(status='active').order_by(Branch.code).all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content_type = request.form.get('content_type', 'notice')
        body = request.form.get('body', '').strip()
        is_global = request.form.get('is_global') == 'on'
        target_branches = request.form.getlist('target_branches')
        is_published = request.form.get('is_published') == 'on'
        if not title:
            flash('제목을 입력해주세요.', 'error')
            return render_template('cms/new_content.html', branches=branches)
        item = ContentItem(title=title, content_type=content_type, body=body,
                           is_global=is_global, is_published=is_published,
                           created_by=current_user.user_id)
        db.session.add(item)
        db.session.flush()
        if not is_global and target_branches:
            for branch_id in target_branches:
                db.session.add(ContentPermission(content_id=item.content_id,
                                                  branch_id=branch_id,
                                                  granted_by=current_user.user_id))
        db.session.flush()
        if is_published:
            notif_link = url_for('branch.notice_detail', content_id=item.content_id)
            if is_global:
                Notification.send_to_all_branches(
                    title=f'[본사 공지] {title}', notif_type='new_notice',
                    link_url=notif_link,
                    roles=['branch_owner', 'branch_manager', 'teacher'])
            elif target_branches:
                for bid in target_branches:
                    Notification.send_to_branch(branch_id=bid,
                                                title=f'[본사 공지] {title}',
                                                notif_type='new_notice',
                                                link_url=notif_link,
                                                roles=['branch_owner', 'branch_manager', 'teacher'])
        db.session.commit()
        flash(f'콘텐츠가 {"발행" if is_published else "저장"}되었습니다.', 'success')
        return redirect(url_for('cms.index'))
    return render_template('cms/new_content.html', branches=branches)


@cms_bp.route('/<content_id>/publish', methods=['POST'])
@login_required
@requires_role('super_admin', 'hq_manager')
def publish(content_id):
    item = ContentItem.query.get_or_404(content_id)
    item.is_published = not item.is_published
    db.session.commit()
    status = '발행' if item.is_published else '발행 취소'
    return jsonify({'success': True, 'published': item.is_published, 'message': f'{status}되었습니다.'})


@cms_bp.route('/<content_id>/views')
@login_required
@requires_role('super_admin', 'hq_manager')
def view_stats(content_id):
    item = ContentItem.query.get_or_404(content_id)
    views = ContentView.query.filter_by(content_id=content_id)\
        .order_by(ContentView.viewed_at.desc()).all()
    branches = Branch.query.filter_by(status='active').all()
    return render_template('cms/view_stats.html', item=item, views=views, branches=branches)


# ═══════════════════════════════════════════════
# 공통 헬퍼
# ═══════════════════════════════════════════════

def _all_books():
    return Book.query.filter_by(is_active=True).order_by(Book.title).all()


# ═══════════════════════════════════════════════
# 1. 어휘 퀴즈 관리
# ═══════════════════════════════════════════════

@cms_bp.route('/vocab')
@login_required
def vocab_list():
    if not _hq_only(): abort(403)
    q = request.args.get('q', '').strip()
    book_id = request.args.get('book_id', '')
    query = BankQuestion.query.filter_by(type='vocab_quiz', is_active=True)
    if q:
        query = query.filter(BankQuestion.title.ilike(f'%{q}%') |
                             BankQuestion.tags.ilike(f'%{q}%'))
    if book_id:
        query = query.filter_by(book_id=book_id)
    questions = query.order_by(BankQuestion.created_at.desc()).all()
    books = _all_books()
    return render_template('cms/vocab/list.html', questions=questions,
                           q=q, book_id=book_id, books=books)


@cms_bp.route('/vocab/new', methods=['GET', 'POST'])
@login_required
def vocab_new():
    if not _hq_only(): abort(403)
    if request.method == 'POST':
        choices = [request.form.get(f'choice_{i}', '') for i in range(4)]
        data = {
            'word': request.form.get('word', ''),
            'definition': request.form.get('definition', ''),
            'choices': choices,
            'correct_idx': int(request.form.get('correct_idx', 0)),
        }
        q = BankQuestion(
            type='vocab_quiz',
            title=request.form['title'],
            book_id=request.form.get('book_id') or None,
            week_num=request.form.get('week_num') or None,
            difficulty=request.form.get('difficulty', 'medium'),
            tags=request.form.get('tags'),
            data=data,
            created_by=current_user.user_id,
        )
        db.session.add(q)
        db.session.commit()
        flash('어휘 퀴즈가 등록되었습니다.', 'success')
        return redirect(url_for('cms.vocab_list'))
    return render_template('cms/vocab/form.html', books=_all_books(),
                           difficulty_choices=DIFFICULTY_CHOICES)


@cms_bp.route('/vocab/<question_id>/edit', methods=['GET', 'POST'])
@login_required
def vocab_edit(question_id):
    if not _hq_only(): abort(403)
    q = BankQuestion.query.filter_by(question_id=question_id, type='vocab_quiz').first_or_404()
    if request.method == 'POST':
        choices = [request.form.get(f'choice_{i}', '') for i in range(4)]
        q.title = request.form['title']
        q.book_id = request.form.get('book_id') or None
        q.week_num = request.form.get('week_num') or None
        q.difficulty = request.form.get('difficulty', 'medium')
        q.tags = request.form.get('tags')
        q.data = {
            'word': request.form.get('word', ''),
            'definition': request.form.get('definition', ''),
            'choices': choices,
            'correct_idx': int(request.form.get('correct_idx', 0)),
        }
        db.session.commit()
        flash('수정되었습니다.', 'success')
        return redirect(url_for('cms.vocab_list'))
    return render_template('cms/vocab/form.html', question=q, books=_all_books(),
                           difficulty_choices=DIFFICULTY_CHOICES)


@cms_bp.route('/vocab/<question_id>/delete', methods=['POST'])
@login_required
def vocab_delete(question_id):
    if not _hq_only(): abort(403)
    q = BankQuestion.query.filter_by(question_id=question_id, type='vocab_quiz').first_or_404()
    q.is_active = False
    db.session.commit()
    flash('삭제되었습니다.', 'success')
    return redirect(url_for('cms.vocab_list'))


# ═══════════════════════════════════════════════
# 2. 독서 퀴즈 관리
# ═══════════════════════════════════════════════

@cms_bp.route('/reading-quiz')
@login_required
def reading_quiz_list():
    if not _hq_only(): abort(403)
    q = request.args.get('q', '').strip()
    book_id = request.args.get('book_id', '')
    query = BankQuestion.query.filter_by(type='reading_quiz', is_active=True)
    if q:
        query = query.filter(BankQuestion.title.ilike(f'%{q}%'))
    if book_id:
        query = query.filter_by(book_id=book_id)
    questions = query.order_by(BankQuestion.created_at.desc()).all()
    return render_template('cms/reading_quiz/list.html', questions=questions,
                           q=q, book_id=book_id, books=_all_books())


@cms_bp.route('/reading-quiz/new', methods=['GET', 'POST'])
@login_required
def reading_quiz_new():
    if not _hq_only(): abort(403)
    if request.method == 'POST':
        choices = [request.form.get(f'choice_{i}', '') for i in range(4)]
        data = {
            'passage': request.form.get('passage', ''),
            'question': request.form.get('question', ''),
            'choices': choices,
            'correct_idx': int(request.form.get('correct_idx', 0)),
            'explanation': request.form.get('explanation', ''),
        }
        q = BankQuestion(
            type='reading_quiz',
            title=request.form['title'],
            book_id=request.form.get('book_id') or None,
            week_num=request.form.get('week_num') or None,
            difficulty=request.form.get('difficulty', 'medium'),
            tags=request.form.get('tags'),
            data=data,
            created_by=current_user.user_id,
        )
        db.session.add(q)
        db.session.commit()
        flash('독서 퀴즈가 등록되었습니다.', 'success')
        return redirect(url_for('cms.reading_quiz_list'))
    return render_template('cms/reading_quiz/form.html', books=_all_books(),
                           difficulty_choices=DIFFICULTY_CHOICES)


@cms_bp.route('/reading-quiz/<question_id>/edit', methods=['GET', 'POST'])
@login_required
def reading_quiz_edit(question_id):
    if not _hq_only(): abort(403)
    q = BankQuestion.query.filter_by(question_id=question_id, type='reading_quiz').first_or_404()
    if request.method == 'POST':
        choices = [request.form.get(f'choice_{i}', '') for i in range(4)]
        q.title = request.form['title']
        q.book_id = request.form.get('book_id') or None
        q.week_num = request.form.get('week_num') or None
        q.difficulty = request.form.get('difficulty', 'medium')
        q.tags = request.form.get('tags')
        q.data = {
            'passage': request.form.get('passage', ''),
            'question': request.form.get('question', ''),
            'choices': choices,
            'correct_idx': int(request.form.get('correct_idx', 0)),
            'explanation': request.form.get('explanation', ''),
        }
        db.session.commit()
        flash('수정되었습니다.', 'success')
        return redirect(url_for('cms.reading_quiz_list'))
    return render_template('cms/reading_quiz/form.html', question=q,
                           books=_all_books(), difficulty_choices=DIFFICULTY_CHOICES)


@cms_bp.route('/reading-quiz/<question_id>/delete', methods=['POST'])
@login_required
def reading_quiz_delete(question_id):
    if not _hq_only(): abort(403)
    q = BankQuestion.query.filter_by(question_id=question_id, type='reading_quiz').first_or_404()
    q.is_active = False
    db.session.commit()
    return redirect(url_for('cms.reading_quiz_list'))


# ═══════════════════════════════════════════════
# 3. 독서 강의 영상 관리
# ═══════════════════════════════════════════════

@cms_bp.route('/videos')
@login_required
def video_list():
    if not _hq_only(): abort(403)
    q = request.args.get('q', '').strip()
    book_id = request.args.get('book_id', '')
    query = LectureVideo.query
    if q:
        query = query.filter(LectureVideo.title.ilike(f'%{q}%'))
    if book_id:
        query = query.filter_by(book_id=book_id)
    videos = query.order_by(LectureVideo.created_at.desc()).all()
    return render_template('cms/video/list.html', videos=videos,
                           q=q, book_id=book_id, books=_all_books())


@cms_bp.route('/videos/new', methods=['GET', 'POST'])
@login_required
def video_new():
    if not _hq_only(): abort(403)
    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        v = LectureVideo(
            title=request.form['title'],
            description=request.form.get('description'),
            url=url,
            thumbnail_url=request.form.get('thumbnail_url') or None,
            duration_seconds=request.form.get('duration_seconds') or None,
            book_id=request.form.get('book_id') or None,
            week_num=request.form.get('week_num') or None,
            tags=request.form.get('tags'),
            is_published=bool(request.form.get('is_published')),
            created_by=current_user.user_id,
        )
        db.session.add(v)
        db.session.commit()
        flash('강의 영상이 등록되었습니다.', 'success')
        return redirect(url_for('cms.video_list'))
    return render_template('cms/video/form.html', books=_all_books())


@cms_bp.route('/videos/<video_id>/edit', methods=['GET', 'POST'])
@login_required
def video_edit(video_id):
    if not _hq_only(): abort(403)
    v = LectureVideo.query.get_or_404(video_id)
    if request.method == 'POST':
        v.title = request.form['title']
        v.description = request.form.get('description')
        v.url = request.form.get('url', '').strip()
        v.thumbnail_url = request.form.get('thumbnail_url') or None
        v.duration_seconds = request.form.get('duration_seconds') or None
        v.book_id = request.form.get('book_id') or None
        v.week_num = request.form.get('week_num') or None
        v.tags = request.form.get('tags')
        v.is_published = bool(request.form.get('is_published'))
        db.session.commit()
        flash('수정되었습니다.', 'success')
        return redirect(url_for('cms.video_list'))
    return render_template('cms/video/form.html', video=v, books=_all_books())


@cms_bp.route('/videos/<video_id>/delete', methods=['POST'])
@login_required
def video_delete(video_id):
    if not _hq_only(): abort(403)
    v = LectureVideo.query.get_or_404(video_id)
    db.session.delete(v)
    db.session.commit()
    flash('삭제되었습니다.', 'success')
    return redirect(url_for('cms.video_list'))


@cms_bp.route('/videos/<video_id>/toggle-publish', methods=['POST'])
@login_required
def video_toggle_publish(video_id):
    if not _hq_only(): abort(403)
    v = LectureVideo.query.get_or_404(video_id)
    v.is_published = not v.is_published
    db.session.commit()
    return jsonify({'published': v.is_published})


# ═══════════════════════════════════════════════
# 4. 서술형 문항 관리
# ═══════════════════════════════════════════════

@cms_bp.route('/essay-questions')
@login_required
def essay_question_list():
    if not _hq_only(): abort(403)
    q = request.args.get('q', '').strip()
    book_id = request.args.get('book_id', '')
    query = BankQuestion.query.filter_by(type='essay', is_active=True)
    if q:
        query = query.filter(BankQuestion.title.ilike(f'%{q}%'))
    if book_id:
        query = query.filter_by(book_id=book_id)
    questions = query.order_by(BankQuestion.created_at.desc()).all()
    return render_template('cms/essay_question/list.html', questions=questions,
                           q=q, book_id=book_id, books=_all_books())


@cms_bp.route('/essay-questions/new', methods=['GET', 'POST'])
@login_required
def essay_question_new():
    if not _hq_only(): abort(403)
    if request.method == 'POST':
        data = {
            'prompt': request.form.get('prompt', ''),
            'rubric': request.form.get('rubric', ''),
            'max_score': float(request.form.get('max_score') or 100),
            'sample_answer': request.form.get('sample_answer', ''),
        }
        q = BankQuestion(
            type='essay',
            title=request.form['title'],
            book_id=request.form.get('book_id') or None,
            week_num=request.form.get('week_num') or None,
            difficulty=request.form.get('difficulty', 'medium'),
            tags=request.form.get('tags'),
            data=data,
            created_by=current_user.user_id,
        )
        db.session.add(q)
        db.session.commit()
        flash('서술형 문항이 등록되었습니다.', 'success')
        return redirect(url_for('cms.essay_question_list'))
    return render_template('cms/essay_question/form.html', books=_all_books(),
                           difficulty_choices=DIFFICULTY_CHOICES)


@cms_bp.route('/essay-questions/<question_id>/edit', methods=['GET', 'POST'])
@login_required
def essay_question_edit(question_id):
    if not _hq_only(): abort(403)
    q = BankQuestion.query.filter_by(question_id=question_id, type='essay').first_or_404()
    if request.method == 'POST':
        q.title = request.form['title']
        q.book_id = request.form.get('book_id') or None
        q.week_num = request.form.get('week_num') or None
        q.difficulty = request.form.get('difficulty', 'medium')
        q.tags = request.form.get('tags')
        q.data = {
            'prompt': request.form.get('prompt', ''),
            'rubric': request.form.get('rubric', ''),
            'max_score': float(request.form.get('max_score') or 100),
            'sample_answer': request.form.get('sample_answer', ''),
        }
        db.session.commit()
        flash('수정되었습니다.', 'success')
        return redirect(url_for('cms.essay_question_list'))
    return render_template('cms/essay_question/form.html', question=q,
                           books=_all_books(), difficulty_choices=DIFFICULTY_CHOICES)


@cms_bp.route('/essay-questions/<question_id>/delete', methods=['POST'])
@login_required
def essay_question_delete(question_id):
    if not _hq_only(): abort(403)
    q = BankQuestion.query.filter_by(question_id=question_id, type='essay').first_or_404()
    q.is_active = False
    db.session.commit()
    return redirect(url_for('cms.essay_question_list'))


# ═══════════════════════════════════════════════
# 5. 모의고사 관리
# ═══════════════════════════════════════════════

@cms_bp.route('/mock-exams')
@login_required
def mock_exam_list():
    if not _hq_only(): abort(403)
    exams = MockExam.query.order_by(MockExam.created_at.desc()).all()
    return render_template('cms/exam/list.html', exams=exams)


@cms_bp.route('/mock-exams/new', methods=['GET', 'POST'])
@login_required
def mock_exam_new():
    if not _hq_only(): abort(403)
    if request.method == 'POST':
        exam = MockExam(
            title=request.form['title'],
            description=request.form.get('description'),
            time_limit_minutes=request.form.get('time_limit_minutes') or None,
            book_id=request.form.get('book_id') or None,
            week_num=request.form.get('week_num') or None,
            tags=request.form.get('tags'),
            is_published=bool(request.form.get('is_published')),
            created_by=current_user.user_id,
        )
        db.session.add(exam)
        db.session.commit()
        flash('모의고사가 생성되었습니다. 문항을 추가하세요.', 'success')
        return redirect(url_for('cms.mock_exam_detail', exam_id=exam.exam_id))
    return render_template('cms/exam/form.html', books=_all_books())


@cms_bp.route('/mock-exams/<exam_id>')
@login_required
def mock_exam_detail(exam_id):
    if not _hq_only(): abort(403)
    exam = MockExam.query.get_or_404(exam_id)
    return render_template('cms/exam/detail.html', exam=exam,
                           question_types=EXAM_QUESTION_TYPES)


@cms_bp.route('/mock-exams/<exam_id>/edit', methods=['GET', 'POST'])
@login_required
def mock_exam_edit(exam_id):
    if not _hq_only(): abort(403)
    exam = MockExam.query.get_or_404(exam_id)
    if request.method == 'POST':
        exam.title = request.form['title']
        exam.description = request.form.get('description')
        exam.time_limit_minutes = request.form.get('time_limit_minutes') or None
        exam.book_id = request.form.get('book_id') or None
        exam.week_num = request.form.get('week_num') or None
        exam.tags = request.form.get('tags')
        exam.is_published = bool(request.form.get('is_published'))
        db.session.commit()
        flash('수정되었습니다.', 'success')
        return redirect(url_for('cms.mock_exam_detail', exam_id=exam_id))
    return render_template('cms/exam/form.html', exam=exam, books=_all_books())


@cms_bp.route('/mock-exams/<exam_id>/delete', methods=['POST'])
@login_required
def mock_exam_delete(exam_id):
    if not _hq_only(): abort(403)
    exam = MockExam.query.get_or_404(exam_id)
    db.session.delete(exam)
    db.session.commit()
    flash('삭제되었습니다.', 'success')
    return redirect(url_for('cms.mock_exam_list'))


# 문항 개별 추가
@cms_bp.route('/mock-exams/<exam_id>/questions/add', methods=['POST'])
@login_required
def mock_exam_add_question(exam_id):
    if not _hq_only(): abort(403)
    exam = MockExam.query.get_or_404(exam_id)
    qtype = request.form.get('question_type', 'multiple_choice')
    choices = None
    if qtype == 'multiple_choice':
        choices = [request.form.get(f'choice_{i}', '') for i in range(4)]
    mq = MockExamQuestion(
        exam_id=exam_id,
        question_type=qtype,
        passage=request.form.get('passage') or None,
        question_text=request.form['question_text'],
        choices=choices,
        correct_answer=request.form.get('correct_answer'),
        explanation=request.form.get('explanation'),
        score=float(request.form.get('score') or 1),
        order_num=len(exam.questions),
    )
    db.session.add(mq)
    db.session.commit()
    flash('문항이 추가되었습니다.', 'success')
    return redirect(url_for('cms.mock_exam_detail', exam_id=exam_id))


# 문항 삭제
@cms_bp.route('/mock-exams/questions/<int:mq_id>/delete', methods=['POST'])
@login_required
def mock_exam_delete_question(mq_id):
    if not _hq_only(): abort(403)
    mq = MockExamQuestion.query.get_or_404(mq_id)
    exam_id = mq.exam_id
    db.session.delete(mq)
    db.session.commit()
    return redirect(url_for('cms.mock_exam_detail', exam_id=exam_id))


# 엑셀 업로드
@cms_bp.route('/mock-exams/<exam_id>/import', methods=['GET', 'POST'])
@login_required
def mock_exam_import(exam_id):
    if not _hq_only(): abort(403)
    exam = MockExam.query.get_or_404(exam_id)
    preview = None
    errors = []

    if request.method == 'POST':
        action = request.form.get('action', 'preview')
        file = request.files.get('excel_file')

        if action == 'preview' and file and file.filename:
            try:
                rows = _parse_exam_excel(file)
                preview = rows
                if not rows:
                    errors.append('파싱된 문항이 없습니다. 양식을 확인해주세요.')
            except Exception as e:
                errors.append(f'파일 오류: {str(e)}')

        elif action == 'save':
            # 저장: form에서 JSON으로 전달된 rows 처리
            import json
            rows_json = request.form.get('rows_json', '[]')
            try:
                rows = json.loads(rows_json)
                start_order = len(exam.questions)
                for i, row in enumerate(rows):
                    mq = MockExamQuestion(
                        exam_id=exam_id,
                        question_type=row.get('type', 'multiple_choice'),
                        passage=row.get('passage') or None,
                        question_text=row['question'],
                        choices=row.get('choices'),
                        correct_answer=str(row.get('correct', '')),
                        explanation=row.get('explanation'),
                        score=float(row.get('score') or 1),
                        order_num=start_order + i,
                    )
                    db.session.add(mq)
                db.session.commit()
                flash(f'{len(rows)}개 문항이 추가되었습니다.', 'success')
                return redirect(url_for('cms.mock_exam_detail', exam_id=exam_id))
            except Exception as e:
                errors.append(f'저장 오류: {str(e)}')

    return render_template('cms/exam/import.html', exam=exam,
                           preview=preview, errors=errors)


def _parse_exam_excel(file_obj):
    """
    엑셀 컬럼 형식:
    A: 문항유형 (객관식/단답형/서술형)
    B: 지문 (optional)
    C: 문제
    D~G: 보기1~4 (객관식만)
    H: 정답
    I: 배점
    J: 해설 (optional)
    """
    import openpyxl
    from io import BytesIO
    wb = openpyxl.load_workbook(BytesIO(file_obj.read()), read_only=True)
    ws = wb.active
    rows = []
    TYPE_MAP = {'객관식': 'multiple_choice', '단답형': 'short_answer', '서술형': 'essay'}

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[2]:  # 문제(C열) 없으면 스킵
            continue
        qtype_raw = str(row[0] or '객관식').strip()
        qtype = TYPE_MAP.get(qtype_raw, 'multiple_choice')
        choices = None
        if qtype == 'multiple_choice':
            choices = [str(row[j] or '') for j in range(3, 7)]
            choices = [c for c in choices if c]

        rows.append({
            'type': qtype,
            'type_display': qtype_raw,
            'passage': str(row[1] or '') or None,
            'question': str(row[2] or ''),
            'choices': choices,
            'correct': str(row[7] or '') if row[7] is not None else '',
            'score': float(row[8] or 1) if row[8] is not None else 1,
            'explanation': str(row[9] or '') if len(row) > 9 and row[9] else '',
        })
    return rows


# ═══════════════════════════════════════════════
# 6. 학습 교재 관리
# ═══════════════════════════════════════════════

@cms_bp.route('/materials')
@login_required
def material_list():
    if not _hq_only(): abort(403)
    q = request.args.get('q', '').strip()
    book_id = request.args.get('book_id', '')
    query = StudyMaterial.query
    if q:
        query = query.filter(StudyMaterial.title.ilike(f'%{q}%'))
    if book_id:
        query = query.filter_by(book_id=book_id)
    materials = query.order_by(StudyMaterial.created_at.desc()).all()
    return render_template('cms/material/list.html', materials=materials,
                           q=q, book_id=book_id, books=_all_books())


@cms_bp.route('/materials/new', methods=['GET', 'POST'])
@login_required
def material_new():
    if not _hq_only(): abort(403)
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            flash('파일을 선택해주세요.', 'warning')
            return render_template('cms/material/form.html', books=_all_books())
        if not _allowed_file(file.filename):
            flash('허용되지 않는 파일 형식입니다.', 'warning')
            return render_template('cms/material/form.html', books=_all_books())

        file_path, file_name, file_type, file_size = _save_file(file)
        m = StudyMaterial(
            title=request.form['title'],
            description=request.form.get('description'),
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            book_id=request.form.get('book_id') or None,
            week_num=request.form.get('week_num') or None,
            tags=request.form.get('tags'),
            is_published=bool(request.form.get('is_published')),
            created_by=current_user.user_id,
        )
        db.session.add(m)
        db.session.commit()
        flash('교재가 등록되었습니다.', 'success')
        return redirect(url_for('cms.material_list'))
    return render_template('cms/material/form.html', books=_all_books())


@cms_bp.route('/materials/<material_id>/edit', methods=['GET', 'POST'])
@login_required
def material_edit(material_id):
    if not _hq_only(): abort(403)
    m = StudyMaterial.query.get_or_404(material_id)
    if request.method == 'POST':
        m.title = request.form['title']
        m.description = request.form.get('description')
        m.book_id = request.form.get('book_id') or None
        m.week_num = request.form.get('week_num') or None
        m.tags = request.form.get('tags')
        m.is_published = bool(request.form.get('is_published'))
        # 파일 교체 (선택)
        file = request.files.get('file')
        if file and file.filename and _allowed_file(file.filename):
            file_path, file_name, file_type, file_size = _save_file(file)
            m.file_path = file_path
            m.file_name = file_name
            m.file_type = file_type
            m.file_size = file_size
        db.session.commit()
        flash('수정되었습니다.', 'success')
        return redirect(url_for('cms.material_list'))
    return render_template('cms/material/form.html', material=m, books=_all_books())


@cms_bp.route('/materials/<material_id>/delete', methods=['POST'])
@login_required
def material_delete(material_id):
    if not _hq_only(): abort(403)
    m = StudyMaterial.query.get_or_404(material_id)
    db.session.delete(m)
    db.session.commit()
    flash('삭제되었습니다.', 'success')
    return redirect(url_for('cms.material_list'))


@cms_bp.route('/materials/<material_id>/download')
@login_required
def material_download(material_id):
    m = StudyMaterial.query.get_or_404(material_id)
    if not m.is_published and not _hq_only():
        abort(403)
    m.download_count += 1
    db.session.commit()
    static_dir = os.path.join(os.path.dirname(__file__), '..', 'static')
    return send_from_directory(static_dir, m.file_path,
                               as_attachment=True,
                               download_name=m.file_name)


@cms_bp.route('/materials/<material_id>/toggle-publish', methods=['POST'])
@login_required
def material_toggle_publish(material_id):
    if not _hq_only(): abort(403)
    m = StudyMaterial.query.get_or_404(material_id)
    m.is_published = not m.is_published
    db.session.commit()
    return jsonify({'published': m.is_published})
