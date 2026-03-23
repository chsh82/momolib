# -*- coding: utf-8 -*-
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from app.models.user import User
from app.models.branch import Branch, BranchContract
from app.models.content import ContentItem, ContentPermission, ContentView
from app.models.revenue import RevenueRecord
from app.models.member import StudentProfile, ParentStudent
from app.models.notification import Notification
from app.models.essay import Essay, EssayVersion, EssayResult
