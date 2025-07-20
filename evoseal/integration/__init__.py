"""EVOSEAL Integration Module

This module provides integration adapters and orchestration for external components
(DGM, OpenEvolve, SEAL (Self-Adapting Language Models)) within the EVOSEAL evolution pipeline.
"""

from .base_adapter import (
    BaseComponentAdapter,
    ComponentConfig,
    ComponentManager,
    ComponentResult,
    ComponentState,
    ComponentStatus,
    ComponentType,
)

# Import adapters with optional dependencies
try:
    from .dgm.dgm_adapter import DGMAdapter, create_dgm_adapter

    _DGM_AVAILABLE = True
except ImportError as e:
    _DGM_AVAILABLE = False
    DGMAdapter = None
    create_dgm_adapter = None
    import warnings

    warnings.warn(f"DGM adapter not available: {e}", ImportWarning)

try:
    from .openevolve.openevolve_adapter import OpenEvolveAdapter, create_openevolve_adapter

    _OPENEVOLVE_AVAILABLE = True
except ImportError as e:
    _OPENEVOLVE_AVAILABLE = False
    OpenEvolveAdapter = None
    create_openevolve_adapter = None
    import warnings

    warnings.warn(f"OpenEvolve adapter not available: {e}", ImportWarning)

try:
    from .seal.seal_adapter import SEALAdapter, create_seal_adapter

    _SEAL_AVAILABLE = True
except ImportError as e:
    _SEAL_AVAILABLE = False
    SEALAdapter = None
    create_seal_adapter = None
    import warnings

    warnings.warn(f"SEAL (Self-Adapting Language Models) adapter not available: {e}", ImportWarning)
from .orchestrator import IntegrationOrchestrator, create_integration_orchestrator

__all__ = [
    # Base classes
    "BaseComponentAdapter",
    "ComponentConfig",
    "ComponentManager",
    "ComponentResult",
    "ComponentState",
    "ComponentStatus",
    "ComponentType",
    # Component adapters
    "DGMAdapter",
    "create_dgm_adapter",
    "OpenEvolveAdapter",
    "create_openevolve_adapter",
    "SEALAdapter",
    "create_seal_adapter",
    # Orchestrator
    "IntegrationOrchestrator",
    "create_integration_orchestrator",
]
