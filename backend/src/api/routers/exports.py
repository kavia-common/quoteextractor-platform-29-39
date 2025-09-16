from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.models import ExportFormat, ExportJob, JobStatus
from src.api.store import EXPORT_JOBS, QUOTES, generate_id

router = APIRouter(tags=["exports"])


class ExportCreateRequest(BaseModel):
    quote_ids: List[str] = Field(default_factory=list, description="Quotes to include.")
    format: ExportFormat = Field(..., description="Export format.")


class ExportResponse(BaseModel):
    export: ExportJob


@router.post("", summary="Create export job", description="Create export job (MVP: immediate completion).", response_model=ExportResponse)
def create_export_job(payload: ExportCreateRequest) -> ExportResponse:
    """
    PUBLIC_INTERFACE
    Create an export job; MVP completes immediately and sets a mock result URL.
    """
    # Validate quotes exist
    for qid in payload.quote_ids:
        if qid not in QUOTES:
            raise HTTPException(status_code=404, detail=f"Quote not found: {qid}")

    job_id = generate_id("export")
    job = ExportJob(
        id=job_id,
        quote_ids=payload.quote_ids,
        format=payload.format,
        status=JobStatus.processing,
    )
    # MVP: instantly "process"
    job.status = JobStatus.completed
    job.result_url = f"/mock/exports/{job_id}.{_format_extension(payload.format)}"
    job.updated_at = datetime.utcnow()
    EXPORT_JOBS[job_id] = job
    return ExportResponse(export=job)


@router.get("", summary="List export jobs", description="List all export jobs.")
def list_export_jobs():
    """
    PUBLIC_INTERFACE
    List exports.
    """
    return {"items": list(EXPORT_JOBS.values())}


@router.get("/{job_id}", summary="Get export job", description="Get export job by ID.")
def get_export_job(job_id: str) -> ExportJob:
    """
    PUBLIC_INTERFACE
    Get export job by ID.
    """
    job = EXPORT_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    return job


def _format_extension(fmt: ExportFormat) -> str:
    mapping = {
        ExportFormat.plain_text: "txt",
        ExportFormat.json: "json",
        ExportFormat.twitter: "txt",
        ExportFormat.linkedin: "txt",
        ExportFormat.instagram: "txt",
        ExportFormat.srt: "srt",
        ExportFormat.vtt: "vtt",
    }
    return mapping.get(fmt, "txt")
