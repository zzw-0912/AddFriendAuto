from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.client_update import ClientUpdateConfigResponse
from app.services.client_update_service import get_client_update_config


router = APIRouter(prefix="/client-update", tags=["client-update"])


@router.get("/config", response_model=ClientUpdateConfigResponse)
def get_config(db: Session = Depends(get_db)):
    return get_client_update_config(db)
