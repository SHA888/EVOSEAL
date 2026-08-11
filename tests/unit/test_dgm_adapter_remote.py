import types

import pytest

from evoseal.integration.dgmr.dgm_adapter import create_dgm_adapter

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
        self.calls = {"status": 0}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json=None, headers=None):
        if url.endswith("/dgm/jobs/advance"):
            return _FakeResponse(200, {"job_id": "job-1"})
        if url.endswith("/dgm/archive/update"):
            return _FakeResponse(200, {"ok": True, "updated": True})
        return _FakeResponse(404, {"error": "not found"})

    def get(self, url, headers=None):
        if "/dgm/jobs/" in url and url.endswith("/status"):
            # return completed immediately
            return _FakeResponse(200, {"status": "completed"})
        if "/dgm/jobs/" in url and url.endswith("/result"):
            return _FakeResponse(200, {"result": {"best": "ok"}})
        return _FakeResponse(404, {"error": "not found"})


@pytest.mark.asyncio
async def test_dgm_advance_generation_remote(monkeypatch):
    # Patch module-level aiohttp symbol used by the adapter
    from evoseal.integration.dgmr import dgm_adapter as dgm_mod

    class _FakeTimeout:
        def __init__(self, total=None):
            self.total = total

    monkeypatch.setattr(
        dgm_mod,
        "aiohttp",
        types.SimpleNamespace(ClientSession=_FakeSession, ClientTimeout=_FakeTimeout),
        raising=False,
    )

    adapter = create_dgm_adapter(
        enabled=True,
        timeout=10,
        config={"remote": {"base_url": "http://localhost:9999"}},
    )

    ok = await adapter.initialize()
    assert ok
    ok = await adapter.start()
    assert ok

    res = await adapter.execute("advance_generation", data={})
    assert res.success, res.error
    assert res.data["result"]["result"]["best"] == "ok"

    await adapter.stop()


@pytest.mark.asyncio
async def test_dgm_update_archive_remote(monkeypatch):
    from evoseal.integration.dgmr import dgm_adapter as dgm_mod

    class _FakeTimeout:
        def __init__(self, total=None):
            self.total = total

    monkeypatch.setattr(
        dgm_mod,
        "aiohttp",
        types.SimpleNamespace(ClientSession=_FakeSession, ClientTimeout=_FakeTimeout),
        raising=False,
    )

    adapter = create_dgm_adapter(
        enabled=True,
        timeout=10,
        config={"remote": {"base_url": "http://localhost:9999"}},
    )

    assert await adapter.initialize()
    assert await adapter.start()

    res = await adapter.execute("update_archive", data=["run-1", "run-2"])
    assert res.success, res.error
    assert res.data["result"]["ok"] is True

    await adapter.stop()


class _FakeSessionJobFailed:
    """Fake session where the job fails after submission."""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json=None, headers=None):
        if url.endswith("/dgm/jobs/advance"):
            return _FakeResponse(200, {"job_id": "job-failed-1"})
        return _FakeResponse(404, {"error": "not found"})

    def get(self, url, headers=None):
        if "/dgm/jobs/" in url and url.endswith("/status"):
            return _FakeResponse(200, {"status": "failed", "error": "evaluation crashed"})
        return _FakeResponse(404, {"error": "not found"})


@pytest.mark.asyncio
async def test_dgm_advance_generation_remote_failed(monkeypatch):
    """A failed DGM job must report success=False, not silently succeed."""
    from evoseal.integration.dgmr import dgm_adapter as dgm_mod

    class _FakeTimeout:
        def __init__(self, total=None):
            self.total = total

    monkeypatch.setattr(
        dgm_mod,
        "aiohttp",
        types.SimpleNamespace(ClientSession=_FakeSessionJobFailed, ClientTimeout=_FakeTimeout),
        raising=False,
    )

    adapter = create_dgm_adapter(
        enabled=True,
        timeout=10,
        config={"remote": {"base_url": "http://localhost:9999"}},
    )

    assert await adapter.initialize()
    assert await adapter.start()

    res = await adapter.execute("advance_generation", data={})
    assert not res.success, "Failed job should report success=False"
    assert "evaluation crashed" in res.error

    await adapter.stop()


class _FakeSessionJobFailedNullError:
    """Fake session where the job fails with a null error value."""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json=None, headers=None):
        if url.endswith("/dgm/jobs/advance"):
            return _FakeResponse(200, {"job_id": "job-failed-null-1"})
        return _FakeResponse(404, {"error": "not found"})

    def get(self, url, headers=None):
        if "/dgm/jobs/" in url and url.endswith("/status"):
            return _FakeResponse(200, {"status": "failed", "error": None})
        return _FakeResponse(404, {"error": "not found"})


@pytest.mark.asyncio
async def test_dgm_advance_generation_remote_failed_null_error(monkeypatch):
    """A failed job with error=null must surface the generic fallback, not None."""
    from evoseal.integration.dgmr import dgm_adapter as dgm_mod

    class _FakeTimeout:
        def __init__(self, total=None):
            self.total = total

    monkeypatch.setattr(
        dgm_mod,
        "aiohttp",
        types.SimpleNamespace(
            ClientSession=_FakeSessionJobFailedNullError, ClientTimeout=_FakeTimeout
        ),
        raising=False,
    )

    adapter = create_dgm_adapter(
        enabled=True,
        timeout=10,
        config={"remote": {"base_url": "http://localhost:9999"}},
    )

    assert await adapter.initialize()
    assert await adapter.start()

    res = await adapter.execute("advance_generation", data={})
    assert not res.success, "Failed job should report success=False"
    assert res.error is not None
    assert res.error != ""
    assert "job-failed-null-1" in res.error

    await adapter.stop()
