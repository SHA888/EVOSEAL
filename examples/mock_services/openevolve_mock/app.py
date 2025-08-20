import uuid

from fastapi import FastAPI

app = FastAPI()


@app.post("/openevolve/jobs/evolve")
async def evolve(payload: dict):
    return {"job_id": f"oe-{uuid.uuid4().hex[:8]}"}


@app.get("/openevolve/jobs/{job_id}/status")
async def status(job_id: str):
    return {"status": "completed"}


@app.get("/openevolve/jobs/{job_id}/result")
async def result(job_id: str):
    return {"result": {"program_id": "p-e2e", "score": 0.91, "job_id": job_id}}
