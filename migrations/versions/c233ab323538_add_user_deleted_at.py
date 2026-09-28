"""add users.deleted_at (soft delete)

2026-09-28: 지점의 "회원 삭제"가 raw SQL DELETE로 CASCADE되어 첨삭·진도
기록까지 복구 불가능하게 사라지는 문제(운영 리뷰 I번 항목)를 고치기 위해
소프트삭제 컬럼을 추가한다. 기존 테이블 구조는 건드리지 않고 users에
nullable 컬럼 하나만 추가하므로 기존 데이터에 영향 없음.

Revision ID: c233ab323538
Revises: 37b334ba3fc8
Create Date: 2026-09-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c233ab323538'
down_revision = '37b334ba3fc8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')
