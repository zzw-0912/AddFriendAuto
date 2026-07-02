"""drop unused contacts table

Revision ID: f1a2b3c4d5e6
Revises: e9f0a1b2c3d4
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e9f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("contacts"):
        op.drop_table("contacts")


def downgrade() -> None:
    if not _has_table("contacts"):
        op.create_table(
            "contacts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("wechat_nickname", sa.String(length=255), nullable=True),
            sa.Column("wechat_id", sa.String(length=255), nullable=True),
            sa.Column("tag", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=True),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_contacts_id"), "contacts", ["id"], unique=False)
