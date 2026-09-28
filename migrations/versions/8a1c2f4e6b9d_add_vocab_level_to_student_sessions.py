"""add vocab_level to vocab_quiz_student_sessions

Revision ID: 8a1c2f4e6b9d
Revises: 4d83374ccc5f
Create Date: 2026-09-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8a1c2f4e6b9d'
down_revision = '4d83374ccc5f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vocab_quiz_student_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vocab_level', sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_vocab_quiz_student_sessions_vocab_level'), ['vocab_level'], unique=False
        )


def downgrade():
    with op.batch_alter_table('vocab_quiz_student_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vocab_quiz_student_sessions_vocab_level'))
        batch_op.drop_column('vocab_level')
