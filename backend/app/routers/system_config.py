from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SpringDisplayConfigIn, SpringDisplayConfigOut
from app.services.system_config import get_spring_display_config, set_spring_display_config


router = APIRouter(prefix="/api/system-config", tags=["system-config"])


@router.get("/spring-display", response_model=SpringDisplayConfigOut)
def get_spring_display(db: Session = Depends(get_db)):
    return get_spring_display_config(db)


@router.put("/spring-display", response_model=SpringDisplayConfigOut)
def set_spring_display(data: SpringDisplayConfigIn, db: Session = Depends(get_db)):
    return set_spring_display_config(db, data)
