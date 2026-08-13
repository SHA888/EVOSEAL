# EVOSEAL Setup Guide

This guide will help you set up the EVOSEAL development environment.

## Prerequisites

- Python 3.9 or higher
- Git
- pip (Python package installer)
- [Ollama](https://ollama.com/download) (optional — for local model inference without API keys)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone --recurse-submodules git@github.com:SHA888/EVOSEAL.git
   cd EVOSEAL
   ```

2. **Set up the development environment**
   ```bash
   # Make the setup script executable
   chmod +x scripts/setup.sh

   # Run the setup script
   ./scripts/setup.sh
   ```
   This will:
   - Create a Python virtual environment
   - Install all dependencies
   - Set up Git hooks
   - Create a `.env` file from the example

3. **Activate the virtual environment**
   ```bash
   source .venv/bin/activate
   ```

4. **Configure environment variables**
   Edit the `.env` file with your API keys and configuration:
   ```bash
   cp .env.example .env
   nano .env  # or use your preferred editor
   ```

## Local Models (Ollama)

The prompt-level co-evolution path can run entirely on local models via
[Ollama](https://ollama.com/), with no API keys or GPU required. Two models take
distinct roles in the co-evolution loop:

| Role       | Preferred family         | Purpose                          |
|------------|--------------------------|----------------------------------|
| `coder`    | DeepSeek-Coder-V2-Lite   | Writes code for a task           |
| `reviewer` | Qwen2.5-Coder            | Reviews and scores the output    |

Models are **auto-discovered** from what is installed in Ollama and matched by
family (case-insensitive substring). If you pull a different model from a
compatible family, EVOSEAL will find it automatically. When multiple installed
models match the same family, the **first** one returned by Ollama's list API is
used; if that isn't what you want, set an explicit override (see below) to pin
the exact tag. Models from unrelated families (e.g. `codellama`) require an
explicit override.

### Setup

1. **Install Ollama** (https://ollama.com/download) and verify it is running:
   ```bash
   ollama --version
   curl -s http://localhost:11434/api/tags
   ```
   If the `curl` command fails or returns empty, Ollama is not running. Start it
   with `ollama serve` (or launch the Ollama desktop app) and try again.

2. **Pull the default models**:
   ```bash
   ollama pull deepseek-coder-v2:16b-lite-instruct-q8_0
   ollama pull qwen2.5-coder:7b-instruct-q6_K
   ```
   These are quantised to run on CPU. Smaller alternatives also work — EVOSEAL
   discovers whatever is installed.

3. **Override a role** (optional):
   ```bash
   export EVOSEAL_CODER_MODEL="codellama:13b"
   export EVOSEAL_REVIEWER_MODEL="qwen2.5-coder:3b"
   ```

4. **Verify the provider unit tests** (these stub the Ollama HTTP layer — no
   running Ollama instance required):
   ```bash
   pytest tests/unit/providers/test_local_models.py tests/unit/providers/test_ollama_provider.py -v
   ```

   > **Note:** These tests validate the discovery, matching, and fallback logic
   > against a mocked Ollama API. They do **not** prove that a real Ollama
   > instance is running and serving models. Live end-to-end verification
   > (pull a model, run a co-evolution generation, confirm output) is a
   > separate step — see TODO.md for tracking.

For the architecture behind prompt-level co-evolution with local models, see
[`docs/architecture/local_coevolution.md`](../architecture/local_coevolution.md).

## Project Structure

```
evo-seal/
├── .github/                 # GitHub workflows and templates
├── config/                  # Configuration files
├── data/                    # Data files
├── docs/                    # Documentation
├── evoseal/                 # Main package
│   ├── core/                # Core functionality
│   ├── integration/         # Integration with DGM, OpenEvolve, SEAL (Self-Adapting Language Models)
│   └── utils/               # Utility functions
├── logs/                    # Log files
├── notebooks/               # Jupyter notebooks
├── scripts/                 # Utility scripts
├── tests/                   # Test suite
├── .env.example            # Example environment variables
├── .gitignore              # Git ignore rules
├── pyproject.toml          # Python project configuration
├── README.md               # Project documentation
└── requirements/           # Dependency files
    ├── base.txt           # Core dependencies
    ├── dev.txt            # Development dependencies
    └── test.txt           # Test dependencies
```

## Development Workflow

1. **Activate the virtual environment**
   ```bash
   source .venv/bin/activate
   ```

2. **Run tests**
   ```bash
   pytest
   ```

3. **Run code quality checks**
   ```bash
   black .
   isort .
   flake8
   mypy .
   ```

4. **Run the linter and formatter automatically before commit**
   ```bash
   pre-commit install
   ```

## Contributing

1. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit them:
   ```bash
   git add .
   git commit -m "Your commit message"
   ```

3. Push your changes to the remote repository:
   ```bash
   git push -u origin feature/your-feature-name
   ```

4. Create a pull request on GitHub.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
