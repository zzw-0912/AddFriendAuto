from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.contact import ContactResponse
from app.services.contact_service import search_contacts

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("/search", response_model=list[ContactResponse])
def search(
    q: str = Query("", description="Search by nickname or wechat ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return search_contacts(q, db)
