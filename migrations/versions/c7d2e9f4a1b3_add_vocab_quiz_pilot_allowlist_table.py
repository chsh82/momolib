"""add vocab_quiz_pilot_allowlist table

Revision ID: c7d2e9f4a1b3
Revises: 8a1c2f4e6b9d
Create Date: 2026-09-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d2e9f4a1b3'
down_revision = '8a1c2f4e6b9d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'vocab_quiz_pilot_allowlist',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('allowed_levels_json', sa.Text(), nullable=False),
        sa.Column('added_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('vocab_quiz_pilot_allowlist', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_vocab_quiz_pilot_allowlist_user_id'), ['user_id'], unique=True
        )


def downgrade():
    with op.batch_alter_table('vocab_quiz_pilot_allowlist', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vocab_quiz_pilot_allowlist_user_id'))
    op.drop_table('vocab_quiz_pilot_allowlist')
