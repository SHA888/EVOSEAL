import uuid

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class ArchiveUpdate(BaseModel):
    runs: list | None = None
    data: dict | None = None


@app.post("/dgm/jobs/advance")
async def advance(payload: dict):
    return {"job_id": f"dgm-{uuid.uuid4().hex[:8]}"}


@app.get("/dgm/jobs/{job_id}/status")
async def status(job_id: str):
    return {"status": "completed"}


@app.get("/dgm/jobs/{job_id}/result")
async def result(job_id: str):
    return {"result": {"runs": ["r1", "r2"], "job_id": job_id}}


@app.post("/dgm/archive/update")
async def update_archive(payload: ArchiveUpdate):
    return {"ok": True, "updated": True, "count": len(payload.runs or [])}
