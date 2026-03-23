from flask import Blueprint
hq_bp = Blueprint('hq', __name__)
from app.hq import routes
