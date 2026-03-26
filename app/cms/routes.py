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
    VOCAB_CATEGORIES, READING_CATEGORIES, READING_TYPE_CHOICES,
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
    cat_large  = request.args.get('cat_large', '')
    cat_medium = request.args.get('cat_medium', '')
    cat_small  = request.args.get('cat_small', '')

    query = BankQuestion.query.filter_by(type='vocab_quiz', is_active=True)
    if q:
        query = query.filter(BankQuestion.title.ilike(f'%{q}%') |
                             BankQuestion.tags.ilike(f'%{q}%'))
    if book_id:
        query = query.filter_by(book_id=book_id)
    if cat_large:
        query = query.filter_by(cat_large=cat_large)
    if cat_medium:
        query = query.filter_by(cat_medium=cat_medium)
    if cat_small:
        query = query.filter_by(cat_small=cat_small)

    questions = query.order_by(BankQuestion.created_at.desc()).all()
    books = _all_books()
    return render_template('cms/vocab/list.html', questions=questions,
                           q=q, book_id=book_id, books=books,
                           cat_large=cat_large, cat_medium=cat_medium, cat_small=cat_small,
                           vocab_categories=VOCAB_CATEGORIES)


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
            cat_large=request.form.get('cat_large') or None,
            cat_medium=request.form.get('cat_medium') or None,
            cat_small=request.form.get('cat_small') or None,
            data=data,
            created_by=current_user.user_id,
        )
        db.session.add(q)
        db.session.commit()
        flash('어휘 퀴즈가 등록되었습니다.', 'success')
        return redirect(url_for('cms.vocab_list'))
    return render_template('cms/vocab/form.html', books=_all_books(),
                           difficulty_choices=DIFFICULTY_CHOICES,
                           vocab_categories=VOCAB_CATEGORIES)


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
        q.cat_large  = request.form.get('cat_large') or None
        q.cat_medium = request.form.get('cat_medium') or None
        q.cat_small  = request.form.get('cat_small') or None
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
                           difficulty_choices=DIFFICULTY_CHOICES,
                           vocab_categories=VOCAB_CATEGORIES)


@cms_bp.route('/vocab/<question_id>/delete', methods=['POST'])
@login_required
def vocab_delete(question_id):
    if not _hq_only(): abort(403)
    q = BankQuestion.query.filter_by(question_id=question_id, type='vocab_quiz').first_or_404()
    q.is_active = False
    db.session.commit()
    flash('삭제되었습니다.', 'success')
    return redirect(url_for('cms.vocab_list'))


