from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.device import BindDeviceRequest, DeviceResponse
from app.services.device_service import bind_device, get_current_device

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/bind", response_model=DeviceResponse)
def bind(req: BindDeviceRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return bind_device(user, req.machine_code, db)


@router.get("/current", response_model=DeviceResponse | None)
def current(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_current_device(user, db)
