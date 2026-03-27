# -*- coding: utf-8 -*-
"""뱃지 아이템에 위치 데이터 추가"""
from app import create_app
from app.models import db
from app.models.avatar import AvatarItem

POSITIONS = {
    '반짝별':  'top-right',
    '불꽃':    'bottom-right',
    '왕관':    'top-center',
    '다이아':  'top-right',
    '로켓':    'bottom-right',
    '무지개':  'top-center',
}

app = create_app()
with app.app_context():
    for name, pos in POSITIONS.items():
        item = AvatarItem.query.filter_by(name=name, category='badge').first()
        if item:
            data = dict(item.data or {})
            data['pos'] = pos
            item.data = data
            print(f"OK: {name} → {pos}")
    db.session.commit()
    print("완료!")
