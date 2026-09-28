from flask import Blueprint, abort, current_app
from flask_login import current_user

vocab_quiz_student_bp = Blueprint('vocab_quiz_student', __name__)


@vocab_quiz_student_bp.before_request
def _require_feature_flag():
    """기능 플래그가 꺼져 있으면(기본값) 로그인·역할과 무관하게 이
    블루프린트의 모든 라우트를 404로 막는다. config.py의
    VOCAB_QUIZ_STUDENT_ENABLED 참고 - 운영 환경변수에는 설정돼 있지
    않으므로 기본 OFF다."""
    if not current_app.config.get('VOCAB_QUIZ_STUDENT_ENABLED', False):
        abort(404)


@vocab_quiz_student_bp.before_request
def _require_pilot_allowlist():
    """feature flag가 켜져 있어도, 파일럿 대상 allowlist에 없는 학생은
    전부 403 - 기본 차단(allowlist가 비어 있으면 어떤 student 계정도
    통과 못 함). 비로그인·비학생 역할은 여기서 판단하지 않고 그대로
    통과시켜, 기존 @login_required(302/401)와 각 라우트의
    _student_only()(403) 처리를 그대로 따르게 한다 - 이 훅은 오직
    "student 역할이면서 allowlist에 없는 경우"만 추가로 막는다."""
    if not getattr(current_user, 'is_authenticated', False):
        return
    if getattr(current_user, 'role', None) != 'student':
        return
    from app.vocab_quiz.eligibility import student_is_pilot_allowed
    if not student_is_pilot_allowed(current_user.user_id):
        current_app.logger.info(
            f'[vocab_quiz_student] event=access_denied user_id={current_user.user_id} reason=NOT_IN_ALLOWLIST'
        )
        abort(403)


from app.vocab_quiz_student import routes  # noqa
