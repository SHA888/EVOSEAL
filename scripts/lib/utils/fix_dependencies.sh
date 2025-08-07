#!/bin/bash

# Exit on error and print commands
set -ex

# Activate virtual environment
source .venv/bin/activate

# Update pip to the latest version
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Update packaging to a version that satisfies all requirements
echo "Updating packaging..."
pip install --upgrade 'packaging>=23.2,<24.0'

# Update importlib-metadata to a version that satisfies commitizen
echo "Updating importlib-metadata..."
pip install --upgrade 'importlib-metadata>=8.0.0,<9.0.0'

# Update pydantic to a version that works with safety-schemas
echo "Updating pydantic..."
pip install --upgrade 'pydantic>=2.6.0,<2.10.0'

# Update pydantic-core to a compatible version
echo "Updating pydantic-core..."
pip install --upgrade 'pydantic-core>=2.14.0,<2.15.0'

# Reinstall safety with compatible versions
echo "Reinstalling safety with compatible versions..."
pip uninstall -y safety safety-schemas
pip install 'safety>=2.0.0,<3.0.0' 'safety-schemas>=0.1.0,<0.2.0'

# Update Jupyter-related packages to fix security vulnerabilities
echo "Updating Jupyter packages..."
pip install --upgrade \
    'ipython>=8.10.0' \
    'jupyterlab>=4.2.5' \
    'notebook>=7.2.2' \
    'jupyter>=1.0.0' \
    'ipykernel>=6.4.1' \
    'nbconvert>=7.0.0' \
    'nbformat>=5.9.0' \
    'ipywidgets>=8.1.0'

# Update requirements files
echo "Updating requirements files..."
pip freeze > requirements/frozen_requirements_updated.txt

# Verify all dependencies are compatible
echo "Verifying dependencies..."
pip check || (
    echo "⚠️  Some dependencies have compatibility issues. Please review the output above."
    echo "You may need to manually resolve these issues."
    exit 1
)

echo "✅ Dependencies updated successfully!"
echo "Please review the updated requirements in requirements/frozen_requirements_updated.txt"
