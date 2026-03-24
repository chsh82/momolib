"""add vocab category columns to bank_questions

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-03-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('bank_questions', sa.Column('cat_large',  sa.String(30), nullable=True))
    op.add_column('bank_questions', sa.Column('cat_medium', sa.String(30), nullable=True))
    op.add_column('bank_questions', sa.Column('cat_small',  sa.String(30), nullable=True))


def downgrade():
    op.drop_column('bank_questions', 'cat_small')
    op.drop_column('bank_questions', 'cat_medium')
    op.drop_column('bank_questions', 'cat_large')
