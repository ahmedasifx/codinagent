"""Artifact download endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..core.artifacts import resolve_path

router = APIRouter()


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(artifact_id: str):
    path = resolve_path(artifact_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path)
