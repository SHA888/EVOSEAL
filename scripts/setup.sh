#!/bin/bash

# Exit on error
set -e

echo "🚀 Setting up EVOSEAL development environment..."

# Create and activate virtual environment
echo "🔧 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "🔄 Upgrading pip..."
pip install --upgrade pip

# Install development dependencies
echo "📦 Installing development dependencies..."
pip install -e ".[dev]"

# Initialize Git hooks
echo "🔧 Setting up Git hooks..."
pre-commit install

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "ℹ️ Please update the .env file with your configuration"
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs data/knowledge

echo "✨ Setup complete! Activate the virtual environment with 'source venv/bin/activate'"
echo "📝 Don't forget to update your .env file with your API keys and other configuration"
