#!/bin/bash

# Exit on error and print commands
set -ex

# Activate virtual environment
source .venv/bin/activate

# Update pip to the latest version (with security fixes)
python -m pip install --upgrade pip==25.1.1

# Install the pinned requirements
echo "Installing pinned requirements..."
pip install -r requirements/pinned_requirements.txt

# Install the pinned development requirements
echo "Installing pinned development requirements..."
pip install -r requirements/pinned_dev_requirements.txt

# Install security tools with compatible versions
echo "Installing security tools..."
pip install -r requirements/security.txt

# Update the main requirements files
echo "Updating main requirements files..."
cp requirements/pinned_requirements.txt requirements/base.txt
cp requirements/pinned_dev_requirements.txt requirements/dev.txt

# Create a backup of the original security.txt if it exists and is different
if [ -f "requirements/security.txt" ] && ! cmp -s "requirements/security.txt" "requirements/security.txt.bak" 2>/dev/null; then
    cp requirements/security.txt "requirements/security.txt.bak"
fi

# Verify all dependencies are compatible
echo "Verifying dependencies..."
if ! pip check; then
    echo "⚠️  Some dependencies have compatibility issues. Please review the output above."
    exit 1
fi

echo "✅ Dependencies updated successfully!"
echo "All dependencies are now pinned to specific versions for security and stability."
echo "To update a specific package in the future, update the pinned version in the appropriate requirements file."