@cms_bp.route('/vocab/template')
@login_required
def vocab_template():
    """어휘 퀴즈 엑셀 템플릿 다운로드"""
    if not _hq_only(): abort(403)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO
    from flask import send_file

    wb = Workbook()
    ws = wb.active
    ws.title = '어휘퀴즈'

    headers = ['제목', '단어', '뜻(정답)', '보기1', '보기2', '보기3', '보기4',
               '정답번호(1~4)', '난이도(easy/medium/hard)', '주차(숫자)', '태그(쉼표구분)',
               '대분류', '중분류', '소분류']
    col_widths = [25, 15, 25, 20, 20, 20, 20, 16, 22, 12, 25, 22, 20, 18]

    header_fill = PatternFill('solid', fgColor='4F46E5')
    header_font = Font(bold=True, color='FFFFFF', size=10)
    req_fill   = PatternFill('solid', fgColor='EEF2FF')
    thin = Side(style='thin', color='D1D5DB')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border
        ws.column_dimensions[get_column_letter(col)].width = w

    ws.row_dimensions[1].height = 36

    # 예시 데이터 3행
    samples = [
        ['호기심 많은 소년 - 어휘1', '탐구하다', '무엇인가를 깊이 파고들어 연구하다',
         '탐구하다', '포기하다', '무시하다', '즐기다', 1, 'medium', 1, '독서,어휘',
         '배경지식·스키마 어휘', '문학', '소설'],
        ['분석하다 - 도구어1', '분석하다', '대상을 여러 요소로 나누어 살펴보다',
         '분석하다', '회피하다', '포기하다', '나열하다', 1, 'medium', '', '',
         '학습 도구어', '사고·인지 동사', '분석'],
        ['인과 관계 - 접속어', '따라서', '앞의 내용이 원인이 되어 결론을 이끄는 말',
         '그러나', '반면에', '따라서', '또한', 3, 'easy', '', '',
         '학습 도구어', '접속·연결어', '인과'],
    ]
    for row_num, row_data in enumerate(samples, 2):
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col, value=val)
            cell.fill = req_fill
            cell.border = border
            cell.alignment = Alignment(vertical='center')

    # 안내 시트
    ws2 = wb.create_sheet('작성 안내')
    notes = [
        ('컬럼', '설명', '필수'),
        ('제목', '문항 분류 이름 (예: 책제목-어휘1)', 'O'),
        ('단어', '테스트할 단어', 'O'),
        ('뜻(정답)', '단어의 올바른 뜻 (정답 보기)', 'O'),
        ('보기1~4', '4개 보기 입력. 정답번호에 해당하는 보기가 뜻과 같아야 함', 'O'),
        ('정답번호', '1~4 중 정답 보기 번호', 'O'),
        ('난이도', 'easy / medium / hard 중 하나 (빈칸이면 medium)', 'X'),
        ('주차', '커리큘럼 주차 숫자 (빈칸 가능)', 'X'),
        ('태그', '쉼표로 구분 (예: 독서,어휘,초등)', 'X'),
        ('대분류', '배경지식·스키마 어휘 또는 학습 도구어', 'X'),
        ('중분류', '대분류에 속하는 중분류 (예: 문학, 사고·인지 동사)', 'X'),
        ('소분류', '중분류에 속하는 소분류 (예: 소설, 분석)', 'X'),
    ]
    ws2.column_dimensions['A'].width = 14
    ws2.column_dimensions['B'].width = 55
    ws2.column_dimensions['C'].width = 8
    for r, (a, b, c) in enumerate(notes, 1):
        ws2.cell(row=r, column=1, value=a).font = Font(bold=(r == 1))
        ws2.cell(row=r, column=2, value=b)
        ws2.cell(row=r, column=3, value=c)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='어휘퀴즈_업로드양식.xlsx')


@cms_bp.route('/vocab/bulk-upload', methods=['POST'])
@login_required
def vocab_bulk_upload():
    """엑셀 파일로 어휘 퀴즈 일괄 등록"""
    if not _hq_only(): abort(403)
    from openpyxl import load_workbook
    from io import BytesIO

    file = request.files.get('excel_file')
    if not file or not file.filename.endswith('.xlsx'):
        flash('xlsx 파일을 선택해주세요.', 'error')
        return redirect(url_for('cms.vocab_list'))

    try:
        wb = load_workbook(BytesIO(file.read()), data_only=True)
        ws = wb.active
    except Exception:
        flash('파일을 읽을 수 없습니다. 올바른 xlsx 파일인지 확인해주세요.', 'error')
        return redirect(url_for('cms.vocab_list'))

    DIFFICULTY_VALID = {'easy', 'medium', 'hard'}
    saved = 0
    errors = []

    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
        if not any(row):  # 빈 행 스킵
            continue

        title     = str(row[0]).strip()  if row[0] else ''
        word      = str(row[1]).strip()  if row[1] else ''
        definition= str(row[2]).strip()  if row[2] else ''
        choices   = [str(row[i]).strip() if row[i] else '' for i in range(3, 7)]
        correct_raw = row[7]
        difficulty  = str(row[8]).strip().lower() if row[8] else 'medium'
        week_num    = int(row[9]) if row[9] and str(row[9]).strip().isdigit() else None
        tags        = str(row[10]).strip() if row[10] else ''
        cat_large   = str(row[11]).strip() if len(row) > 11 and row[11] else None
        cat_medium  = str(row[12]).strip() if len(row) > 12 and row[12] else None
        cat_small   = str(row[13]).strip() if len(row) > 13 and row[13] else None

        # 필수값 검증
        if not title or not word or not definition:
            errors.append(f'{row_num}행: 제목/단어/뜻은 필수입니다.')
            continue
        if not all(choices):
            errors.append(f'{row_num}행: 보기1~4를 모두 입력해주세요.')
            continue
        try:
            correct_idx = int(correct_raw) - 1
            if correct_idx not in range(4):
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f'{row_num}행: 정답번호는 1~4 사이 숫자여야 합니다.')
            continue
        if difficulty not in DIFFICULTY_VALID:
            difficulty = 'medium'

        q = BankQuestion(
            type='vocab_quiz',
            title=title,
            difficulty=difficulty,
            week_num=week_num,
            tags=tags or None,
            cat_large=cat_large,
            cat_medium=cat_medium,
            cat_small=cat_small,
            data={'word': word, 'definition': definition,
                  'choices': choices, 'correct_idx': correct_idx},
            created_by=current_user.user_id,
        )
        db.session.add(q)
        saved += 1

    if saved:
        db.session.commit()

    if errors:
        flash(f'{saved}개 등록 완료. 오류 {len(errors)}건: ' + ' / '.join(errors[:3])
              + ('...' if len(errors) > 3 else ''), 'warning' if saved else 'error')
    else:
        flash(f'{saved}개 어휘 퀴즈가 등록되었습니다.', 'success')

    return redirect(url_for('cms.vocab_list'))


