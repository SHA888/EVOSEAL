import types

import pytest

from evoseal.integration.oe.openevolve_adapter import create_openevolve_adapter

pytestmark = pytest.mark.unit


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
        if url.endswith("/openevolve/jobs/evolve"):
            return _FakeResponse(200, {"job_id": "job-oe-1"})
        return _FakeResponse(404, {"error": "not found"})

    def get(self, url, headers=None):
        if "/openevolve/jobs/" in url and url.endswith("/status"):
            return _FakeResponse(200, {"status": "completed"})
        if "/openevolve/jobs/" in url and url.endswith("/result"):
            return _FakeResponse(200, {"result": {"program_id": "p1", "score": 0.9}})
        return _FakeResponse(404, {"error": "not found"})


@pytest.mark.asyncio
async def test_openevolve_evolve_remote(monkeypatch):
    from evoseal.integration.oe import openevolve_adapter as oe_mod

    class _FakeTimeout:
        def __init__(self, total=None):
            self.total = total

    monkeypatch.setattr(
        oe_mod,
        "aiohttp",
        types.SimpleNamespace(ClientSession=_FakeSession, ClientTimeout=_FakeTimeout),
        raising=False,
    )

    adapter = create_openevolve_adapter(
        enabled=True,
        timeout=10,
        config={"mode": "remote", "remote": {"base_url": "http://localhost:9999"}},
    )

    assert await adapter.initialize()
    assert await adapter.start()

    res = await adapter.execute("evolve", data={"job": {"foo": "bar"}})
    assert res.success, res.error
    assert res.data["result"]["result"]["program_id"] == "p1"

    await adapter.stop()
