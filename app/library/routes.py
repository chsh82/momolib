# -*- coding: utf-8 -*-
from flask import render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app.library import library_bp
from app.models import db
from app.models.library import (Book, LearningContent, QuizQuestion,
                                  ReadingRecord, ContentCompletion, EssaySubmission,
                                  GENRE_CHOICES, LEVEL_CHOICES, CONTENT_TYPES)
from app.models.reading_mbti import (ReadingMBTITest, ReadingMBTIQuestion,
                                      ReadingMBTIType, ReadingMBTIResponse, ReadingMBTIResult)
from app.models.user import User


# ─────────────────────────────────────────────
# HQ / Admin: 도서 관리
# ─────────────────────────────────────────────

@library_bp.route('/books')
@login_required
def book_list():
    if not (current_user.is_hq or current_user.is_branch_owner or current_user.is_branch_staff):
        abort(403)
    q = request.args.get('q', '').strip()
    genre = request.args.get('genre', '')
    level = request.args.get('level', '')
    query = Book.query.filter_by(is_active=True)
    if q:
        query = query.filter(Book.title.ilike(f'%{q}%') | Book.author.ilike(f'%{q}%'))
    if genre:
        query = query.filter_by(genre=genre)
    if level:
        query = query.filter_by(level=level)
    books = query.order_by(Book.created_at.desc()).all()
    return render_template('library/book_list.html', books=books, q=q,
                           genre=genre, level=level,
                           genre_choices=GENRE_CHOICES, level_choices=LEVEL_CHOICES)


@library_bp.route('/books/new', methods=['GET', 'POST'])
@login_required
def book_new():
    if not current_user.is_hq:
        abort(403)
    if request.method == 'POST':
        book = Book(
            isbn=request.form.get('isbn') or None,
            title=request.form['title'],
            author=request.form.get('author'),
            publisher=request.form.get('publisher'),
            publication_year=request.form.get('publication_year') or None,
            cover_image_url=request.form.get('cover_image_url'),
            description=request.form.get('description'),
            genre=request.form.get('genre'),
            level=request.form.get('level', 'all'),
            tags=request.form.get('tags'),
            created_by=current_user.user_id,
        )
        db.session.add(book)
        db.session.commit()
        flash('도서가 등록되었습니다.', 'success')
        return redirect(url_for('library.book_detail', book_id=book.book_id))
    return render_template('library/book_form.html',
                           genre_choices=GENRE_CHOICES, level_choices=LEVEL_CHOICES)


