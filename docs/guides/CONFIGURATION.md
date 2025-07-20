# EVOSEAL Configuration Guide

This document describes how to configure the EVOSEAL system for different environments.

## Table of Contents
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Configuration Files](#configuration-files)
- [Component Configuration](#component-configuration)
- [Environment-Specific Settings](#environment-specific-settings)
- [Validation](#validation)
- [Troubleshooting](#troubleshooting)

## Project Structure

EVOSEAL uses a modular architecture with the following key components:

```
EVOSEAL/
├── evoseal/             # Main package
│   ├── core/            # Core framework components
│   │   ├── controller.py
│   │   ├── evaluator.py
│   │   ├── selection.py
│   │   └── version_database.py
│   │
│   ├── integration/     # Integration modules
│   │   ├── dgm/         # Darwin Godel Machine
│   │   ├── openevolve/  # OpenEvolve framework
│   │   └── seal/        # SEAL interface
│   │
│   ├── models/         # Data models and schemas
│   ├── providers/       # AI/ML model providers
│   ├── storage/         # Data persistence
│   ├── utils/           # Utility functions
│   └── examples/        # Example scripts and templates
│       ├── basic/       # Basic usage examples
│       ├── workflows/   # Workflow examples
│       └── templates/   # Project templates
│
├── config/            # Configuration files
│   ├── development.json
│   ├── testing.json
│   └── production.json
│   └── settings.py      # Main configuration module
└── scripts/             # Utility scripts
```

## Environment Variables

EVOSEAL uses environment variables for sensitive or environment-specific configuration:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `ENV` | Current environment (`development`, `testing`, or `production`) | No | `development` |
| `SECRET_KEY` | Secret key for cryptographic operations | Yes | - |
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | No | `INFO` |
| `LOG_FILE` | Path to log file | No | `logs/evoseal.log` |
| `DATABASE_URL` | Database connection URL | No | `sqlite:///evoseal.db` |

## Configuration Files

EVOSEAL supports YAML configuration files in addition to JSON. The recommended approach is to use YAML for main project configuration, as it is more readable and supports comments.

### SystemConfig Model (YAML Support)

The `evoseal.models.system_config.SystemConfig` class provides:
- Loading configuration from YAML: `SystemConfig.from_yaml('path/to/config.yaml')`
- Dot-notation access: `config.get('dgm.max_iterations')`
- Validation of required sections: `dgm`, `openevolve`, `seal`, `integration`

**Example YAML structure:**
```yaml
dgm:
  enabled: true
  max_iterations: 100
openevolve:
  enabled: true
seal:
  enabled: true
integration:
  foo: bar
```

**Example usage:**
```python
from evoseal.models.system_config import SystemConfig
config = SystemConfig.from_yaml('configs/evoseal.yaml')
config.validate()  # Raises if required sections are missing
max_iters = config.get('dgm.max_iterations', 100)
```

### Environment-Specific Configuration

Environment-specific settings are loaded from JSON or YAML files in the `config/` directory:

- `config/development.json` or `.yaml` - Development settings (local development)
- `config/testing.json` or `.yaml` - Testing settings (CI/CD, local testing)
- `config/production.json` or `.yaml` - Production settings

## Component Configuration

### DGM (Darwin Godel Machine)

```json
{
  "dgm": {
    "enabled": true,
    "module_path": "dgm",
    "max_iterations": 100,
    "temperature": 0.7,
    "checkpoint_dir": "checkpoints/dgm"
  }
}
```

### OpenEvolve

```json
{
  "openevolve": {
    "enabled": true,
    "module_path": "openevolve",
    "population_size": 50,
    "max_generations": 100,
    "mutation_rate": 0.1,
    "checkpoint_dir": "checkpoints/openevolve"
  }
}
```

### SEAL (Self-Adapting Language Models)

```json
{
  "seal": {
    "enabled": true,
    "module_path": "SEAL",
    "few_shot_enabled": true,
    "knowledge_base_path": "data/knowledge",
    "max_context_length": 4096,
    "default_model": "gpt-4"
  }
}
```

## Environment Setup

1. **Clone the repository with submodules**:
   ```bash
   git clone --recurse-submodules https://github.com/yourusername/EVOSEAL.git
   cd EVOSEAL
   ```

2. **Set up the development environment**:
   ```bash
   # Run the setup script
   ./scripts/setup.sh

   # Activate the virtual environment
   source .venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. **Configure environment variables** (if needed):
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Validation

To verify your configuration:

```bash
# Check environment configuration
python scripts/check_env.py

# Or run the setup script which includes validation
./scripts/setup.sh
```

## Best Practices

1. **Development vs Production**
   - Use `ENV=development` for local development
   - Set `ENV=production` in production
   - Never commit sensitive data to version control

2. **Logging**
   - Use `DEBUG` level in development
   - Use `WARNING` or higher in production
   - Configure log rotation for production deployments

3. **Security**
   - Never commit `.env` files
   - Use strong secret keys
   - Restrict file permissions on sensitive configuration

## Troubleshooting

### Common Issues

1. **Missing Submodules**
   ```bash
   git submodule update --init --recursive
   ```

2. **Configuration Not Loading**
   - Check the value of `ENV` environment variable
   - Verify JSON syntax in config files
   - Check for typos in variable names

3. **Permission Issues**
   - Ensure the application has write access to log and data directories
   - Check file permissions on configuration files

4. **Module Not Found**
   - Verify the `module_path` in your configuration points to the correct location
   - Ensure submodules are properly initialized

For additional help, please refer to the project documentation or open an issue.