# ═══════════════════════════════════════════════
# 2. 독서 퀴즈 관리
# ═══════════════════════════════════════════════

@cms_bp.route('/reading-quiz')
@login_required
def reading_quiz_list():
    if not _hq_only(): abort(403)
    q            = request.args.get('q', '').strip()
    book_id      = request.args.get('book_id', '')
    filter_large = request.args.get('cat_large', '')
    filter_medium= request.args.get('cat_medium', '')
    filter_small = request.args.get('cat_small', '')
    filter_rtype = request.args.get('reading_type', '')
    query = BankQuestion.query.filter_by(type='reading_quiz', is_active=True)
    if q:
        query = query.filter(BankQuestion.title.ilike(f'%{q}%'))
    if book_id:
        query = query.filter_by(book_id=book_id)
    if filter_large:
        query = query.filter_by(cat_large=filter_large)
    if filter_medium:
        query = query.filter_by(cat_medium=filter_medium)
    if filter_small:
        query = query.filter_by(cat_small=filter_small)
    if filter_rtype:
        query = query.filter_by(reading_type=filter_rtype)
    questions = query.order_by(BankQuestion.created_at.desc()).all()
    return render_template('cms/reading_quiz/list.html', questions=questions,
                           q=q, book_id=book_id, books=_all_books(),
                           filter_large=filter_large, filter_medium=filter_medium,
                           filter_small=filter_small, filter_rtype=filter_rtype,
                           reading_categories=READING_CATEGORIES,
                           reading_type_choices=READING_TYPE_CHOICES)


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
            reading_type=request.form.get('reading_type') or None,
            cat_large=request.form.get('cat_large') or None,
            cat_medium=request.form.get('cat_medium') or None,
            cat_small=request.form.get('cat_small') or None,
            tags=request.form.get('tags'),
            data=data,
            created_by=current_user.user_id,
        )
        db.session.add(q)
        db.session.commit()
        flash('독서 퀴즈가 등록되었습니다.', 'success')
        return redirect(url_for('cms.reading_quiz_list'))
    return render_template('cms/reading_quiz/form.html', books=_all_books(),
                           difficulty_choices=DIFFICULTY_CHOICES,
                           reading_categories=READING_CATEGORIES,
                           reading_type_choices=READING_TYPE_CHOICES)


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
        q.reading_type = request.form.get('reading_type') or None
        q.cat_large  = request.form.get('cat_large') or None
        q.cat_medium = request.form.get('cat_medium') or None
        q.cat_small  = request.form.get('cat_small') or None
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
                           books=_all_books(), difficulty_choices=DIFFICULTY_CHOICES,
                           reading_categories=READING_CATEGORIES,
                           reading_type_choices=READING_TYPE_CHOICES)


@cms_bp.route('/reading-quiz/<question_id>/delete', methods=['POST'])
@login_required
def reading_quiz_delete(question_id):
    if not _hq_only(): abort(403)
    q = BankQuestion.query.filter_by(question_id=question_id, type='reading_quiz').first_or_404()
    q.is_active = False
    db.session.commit()
    return redirect(url_for('cms.reading_quiz_list'))


