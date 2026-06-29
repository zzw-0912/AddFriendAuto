"""add current schema gaps

Revision ID: 9b7c2d4e6f01
Revises: 56364eee2324
Create Date: 2026-06-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "9b7c2d4e6f01"
down_revision: Union[str, None] = "56364eee2324"
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


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if _has_table(table_name) and not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    _add_column_if_missing("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    _add_column_if_missing("users", sa.Column("referral_code", sa.String(length=16), nullable=True))
    _create_index_if_missing("ix_users_referral_code", "users", ["referral_code"], unique=True)

    _add_column_if_missing("memberships", sa.Column("plan_id", sa.Integer(), nullable=True))
    _add_column_if_missing("task_results", sa.Column("message", sa.Text(), nullable=True))

    if not _has_table("feedbacks"):
        op.create_table(
            "feedbacks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("images", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_feedbacks_id", "feedbacks", ["id"], unique=False)
    _create_index_if_missing("ix_feedbacks_user_id", "feedbacks", ["user_id"], unique=False)


def downgrade() -> None:
    if _has_table("feedbacks"):
        op.drop_index("ix_feedbacks_user_id", table_name="feedbacks")
        op.drop_index("ix_feedbacks_id", table_name="feedbacks")
        op.drop_table("feedbacks")

    if _has_table("task_results") and _has_column("task_results", "message"):
        op.drop_column("task_results", "message")
    if _has_table("memberships") and _has_column("memberships", "plan_id"):
        op.drop_column("memberships", "plan_id")
    if _has_table("users") and _has_index("users", "ix_users_referral_code"):
        op.drop_index("ix_users_referral_code", table_name="users")
    if _has_table("users") and _has_column("users", "referral_code"):
        op.drop_column("users", "referral_code")
    if _has_table("users") and _has_column("users", "password_hash"):
        op.drop_column("users", "password_hash")
