from flask import Blueprint

avatar_bp = Blueprint('avatar', __name__)

from app.avatar import routes  # noqa