@cms_bp.route('/reading-quiz/template')
@login_required
def reading_quiz_template():
    """독서 퀴즈 엑셀 템플릿 다운로드"""
    if not _hq_only(): abort(403)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO
    from flask import send_file

    wb = Workbook()
    ws = wb.active
    ws.title = '독서퀴즈'

    headers = ['제목', '지문', '문제', '보기1', '보기2', '보기3', '보기4',
               '정답번호(1~4)', '해설', '난이도(easy/medium/hard)', '독해유형',
               '주차(숫자)', '태그(쉼표구분)', '대분류', '중분류', '소분류']
    col_widths = [25, 40, 30, 20, 20, 20, 20, 14, 30, 22, 14, 12, 25, 16, 18, 12]

    header_fill = PatternFill('solid', fgColor='4F46E5')
    header_font = Font(bold=True, color='FFFFFF', size=10)
    req_fill   = PatternFill('solid', fgColor='EEF2FF')
    thin = Side(style='thin', color='D1D5DB')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border
        ws.column_dimensions[get_column_letter(col)].width = w

    ws.row_dimensions[1].height = 36

    # 예시 데이터 2행
    samples = [
        ['흥부와 놀부 - 문제1',
         '옛날 어느 마을에 형제가 살았습니다. 형 놀부는 심술궂고 욕심이 많았으며, 동생 흥부는 착하고 마음이 따뜻했습니다.',
         '이 글에서 흥부의 성격으로 알맞은 것은?',
         '욕심이 많다', '심술궂다', '착하고 따뜻하다', '거만하다',
         3, '흥부는 착하고 마음이 따뜻하다고 나와 있습니다.', 'easy', '사실적',
         1, '독서,문학', '문학', '소설·동화', '초3'],
        ['지구 온난화 - 문제1',
         '지구 온난화란 지구의 평균 기온이 점점 높아지는 현상입니다. 이산화탄소 등 온실가스 증가가 주요 원인입니다.',
         '이 글을 바탕으로 추론할 수 있는 내용으로 가장 적절한 것은?',
         '지구 온난화는 자연적인 현상이다', '온실가스를 줄이면 온난화를 늦출 수 있다',
         '이산화탄소는 지구에 도움이 된다', '지구 기온은 앞으로 낮아질 것이다',
         2, '온실가스 증가가 원인이므로 이를 줄이면 온난화를 늦출 수 있습니다.', 'medium', '추론적',
         2, '환경,과학', '비문학', '과학·기술', '중1'],
    ]
    for row_num, row_data in enumerate(samples, 2):
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col, value=val)
            cell.fill = req_fill
            cell.border = border
            cell.alignment = Alignment(vertical='center', wrap_text=True)
        ws.row_dimensions[row_num].height = 50

    # 안내 시트
    ws2 = wb.create_sheet('작성 안내')
    notes = [
        ('컬럼', '설명', '필수'),
        ('제목', '문항 분류 이름 (예: 책제목-문제1)', 'O'),
        ('지문', '독해 지문 텍스트 (없으면 빈칸)', 'X'),
        ('문제', '문항 질문', 'O'),
        ('보기1~4', '4개 보기 입력', 'O'),
        ('정답번호', '1~4 중 정답 보기 번호', 'O'),
        ('해설', '정답 해설 (없으면 빈칸)', 'X'),
        ('난이도', 'easy / medium / hard (빈칸이면 medium)', 'X'),
        ('독해유형', '사실적 / 분석적 / 추론적 / 적용적 / 비판적 중 하나', 'X'),
        ('주차', '커리큘럼 주차 숫자 (빈칸 가능)', 'X'),
        ('태그', '쉼표로 구분 (예: 독서,문학,초등)', 'X'),
        ('대분류', '문학 또는 비문학', 'X'),
        ('중분류', '소설·동화 / 시·동시 / 수필·일기 / 희곡·시나리오 / 설명문·정보글 / 논설문·주장글 / 전기·인물이야기 / 사회·역사 / 과학·기술 / 예술·문화', 'X'),
        ('소분류', '초1 / 초2 / 초3 / 초4 / 초5 / 초6 / 중1 / 중2 / 중3 / 고등', 'X'),
    ]
    ws2.column_dimensions['A'].width = 14
    ws2.column_dimensions['B'].width = 80
    ws2.column_dimensions['C'].width = 8
    for r, (a, b, c) in enumerate(notes, 1):
        ws2.cell(row=r, column=1, value=a).font = Font(bold=(r == 1))
        ws2.cell(row=r, column=2, value=b)
        ws2.cell(row=r, column=3, value=c)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='독서퀴즈_업로드양식.xlsx')


