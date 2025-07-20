# EVOSEAL Setup Guide

This guide will help you set up the EVOSEAL development environment.

## Prerequisites

- Python 3.9 or higher
- Git
- pip (Python package installer)

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

## Project Structure

```
evo-seal/
├── .github/                 # GitHub workflows and templates
├── config/                  # Configuration files
├── data/                    # Data files
├── docs/                    # Documentation
├── evoseal/                 # Main package
│   ├── core/                # Core functionality
│   ├── integration/         # Integration with DGM, OpenEvolve, SEAL
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
