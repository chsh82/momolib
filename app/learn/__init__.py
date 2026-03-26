# -*- coding: utf-8 -*-
from flask import Blueprint

learn_bp = Blueprint('learn', __name__)

from app.learn import routes  # noqa
