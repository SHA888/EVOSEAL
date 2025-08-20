import os
import time

import httpx
import pytest


@pytest.mark.e2e
def test_dgm_mock_end_to_end():
    base = os.getenv("DGM_BASE_URL", "http://localhost:8080")

    # advance
    r = httpx.post(f"{base}/dgm/jobs/advance", json={})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    assert job_id.startswith("dgm-")

    # status
    r = httpx.get(f"{base}/dgm/jobs/{job_id}/status")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    # result
    r = httpx.get(f"{base}/dgm/jobs/{job_id}/result")
    assert r.status_code == 200
    data = r.json()["result"]
    assert "runs" in data and isinstance(data["runs"], list)

    # archive update
    r = httpx.post(f"{base}/dgm/archive/update", json={"runs": data["runs"]})
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("updated") is True
    assert j.get("count") == len(data["runs"])  # type: ignore[arg-type]


@pytest.mark.e2e
def test_openevolve_mock_end_to_end():
    base = os.getenv("OPENE_BASE_URL", "http://localhost:8081")

    # evolve
    r = httpx.post(f"{base}/openevolve/jobs/evolve", json={"prompt": "hello"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    assert job_id.startswith("oe-")

    # status
    r = httpx.get(f"{base}/openevolve/jobs/{job_id}/status")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    # result
    r = httpx.get(f"{base}/openevolve/jobs/{job_id}/result")
    assert r.status_code == 200
    result = r.json()["result"]
    assert result.get("program_id")
    assert isinstance(result.get("score"), float)
