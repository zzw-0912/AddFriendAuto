from sqlalchemy.orm import Query

from app.models.plan import Plan


HIDDEN_PUBLIC_PLAN_IDS = {3}
HIDDEN_PUBLIC_PLAN_PRICES_CENTS = {80000}
PUBLIC_MAX_SLOT_COUNT = 2


def is_public_plan(plan: Plan) -> bool:
    return bool(plan.enabled) and plan.id not in HIDDEN_PUBLIC_PLAN_IDS and plan.price_cents not in HIDDEN_PUBLIC_PLAN_PRICES_CENTS


def public_plan_query(query: Query) -> Query:
    return query.filter(
        Plan.enabled == True,
        ~Plan.id.in_(HIDDEN_PUBLIC_PLAN_IDS),
        ~Plan.price_cents.in_(HIDDEN_PUBLIC_PLAN_PRICES_CENTS),
    )
