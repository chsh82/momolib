from flask import Blueprint
cms_bp = Blueprint('cms', __name__)
from app.cms import routes
