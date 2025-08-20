import types

import pytest

from evoseal.integration import ComponentType, create_integration_orchestrator

pytestmark = [pytest.mark.integration]


class _FakeResponse:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload

    async def text(self):
        return str(self._payload)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json=None, headers=None):
        # DGM advance
        if url.endswith("/dgm/jobs/advance"):
            return _FakeResponse(200, {"job_id": "dgm-job-1"})
        # OpenEvolve evolve
        if url.endswith("/openevolve/jobs/evolve"):
            return _FakeResponse(200, {"job_id": "oe-job-1"})
        return _FakeResponse(404, {"error": "not found"})

    def get(self, url, headers=None):
        # DGM status/result
        if "/dgm/jobs/" in url and url.endswith("/status"):
            return _FakeResponse(200, {"status": "completed"})
        if "/dgm/jobs/" in url and url.endswith("/result"):
            return _FakeResponse(200, {"result": {"runs": ["r1", "r2"]}})
        # OpenEvolve status/result
        if "/openevolve/jobs/" in url and url.endswith("/status"):
            return _FakeResponse(200, {"status": "completed"})
        if "/openevolve/jobs/" in url and url.endswith("/result"):
            return _FakeResponse(200, {"result": {"program_id": "p-smoke", "score": 0.8}})
        return _FakeResponse(404, {"error": "not found"})


@pytest.mark.asyncio
async def test_integration_orchestrator_smoke(monkeypatch):
    # Patch aiohttp in both adapters
    from evoseal.integration.dgmr import dgm_adapter as dgm_mod
    from evoseal.integration.oe import openevolve_adapter as oe_mod

    class _FakeTimeout:
        def __init__(self, total=None):
            self.total = total

    aiohttp_ns = types.SimpleNamespace(ClientSession=_FakeSession, ClientTimeout=_FakeTimeout)

    monkeypatch.setattr(dgm_mod, "aiohttp", aiohttp_ns, raising=False)
    monkeypatch.setattr(oe_mod, "aiohttp", aiohttp_ns, raising=False)

    orch = create_integration_orchestrator(
        dgm_config={
            "enabled": True,
            "timeout": 10,
            "config": {"remote": {"base_url": "http://fake"}},
        },
        openevolve_config={
            "enabled": True,
            "timeout": 10,
            "config": {"mode": "remote", "remote": {"base_url": "http://fake"}},
        },
        seal_config=None,
    )

    assert await orch.initialize(orch._component_configs)
    assert await orch.start()

    wf_cfg = {
        "workflow_id": "smoke",
        "dgm_config": {},
        "openevolve_config": {"remote": {"job": {"foo": "bar"}}},
        "new_run_ids": ["r1", "r2"],
    }

    res = await orch.execute_evolution_workflow(wf_cfg)
    assert res["success"] is True
    stages = {s["stage"]: s for s in res["stages"]}
    assert stages["dgm_generation"]["success"] is True
    assert stages["openevolve_evolution"]["success"] is True

    assert await orch.stop()
