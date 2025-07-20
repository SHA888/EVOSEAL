"""
Integration Orchestrator for EVOSEAL

This module provides the main orchestrator that manages the integration of all
components (DGM, OpenEvolve, SEAL (Self-Adapting Language Models)) and coordinates their interactions within
the EVOSEAL evolution pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

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
except ImportError:
    _DGM_AVAILABLE = False
    create_dgm_adapter = None

try:
    from .openevolve.openevolve_adapter import OpenEvolveAdapter, create_openevolve_adapter

    _OPENEVOLVE_AVAILABLE = True
except ImportError:
    _OPENEVOLVE_AVAILABLE = False
    create_openevolve_adapter = None

try:
    from .seal.seal_adapter import SEALAdapter, create_seal_adapter

    _SEAL_AVAILABLE = True
except ImportError:
    _SEAL_AVAILABLE = False
    create_seal_adapter = None

logger = logging.getLogger(__name__)


class IntegrationOrchestrator:
    """
    Main orchestrator for component integration in EVOSEAL.

    Manages the lifecycle, configuration, and coordination of all components
    (DGM, OpenEvolve, SEAL (Self-Adapting Language Models)) within the evolution pipeline.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.component_manager = ComponentManager()
        self.logger = logging.getLogger(f"{__name__}.IntegrationOrchestrator")
        self._initialized = False
        self._running = False

    async def initialize(
        self, component_configs: Optional[Dict[ComponentType, Dict[str, Any]]] = None
    ) -> bool:
        """
        Initialize all components with their configurations.

        Args:
            component_configs: Optional configurations for each component type

        Returns:
            True if all enabled components initialized successfully
        """
        if self._initialized:
            return True

        try:
            component_configs = component_configs or {}

            # Initialize DGM if configured and available
            if ComponentType.DGM in component_configs and _DGM_AVAILABLE:
                dgm_config = component_configs[ComponentType.DGM]
                dgm_adapter = create_dgm_adapter(**dgm_config)
                self.component_manager.register_component(dgm_adapter)
            elif ComponentType.DGM in component_configs and not _DGM_AVAILABLE:
                self.logger.warning("DGM configuration provided but DGM adapter not available")

            # Initialize OpenEvolve if configured and available
            if ComponentType.OPENEVOLVE in component_configs and _OPENEVOLVE_AVAILABLE:
                oe_config = component_configs[ComponentType.OPENEVOLVE]
                oe_adapter = create_openevolve_adapter(**oe_config)
                self.component_manager.register_component(oe_adapter)
            elif ComponentType.OPENEVOLVE in component_configs and not _OPENEVOLVE_AVAILABLE:
                self.logger.warning(
                    "OpenEvolve configuration provided but OpenEvolve adapter not available"
                )

            # Initialize SEAL (Self-Adapting Language Models) if configured and available
            if ComponentType.SEAL in component_configs and _SEAL_AVAILABLE:
                seal_config = component_configs[ComponentType.SEAL]
                seal_adapter = create_seal_adapter(**seal_config)
                self.component_manager.register_component(seal_adapter)
            elif ComponentType.SEAL in component_configs and not _SEAL_AVAILABLE:
                self.logger.warning(
                    "SEAL (Self-Adapting Language Models) configuration provided but SEAL (Self-Adapting Language Models) adapter not available"
                )

            # Initialize all registered components
            results = await self.component_manager.initialize_all()

            # Check if all enabled components initialized successfully
            success = all(results.values()) if results else True

            if success:
                self._initialized = True
                self.logger.info("Integration orchestrator initialized successfully")
            else:
                failed_components = [comp.value for comp, result in results.items() if not result]
                self.logger.error(f"Failed to initialize components: {failed_components}")

            return success

        except Exception as e:
            self.logger.exception("Error initializing integration orchestrator")
            return False

    async def start(self) -> bool:
        """Start all components."""
        if not self._initialized:
            self.logger.error("Cannot start - orchestrator not initialized")
            return False

        if self._running:
            return True

        try:
            results = await self.component_manager.start_all()
            success = all(results.values()) if results else True

            if success:
                self._running = True
                self.logger.info("All components started successfully")
            else:
                failed_components = [comp.value for comp, result in results.items() if not result]
                self.logger.error(f"Failed to start components: {failed_components}")

            return success

        except Exception as e:
            self.logger.exception("Error starting components")
            return False

    async def stop(self) -> bool:
        """Stop all components."""
        if not self._running:
            return True

        try:
            results = await self.component_manager.stop_all()
            success = all(results.values()) if results else True

            if success:
                self._running = False
                self.logger.info("All components stopped successfully")
            else:
                failed_components = [comp.value for comp, result in results.items() if not result]
                self.logger.error(f"Failed to stop components: {failed_components}")

            return success

        except Exception as e:
            self.logger.exception("Error stopping components")
            return False

    def get_component(self, component_type: ComponentType) -> Optional[BaseComponentAdapter]:
        """Get a specific component adapter."""
        return self.component_manager.get_component(component_type)

    def get_all_status(self) -> Dict[ComponentType, ComponentStatus]:
        """Get status of all components."""
        return self.component_manager.get_all_status()

    async def get_all_metrics(self) -> Dict[ComponentType, Dict[str, Any]]:
        """Get metrics from all components."""
        return await self.component_manager.get_all_metrics()

    async def execute_component_operation(
        self, component_type: ComponentType, operation: str, data: Any = None, **kwargs
    ) -> ComponentResult:
        """
        Execute an operation on a specific component.

        Args:
            component_type: Type of component to execute on
            operation: Operation to execute
            data: Data to pass to the operation
            **kwargs: Additional arguments for the operation

        Returns:
            Result of the operation
        """
        component = self.get_component(component_type)
        if not component:
            return ComponentResult(
                success=False,
                error=f"Component {component_type.value} not found or not initialized",
            )

        return await component.execute(operation, data, **kwargs)

    async def execute_evolution_workflow(self, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a complete evolution workflow coordinating all components.

        This is a high-level method that orchestrates the interaction between
        DGM, OpenEvolve, and SEAL (Self-Adapting Language Models) to perform a complete evolution cycle.

        Args:
            workflow_config: Configuration for the evolution workflow

        Returns:
            Results of the evolution workflow
        """
        try:
            workflow_results = {
                "workflow_id": workflow_config.get("workflow_id", "default"),
                "stages": [],
                "success": False,
                "error": None,
            }

            # Stage 1: DGM - Choose parents and advance generation
            if self.get_component(ComponentType.DGM):
                self.logger.info(
                    "Executing DGM stage - parent selection and generation advancement"
                )

                dgm_result = await self.execute_component_operation(
                    ComponentType.DGM,
                    "advance_generation",
                    data=workflow_config.get("dgm_config", {}),
                    **workflow_config.get("dgm_params", {}),
                )

                workflow_results["stages"].append(
                    {
                        "stage": "dgm_generation",
                        "success": dgm_result.success,
                        "data": dgm_result.data,
                        "error": dgm_result.error,
                        "execution_time": dgm_result.execution_time,
                    }
                )

                if not dgm_result.success:
                    workflow_results["error"] = f"DGM stage failed: {dgm_result.error}"
                    return workflow_results

            # Stage 2: OpenEvolve - Code evolution and optimization
            if self.get_component(ComponentType.OPENEVOLVE):
                self.logger.info("Executing OpenEvolve stage - code evolution")

                oe_result = await self.execute_component_operation(
                    ComponentType.OPENEVOLVE,
                    "evolve",
                    data=workflow_config.get("openevolve_config", {}),
                    **workflow_config.get("openevolve_params", {}),
                )

                workflow_results["stages"].append(
                    {
                        "stage": "openevolve_evolution",
                        "success": oe_result.success,
                        "data": oe_result.data,
                        "error": oe_result.error,
                        "execution_time": oe_result.execution_time,
                    }
                )

                if not oe_result.success:
                    workflow_results["error"] = f"OpenEvolve stage failed: {oe_result.error}"
                    return workflow_results

            # Stage 3: SEAL (Self-Adapting Language Models) - Code analysis and improvement
            if self.get_component(ComponentType.SEAL):
                self.logger.info(
                    "Executing SEAL (Self-Adapting Language Models) stage - code analysis and improvement"
                )

                seal_result = await self.execute_component_operation(
                    ComponentType.SEAL,
                    "analyze_code",
                    data=workflow_config.get("seal_config", {}),
                    **workflow_config.get("seal_params", {}),
                )

                workflow_results["stages"].append(
                    {
                        "stage": "seal_analysis",
                        "success": seal_result.success,
                        "data": seal_result.data,
                        "error": seal_result.error,
                        "execution_time": seal_result.execution_time,
                    }
                )

                if not seal_result.success:
                    workflow_results["error"] = (
                        f"SEAL (Self-Adapting Language Models) stage failed: {seal_result.error}"
                    )
                    return workflow_results

            # Stage 4: Integration - Combine results and update archive
            if self.get_component(ComponentType.DGM):
                self.logger.info("Executing integration stage - updating archive")

                # Extract new run IDs from previous stages (this would be more sophisticated in practice)
                new_run_ids = workflow_config.get("new_run_ids", [])

                if new_run_ids:
                    update_result = await self.execute_component_operation(
                        ComponentType.DGM,
                        "update_archive",
                        data=new_run_ids,
                        **workflow_config.get("archive_params", {}),
                    )

                    workflow_results["stages"].append(
                        {
                            "stage": "archive_update",
                            "success": update_result.success,
                            "data": update_result.data,
                            "error": update_result.error,
                            "execution_time": update_result.execution_time,
                        }
                    )

            workflow_results["success"] = True
            self.logger.info("Evolution workflow completed successfully")
            return workflow_results

        except Exception as e:
            self.logger.exception("Error executing evolution workflow")
            workflow_results["error"] = str(e)
            return workflow_results

    async def execute_parallel_operations(
        self, operations: List[Dict[str, Any]]
    ) -> List[ComponentResult]:
        """
        Execute multiple component operations in parallel.

        Args:
            operations: List of operation dictionaries with keys:
                       - component_type: ComponentType
                       - operation: str
                       - data: Any (optional)
                       - kwargs: Dict (optional)

        Returns:
            List of ComponentResult objects
        """
        tasks = []

        for op_config in operations:
            component_type = op_config["component_type"]
            operation = op_config["operation"]
            data = op_config.get("data")
            kwargs = op_config.get("kwargs", {})

            task = self.execute_component_operation(component_type, operation, data, **kwargs)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to ComponentResult objects
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(ComponentResult(success=False, error=str(result)))
            else:
                processed_results.append(result)

        return processed_results

    def is_initialized(self) -> bool:
        """Check if the orchestrator is initialized."""
        return self._initialized

    def is_running(self) -> bool:
        """Check if the orchestrator is running."""
        return self._running

    def get_available_components(self) -> List[ComponentType]:
        """Get list of available/registered components."""
        return list(self.component_manager.components.keys())


def create_integration_orchestrator(
    dgm_config: Optional[Dict[str, Any]] = None,
    openevolve_config: Optional[Dict[str, Any]] = None,
    seal_config: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> IntegrationOrchestrator:
    """
    Factory function to create an integration orchestrator with component configurations.

    Args:
        dgm_config: Configuration for DGM component
        openevolve_config: Configuration for OpenEvolve component
        seal_config: Configuration for SEAL component
        **kwargs: Additional orchestrator configuration

    Returns:
        Configured IntegrationOrchestrator instance
    """
    orchestrator = IntegrationOrchestrator(kwargs)

    # Prepare component configurations
    component_configs = {}

    if dgm_config:
        component_configs[ComponentType.DGM] = dgm_config

    if openevolve_config:
        component_configs[ComponentType.OPENEVOLVE] = openevolve_config

    if seal_config:
        component_configs[ComponentType.SEAL] = seal_config

    # Store for later initialization
    orchestrator._component_configs = component_configs

    return orchestrator
