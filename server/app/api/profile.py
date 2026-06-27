from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.profile import ProfileResponse
from app.services.profile_service import get_profile

router = APIRouter(tags=["profile"])


@router.get("/me/profile", response_model=ProfileResponse)
def my_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_profile(user, db)
