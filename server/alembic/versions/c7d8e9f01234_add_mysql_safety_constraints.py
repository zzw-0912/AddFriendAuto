"""add mysql safety constraints

Revision ID: c7d8e9f01234
Revises: b4f2a8c9d103
Create Date: 2026-06-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "c7d8e9f01234"
down_revision: Union[str, None] = "b4f2a8c9d103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}
    return index_name in indexes or index_name in unique_constraints


def _create_unique_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=True)


def _drop_index_if_present(index_name: str, table_name: str) -> None:
    if _has_table(table_name) and _has_index(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    if _has_table("task_results"):
        op.execute(sa.text("""
            DELETE FROM task_results
            WHERE contact_id IS NOT NULL
              AND id NOT IN (
                SELECT keep_id
                FROM (
                  SELECT MIN(id) AS keep_id
                  FROM task_results
                  WHERE contact_id IS NOT NULL
                  GROUP BY task_id, contact_id
                ) AS kept
              )
        """))

    _create_unique_index_if_missing("uq_devices_user_id", "devices", ["user_id"])
    _create_unique_index_if_missing("uq_trial_quotas_user_id", "trial_quotas", ["user_id"])
    _create_unique_index_if_missing("uq_task_results_task_contact", "task_results", ["task_id", "contact_id"])


def downgrade() -> None:
    _drop_index_if_present("uq_task_results_task_contact", "task_results")
    _drop_index_if_present("uq_trial_quotas_user_id", "trial_quotas")
    _drop_index_if_present("uq_devices_user_id", "devices")
