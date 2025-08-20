import argparse
import asyncio
import types

from evoseal.integration import create_integration_orchestrator


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
        if url.endswith("/dgm/jobs/advance"):
            return _FakeResponse(200, {"job_id": "dgm-job-1"})
        if url.endswith("/openevolve/jobs/evolve"):
            return _FakeResponse(200, {"job_id": "oe-job-1"})
        if url.endswith("/dgm/archive/update"):
            return _FakeResponse(200, {"ok": True})
        return _FakeResponse(404, {"error": "not found"})

    def get(self, url, headers=None):
        if url.endswith("/status"):
            return _FakeResponse(200, {"status": "completed"})
        if url.endswith("/result"):
            if "/dgm/jobs/" in url:
                return _FakeResponse(200, {"result": {"runs": ["r1", "r2"]}})
            if "/openevolve/jobs/" in url:
                return _FakeResponse(200, {"result": {"program_id": "p1", "score": 0.9}})
        return _FakeResponse(404, {"error": "not found"})


async def main():
    parser = argparse.ArgumentParser(description="Minimal EVOSEAL workflow runner")
    parser.add_argument(
        "--mock", action="store_true", help="Mock remote services via aiohttp patch"
    )
    parser.add_argument("--dgm-base", default="http://localhost:8000", help="DGM base URL")
    parser.add_argument("--oe-base", default="http://localhost:8001", help="OpenEvolve base URL")
    args = parser.parse_args()

    orch = create_integration_orchestrator(
        dgm_config={
            "enabled": True,
            "timeout": 60,
            "config": {"remote": {"base_url": args.dgm_base}},
        },
        openevolve_config={
            "enabled": True,
            "timeout": 120,
            "config": {"mode": "remote", "remote": {"base_url": args.oe_base}},
        },
    )

    if args.mock:
        from evoseal.integration.dgmr import dgm_adapter as dgm_mod
        from evoseal.integration.oe import openevolve_adapter as oe_mod

        class _FakeTimeout:
            def __init__(self, total=None):
                self.total = total

        aiohttp_ns = types.SimpleNamespace(ClientSession=_FakeSession, ClientTimeout=_FakeTimeout)
        setattr(dgm_mod, "aiohttp", aiohttp_ns)
        setattr(oe_mod, "aiohttp", aiohttp_ns)

    await orch.initialize(orch._component_configs)
    await orch.start()

    res = await orch.execute_evolution_workflow(
        {
            "workflow_id": "example",
            "dgm_config": {},
            "openevolve_config": {"remote": {"job": {"foo": "bar"}}},
            "new_run_ids": ["r1", "r2"],
        }
    )

    print("Workflow result:")
    print(res)

    await orch.stop()


if __name__ == "__main__":
    asyncio.run(main())
