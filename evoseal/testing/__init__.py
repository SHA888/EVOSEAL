"""Testing infrastructure for EVOSEAL.

Provides deterministic mock implementations of the external components
(DGM, OpenEvolve, SEAL) so the evolution loop can be exercised in tests, CI,
and ``--dry-run`` mode without API keys or running services.

See :mod:`evoseal.testing.mock_components` and Plans.md task 2.3.
"""

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

__all__ = [
    "MockDGMAdapter",
    "MockOpenEvolveAdapter",
    "MockSEALAdapter",
    "create_mock_adapter",
    "create_mock_dgm_adapter",
    "create_mock_openevolve_adapter",
    "create_mock_seal_adapter",
    "is_mock_mode",
    "resolve_seed",
]
