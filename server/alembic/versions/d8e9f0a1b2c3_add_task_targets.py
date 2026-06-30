"""add task targets

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f01234
Create Date: 2026-06-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7d8e9f01234"
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


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    if _has_table("tasks") and not _has_column("tasks", "target_type"):
        op.add_column("tasks", sa.Column("target_type", sa.String(length=20), nullable=False, server_default="phone"))

    if _has_table("task_results") and not _has_column("task_results", "target_id"):
        op.add_column("task_results", sa.Column("target_id", sa.Integer(), nullable=True))
    if _has_table("task_results") and not _has_column("task_results", "target_type"):
        op.add_column("task_results", sa.Column("target_type", sa.String(length=20), nullable=True))
    _create_index_if_missing("ix_task_results_target_id", "task_results", ["target_id"])
    _create_index_if_missing("uq_task_results_task_target", "task_results", ["task_id", "target_id"], unique=True)

    if not _has_table("task_targets"):
        op.create_table(
            "task_targets",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("target_type", sa.String(length=20), nullable=False),
            sa.Column("target_value", sa.String(length=255), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("claimed_task_id", sa.Integer(), nullable=True),
            sa.Column("claimed_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("result_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_task_targets_id", "task_targets", ["id"])
    _create_index_if_missing("ix_task_targets_user_id", "task_targets", ["user_id"])
    _create_index_if_missing("ix_task_targets_user_type_status", "task_targets", ["user_id", "target_type", "status"])
    _create_index_if_missing("ix_task_targets_claimed_task", "task_targets", ["claimed_task_id"])


def downgrade() -> None:
    if _has_table("task_targets"):
        for index_name in [
            "ix_task_targets_claimed_task",
            "ix_task_targets_user_type_status",
            "ix_task_targets_user_id",
            "ix_task_targets_id",
        ]:
            if _has_index("task_targets", index_name):
                op.drop_index(index_name, table_name="task_targets")
        op.drop_table("task_targets")

    if _has_table("task_results") and _has_index("task_results", "uq_task_results_task_target"):
        op.drop_index("uq_task_results_task_target", table_name="task_results")
    if _has_table("task_results") and _has_index("task_results", "ix_task_results_target_id"):
        op.drop_index("ix_task_results_target_id", table_name="task_results")
    if _has_table("task_results") and _has_column("task_results", "target_type"):
        op.drop_column("task_results", "target_type")
    if _has_table("task_results") and _has_column("task_results", "target_id"):
        op.drop_column("task_results", "target_id")
    if _has_table("tasks") and _has_column("tasks", "target_type"):
        op.drop_column("tasks", "target_type")
