# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


# 마일리지 지급 사유 상수
class MileageReason:
    LMS_VIDEO       = 'lms_video'        # LMS 영상 시청 완료
    LMS_QUIZ_PASS   = 'lms_quiz_pass'    # LMS 퀴즈 정답
    LMS_QUIZ_FAIL   = 'lms_quiz_fail'    # LMS 퀴즈 오답 (도전 보상)
    LMS_DISCUSSION  = 'lms_discussion'   # LMS 토론/글쓰기 제출
    LIBRARY_CONTENT = 'library_content'  # 도서 콘텐츠 완료
    BOOK_FINISH     = 'book_finish'      # 독서 완료
    MBTI_TEST       = 'mbti_test'        # 독서MBTI 검사 완료
    DAILY_LOGIN     = 'daily_login'      # 일일 로그인
    ITEM_PURCHASE   = 'item_purchase'    # 아이템 구매 (차감)
    ADMIN_GRANT     = 'admin_grant'      # 관리자 지급

    DISPLAY = {
        'lms_video':       '📹 LMS 영상 시청',
        'lms_quiz_pass':   '🎯 퀴즈 정답',
        'lms_quiz_fail':   '💪 퀴즈 도전',
        'lms_discussion':  '💬 토론/글쓰기 제출',
        'library_content': '📖 도서 콘텐츠 완료',
        'book_finish':     '📚 독서 완료',
        'mbti_test':       '🧠 독서MBTI 검사',
        'daily_login':     '☀️ 일일 로그인',
        'item_purchase':   '🛍️ 아이템 구매',
        'admin_grant':     '🎁 관리자 지급',
    }

    AMOUNTS = {
        'lms_video':       10,
        'lms_quiz_pass':   20,
        'lms_quiz_fail':   5,
        'lms_discussion':  15,
        'library_content': 10,
        'book_finish':     20,
        'mbti_test':       30,
        'daily_login':     5,
    }


class MileageLog(db.Model):
    """마일리지 적립/차감 내역"""
    __tablename__ = 'mileage_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)          # 양수=적립, 음수=차감
    balance_after = db.Column(db.Integer, nullable=False)   # 변경 후 잔액
    reason = db.Column(db.String(50), nullable=False)       # MileageReason 상수
    description = db.Column(db.String(200), nullable=True)  # 부가 설명
    ref_type = db.Column(db.String(50), nullable=True)      # 연관 객체 타입
    ref_id = db.Column(db.String(100), nullable=True)       # 연관 객체 ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    student = db.relationship('User', foreign_keys=[student_id],
                              backref=db.backref('mileage_logs', lazy='dynamic'))

    @property
    def reason_display(self):
        return MileageReason.DISPLAY.get(self.reason, self.reason)

    @property
    def is_earn(self):
        return self.amount > 0


class AvatarItem(db.Model):
    """아바타 아이템 상점 목록"""
    __tablename__ = 'avatar_items'

    item_id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    category = db.Column(db.String(30), nullable=False)     # badge / background / frame / overlay
    price = db.Column(db.Integer, nullable=False, default=100)
    # 아이템 시각 정보 (emoji, color, overlay_url 등)
    data = db.Column(db.JSON, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    CATEGORY_DISPLAY = {
        'badge':      '뱃지',
        'background': '배경',
        'frame':      '프레임',
        'overlay':    '아이템',
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.item_id:
            self.item_id = str(uuid.uuid4())

    @property
    def category_display(self):
        return self.CATEGORY_DISPLAY.get(self.category, self.category)

    @property
    def display_icon(self):
        if self.data:
            return self.data.get('emoji', '🎁')
        return '🎁'


class StudentAvatar(db.Model):
    """학생의 현재 아바타 설정"""
    __tablename__ = 'student_avatars'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                           nullable=False, unique=True)
    character = db.Column(db.String(100), nullable=False, default='momo_girl_nobg.png')
    # 장착 아이템: {'badge': item_id, 'background': item_id, 'frame': item_id}
    equipped = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('User', foreign_keys=[student_id],
                              backref=db.backref('avatar', uselist=False))

    @property
    def character_display(self):
        name_map = {
            'momo_girl_nobg.png':       '모모',
            'scientist_nobg.png':       '호라박사',
            'turtle_nobg.png':          '카시오페이아',
            'old_man_broom_clean.png':  '베포',
            'purple_boy_clean.png':     '기기',
            'captain_nemo_clean.png':   '네모선장',
            'nature_boy_clean.png':     '콩세유',
            'traveler_clean.png':       '파스파르투',
            'indian_girl_clean.png':    '아우다부인',
            'black_suit_man_clean.png': '회색신사',
            'napoleon_pig_clean.png':   '나폴레옹',
            'old_professor_clean.png':  '아로낙스박사',
            'phileas_fogg_clean.png':   '필리어스 포그',
        }
        return name_map.get(self.character, self.character)


class StudentAvatarInventory(db.Model):
    """학생이 보유한 아이템 목록"""
    __tablename__ = 'student_avatar_inventory'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    item_id = db.Column(db.String(36), db.ForeignKey('avatar_items.item_id', ondelete='CASCADE'),
                        nullable=False)
    acquired_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'item_id', name='uq_student_item'),
    )

    student = db.relationship('User', foreign_keys=[student_id])
    item = db.relationship('AvatarItem', backref='inventory_entries')
