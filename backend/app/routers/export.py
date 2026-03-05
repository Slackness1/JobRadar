from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ExportParams
from app.services.exporter import export_csv, export_excel, export_json

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/csv")
def export_csv_endpoint(params: ExportParams, db: Session = Depends(get_db)):
    content = export_csv(
        db,
        fields=params.fields or None,
        search=params.search,
        tracks_filter=params.tracks or None,
        min_score=params.min_score,
        days=params.days,
        job_stage=params.job_stage,
    )
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs_export.csv"},
    )


@router.post("/excel")
def export_excel_endpoint(params: ExportParams, db: Session = Depends(get_db)):
    content = export_excel(
        db,
        fields=params.fields or None,
        search=params.search,
        tracks_filter=params.tracks or None,
        min_score=params.min_score,
        days=params.days,
        job_stage=params.job_stage,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=jobs_export.xlsx"},
    )


@router.post("/json")
def export_json_endpoint(params: ExportParams, db: Session = Depends(get_db)):
    content = export_json(
        db,
        fields=params.fields or None,
        search=params.search,
        tracks_filter=params.tracks or None,
        min_score=params.min_score,
        days=params.days,
        job_stage=params.job_stage,
    )
    return Response(
        content=content.encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=jobs_export.json"},
    )
