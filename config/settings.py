"""
EVOSEAL Configuration Settings

This module contains all the configuration settings for the EVOSEAL project.
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "evoseal.log"))

# DGM Configuration
DGM_CONFIG = {
    "model": "claude-3.5-sonnet",
    "max_iterations": 100,
    "temperature": 0.7,
}

# OpenEvolve Configuration
OPENEVOLVE_CONFIG = {
    "population_size": 50,
    "max_generations": 100,
    "mutation_rate": 0.1,
}

# SEAL Configuration
SEAL_CONFIG = {
    "few_shot_enabled": True,
    "knowledge_base_path": str(BASE_DIR / "data" / "knowledge"),
}

# Integration Settings
INTEGRATION_SETTINGS = {
    "max_retries": 3,
    "timeout_seconds": 30,
}

# Ensure required directories exist
for directory in ["logs", "data/knowledge"]:
    os.makedirs(BASE_DIR / directory, exist_ok=True)
