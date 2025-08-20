import types

import pytest

from evoseal.integration.oe import openevolve_adapter as oe_mod
from evoseal.integration.oe.openevolve_adapter import create_openevolve_adapter

pytestmark = pytest.mark.unit


class _FakeBestProgram:
    def __init__(self):
        self.id = "pkg-prog-1"
        self.metrics = {"score": 0.95}


class _FakeDB:
    def load(self, checkpoint):
        return True


class _FakeOE:
    def __init__(self, initial_program_path, evaluation_file, config, output_dir):
        self.initial_program_path = initial_program_path
        self.evaluation_file = evaluation_file
        self.config = config
        self.output_dir = output_dir
        self.database = _FakeDB()

    async def run(self, iterations=None, target_score=None):
        return _FakeBestProgram()


@pytest.mark.asyncio
async def test_openevolve_evolve_package(monkeypatch, tmp_path):
    # Fake controller module with OpenEvolve class
    fake_controller = types.SimpleNamespace(OpenEvolve=_FakeOE)

    # Fake config module with load_config
    def _fake_load_config(path):
        return {"_loaded_from": str(path)}

    fake_cfg_mod = types.SimpleNamespace(load_config=_fake_load_config)

    # Patch import_module used inside the adapter
    def _fake_import_module(name: str):
        if name == "openevolve.controller":
            return fake_controller
        if name == "openevolve.config":
            return fake_cfg_mod
        raise ImportError(name)

    monkeypatch.setattr(oe_mod, "import_module", _fake_import_module, raising=True)

    adapter = create_openevolve_adapter(
        enabled=True,
        timeout=10,
        config={
            "mode": "package",
            "package": {
                "initial_program_path": str(tmp_path / "prog.py"),
                "evaluation_file": str(tmp_path / "eval.py"),
                "output_dir": str(tmp_path / "out"),
                "config_path": str(tmp_path / "cfg.yaml"),
                "iterations": 3,
                "target_score": 0.9,
                "checkpoint": str(tmp_path / "ckpt.db"),
            },
        },
    )

    assert await adapter.initialize()
    assert await adapter.start()

    res = await adapter.execute("evolve", data={})
    assert res.success, res.error
    assert res.data["result"]["program_id"] == "pkg-prog-1"
    assert res.data["result"]["score"] == 0.95

    assert await adapter.stop()
