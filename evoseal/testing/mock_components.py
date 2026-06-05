"""Deterministic mock component adapters for EVOSEAL (Plans.md 2.3).

The evolution loop depends on three external components — DGM (variant
generation), OpenEvolve (evaluation), and SEAL (code analysis / adaptation).
Exercising the loop in tests or CI would otherwise require API keys and running
services. This module provides drop-in :class:`BaseComponentAdapter` mocks that:

- implement the same async ``execute`` / ``get_metrics`` / lifecycle surface,
- return well-formed ``ComponentResult`` objects matching the real data shapes,
- are **deterministic**: output is a pure function of ``(seed, operation, data)``,
  so the same seed yields the same result regardless of call order.

Wiring is **all-or-nothing** via the ``EVOSEAL_MOCK_MODE`` environment variable:
when set truthy, :class:`~evoseal.integration.orchestrator.IntegrationOrchestrator`
registers mocks for *every* configured component, never a mix of real and mock.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from evoseal.integration.base_adapter import (
    BaseComponentAdapter,
    ComponentConfig,
    ComponentResult,
    ComponentType,
)

_TRUTHY = {"true", "1", "yes", "on"}


def is_mock_mode() -> bool:
    """Return True when ``EVOSEAL_MOCK_MODE`` is set to a truthy value."""
    return os.environ.get("EVOSEAL_MOCK_MODE", "").strip().lower() in _TRUTHY


def resolve_seed(explicit: int | None = None) -> int:
    """Resolve the deterministic seed.

    Precedence: explicit argument > ``EVOSEAL_MOCK_SEED`` env var > 0.
    """
    if explicit is not None:
        return int(explicit)
    raw = os.environ.get("EVOSEAL_MOCK_SEED", "").strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def _digest(seed: int, *parts: Any) -> int:
    """Stable 64-bit integer derived from the seed and call inputs.

    Uses SHA-256 over a canonical string so the value is reproducible across
    processes and Python runs (unlike the salted built-in ``hash``).
    """
    payload = "::".join([str(seed), *(repr(p) for p in parts)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _unit_float(seed: int, *parts: Any) -> float:
    """Deterministic float in [0, 1) from the seed and call inputs."""
    return _digest(seed, *parts) / 2**64


def _ranged_int(seed: int, lo: int, hi: int, *parts: Any) -> int:
    """Deterministic int in the inclusive range [lo, hi]."""
    if hi <= lo:
        return lo
    return lo + _digest(seed, *parts) % (hi - lo + 1)


class _MockAdapter(BaseComponentAdapter):
    """Common base for the mock adapters.

    Subclasses implement :meth:`_dispatch` to map an operation name to a result
    payload. The base handles lifecycle (always succeeds), metrics, and the
    unknown-operation failure path.
    """

    _component_type: ComponentType
    _operations: tuple[str, ...] = ()

    def __init__(self, config: ComponentConfig, seed: int | None = None):
        super().__init__(config)
        self.seed = resolve_seed(seed)
        self._calls = 0

    async def _initialize_impl(self) -> bool:
        return True

    async def _start_impl(self) -> bool:
        return True

    async def _stop_impl(self) -> bool:
        return True

    async def execute(self, operation: str, data: Any = None, **kwargs: Any) -> ComponentResult:
        self._calls += 1
        if operation not in self._operations:
            return ComponentResult(
                success=False,
                error=(
                    f"Mock {self._component_type.value} adapter does not support "
                    f"operation {operation!r}; known: {', '.join(self._operations)}"
                ),
            )
        payload = self._dispatch(operation, data, **kwargs)
        return ComponentResult(success=True, data=payload, metrics={"mock": True})

    async def get_metrics(self) -> dict[str, Any]:
        return {
            "component": self._component_type.value,
            "mock": True,
            "seed": self.seed,
            "operations_executed": self._calls,
        }

    def _dispatch(self, operation: str, data: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


class MockDGMAdapter(_MockAdapter):
    """Mock DGM: deterministic variant generation and archive updates."""

    _component_type = ComponentType.DGM
    _operations = ("advance_generation", "update_archive")

    def _dispatch(self, operation: str, data: Any, **kwargs: Any) -> dict[str, Any]:
        if operation == "advance_generation":
            generation = 0
            if isinstance(data, dict):
                generation = int(data.get("generation", 0))
            n = _ranged_int(self.seed, 2, 4, "advance_generation", generation, "count")
            run_ids = [f"mock_run_g{generation}_{i}" for i in range(n)]
            parent_ids = [f"mock_run_g{generation - 1}_{i}" for i in range(n)] if generation else []
            return {
                "generation": generation,
                "run_ids": run_ids,
                "parent_ids": parent_ids,
                "best_fitness": round(_unit_float(self.seed, "fitness", generation), 6),
            }
        # update_archive
        new_ids: list[str] = list(data) if isinstance(data, list | tuple) else []
        return {"archive": new_ids, "added": new_ids, "count": len(new_ids)}


class MockOpenEvolveAdapter(_MockAdapter):
    """Mock OpenEvolve: deterministic evaluation producing a program + score."""

    _component_type = ComponentType.OPENEVOLVE
    _operations = ("evolve",)

    def _dispatch(self, operation: str, data: Any, **kwargs: Any) -> dict[str, Any]:
        iterations = 0
        if isinstance(data, dict):
            iterations = int(data.get("iterations", 0))
        program_idx = _digest(self.seed, "program", iterations) % 1_000_000
        return {
            "program_id": f"mock_prog_{program_idx:06d}",
            "score": round(_unit_float(self.seed, "score", iterations), 6),
            "iterations": iterations,
        }


class MockSEALAdapter(_MockAdapter):
    """Mock SEAL: deterministic code analysis / generation responses."""

    _component_type = ComponentType.SEAL
    _operations = (
        "submit_prompt",
        "batch_submit",
        "analyze_code",
        "generate_code",
        "improve_code",
        "explain_code",
        "review_code",
        "optimize_prompt",
    )

    def _dispatch(self, operation: str, data: Any, **kwargs: Any) -> dict[str, Any]:
        key = repr(data)
        score = round(_unit_float(self.seed, operation, key), 6)
        if operation == "analyze_code":
            return {
                "analysis": f"mock analysis (score={score})",
                "score": score,
                "suggestions": [
                    f"mock suggestion {i}" for i in range(_ranged_int(self.seed, 1, 3, key))
                ],
            }
        if operation in ("generate_code", "improve_code"):
            return {"code": f"# mock {operation} output (score={score})\npass", "score": score}
        if operation == "batch_submit":
            items = list(data) if isinstance(data, list | tuple) else [data]
            return {"responses": [f"mock response {i}" for i in range(len(items))]}
        # submit_prompt / explain_code / review_code / optimize_prompt
        return {"result": f"mock {operation} response (score={score})", "score": score}


_FACTORY_BY_TYPE = {
    ComponentType.DGM: MockDGMAdapter,
    ComponentType.OPENEVOLVE: MockOpenEvolveAdapter,
    ComponentType.SEAL: MockSEALAdapter,
}


def create_mock_adapter(
    component_type: ComponentType, *, seed: int | None = None, **_config: Any
) -> BaseComponentAdapter:
    """Create a mock adapter for the given component type.

    Extra keyword arguments (real-adapter config) are accepted and ignored so
    the mock is a drop-in replacement for the real factory signatures.
    """
    cls = _FACTORY_BY_TYPE.get(component_type)
    if cls is None:
        raise ValueError(f"No mock adapter for component type {component_type!r}")
    config = ComponentConfig(component_type=component_type)
    return cls(config, seed=seed)


def create_mock_dgm_adapter(*, seed: int | None = None, **config: Any) -> MockDGMAdapter:
    return create_mock_adapter(ComponentType.DGM, seed=seed, **config)  # type: ignore[return-value]


def create_mock_openevolve_adapter(
    *, seed: int | None = None, **config: Any
) -> MockOpenEvolveAdapter:
    return create_mock_adapter(ComponentType.OPENEVOLVE, seed=seed, **config)  # type: ignore[return-value]


def create_mock_seal_adapter(*, seed: int | None = None, **config: Any) -> MockSEALAdapter:
    return create_mock_adapter(ComponentType.SEAL, seed=seed, **config)  # type: ignore[return-value]
