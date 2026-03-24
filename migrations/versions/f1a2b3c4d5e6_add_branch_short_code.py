"""add branch short_code

Revision ID: f1a2b3c4d5e6
Revises: b9db68a1d6d2
Create Date: 2026-03-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = 'b9db68a1d6d2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('branches', sa.Column('short_code', sa.String(length=4), nullable=True))


def downgrade():
    op.drop_column('branches', 'short_code')
