#!/usr/bin/env python3
"""
Environment configuration checker for EVOSEAL.
Verifies that all required environment variables and submodules are properly configured.
"""

import os
import sys
import json
import importlib.util
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

try:
    from pydantic import BaseModel, BaseSettings
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseModel
    BaseSettings = BaseModel  # Fallback to BaseModel if BaseSettings not available

# Define required environment variables by environment
REQUIRED_ENV_VARS = {
    "all": ["ENV", "SECRET_KEY"],
    "development": [],  # Most settings have defaults in development
    "testing": [],
    "production": ["SECRET_KEY", "DATABASE_URL"]  # These should be explicitly set in production
}

# Component configurations to verify
COMPONENTS = ["dgm", "openevolve", "seal"]

# Component modules to check
COMPONENT_MODULES = {
    "dgm": "dgm",
    "openevolve": "openevolve",
    "SEAL": "SEAL"
}

COMPONENT_DESCRIPTIONS = {
    "dgm": "Darwin Godel Machine",
    "openevolve": "OpenEvolve Framework",
    "SEAL": "Self-Adapting Language Models"
}

# Component-specific requirements
COMPONENT_REQUIREMENTS = [
    {
        "module": "dgm",
        "description": COMPONENT_DESCRIPTIONS["dgm"],
        "required_files": ["__init__.py", "DGM_outer.py"]
    },
    {
        "module": "openevolve",
        "description": COMPONENT_DESCRIPTIONS["openevolve"],
        "required_files": ["__init__.py", "controller.py"]
    },
    {
        "module": "SEAL",
        "description": COMPONENT_DESCRIPTIONS["SEAL"],
        "required_files": ["__init__.py", "seal_model.py"]
    }
]

# Add project root and submodules to path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Add submodule directories to Python path
for submodule in ['dgm', 'openevolve', 'SEAL']:
    submodule_path = PROJECT_ROOT / submodule
    if submodule_path.exists() and str(submodule_path) not in sys.path:
        sys.path.insert(0, str(submodule_path))

def verify_submodule(submodule_name: str, module_name: str) -> Dict[str, Any]:
    """Verify a submodule is properly set up."""
    submodule_path = PROJECT_ROOT / submodule_name
    exists = submodule_path.exists() and submodule_path.is_dir()
    
    result = {
        'name': submodule_name,
        'exists': exists,
        'path': str(submodule_path),
        'is_initialized': False,
        'has_init_file': False,
        'import_success': False,
        'import_message': ''
    }
    
    if exists:
        # Check for __init__.py or setup.py to verify it's a Python package
        init_file = submodule_path / '__init__.py'
        setup_file = submodule_path / 'setup.py'
        result['has_init_file'] = init_file.exists() or setup_file.exists()
        
        # Try to import the module
        import_success, import_msg = check_module_import(module_name)
        result['import_success'] = import_success
        result['import_message'] = import_msg
        
        # Check if the submodule is properly initialized
        if (submodule_path / '.git').exists():
            result['is_initialized'] = True
    else:
        result['import_message'] = f"Submodule directory not found at {submodule_path}"
    
    return result

def check_module_path(module_path: str, base_dir: Path) -> Tuple[bool, List[str]]:
    """Check if a module path exists and contains required files.
    
    Returns:
        Tuple of (is_valid, messages) where messages contains any issues found
    """
    messages = []
    
    # Handle absolute and relative paths
    if os.path.isabs(module_path):
        full_path = Path(module_path)
    else:
        full_path = base_dir / module_path
    
    if not full_path.exists():
        return False, [f"Module directory not found: {full_path}"]
    if not full_path.is_dir():
        return False, [f"Path is not a directory: {full_path}"]
    
    return True, []

