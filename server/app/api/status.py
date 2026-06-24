from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.status import UserStatusResponse
from app.services.status_service import get_user_status

router = APIRouter(tags=["me"])


@router.get("/me/status", response_model=UserStatusResponse)
def my_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_user_status(user, db)
