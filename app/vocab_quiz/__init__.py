from flask import Blueprint

vocab_quiz_bp = Blueprint('vocab_quiz', __name__)

from app.vocab_quiz import routes  # noqa
from app.vocab_quiz import publish_review_routes  # noqa