def check_python_module(module_name: str) -> Tuple[bool, List[str]]:
    """Check if a Python module can be imported."""
    try:
        importlib.import_module(module_name)
        return True, [f"Successfully imported {module_name}"]
    except ImportError as e:
        return False, [f"Failed to import {module_name}: {str(e)}"]
    except Exception as e:
        return False, [f"Error importing {module_name}: {str(e)}"]

def check_module_import(module_name: str) -> Tuple[bool, str]:
    """Check if a module can be imported."""
    try:
        # Special handling for submodules that might have different import paths
        import_map = {
            'dgm': 'dgm',
            'openevolve': 'openevolve',
            'SEAL': 'SEAL'
        }
        
        import_name = import_map.get(module_name, module_name)
        importlib.import_module(import_name)
        return True, f"Successfully imported {import_name}"
    except ImportError as e:
        # Try to provide more helpful error messages
        if 'No module named' in str(e):
            return False, f"Module not found: {module_name}. Make sure the submodule is properly initialized."
        return False, f"Error importing {module_name}: {str(e)}"

def check_environment() -> Tuple[bool, Dict[str, List[str]]]:
    """Check if all required environment variables and module paths are set.
    
    Returns:
        Tuple of (success, results) where results is a dictionary of component names to lists of messages
    """
    results = {}
    all_success = True
    
    # Check environment variables
    env = os.getenv('ENV', 'development')
    results['environment'] = [f"Using environment: {env}"]
    
    # Check required environment variables
    missing_vars = []
    for var in REQUIRED_ENV_VARS[env]:
        if os.getenv(var) is None:
            missing_vars.append(var)
            all_success = False
    
    if missing_vars:
        results['missing_vars'] = [f"Missing required environment variables: {', '.join(missing_vars)}"]
    
    # Check component modules
    for component, module_name in COMPONENT_MODULES.items():
        try:
            # Check if module can be imported
            success, messages = check_python_module(module_name)
            results[component] = messages
            if not success:
                all_success = False
        except Exception as e:
            results[component] = [f"Error checking {component}: {str(e)}"]
            all_success = False
    
    return all_success, results

def generate_env_file() -> str:
    """Generate a sample .env file with all required variables.
    
    Returns:
        str: Contents of the sample .env file
    """
    # Generate a secure random secret key
    try:
        import secrets
        secret_key = secrets.token_hex(32)
    except:
        secret_key = "generate-a-secure-secret-key-here"
    
    lines = [
        "# EVOSEAL Environment Variables",
        "# Copy this file to .env and update the values\n",
        "# Core Settings",
        f"ENV=development  # development, testing, or production",
        f"SECRET_KEY={secret_key}  # Auto-generated secret key\n",
        "# Database Configuration",
        "DATABASE_URL=sqlite:///evoseal.db  # For production, use PostgreSQL: postgresql://user:password@localhost/evoseal\n",
        "# Logging Configuration",
        "LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL",
        "LOG_FILE=logs/evoseal.log\n",
        "# Component Configuration",
        "# ----------------------",
        "# These paths are relative to the project root or can be absolute paths\n",
        "# DGM (Darwin Godel Machine) Configuration",
        "DGM_MODULE_PATH=dgm  # Path to DGM submodule",
        "DGM_CHECKPOINT_DIR=checkpoints/dgm\n",
        "# OpenEvolve Configuration",
        "OPENEVOLVE_MODULE_PATH=openevolve  # Path to OpenEvolve submodule",
        "OPENEVOLVE_CHECKPOINT_DIR=checkpoints/openevolve\n",
        "# SEAL (Self-Adapting Language Models) Configuration",
        "SEAL_MODULE_PATH=SEAL  # Path to SEAL submodule",
        "SEAL_KNOWLEDGE_BASE=data/knowledge",
        "SEAL_MAX_CONTEXT_LENGTH=4096\n",
        "# Optional External Integrations",
        "# -----------------------------\n",
        "# OpenAI/OpenRouter (for SEAL's default model)",
        "# OPENAI_API_KEY=your_openai_api_key_here\n",
        "# Other optional API keys (uncomment and set as needed)",
        "# GOOGLE_API_KEY=your_google_api_key_here",
        "# MISTRAL_API_KEY=your_mistral_key_here",
        "# ANTHROPIC_API_KEY=your_anthropic_key_here",
        "# PERPLEXITY_API_KEY=your_perplexity_key_here\n",
        "# Development Settings (only used when ENV=development)",
        "# ---------------------------------------------------",
        "# DEBUG=True",
        "# TESTING=False\n",
        "# Production Settings (only used when ENV=production)",
        "# -------------------------------------------------",
        "# SECURE_COOKIES=True",
        "# SESSION_COOKIE_SECURE=True",
        "# CSRF_COOKIE_SECURE=True",
        "# LOG_LEVEL=WARNING  # More restrictive logging in production\n",
        "# Testing Settings (only used when ENV=testing)",
        "# -------------------------------------------",
        "# TESTING=True",
        "# DATABASE_URL=sqlite:///:memory:  # Use in-memory database for tests"
    ]
    return "\n".join(lines)

