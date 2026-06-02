import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.analysis_service import AnalyzeResponse, run_incident_analysis

router = APIRouter(prefix="/projects", tags=["Analysis"])


@router.post(
    "/{project_id}/analyze/incidents",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Run the incident analysis agent over a project's cleaned records",
)
def analyze_incidents(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    return run_incident_analysis(project_id, db)
