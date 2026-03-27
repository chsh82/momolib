# -*- coding: utf-8 -*-
"""아바타 상점 초기 아이템 데이터 삽입"""
from app import create_app
from app.models import db
from app.models.avatar import AvatarItem

ITEMS = [
    # ── 뱃지 ──────────────────────────────────────────
    {'name': '반짝별',      'category': 'badge', 'price':  80,
     'description': '열심히 공부한 나에게!', 'sort_order': 1,
     'data': {'emoji': '⭐'}},
    {'name': '불꽃',        'category': 'badge', 'price': 120,
     'description': '매일 출석하는 학습 열정!', 'sort_order': 2,
     'data': {'emoji': '🔥'}},
    {'name': '왕관',        'category': 'badge', 'price': 200,
     'description': '독서의 왕!', 'sort_order': 3,
     'data': {'emoji': '👑'}},
    {'name': '다이아',      'category': 'badge', 'price': 300,
     'description': '최고의 학습자 뱃지', 'sort_order': 4,
     'data': {'emoji': '💎'}},
    {'name': '로켓',        'category': 'badge', 'price': 150,
     'description': '목표를 향해 발사!', 'sort_order': 5,
     'data': {'emoji': '🚀'}},
    {'name': '무지개',      'category': 'badge', 'price': 180,
     'description': '다채로운 학습의 기쁨', 'sort_order': 6,
     'data': {'emoji': '🌈'}},

    # ── 배경 ──────────────────────────────────────────
    {'name': '하늘 배경',   'category': 'background', 'price': 100,
     'description': '맑고 청명한 하늘색', 'sort_order': 1,
     'data': {'color': 'linear-gradient(135deg,#bfdbfe,#93c5fd)'}},
    {'name': '라벤더 배경', 'category': 'background', 'price': 100,
     'description': '은은한 보라빛 배경', 'sort_order': 2,
     'data': {'color': 'linear-gradient(135deg,#e9d5ff,#c4b5fd)'}},
    {'name': '민트 배경',   'category': 'background', 'price': 100,
     'description': '상쾌한 민트 그린', 'sort_order': 3,
     'data': {'color': 'linear-gradient(135deg,#a7f3d0,#6ee7b7)'}},
    {'name': '선셋 배경',   'category': 'background', 'price': 150,
     'description': '노을처럼 따뜻한 배경', 'sort_order': 4,
     'data': {'color': 'linear-gradient(135deg,#fde68a,#fca5a5)'}},
    {'name': '우주 배경',   'category': 'background', 'price': 250,
     'description': '신비로운 우주의 빛', 'sort_order': 5,
     'data': {'color': 'linear-gradient(135deg,#1e1b4b,#4c1d95)'}},

    # ── 프레임 ────────────────────────────────────────
    {'name': '골드 프레임', 'category': 'frame', 'price': 150,
     'description': '빛나는 황금 테두리', 'sort_order': 1,
     'data': {'color': '#f59e0b'}},
    {'name': '은빛 프레임', 'category': 'frame', 'price': 100,
     'description': '세련된 실버 테두리', 'sort_order': 2,
     'data': {'color': '#94a3b8'}},
    {'name': '보라 프레임', 'category': 'frame', 'price': 120,
     'description': '신비로운 보라 테두리', 'sort_order': 3,
     'data': {'color': '#a855f7'}},
    {'name': '하늘 프레임', 'category': 'frame', 'price': 120,
     'description': '청량한 파랑 테두리', 'sort_order': 4,
     'data': {'color': '#38bdf8'}},
    {'name': '무지개 프레임', 'category': 'frame', 'price': 300,
     'description': '화려한 그라데이션 테두리', 'sort_order': 5,
     'data': {'color': '#f97316', 'gradient': True}},
]

app = create_app()
with app.app_context():
    added = 0
    for item_data in ITEMS:
        exists = AvatarItem.query.filter_by(
            name=item_data['name'], category=item_data['category']
        ).first()
        if not exists:
            item = AvatarItem(
                name=item_data['name'],
                category=item_data['category'],
                price=item_data['price'],
                description=item_data.get('description'),
                sort_order=item_data.get('sort_order', 0),
                data=item_data.get('data'),
                is_active=True,
            )
            db.session.add(item)
            added += 1
    db.session.commit()
    print(f"완료! {added}개 아이템 추가됨 (이미 있는 항목은 건너뜀)")
