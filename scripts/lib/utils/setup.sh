#!/bin/bash

# Exit on error
set -e

echo "🚀 Setting up EVOSEAL development environment..."

# Initialize and update Git submodules
echo "🔧 Initializing Git submodules..."
git submodule update --init --recursive

# Create and activate virtual environment
echo "🔧 Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
echo "🔄 Upgrading pip..."
pip install --upgrade pip

# Install development dependencies
echo "📦 Installing development dependencies..."
pip install -e ".[dev]"

# Initialize Git hooks
echo "🔧 Setting up Git hooks..."
pre-commit install

# Create required directories
echo "📂 Creating required directories..."
mkdir -p logs data/knowledge checkpoints/openevolve

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Please edit the .env file with your configuration"
    echo "   You can generate a secure SECRET_KEY with: openssl rand -hex 32"
    echo ""
    read -p "Would you like to open the .env file for editing now? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} .env
    fi
fi

# Check environment configuration
echo "🔍 Validating environment configuration..."
python scripts/check_env.py || {
    echo ""
    echo "❌ Some required configuration is missing. Please fix the issues above."
    echo "   Edit the .env file and run this script again."
    exit 1
}

echo ""
echo "✅ Environment setup complete!"

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs data/knowledge

echo "✨ Setup complete! Activate the virtual environment with 'source .venv/bin/activate'"
echo "📝 Don't forget to update your .env file with your API keys and other configuration"
