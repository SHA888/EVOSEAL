"""
Workflow Orchestration Module

This module handles the main workflow orchestration for the EVOSEAL system,
coordinating between DGM, OpenEvolve, and SEAL components.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class WorkflowManager:
    """Manages the execution of the EVOSEAL workflow."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the workflow manager with optional configuration."""
        self.config = config or {}
        self.initialized = False
        
    def initialize(self):
        """Initialize all components and their connections."""
        if self.initialized:
            return
            
        logger.info("Initializing EVOSEAL workflow manager...")
        
        # Initialize components
        self._init_components()
        
        self.initialized = True
        logger.info("EVOSEAL workflow manager initialized successfully")
    
    def _init_components(self):
        """Initialize individual components."""
        # Initialize DGM integration
        from evoseal.integration.dgm import DGMIntegration
        self.dgm = DGMIntegration(self.config.get('dgm', {}))
        
        # Initialize OpenEvolve integration
        from evoseal.integration.openevolve import OpenEvolveIntegration
        self.openevolve = OpenEvolveIntegration(self.config.get('openevolve', {}))
        
        # Initialize SEAL integration
        from evoseal.integration.seal import SEALIntegration
        self.seal = SEALIntegration(self.config.get('seal', {}))
    
    def run(self, task_description: str, **kwargs):
        """
        Execute the main workflow.
        
        Args:
            task_description: Description of the task to be solved
            **kwargs: Additional parameters for the workflow
            
        Returns:
            Dict containing the results of the workflow execution
        """
        if not self.initialized:
            self.initialize()
            
        logger.info(f"Starting workflow for task: {task_description}")
        
        try:
            # 1. Use SEAL for initial solution generation
            initial_solution = self.seal.generate_initial_solution(task_description)
            
            # 2. Use DGM for evolutionary improvement
            improved_solution = self.dgm.improve_solution(initial_solution)
            
            # 3. Use OpenEvolve for optimization
            optimized_solution = self.openevolve.optimize(improved_solution)
            
            logger.info("Workflow completed successfully")
            return {
                'status': 'success',
                'initial_solution': initial_solution,
                'improved_solution': improved_solution,
                'optimized_solution': optimized_solution
            }
            
        except Exception as e:
            logger.error(f"Workflow failed: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e)
            }
