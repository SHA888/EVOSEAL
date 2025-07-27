#!/usr/bin/env python3
"""
Phase 3: Continuous Evolution Integration Script

This script launches the complete Phase 3 system including:
- Continuous Evolution Service
- Monitoring Dashboard
- Health checks and safety controls
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional
import argparse

# Add EVOSEAL to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evoseal.services import ContinuousEvolutionService
from evoseal.services.monitoring_dashboard import MonitoringDashboard
from evoseal.config import SEALConfig


logger = logging.getLogger(__name__)


class Phase3Orchestrator:
    """
    Orchestrates the complete Phase 3 continuous evolution system.
    
    Manages the lifecycle of both the evolution service and monitoring dashboard,
    ensuring they work together seamlessly.
    """
    
    def __init__(
        self,
        config_file: Optional[Path] = None,
        dashboard_host: str = "localhost",
        dashboard_port: int = 8080,
        evolution_interval: int = 3600,  # 1 hour
        training_check_interval: int = 1800,  # 30 minutes
        min_evolution_samples: int = 50
    ):
        """
        Initialize the Phase 3 orchestrator.
        
        Args:
            config_file: Path to EVOSEAL configuration file
            dashboard_port: Port for monitoring dashboard
            evolution_interval: Seconds between evolution cycles
            training_check_interval: Seconds between training checks
            min_evolution_samples: Minimum samples for training
        """
        # Load configuration
        self.config = SEALConfig()
        if config_file and config_file.exists():
            # Load custom config if provided
            logger.info(f"Loading config from {config_file}")
        
        # Initialize services
        self.evolution_service = ContinuousEvolutionService(
            config=self.config,
            evolution_interval=evolution_interval,
            training_check_interval=training_check_interval,
            min_evolution_samples=min_evolution_samples
        )
        
        self.dashboard = MonitoringDashboard(
            evolution_service=self.evolution_service,
            host=dashboard_host,
            port=dashboard_port
        )
        
        # Orchestrator state
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        logger.info("Phase3Orchestrator initialized")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start(self):
        """Start the complete Phase 3 system."""
        if self.is_running:
            logger.warning("Phase 3 system is already running")
            return
        
        logger.info("🚀 Starting Phase 3: Continuous Evolution System")
        self.is_running = True
        
        try:
            # Start monitoring dashboard first
            logger.info("📊 Starting monitoring dashboard...")
            await self.dashboard.start()
            
            # Start evolution service
            logger.info("🧬 Starting continuous evolution service...")
            evolution_task = asyncio.create_task(self.evolution_service.start())
            
            # Wait for shutdown signal
            logger.info("✅ Phase 3 system fully operational!")
            logger.info(f"🌐 Dashboard: http://localhost:{self.dashboard.port}")
            logger.info("🔄 Continuous evolution active")
            
            await self.shutdown_event.wait()
            
            # Cancel evolution service
            evolution_task.cancel()
            try:
                await evolution_task
            except asyncio.CancelledError:
                pass
                
        except Exception as e:
            logger.error(f"Error in Phase 3 system: {e}")
            raise
        finally:
            await self._cleanup()
    
    async def shutdown(self):
        """Gracefully shutdown the Phase 3 system."""
        logger.info("🛑 Shutting down Phase 3 system...")
        self.is_running = False
        self.shutdown_event.set()
        
        # Shutdown services
        try:
            await self.evolution_service.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down evolution service: {e}")
        
        try:
            await self.dashboard.stop()
        except Exception as e:
            logger.error(f"Error shutting down dashboard: {e}")
    
    async def _cleanup(self):
        """Cleanup resources."""
        logger.info("🧹 Cleaning up Phase 3 resources...")
        # Add any additional cleanup here
    
    def get_system_status(self) -> dict:
        """Get overall system status."""
        return {
            "phase3_orchestrator": {
                "is_running": self.is_running,
                "evolution_service_running": self.evolution_service.is_running,
                "dashboard_running": self.dashboard.is_running
            },
            "evolution_service": self.evolution_service.get_service_status(),
            "dashboard_port": self.dashboard.port
        }


async def run_health_check():
    """Run a health check of the Phase 3 system."""
    logger.info("🔍 Running Phase 3 health check...")
    
    try:
        # Check if required dependencies are available
        logger.info("Checking dependencies...")
        
        # Check Ollama connection
        import aiohttp
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get('http://localhost:11434/api/tags', timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [model['name'] for model in data.get('models', [])]
                        if 'devstral:latest' in models:
                            logger.info("✅ Ollama and Devstral model available")
                        else:
                            logger.warning("⚠️ Devstral model not found in Ollama")
                    else:
                        logger.warning("⚠️ Ollama API not responding correctly")
            except Exception as e:
                logger.error(f"❌ Ollama connection failed: {e}")
                return False
        
        # Check Phase 1 and Phase 2 components
        try:
            from evoseal.evolution import EvolutionDataCollector
            from evoseal.fine_tuning import (
                DevstralFineTuner, TrainingManager, ModelValidator,
                ModelVersionManager, BidirectionalEvolutionManager
            )
            logger.info("✅ All Phase 1 and Phase 2 components available")
        except ImportError as e:
            logger.error(f"❌ Missing components: {e}")
            return False
        
        # Check data directories
        data_dir = Path("data/continuous_evolution")
        if not data_dir.exists():
            data_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Created data directory: {data_dir}")
        else:
            logger.info(f"✅ Data directory exists: {data_dir}")
        
        logger.info("🎉 Health check passed! Phase 3 system ready to start.")
        return True
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return False


async def main():
    """Main entry point for Phase 3 system."""
    parser = argparse.ArgumentParser(description="EVOSEAL Phase 3: Continuous Evolution System")
    parser.add_argument("--config", type=Path, help="Path to configuration file")
    parser.add_argument("--host", type=str, default="localhost", help="Dashboard host address (default: localhost)")
    parser.add_argument("--port", type=int, default=8080, help="Dashboard port (default: 8080)")
    parser.add_argument("--evolution-interval", type=int, default=3600, 
                       help="Evolution check interval in seconds (default: 3600)")
    parser.add_argument("--training-interval", type=int, default=1800,
                       help="Training check interval in seconds (default: 1800)")
    parser.add_argument("--min-samples", type=int, default=50,
                       help="Minimum evolution samples for training (default: 50)")
    parser.add_argument("--health-check", action="store_true",
                       help="Run health check only")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('phase3_continuous_evolution.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger.info("🧬 EVOSEAL Phase 3: Continuous Evolution System")
    logger.info("=" * 60)
    
    # Run health check if requested
    if args.health_check:
        success = await run_health_check()
        sys.exit(0 if success else 1)
    
    # Run health check before starting
    logger.info("Running pre-start health check...")
    if not await run_health_check():
        logger.error("Health check failed. Please resolve issues before starting.")
        sys.exit(1)
    
    # Create and start orchestrator
    orchestrator = Phase3Orchestrator(
        config_file=args.config,
        dashboard_host=args.host,
        dashboard_port=args.port,
        evolution_interval=args.evolution_interval,
        training_check_interval=args.training_interval,
        min_evolution_samples=args.min_samples
    )
    
    try:
        await orchestrator.start()
    except KeyboardInterrupt:
        logger.info("System interrupted by user")
    except Exception as e:
        logger.error(f"System failed: {e}")
        sys.exit(1)
    
    logger.info("🎉 Phase 3 system shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
