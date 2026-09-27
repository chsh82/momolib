from flask import Blueprint

vocab_quiz_student_bp = Blueprint('vocab_quiz_student', __name__)

from app.vocab_quiz_student import routes  # noqa
