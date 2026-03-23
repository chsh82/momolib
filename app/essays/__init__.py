from flask import Blueprint
essays_bp = Blueprint('essays', __name__)
from app.essays import routes
