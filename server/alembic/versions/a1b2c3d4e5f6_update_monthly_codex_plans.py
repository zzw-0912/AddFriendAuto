"""update monthly Codex-style plans

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-07-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _upsert_plan(plan_id: int, name: str, duration_days: int, price_cents: int, enabled: bool) -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            UPDATE plans
            SET name = :name,
                duration_days = :duration_days,
                price_cents = :price_cents,
                enabled = :enabled
            WHERE id = :plan_id
            """
        ),
        {
            "plan_id": plan_id,
            "name": name,
            "duration_days": duration_days,
            "price_cents": price_cents,
            "enabled": enabled,
        },
    )
    if result.rowcount:
        return
    bind.execute(
        sa.text(
            """
            INSERT INTO plans (id, name, duration_days, price_cents, enabled)
            VALUES (:plan_id, :name, :duration_days, :price_cents, :enabled)
            """
        ),
        {
            "plan_id": plan_id,
            "name": name,
            "duration_days": duration_days,
            "price_cents": price_cents,
            "enabled": enabled,
        },
    )


def upgrade() -> None:
    if not _has_table("plans"):
        return
    _upsert_plan(1, "Plus", 30, 30000, True)
    _upsert_plan(2, "Pro 5x", 30, 50000, True)
    _upsert_plan(3, "Pro 20x", 30, 80000, True)


def downgrade() -> None:
    if not _has_table("plans"):
        return
    _upsert_plan(1, "月卡", 30, 30000, True)
    _upsert_plan(2, "季卡", 90, 50000, True)
    _upsert_plan(3, "年卡", 365, 80000, True)
