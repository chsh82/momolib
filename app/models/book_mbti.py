# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from app.models import db


# ── 9가지 독서 취향 타입 ────────────────────────────────────
BOOK_MBTI_TYPES = {
    'harry': {
        'name': '오즈의 도로시형',
        'emoji': '🌈',
        'desc': '신비로운 세계에서 용감하게 모험을 떠나는 영웅',
        'genres': ['판타지', '모험', '영웅'],
        'character': '오즈의 도로시',
        'work': '오즈의 마법사',
    },
    'nemo': {
        'name': '네모 선장형',
        'emoji': '🌊',
        'desc': '미지의 세계를 과학으로 탐험하는 탐험가',
        'genres': ['SF', '과학', '바다', '탐험'],
        'character': '네모 선장',
        'work': '해저 이만리',
    },
    'lyra': {
        'name': '지킬 박사형',
        'emoji': '🧪',
        'desc': '어둠과 빛 사이, 숨겨진 진실을 탐구하는 탐험가',
        'genres': ['공포', '스릴러', '다크판타지'],
        'character': '지킬 박사',
        'work': '지킬 박사와 하이드',
    },
    'alice': {
        'name': '앨리스형',
        'emoji': '🐇',
        'desc': '신비롭고 엉뚱한 상상 세계를 꿈꾸는 몽상가',
        'genres': ['마법', '판타지', '환상'],
        'character': '앨리스',
        'work': '이상한 나라의 앨리스',
    },
    'holmes': {
        'name': '셜록 홈즈형',
        'emoji': '🔍',
        'desc': '논리와 관찰로 사건을 해결하는 탐정',
        'genres': ['추리', '미스터리', '반전'],
        'character': '셜록 홈즈',
        'work': '셜록 홈즈 시리즈',
    },
    'fogg': {
        'name': '필리어스 포그형',
        'emoji': '🌍',
        'desc': '세계를 누비며 역사 속 모험을 즐기는 탐험가',
        'genres': ['역사', '위인', '세계문화'],
        'character': '필리어스 포그',
        'work': '80일간의 세계일주',
    },
    'anne': {
        'name': '빨간 머리 앤형',
        'emoji': '🍀',
        'desc': '따뜻한 마음으로 친구와 함께 성장하는 이야기꾼',
        'genres': ['성장', '우정', '가족'],
        'character': '빨간 머리 앤',
        'work': '빨간 머리 앤',
    },
    'pippi': {
        'name': '톰 소여형',
        'emoji': '🎣',
        'desc': '규칙 따윈 없이 웃음과 자유가 넘치는 개구쟁이',
        'genres': ['유머', '일상', '코미디'],
        'character': '톰 소여',
        'work': '톰 소여의 모험',
    },
    'mowgli': {
        'name': '모글리형',
        'emoji': '🌿',
        'desc': '자연과 동물 속에서 살아가는 야생 탐험가',
        'genres': ['자연', '동물', '생존', '환경'],
        'character': '모글리',
        'work': '정글북',
    },
}

