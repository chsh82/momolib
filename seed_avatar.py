#!/usr/bin/env python3
"""아바타 상점 아이템 시드 스크립트"""
from app import create_app
from app.models import db
from app.models.avatar import AvatarItem

ITEMS = [
    # ── 뱃지 ──────────────────────────────────────────
    {'name': '별 뱃지',    'category': 'badge', 'price':  50,
     'description': '빛나는 별 뱃지',
     'data': {'emoji': '⭐'}, 'sort_order': 1},
    {'name': '왕관 뱃지',  'category': 'badge', 'price': 100,
     'description': '황금 왕관 뱃지',
     'data': {'emoji': '👑'}, 'sort_order': 2},
    {'name': '하트 뱃지',  'category': 'badge', 'price':  80,
     'description': '사랑스러운 하트',
     'data': {'emoji': '❤️'}, 'sort_order': 3},
    {'name': '번개 뱃지',  'category': 'badge', 'price':  80,
     'description': '빠른 번개 뱃지',
     'data': {'emoji': '⚡'}, 'sort_order': 4},
    {'name': '불꽃 뱃지',  'category': 'badge', 'price': 120,
     'description': '열정의 불꽃',
     'data': {'emoji': '🔥'}, 'sort_order': 5},
    {'name': '다이아 뱃지','category': 'badge', 'price': 200,
     'description': '최고의 다이아몬드',
     'data': {'emoji': '💎'}, 'sort_order': 6},
    {'name': '로켓 뱃지',  'category': 'badge', 'price': 150,
     'description': '우주를 향해 출발!',
     'data': {'emoji': '🚀'}, 'sort_order': 7},
    {'name': '책 뱃지',    'category': 'badge', 'price':  60,
     'description': '독서왕의 상징',
     'data': {'emoji': '📚'}, 'sort_order': 8},

    # ── 배경 ──────────────────────────────────────────
    {'name': '하늘 배경',   'category': 'background', 'price': 150,
     'description': '맑은 하늘색 배경',
     'data': {'color': 'linear-gradient(135deg,#bfdbfe,#93c5fd)'}, 'sort_order': 1},
    {'name': '노을 배경',   'category': 'background', 'price': 150,
     'description': '따뜻한 노을빛 배경',
     'data': {'color': 'linear-gradient(135deg,#fed7aa,#fca5a5)'}, 'sort_order': 2},
    {'name': '숲 배경',     'category': 'background', 'price': 150,
     'description': '싱그러운 초록 배경',
     'data': {'color': 'linear-gradient(135deg,#bbf7d0,#6ee7b7)'}, 'sort_order': 3},
    {'name': '보라 배경',   'category': 'background', 'price': 150,
     'description': '신비로운 보라빛 배경',
     'data': {'color': 'linear-gradient(135deg,#e9d5ff,#c4b5fd)'}, 'sort_order': 4},
    {'name': '황금 배경',   'category': 'background', 'price': 250,
     'description': '빛나는 황금 배경',
     'data': {'color': 'linear-gradient(135deg,#fef08a,#fde047)'}, 'sort_order': 5},
    {'name': '우주 배경',   'category': 'background', 'price': 300,
     'description': '별이 가득한 밤하늘',
     'data': {'color': 'linear-gradient(135deg,#1e1b4b,#312e81)'}, 'sort_order': 6},

    # ── 프레임 ─────────────────────────────────────────
    {'name': '오렌지 프레임', 'category': 'frame', 'price': 100,
     'description': '활기찬 오렌지 테두리',
     'data': {'color': '#f97316'}, 'sort_order': 1},
    {'name': '파랑 프레임',   'category': 'frame', 'price': 100,
     'description': '시원한 파란 테두리',
     'data': {'color': '#3b82f6'}, 'sort_order': 2},
    {'name': '초록 프레임',   'category': 'frame', 'price': 100,
     'description': '생기 있는 초록 테두리',
     'data': {'color': '#22c55e'}, 'sort_order': 3},
    {'name': '보라 프레임',   'category': 'frame', 'price': 100,
     'description': '신비로운 보라 테두리',
     'data': {'color': '#a855f7'}, 'sort_order': 4},
    {'name': '황금 프레임',   'category': 'frame', 'price': 200,
     'description': '특별한 황금 테두리',
     'data': {'color': '#f59e0b'}, 'sort_order': 5},
    {'name': '무지개 프레임', 'category': 'frame', 'price': 350,
     'description': '화려한 무지개 테두리',
     'data': {'color': '#e879f9'}, 'sort_order': 6},
]


def seed():
    app = create_app()
    with app.app_context():
        added = 0
        for item_data in ITEMS:
            exists = AvatarItem.query.filter_by(
                name=item_data['name'],
                category=item_data['category']
            ).first()
            if not exists:
                item = AvatarItem(**item_data)
                db.session.add(item)
                added += 1
                print(f'  추가: [{item_data["category"]}] {item_data["name"]} ({item_data["price"]}🪙)')
            else:
                print(f'  스킵: {item_data["name"]} (이미 존재)')
        db.session.commit()
        print(f'\n완료: {added}개 추가됨')


if __name__ == '__main__':
    seed()
