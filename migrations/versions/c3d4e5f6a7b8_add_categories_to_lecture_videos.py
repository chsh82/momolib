"""add categories to lecture_videos

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('lecture_videos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cat_large',  sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('cat_medium', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('cat_small',  sa.String(length=30), nullable=True))


def downgrade():
    with op.batch_alter_table('lecture_videos', schema=None) as batch_op:
        batch_op.drop_column('cat_small')
        batch_op.drop_column('cat_medium')
        batch_op.drop_column('cat_large')
