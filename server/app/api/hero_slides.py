from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.hero_slide import HeroSlideResponse
from app.services.hero_slide_service import list_hero_slides


router = APIRouter(tags=["hero-slides"])


@router.get("/hero-slides", response_model=list[HeroSlideResponse])
def get_hero_slides(db: Session = Depends(get_db)):
    return list_hero_slides(db)
