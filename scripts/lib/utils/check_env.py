#!/usr/bin/env python3
"""
Environment validation script for EVOSEAL.
Checks for required environment variables and dependencies.
"""

import logging
import os
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def setup_default_environment():
    """Set up default environment variables if they don't exist."""
    # Set default values based on the current directory
    default_home = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    defaults = {
        "PYTHONPATH": f"{default_home}:{default_home}/SEAL",
        "EVOSEAL_HOME": default_home,
        "EVOSEAL_VENV": os.path.join(default_home, ".venv"),
        "EVOSEAL_LOGS": os.path.join(default_home, "logs"),
        "EVOSEAL_DATA": os.path.join(default_home, "data"),
    }

    # Set defaults if not already set
    for key, value in defaults.items():
        if key not in os.environ:
            os.environ[key] = value
            logger.warning(f"⚠️  Using default {key}={value}")

    # Ensure directories exist
    for dir_path in [os.environ["EVOSEAL_LOGS"], os.environ["EVOSEAL_DATA"]]:
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"📁 Ensured directory exists: {dir_path}")


def check_environment():
    """Check the environment for required configuration."""
    logger.info("🔍 Validating environment configuration...")

    # Set up default environment
    setup_default_environment()

    # Check Python version
    if sys.version_info < (3, 8):
        logger.error("❌ Python 3.8 or higher is required")
        return False

    logger.info("✅ Environment validation passed")
    return True


if __name__ == "__main__":
    if not check_environment():
        sys.exit(1)
