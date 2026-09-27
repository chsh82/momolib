from flask import Blueprint, abort, current_app

vocab_quiz_student_bp = Blueprint('vocab_quiz_student', __name__)


@vocab_quiz_student_bp.before_request
def _require_feature_flag():
    """기능 플래그가 꺼져 있으면(기본값) 로그인·역할과 무관하게 이
    블루프린트의 모든 라우트를 404로 막는다. config.py의
    VOCAB_QUIZ_STUDENT_ENABLED 참고 - 운영 환경변수에는 설정돼 있지
    않으므로 기본 OFF다."""
    if not current_app.config.get('VOCAB_QUIZ_STUDENT_ENABLED', False):
        abort(404)


from app.vocab_quiz_student import routes  # noqa
