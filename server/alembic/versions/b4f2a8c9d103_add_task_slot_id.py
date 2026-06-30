"""add task slot id

Revision ID: b4f2a8c9d103
Revises: 9b7c2d4e6f01
Create Date: 2026-06-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "b4f2a8c9d103"
down_revision: Union[str, None] = "9b7c2d4e6f01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}
    return index_name in indexes or index_name in unique_constraints


def upgrade() -> None:
    if _has_table("tasks") and not _has_column("tasks", "slot_id"):
        op.add_column("tasks", sa.Column("slot_id", sa.Integer(), nullable=False, server_default="1"))
    if _has_table("tasks") and not _has_index("tasks", "ix_tasks_user_slot_status"):
        op.create_index("ix_tasks_user_slot_status", "tasks", ["user_id", "slot_id", "status"], unique=False)


def downgrade() -> None:
    if _has_table("tasks") and _has_index("tasks", "ix_tasks_user_slot_status"):
        op.drop_index("ix_tasks_user_slot_status", table_name="tasks")
    if _has_table("tasks") and _has_column("tasks", "slot_id"):
        op.drop_column("tasks", "slot_id")
