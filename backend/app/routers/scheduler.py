from fastapi import APIRouter
from app.schemas import SchedulerConfigOut, SchedulerConfigIn
from app.services.scheduler_service import get_scheduler_info, update_cron

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("", response_model=SchedulerConfigOut)
@router.get("/", response_model=SchedulerConfigOut)
def get_config():
    return get_scheduler_info()


@router.put("", response_model=SchedulerConfigOut)
@router.put("/", response_model=SchedulerConfigOut)
def update_config(data: SchedulerConfigIn):
    update_cron(data.cron_expression)
    return get_scheduler_info()