def print_section(title: str, char: str = "=", width: int = 80) -> None:
    """Print a formatted section header."""
    print(f"\n{char * width}")
    print(f"{title.upper():^{width}}")
    print(f"{char * width}")

def print_subsection(title: str, char: str = "-") -> None:
    """Print a formatted subsection header."""
    print(f"\n{title}")
    print(char * len(title))

def print_status(message: str, status: str = "info", indent: int = 3) -> None:
    """Print a status message with appropriate formatting."""
    status_icons = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️ ",
        "info": "ℹ️ "
    }
    icon = status_icons.get(status.lower(), "•")
    print(f"{' ' * indent}{icon} {message}")

def main():
    """Main function to check environment configuration."""
    print("\n" + "=" * 80)
    print(f"{'EVOSEAL ENVIRONMENT CONFIGURATION CHECK':^80}")
    print("=" * 80)
    print("\n🔍 Checking environment configuration...\n")
    
    success, results = check_environment()
    
    # Print environment variables section
    print("=" * 80)
    print(f"{'ENVIRONMENT VARIABLES':^80}")
    print("=" * 80)
    
    if 'missing_vars' in results:
        print("\nMissing Required Variables")
        print("-" * 35)
        for var in results['missing_vars']:
            print(f"   ❌ {var}")
    
    # Print component status section
    print("\n" + "=" * 80)
    print(f"{'COMPONENT STATUS':^80}")
    print("=" * 80)
    
    component_results = {k: v for k, v in results.items() 
                         if k not in ['environment', 'missing_vars']}
    
    if not component_results:
        print("\nNo component checks were performed.")
    else:
        for component, messages in component_results.items():
            print(f"\n{component.upper()}")
            print("-" * len(component) + "-" * 2)
            for msg in messages:
                status = "✅" if "Successfully" in msg else "❌"
                print(f"   {status} {msg}")
    
    # Print summary section
    print("\n" + "=" * 80)
    print(f"{'SUMMARY':^80}")
    print("=" * 80)
    
    if success:
        print("\n✅ All environment checks passed!")
    else:
        print("\n❌ Some configuration issues need to be addressed:")
        
        if 'missing_vars' in results:
            print("\n  To fix missing environment variables:")
            print("  1. Edit the .env file or set the variables in your shell")
            print("  2. For sensitive values, ensure they are properly secured")
        
        # Only show component fix instructions if there are component checks
        if any(k not in ['environment', 'missing_vars'] for k in results):
            print("\n  To fix component issues:")
            print("  1. Initialize submodules if not already done:")
            print("     git submodule update --init --recursive")
            print("  2. Install required dependencies:")
            print("     pip install -r requirements.txt")
    
    print("\n  After making changes, run this script again to verify your configuration.")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    sys.exit(main())
