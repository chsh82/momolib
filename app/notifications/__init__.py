from flask import Blueprint
notif_bp = Blueprint('notif', __name__)
from app.notifications import routes
