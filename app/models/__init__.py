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
from app.models.branch_post import BranchPost, BranchPostRead
from app.models.credit import EssayCredit, EssayCreditLog
from app.models.library import (Book, LearningContent, QuizQuestion,
                                 ReadingRecord, ContentCompletion, EssaySubmission)
from app.models.reading_mbti import (ReadingMBTITest, ReadingMBTIQuestion,
                                      ReadingMBTIType, ReadingMBTIResponse, ReadingMBTIResult)
from app.models.content_bank import (BankQuestion, LectureVideo,
                                      MockExam, MockExamQuestion, StudyMaterial)
from app.models.lms import (Curriculum, CurriculumItem, Package, PackageCurriculum,
                             BranchPackageAssignment, StudentPackageAssignment)