@library_bp.route('/books/isbn-lookup')
@login_required
def isbn_lookup():
    """ISBN AJAX 조회"""
    isbn = request.args.get('isbn', '').strip()
    if not isbn:
        return jsonify({'error': 'ISBN을 입력하세요.'})
    try:
        from app.services.isbn_service import ISBNService
        svc = ISBNService()
        data = svc.lookup_isbn(isbn)
        if data:
            return jsonify({'ok': True, 'data': data})
        return jsonify({'ok': False, 'error': '검색 결과가 없습니다.'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@library_bp.route('/books/<book_id>')
@login_required
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template('library/book_detail.html', book=book,
                           content_types=CONTENT_TYPES)


@library_bp.route('/books/<book_id>/edit', methods=['GET', 'POST'])
@login_required
def book_edit(book_id):
    if not current_user.is_hq:
        abort(403)
    book = Book.query.get_or_404(book_id)
    if request.method == 'POST':
        book.title = request.form['title']
        book.author = request.form.get('author')
        book.publisher = request.form.get('publisher')
        book.publication_year = request.form.get('publication_year') or None
        book.cover_image_url = request.form.get('cover_image_url')
        book.description = request.form.get('description')
        book.genre = request.form.get('genre')
        book.level = request.form.get('level', 'all')
        book.tags = request.form.get('tags')
        db.session.commit()
        flash('수정되었습니다.', 'success')
        return redirect(url_for('library.book_detail', book_id=book_id))
    return render_template('library/book_form.html', book=book,
                           genre_choices=GENRE_CHOICES, level_choices=LEVEL_CHOICES)


@library_bp.route('/books/<book_id>/delete', methods=['POST'])
@login_required
def book_delete(book_id):
    if not current_user.is_hq:
        abort(403)
    book = Book.query.get_or_404(book_id)
    book.is_active = False
    db.session.commit()
    flash('도서가 삭제되었습니다.', 'success')
    return redirect(url_for('library.book_list'))


# ─────────────────────────────────────────────
# HQ: 콘텐츠 관리
# ─────────────────────────────────────────────

@library_bp.route('/books/<book_id>/contents/new', methods=['GET', 'POST'])
@login_required
def content_new(book_id):
    if not current_user.is_hq:
        abort(403)
    book = Book.query.get_or_404(book_id)
    if request.method == 'POST':
        ctype = request.form['type']
        data = {}
        if ctype == 'video':
            data = {
                'url': request.form.get('video_url', ''),
                'duration_seconds': int(request.form.get('duration_seconds') or 0),
                'thumbnail_url': request.form.get('thumbnail_url', ''),
            }
        elif ctype == 'essay':
            data = {
                'prompt': request.form.get('prompt', ''),
                'rubric': request.form.get('rubric', ''),
                'max_score': float(request.form.get('max_score') or 100),
            }
        content = LearningContent(
            book_id=book_id,
            type=ctype,
            title=request.form['title'],
            description=request.form.get('description'),
            data=data,
            order_num=int(request.form.get('order_num') or 0),
            is_published=bool(request.form.get('is_published')),
            created_by=current_user.user_id,
        )
        db.session.add(content)
        db.session.commit()
        flash('콘텐츠가 추가되었습니다.', 'success')
        return redirect(url_for('library.book_detail', book_id=book_id))
    return render_template('library/content_form.html', book=book,
                           content_types=CONTENT_TYPES)


@library_bp.route('/contents/<content_id>/edit', methods=['GET', 'POST'])
@login_required
def content_edit(content_id):
    if not current_user.is_hq:
        abort(403)
    content = LearningContent.query.get_or_404(content_id)
    if request.method == 'POST':
        content.title = request.form['title']
        content.description = request.form.get('description')
        content.order_num = int(request.form.get('order_num') or 0)
        content.is_published = bool(request.form.get('is_published'))
        if content.type == 'video':
            content.data = {
                'url': request.form.get('video_url', ''),
                'duration_seconds': int(request.form.get('duration_seconds') or 0),
                'thumbnail_url': request.form.get('thumbnail_url', ''),
            }
        elif content.type == 'essay':
            content.data = {
                'prompt': request.form.get('prompt', ''),
                'rubric': request.form.get('rubric', ''),
                'max_score': float(request.form.get('max_score') or 100),
            }
        db.session.commit()
        flash('수정되었습니다.', 'success')
        return redirect(url_for('library.book_detail', book_id=content.book_id))
    return render_template('library/content_form.html', book=content.book,
                           content=content, content_types=CONTENT_TYPES)


@library_bp.route('/contents/<content_id>/delete', methods=['POST'])
@login_required
def content_delete(content_id):
    if not current_user.is_hq:
        abort(403)
    content = LearningContent.query.get_or_404(content_id)
    book_id = content.book_id
    db.session.delete(content)
    db.session.commit()
    flash('콘텐츠가 삭제되었습니다.', 'success')
    return redirect(url_for('library.book_detail', book_id=book_id))


# ─────────────────────────────────────────────
# HQ: 퀴즈 문항 관리
# ─────────────────────────────────────────────

@library_bp.route('/contents/<content_id>/questions')
@login_required
def question_list(content_id):
    if not current_user.is_hq:
        abort(403)
    content = LearningContent.query.get_or_404(content_id)
    return render_template('library/question_list.html', content=content)


@library_bp.route('/contents/<content_id>/questions/new', methods=['GET', 'POST'])
@login_required
def question_new(content_id):
    if not current_user.is_hq:
        abort(403)
    content = LearningContent.query.get_or_404(content_id)
    if request.method == 'POST':
        q = QuizQuestion(
            content_id=content_id,
            question_text=request.form['question_text'],
            choices=_parse_choices(request.form, content.type),
            correct_answer=request.form.get('correct_answer'),
            explanation=request.form.get('explanation'),
            order_num=int(request.form.get('order_num') or 0),
        )
        db.session.add(q)
        db.session.commit()
        flash('문항이 추가되었습니다.', 'success')
        return redirect(url_for('library.question_list', content_id=content_id))
    return render_template('library/question_form.html', content=content)


@library_bp.route('/questions/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
def question_edit(question_id):
    if not current_user.is_hq:
        abort(403)
    q = QuizQuestion.query.get_or_404(question_id)
    if request.method == 'POST':
        q.question_text = request.form['question_text']
        q.choices = _parse_choices(request.form, q.content.type)
        q.correct_answer = request.form.get('correct_answer')
        q.explanation = request.form.get('explanation')
        q.order_num = int(request.form.get('order_num') or 0)
        db.session.commit()
        flash('수정되었습니다.', 'success')
        return redirect(url_for('library.question_list', content_id=q.content_id))
    return render_template('library/question_form.html',
                           content=q.content, question=q)


@library_bp.route('/questions/<int:question_id>/delete', methods=['POST'])
@login_required
def question_delete(question_id):
    if not current_user.is_hq:
        abort(403)
    q = QuizQuestion.query.get_or_404(question_id)
    content_id = q.content_id
    db.session.delete(q)
    db.session.commit()
    return redirect(url_for('library.question_list', content_id=content_id))


def _parse_choices(form, content_type):
    if content_type == 'quiz':
        choices = []
        i = 0
        while f'choice_{i}' in form:
            choices.append({
                'text': form[f'choice_{i}'],
                'is_correct': f'correct_{i}' in form,
            })
            i += 1
        return choices
    elif content_type == 'initial_quiz':
        return {'answer': form.get('initial_answer', ''), 'hint': form.get('hint', '')}
    elif content_type == 'vocab_quiz':
        choices = []
        i = 0
        while f'choice_{i}' in form:
            choices.append(form[f'choice_{i}'])
            i += 1
        return {
            'word': form.get('word', ''),
            'choices': choices,
            'correct_idx': int(form.get('correct_idx') or 0),
        }
    return None


# ─────────────────────────────────────────────
# HQ: 서술형 채점
# ─────────────────────────────────────────────

@library_bp.route('/essay-submissions')
@login_required
def essay_submissions():
    if not (current_user.is_hq or current_user.is_branch_owner or current_user.is_branch_staff):
        abort(403)
    pending = request.args.get('pending', '')
    query = EssaySubmission.query
    if pending:
        query = query.filter(EssaySubmission.score.is_(None))
    submissions = query.order_by(EssaySubmission.submitted_at.desc()).limit(100).all()
    return render_template('library/essay_submissions.html',
                           submissions=submissions, pending=pending)


@library_bp.route('/essay-submissions/<submission_id>', methods=['GET', 'POST'])
@login_required
def essay_submission_grade(submission_id):
    if not (current_user.is_hq or current_user.is_branch_owner or current_user.is_branch_staff):
        abort(403)
    sub = EssaySubmission.query.get_or_404(submission_id)
    if request.method == 'POST':
        sub.score = float(request.form['score'])
        sub.max_score = float(request.form.get('max_score') or sub.content.data.get('max_score', 100))
        sub.feedback = request.form.get('feedback')
        sub.graded_by = current_user.user_id
        from datetime import datetime
        sub.graded_at = datetime.utcnow()
        db.session.commit()
        flash('채점이 완료되었습니다.', 'success')
        return redirect(url_for('library.essay_submissions', pending=1))
    return render_template('library/essay_submission_grade.html', sub=sub)


# ─────────────────────────────────────────────
# Student: 도서 탐색 & 학습
# ─────────────────────────────────────────────

@library_bp.route('/catalog')
@login_required
def catalog():
    q = request.args.get('q', '').strip()
    genre = request.args.get('genre', '')
    level = request.args.get('level', '')
    query = Book.query.filter_by(is_active=True)
    if q:
        query = query.filter(Book.title.ilike(f'%{q}%') | Book.author.ilike(f'%{q}%'))
    if genre:
        query = query.filter_by(genre=genre)
    if level:
        query = query.filter_by(level=level)
    books = query.order_by(Book.created_at.desc()).all()

    # 이미 등록된 독서 기록
    my_records = {r.book_id: r for r in
                  ReadingRecord.query.filter_by(student_id=current_user.user_id).all()}

    return render_template('library/catalog.html', books=books, q=q,
                           genre=genre, level=level,
                           genre_choices=GENRE_CHOICES, level_choices=LEVEL_CHOICES,
                           my_records=my_records)


@library_bp.route('/catalog/<book_id>/start', methods=['POST'])
@login_required
def start_reading(book_id):
    book = Book.query.get_or_404(book_id)
    existing = ReadingRecord.query.filter_by(
        student_id=current_user.user_id, book_id=book_id).first()
    if not existing:
        record = ReadingRecord(
            student_id=current_user.user_id,
            book_id=book_id,
            branch_id=current_user.branch_id,
        )
        db.session.add(record)
        db.session.commit()
        flash(f'"{book.title}" 독서를 시작했습니다!', 'success')
    return redirect(url_for('library.my_book', book_id=book_id))


@library_bp.route('/my-books')
@login_required
def my_books():
    records = (ReadingRecord.query
               .filter_by(student_id=current_user.user_id)
               .order_by(ReadingRecord.started_at.desc()).all())
    return render_template('library/my_books.html', records=records)


@library_bp.route('/my-books/<book_id>')
@login_required
def my_book(book_id):
    book = Book.query.get_or_404(book_id)
    record = ReadingRecord.query.filter_by(
        student_id=current_user.user_id, book_id=book_id).first()
    if not record:
        return redirect(url_for('library.catalog'))

    # 완료된 콘텐츠 목록
    completed_ids = {c.content_id for c in
                     ContentCompletion.query.filter_by(student_id=current_user.user_id).all()}

    contents = [c for c in book.contents if c.is_published]
    return render_template('library/my_book.html', book=book, record=record,
                           contents=contents, completed_ids=completed_ids)


@library_bp.route('/my-books/<book_id>/finish', methods=['POST'])
@login_required
def finish_reading(book_id):
    record = ReadingRecord.query.filter_by(
        student_id=current_user.user_id, book_id=book_id).first_or_404()
    from datetime import datetime
    record.status = 'completed'
    record.finished_at = datetime.utcnow()
    record.rating = request.form.get('rating') or None
    record.review = request.form.get('review')
    db.session.commit()
    flash('독서 완료를 기록했습니다!', 'success')
    return redirect(url_for('library.my_books'))


@library_bp.route('/contents/<content_id>/play')
@login_required
def content_play(content_id):
    content = LearningContent.query.get_or_404(content_id)
    if not content.is_published:
        abort(404)
    record = ReadingRecord.query.filter_by(
        student_id=current_user.user_id, book_id=content.book_id).first()
    if not record:
        abort(403)
    completion = ContentCompletion.query.filter_by(
        student_id=current_user.user_id, content_id=content_id).first()
    return render_template('library/content_play.html',
                           content=content, completion=completion)


@library_bp.route('/contents/<content_id>/submit', methods=['POST'])
@login_required
def content_submit(content_id):
    content = LearningContent.query.get_or_404(content_id)
    ctype = content.type

    if ctype == 'video':
        _complete_content(content_id, score=None, max_score=None, answer_data=None)
        flash('영상을 완료했습니다.', 'success')

    elif ctype in ('quiz', 'initial_quiz', 'vocab_quiz'):
        answers = {}
        score = 0
        max_score = len(content.questions)
        for q in content.questions:
            ans = request.form.get(f'q_{q.question_id}')
            answers[str(q.question_id)] = ans
            if _check_answer(q, ans, ctype):
                score += 1
        _complete_content(content_id, score=score, max_score=max_score,
                          answer_data=answers)
        flash(f'퀴즈 완료! {score}/{max_score}점', 'success')

    elif ctype == 'essay':
        text = request.form.get('essay_text', '').strip()
        if not text:
            flash('내용을 입력해주세요.', 'warning')
            return redirect(url_for('library.content_play', content_id=content_id))
        # 이미 제출한 경우 중복 방지
        existing = EssaySubmission.query.filter_by(
            student_id=current_user.user_id, content_id=content_id).first()
        if not existing:
            sub = EssaySubmission(
                student_id=current_user.user_id,
                content_id=content_id,
                text=text,
                max_score=float((content.data or {}).get('max_score', 100)),
            )
            db.session.add(sub)
            db.session.commit()
        _complete_content(content_id, score=None, max_score=None, answer_data=None)
        flash('서술형 평가를 제출했습니다. 채점 후 점수가 반영됩니다.', 'success')

    return redirect(url_for('library.my_book', book_id=content.book_id))


def _check_answer(question, answer, ctype):
    if answer is None:
        return False
    if ctype == 'quiz':
        return str(question.correct_answer) == str(answer)
    elif ctype == 'initial_quiz':
        return (question.choices or {}).get('answer', '').strip() == answer.strip()
    elif ctype == 'vocab_quiz':
        return str((question.choices or {}).get('correct_idx', -1)) == str(answer)
    return False


def _complete_content(content_id, score, max_score, answer_data):
    existing = ContentCompletion.query.filter_by(
        student_id=current_user.user_id, content_id=content_id).first()
    if existing:
        if score is not None:
            existing.score = score
            existing.max_score = max_score
            existing.answer_data = answer_data
    else:
        c = ContentCompletion(
            student_id=current_user.user_id,
            content_id=content_id,
            score=score,
            max_score=max_score,
            answer_data=answer_data,
        )
        db.session.add(c)
    db.session.commit()


# ─────────────────────────────────────────────
# Student: 학습 분석
# ─────────────────────────────────────────────

@library_bp.route('/my-analytics')
@login_required
def my_analytics():
    records = ReadingRecord.query.filter_by(student_id=current_user.user_id).all()
    completions = ContentCompletion.query.filter_by(student_id=current_user.user_id).all()

    # 장르별 독서수
    genre_counts = {}
    for r in records:
        g = r.book.genre_display if r.book else '기타'
        genre_counts[g] = genre_counts.get(g, 0) + 1

    # 콘텐츠 유형별 완료수
    type_counts = {}
    for c in completions:
        t = c.content.type_display if c.content else '기타'
        type_counts[t] = type_counts.get(t, 0) + 1

    # 평균 점수 (퀴즈류만)
    scored = [c for c in completions if c.score is not None and c.max_score]
    avg_pct = round(sum(c.score_pct for c in scored) / len(scored)) if scored else None

    mbti_result = (ReadingMBTIResult.query
                   .filter_by(user_id=current_user.user_id)
                   .order_by(ReadingMBTIResult.submitted_at.desc()).first())

    return render_template('library/my_analytics.html',
                           records=records, completions=completions,
                           genre_counts=genre_counts, type_counts=type_counts,
                           avg_pct=avg_pct, mbti_result=mbti_result)


# ─────────────────────────────────────────────
# Parent: 자녀 학습 현황
# ─────────────────────────────────────────────

@library_bp.route('/parent/child/<child_id>')
@login_required
def parent_child_analytics(child_id):
    if current_user.role != 'parent':
        abort(403)
    # 자녀 연결 확인
    from app.models.member import ParentStudent
    link = ParentStudent.query.filter_by(
        parent_id=current_user.user_id, student_id=child_id).first_or_404()
    child = User.query.get_or_404(child_id)

    records = ReadingRecord.query.filter_by(student_id=child_id).all()
    completions = ContentCompletion.query.filter_by(student_id=child_id).all()

    genre_counts = {}
    for r in records:
        g = r.book.genre_display if r.book else '기타'
        genre_counts[g] = genre_counts.get(g, 0) + 1

    scored = [c for c in completions if c.score is not None and c.max_score]
    avg_pct = round(sum(c.score_pct for c in scored) / len(scored)) if scored else None

    mbti_result = (ReadingMBTIResult.query
                   .filter_by(user_id=child_id)
                   .order_by(ReadingMBTIResult.submitted_at.desc()).first())

    return render_template('library/parent_child_analytics.html',
                           child=child, records=records, completions=completions,
                           genre_counts=genre_counts, avg_pct=avg_pct,
                           mbti_result=mbti_result)


# ─────────────────────────────────────────────
# 독서MBTI
# ─────────────────────────────────────────────

@library_bp.route('/mbti')
@login_required
def mbti_intro():
    test = ReadingMBTITest.query.filter_by(is_active=True).first()
    my_result = None
    if current_user.role in ('student',):
        my_result = (ReadingMBTIResult.query
                     .filter_by(user_id=current_user.user_id)
                     .order_by(ReadingMBTIResult.submitted_at.desc()).first())
    return render_template('library/mbti_intro.html', test=test, my_result=my_result)


@library_bp.route('/mbti/test')
@login_required
def mbti_test():
    test = ReadingMBTITest.query.filter_by(is_active=True).first()
    if not test:
        flash('테스트가 준비되지 않았습니다.', 'warning')
        return redirect(url_for('library.mbti_intro'))
    questions = test.questions
    return render_template('library/mbti_test.html', test=test, questions=questions)


@library_bp.route('/mbti/submit', methods=['POST'])
@login_required
def mbti_submit():
    test = ReadingMBTITest.query.filter_by(is_active=True).first()
    if not test:
        abort(404)

    result = ReadingMBTIResult(user_id=current_user.user_id, test_id=test.test_id)
    db.session.add(result)
    db.session.flush()

    responses = []
    for q in test.questions:
        val = request.form.get(f'q_{q.question_id}')
        if val is None:
            flash('모든 문항에 응답해주세요.', 'warning')
            db.session.rollback()
            return redirect(url_for('library.mbti_test'))
        responses.append(ReadingMBTIResponse(
            result_id=result.result_id,
            question_id=q.question_id,
            score=int(val),
        ))

    db.session.add_all(responses)

    # 점수 계산
    from app.utils.mbti_calculator import calculate_mbti_scores
    scores = calculate_mbti_scores(test.questions, responses)
    result.reading_score = scores['reading']['score']
    result.thinking_score = scores['thinking']['score']
    result.writing_score = scores['writing']['score']
    result.reading_level = scores['reading']['level']
    result.thinking_level = scores['thinking']['level']
    result.writing_level = scores['writing']['level']
    result.type_code = f"{scores['reading']['level']}_{scores['thinking']['level']}_{scores['writing']['level']}"

    db.session.commit()
    return redirect(url_for('library.mbti_result', result_id=result.result_id))


@library_bp.route('/mbti/result/<result_id>')
@login_required
def mbti_result(result_id):
    result = ReadingMBTIResult.query.get_or_404(result_id)
    if result.user_id != current_user.user_id and not current_user.is_hq:
        abort(403)
    type_info = ReadingMBTIType.query.filter_by(type_code=result.type_code).first()
    return render_template('library/mbti_result.html',
                           result=result, type_info=type_info)
