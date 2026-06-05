"""Tests for the mock component infrastructure (Plans.md 2.3).

These cover three things the DoD requires:
- Mock adapters for DGM / OpenEvolve / SEAL that are drop-in BaseComponentAdapters.
- The EVOSEAL_MOCK_MODE env switch wiring through IntegrationOrchestrator (all-or-nothing).
- Deterministic output for the same seed (and order-independence).
"""

from __future__ import annotations

import pytest

from evoseal.integration.base_adapter import (
    BaseComponentAdapter,
    ComponentResult,
    ComponentState,
    ComponentType,
)
from evoseal.integration.orchestrator import IntegrationOrchestrator
from evoseal.testing.mock_components import (
    MockDGMAdapter,
    MockOpenEvolveAdapter,
    MockSEALAdapter,
    create_mock_adapter,
    create_mock_dgm_adapter,
    create_mock_openevolve_adapter,
    create_mock_seal_adapter,
    is_mock_mode,
    resolve_seed,
)

# Named seeds keep the determinism assertions readable (and satisfy PLR2004).
_ENV_SEED = 123
_EXPLICIT_SEED = 7

# --- env switch -------------------------------------------------------------


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_is_mock_mode_truthy(monkeypatch, value):
    monkeypatch.setenv("EVOSEAL_MOCK_MODE", value)
    assert is_mock_mode() is True


@pytest.mark.parametrize("value", ["false", "0", "no", "", "off"])
def test_is_mock_mode_falsy(monkeypatch, value):
    monkeypatch.setenv("EVOSEAL_MOCK_MODE", value)
    assert is_mock_mode() is False


def test_is_mock_mode_unset(monkeypatch):
    monkeypatch.delenv("EVOSEAL_MOCK_MODE", raising=False)
    assert is_mock_mode() is False


def test_resolve_seed_default(monkeypatch):
    monkeypatch.delenv("EVOSEAL_MOCK_SEED", raising=False)
    assert resolve_seed() == 0


def test_resolve_seed_from_env(monkeypatch):
    monkeypatch.setenv("EVOSEAL_MOCK_SEED", str(_ENV_SEED))
    assert resolve_seed() == _ENV_SEED


def test_resolve_seed_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("EVOSEAL_MOCK_SEED", str(_ENV_SEED))
    assert resolve_seed(_EXPLICIT_SEED) == _EXPLICIT_SEED


# --- adapters are drop-in BaseComponentAdapters -----------------------------


def test_mocks_subclass_base_adapter():
    for cls in (MockDGMAdapter, MockOpenEvolveAdapter, MockSEALAdapter):
        assert issubclass(cls, BaseComponentAdapter)


@pytest.mark.asyncio
async def test_dgm_lifecycle_and_advance_generation():
    adapter = create_mock_dgm_adapter(seed=1)
    assert await adapter.initialize() is True
    assert adapter.get_status().state == ComponentState.READY

    result = await adapter.execute("advance_generation", {"generation": 0})
    assert isinstance(result, ComponentResult)
    assert result.success is True
    assert "run_ids" in result.data
    assert "best_fitness" in result.data
    assert isinstance(result.data["run_ids"], list) and result.data["run_ids"]


@pytest.mark.asyncio
async def test_dgm_update_archive():
    adapter = create_mock_dgm_adapter(seed=1)
    await adapter.initialize()
    result = await adapter.execute("update_archive", ["run_a", "run_b"])
    assert result.success is True
    assert "archive" in result.data


@pytest.mark.asyncio
async def test_openevolve_evolve_returns_score():
    adapter = create_mock_openevolve_adapter(seed=1)
    await adapter.initialize()
    result = await adapter.execute("evolve", {"iterations": 5})
    assert result.success is True
    assert "program_id" in result.data
    assert "score" in result.data
    assert 0.0 <= result.data["score"] <= 1.0


@pytest.mark.asyncio
async def test_seal_analyze_code():
    adapter = create_mock_seal_adapter(seed=1)
    await adapter.initialize()
    result = await adapter.execute("analyze_code", {"code": "def f(): pass"})
    assert result.success is True
    assert "analysis" in result.data


@pytest.mark.asyncio
async def test_unknown_operation_is_graceful_failure():
    adapter = create_mock_dgm_adapter(seed=1)
    await adapter.initialize()
    result = await adapter.execute("does_not_exist")
    assert result.success is False
    assert result.error


@pytest.mark.asyncio
async def test_get_metrics_returns_dict():
    adapter = create_mock_openevolve_adapter(seed=1)
    await adapter.initialize()
    metrics = await adapter.get_metrics()
    assert isinstance(metrics, dict)


# --- determinism ------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_seed_same_output():
    a = create_mock_openevolve_adapter(seed=42)
    b = create_mock_openevolve_adapter(seed=42)
    await a.initialize()
    await b.initialize()
    ra = await a.execute("evolve", {"iterations": 3})
    rb = await b.execute("evolve", {"iterations": 3})
    assert ra.data == rb.data


@pytest.mark.asyncio
async def test_output_is_order_independent():
    """Output depends on (seed, operation, data), not call order."""
    a = create_mock_openevolve_adapter(seed=42)
    b = create_mock_openevolve_adapter(seed=42)
    await a.initialize()
    await b.initialize()
    # a: call X then Y; b: call Y then X. X's result must match between them.
    rax = await a.execute("evolve", {"iterations": 3})
    await a.execute("evolve", {"iterations": 99})
    await b.execute("evolve", {"iterations": 99})
    rbx = await b.execute("evolve", {"iterations": 3})
    assert rax.data == rbx.data


@pytest.mark.asyncio
async def test_different_seed_differs():
    a = create_mock_openevolve_adapter(seed=1)
    b = create_mock_openevolve_adapter(seed=2)
    await a.initialize()
    await b.initialize()
    ra = await a.execute("evolve", {"iterations": 3})
    rb = await b.execute("evolve", {"iterations": 3})
    assert ra.data != rb.data


# --- dispatch + orchestrator wiring -----------------------------------------


def test_create_mock_adapter_dispatch():
    assert isinstance(create_mock_adapter(ComponentType.DGM), MockDGMAdapter)
    assert isinstance(create_mock_adapter(ComponentType.OPENEVOLVE), MockOpenEvolveAdapter)
    assert isinstance(create_mock_adapter(ComponentType.SEAL), MockSEALAdapter)


@pytest.mark.asyncio
async def test_orchestrator_uses_mocks_when_mock_mode(monkeypatch):
    monkeypatch.setenv("EVOSEAL_MOCK_MODE", "true")
    orch = IntegrationOrchestrator()
    ok = await orch.initialize(
        {
            ComponentType.DGM: {},
            ComponentType.OPENEVOLVE: {},
            ComponentType.SEAL: {},
        }
    )
    assert ok is True
    # All-or-nothing: every configured component is a mock.
    assert isinstance(orch.get_component(ComponentType.DGM), MockDGMAdapter)
    assert isinstance(orch.get_component(ComponentType.OPENEVOLVE), MockOpenEvolveAdapter)
    assert isinstance(orch.get_component(ComponentType.SEAL), MockSEALAdapter)
