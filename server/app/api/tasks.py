from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.task import ClaimTargetsResponse, ResultRequest, StartCheckRequest, StartCheckResponse, TaskResponse
from app.services.task_service import claim_targets, finish_task, report_result, start_check

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/start-check", response_model=StartCheckResponse)
def check_start(
    req: StartCheckRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return start_check(user, req.slot_id, req.target_type, req.daily_limit, req.create_tag, req.greeting_text, db)


@router.post("/{task_id}/claim-targets", response_model=ClaimTargetsResponse)
def claim(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return claim_targets(task_id, user, db)


@router.post("/{task_id}/results")
def report(
    task_id: int,
    req: ResultRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return report_result(task_id, req.target_id, req.contact_id, req.event, req.message, user, db)


@router.post("/{task_id}/finish", response_model=TaskResponse)
def finish(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return finish_task(task_id, user, db)