# ── 8문항 × 4선택지, 각 선택지는 타입별 점수 ─────────────
BOOK_MBTI_QUESTIONS = [
    {
        'q': '어떤 배경의 이야기가 좋아?',
        'options': [
            {'text': '🏰 마법과 용이 있는 판타지 세계',
             'scores': {'harry': 2, 'alice': 1, 'lyra': 1}},
            {'text': '🌊 깊은 바다 속이나 우주',
             'scores': {'nemo': 2, 'fogg': 1}},
            {'text': '🌲 정글이나 자연 속',
             'scores': {'mowgli': 2, 'fogg': 1}},
            {'text': '🏫 학교와 도시, 일상적인 공간',
             'scores': {'anne': 1, 'pippi': 1, 'holmes': 1}},
        ]
    },
    {
        'q': '주인공이 어떤 스타일이면 좋아?',
        'options': [
            {'text': '⚔️ 강하고 용감한 영웅',
             'scores': {'harry': 2, 'lyra': 1}},
            {'text': '🔍 논리로 문제를 푸는 천재',
             'scores': {'holmes': 2, 'nemo': 1}},
            {'text': '🤝 친구를 위해 뭐든 하는 아이',
             'scores': {'anne': 2, 'alice': 1}},
            {'text': '😂 규칙 따윈 없고 자유로운 개구쟁이',
             'scores': {'pippi': 2, 'mowgli': 1}},
        ]
    },
    {
        'q': '이야기에서 가장 좋아하는 장면은?',
        'options': [
            {'text': '💥 짜릿한 전투나 모험 장면',
             'scores': {'harry': 1, 'lyra': 1, 'mowgli': 1}},
            {'text': '😮 예상 못 한 반전과 충격',
             'scores': {'holmes': 2, 'lyra': 1}},
            {'text': '😢 눈물 나게 감동적인 순간',
             'scores': {'anne': 2, 'alice': 1}},
            {'text': '😂 배꼽 잡는 웃긴 장면',
             'scores': {'pippi': 2, 'fogg': 1}},
        ]
    },
    {
        'q': '책을 읽고 나면 어떤 느낌이 들면 좋아?',
        'options': [
            {'text': '🔥 가슴이 두근두근 신나는 느낌',
             'scores': {'harry': 1, 'nemo': 1, 'mowgli': 1}},
            {'text': '💡 새로운 걸 배운 느낌',
             'scores': {'nemo': 2, 'holmes': 1, 'fogg': 1}},
            {'text': '🥲 마음이 따뜻해지는 느낌',
             'scores': {'anne': 2, 'alice': 1}},
            {'text': '😌 웃으며 기분이 좋아지는 느낌',
             'scores': {'pippi': 2, 'alice': 1}},
        ]
    },
    {
        'q': '어떤 이야기 흐름이 재미있어?',
        'options': [
            {'text': '🏃 처음부터 끝까지 빠르게 달리는 스토리',
             'scores': {'harry': 1, 'lyra': 1, 'fogg': 1}},
            {'text': '🧩 단서를 하나씩 모아 풀어가는 미스터리',
             'scores': {'holmes': 2, 'lyra': 1}},
            {'text': '🌊 천천히 감정이 쌓여가는 이야기',
             'scores': {'anne': 2, 'alice': 1}},
            {'text': '🎪 엉뚱하고 유쾌한 이야기',
             'scores': {'pippi': 2, 'alice': 1}},
        ]
    },
    {
        'q': '어떤 책이 읽고 싶어?',
        'options': [
            {'text': '🗡️ 악당을 무찌르는 영웅 이야기',
             'scores': {'harry': 2, 'lyra': 1}},
            {'text': '🔬 과학이나 자연의 신비',
             'scores': {'nemo': 2, 'mowgli': 1}},
            {'text': '📜 실제 역사 속 영웅 이야기',
             'scores': {'fogg': 2, 'holmes': 1}},
            {'text': '🌍 다른 나라와 문화 이야기',
             'scores': {'fogg': 1, 'alice': 1, 'anne': 1}},
        ]
    },
    {
        'q': '친구에게 책을 추천한다면?',
        'options': [
            {'text': '"이거 진짜 신나고 짜릿해!"',
             'scores': {'harry': 1, 'lyra': 1, 'mowgli': 1}},
            {'text': '"이거 읽으면 눈물 날 수도 있어..."',
             'scores': {'anne': 2, 'alice': 1}},
            {'text': '"이거 읽으면 진짜 똑똑해질 것 같아!"',
             'scores': {'holmes': 1, 'nemo': 1, 'fogg': 1}},
            {'text': '"이거 진짜 웃겨! 배꼽 빠짐"',
             'scores': {'pippi': 2, 'alice': 1}},
        ]
    },
    {
        'q': '이야기 속 세상에서 내 역할은?',
        'options': [
            {'text': '🗡️ 세상을 구하는 영웅',
             'scores': {'harry': 2, 'lyra': 1}},
            {'text': '🕵️ 사건을 해결하는 탐정',
             'scores': {'holmes': 2, 'nemo': 1}},
            {'text': '💌 친구들의 든든한 버팀목',
             'scores': {'anne': 2, 'alice': 1}},
            {'text': '🌏 세계를 자유롭게 누비는 여행자',
             'scores': {'fogg': 2, 'mowgli': 1}},
        ]
    },
    {
        'q': '무서운 이야기를 읽을 때 어때?',
        'options': [
            {'text': '👻 소름 돋지만 계속 읽게 돼!',
             'scores': {'lyra': 2, 'holmes': 1}},
            {'text': '🌙 신비롭고 어두운 분위기가 좋아',
             'scores': {'alice': 2, 'lyra': 1}},
            {'text': '😨 무서운 이야기는 별로야, 따뜻한 게 좋아',
             'scores': {'anne': 1, 'pippi': 1}},
            {'text': '🔦 무서워도 끝까지 진실을 알고 싶어',
             'scores': {'holmes': 1, 'harry': 1, 'lyra': 1}},
        ]
    },
    {
        'q': '책 속 세상에 들어간다면 어디서 살고 싶어?',
        'options': [
            {'text': '🌊 깊은 바다 속 잠수함에서 과학 탐험',
             'scores': {'nemo': 3}},
            {'text': '🌿 동물들과 함께 우거진 정글 속에서',
             'scores': {'mowgli': 3}},
            {'text': '🗺️ 세계 각지를 기차와 배로 여행하며',
             'scores': {'fogg': 3}},
            {'text': '🌑 어둡고 신비로운 비밀이 가득한 곳에서',
             'scores': {'lyra': 2, 'alice': 1}},
        ]
    },
    {
        'q': '책을 고를 때 가장 끌리는 것은?',
        'options': [
            {'text': '🔬 과학적 발견과 새로운 지식',
             'scores': {'nemo': 2, 'holmes': 1, 'fogg': 1}},
            {'text': '🐾 자연과 동물이 중심이 되는 이야기',
             'scores': {'mowgli': 2, 'alice': 1}},
            {'text': '😱 긴장감과 공포, 소름 돋는 분위기',
             'scores': {'lyra': 2, 'holmes': 1}},
            {'text': '💃 자유롭고 신나는 에너지',
             'scores': {'pippi': 2, 'harry': 1}},
        ]
    },
    {
        'q': '친구들에게 어떤 사람으로 보이고 싶어?',
        'options': [
            {'text': '🌊 지식이 풍부하고 탐구적인 사람',
             'scores': {'nemo': 2, 'holmes': 1}},
            {'text': '🌿 자연을 사랑하는 자유로운 영혼',
             'scores': {'mowgli': 2, 'pippi': 1}},
            {'text': '🌍 다양한 경험과 이야기가 많은 사람',
             'scores': {'fogg': 2, 'anne': 1}},
            {'text': '🌙 신비롭고 깊이 있는 사람',
             'scores': {'lyra': 2, 'alice': 1}},
        ]
    },
]


class BookMBTIResult(db.Model):
    """독서MBTI 취향 테스트 결과"""
    __tablename__ = 'book_mbti_results'

    result_id = db.Column(db.String(36), primary_key=True,
                          default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id',
                        ondelete='CASCADE'), nullable=False, index=True)
    type_code = db.Column(db.String(20), nullable=False)   # harry/nemo/lyra/...
    scores = db.Column(db.JSON, nullable=True)             # 타입별 점수 기록
    taken_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id],
                           backref=db.backref('book_mbti_results', lazy='dynamic'))

    @property
    def type_info(self):
        return BOOK_MBTI_TYPES.get(self.type_code, {})
