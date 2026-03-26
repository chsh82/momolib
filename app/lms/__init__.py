from flask import Blueprint
lms_bp = Blueprint('lms', __name__)
from app.lms import routes