@cms_bp.route('/reading-quiz/bulk-upload', methods=['POST'])
@login_required
def reading_quiz_bulk_upload():
    """엑셀 파일로 독서 퀴즈 일괄 등록"""
    if not _hq_only(): abort(403)
    from openpyxl import load_workbook
    from io import BytesIO

    file = request.files.get('excel_file')
    if not file or not file.filename.endswith('.xlsx'):
        flash('xlsx 파일을 선택해주세요.', 'error')
        return redirect(url_for('cms.reading_quiz_list'))

    try:
        wb = load_workbook(BytesIO(file.read()), data_only=True)
        ws = wb.active
    except Exception:
        flash('파일을 읽을 수 없습니다. 올바른 xlsx 파일인지 확인해주세요.', 'error')
        return redirect(url_for('cms.reading_quiz_list'))

    DIFFICULTY_VALID = {'easy', 'medium', 'hard'}
    READING_TYPE_VALID = {v for v, _ in READING_TYPE_CHOICES}
    saved = 0
    errors = []

    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
        if not any(row):
            continue

        title       = str(row[0]).strip()  if row[0] else ''
        passage     = str(row[1]).strip()  if row[1] else ''
        question    = str(row[2]).strip()  if row[2] else ''
        choices     = [str(row[i]).strip() if row[i] else '' for i in range(3, 7)]
        correct_raw = row[7]
        explanation = str(row[8]).strip()  if len(row) > 8 and row[8] else ''
        difficulty  = str(row[9]).strip().lower()  if len(row) > 9 and row[9] else 'medium'
        reading_type= str(row[10]).strip() if len(row) > 10 and row[10] else None
        week_num    = int(row[11]) if len(row) > 11 and row[11] and str(row[11]).strip().isdigit() else None
        tags        = str(row[12]).strip() if len(row) > 12 and row[12] else ''
        cat_large   = str(row[13]).strip() if len(row) > 13 and row[13] else None
        cat_medium  = str(row[14]).strip() if len(row) > 14 and row[14] else None
        cat_small   = str(row[15]).strip() if len(row) > 15 and row[15] else None

        if not title or not question:
            errors.append(f'{row_num}행: 제목/문제는 필수입니다.')
            continue
        if not all(choices):
            errors.append(f'{row_num}행: 보기1~4를 모두 입력해주세요.')
            continue
        try:
            correct_idx = int(correct_raw) - 1
            if correct_idx not in range(4):
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f'{row_num}행: 정답번호는 1~4 사이 숫자여야 합니다.')
            continue
        if difficulty not in DIFFICULTY_VALID:
            difficulty = 'medium'
        if reading_type and reading_type not in READING_TYPE_VALID:
            reading_type = None

        q = BankQuestion(
            type='reading_quiz',
            title=title,
            difficulty=difficulty,
            reading_type=reading_type,
            week_num=week_num,
            tags=tags or None,
            cat_large=cat_large,
            cat_medium=cat_medium,
            cat_small=cat_small,
            data={'passage': passage, 'question': question,
                  'choices': choices, 'correct_idx': correct_idx,
                  'explanation': explanation},
            created_by=current_user.user_id,
        )
        db.session.add(q)
        saved += 1

    if saved:
        db.session.commit()

    if errors:
        flash(f'{saved}개 등록 완료. 오류 {len(errors)}건: ' + ' / '.join(errors[:3])
              + ('...' if len(errors) > 3 else ''), 'warning' if saved else 'error')
    else:
        flash(f'{saved}개 독서 퀴즈가 등록되었습니다.', 'success')

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
