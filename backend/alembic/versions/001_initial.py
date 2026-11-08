"""Initial schema for auth, event, and home.

Revision ID: 001_initial
Revises:
Create Date: 2026-11-06
"""

from alembic import op

from app.core.database import Base
from app.models import entities  # noqa: F401

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
