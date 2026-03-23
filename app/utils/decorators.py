# -*- coding: utf-8 -*-
from functools import wraps
from flask import abort
from flask_login import current_user


def requires_role(*roles):
    """역할 기반 접근 제어 데코레이터"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def requires_hq(f):
    """본사 계정만 허용"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_hq:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def requires_branch_access(f):
    """지점 계정 또는 본사 계정 허용"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not (current_user.is_hq or current_user.is_branch_staff or current_user.is_branch_owner):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
