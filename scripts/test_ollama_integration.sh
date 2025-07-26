#!/bin/bash

# Test script for EVOSEAL Ollama integration
# Tests the OllamaProvider functionality

set -e

# Source the logging utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_logging.sh"

# Set up environment
EVOSEAL_ROOT="${EVOSEAL_ROOT:-$(dirname "$SCRIPT_DIR")}"
EVOSEAL_VENV="${EVOSEAL_VENV:-$EVOSEAL_ROOT/venv}"

log_info "Starting EVOSEAL Ollama integration test..."

# Check if Ollama is running
log_info "Checking Ollama status..."
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    log_error "Ollama is not running or not accessible at localhost:11434"
    log_info "Please start Ollama with: ollama serve"
    exit 1
fi

# Get available models
log_info "Available Ollama models:"
curl -s http://localhost:11434/api/tags | python3 -m json.tool | grep '"name"' | sed 's/.*"name": "\([^"]*\)".*/  - \1/'

# Activate virtual environment
if [[ -f "$EVOSEAL_VENV/bin/activate" ]]; then
    log_info "Activating EVOSEAL virtual environment..."
    source "$EVOSEAL_VENV/bin/activate"
else
    log_warn "Virtual environment not found at $EVOSEAL_VENV"
fi

# Create a simple test script
TEST_SCRIPT="$EVOSEAL_ROOT/test_ollama_provider.py"
cat > "$TEST_SCRIPT" << 'EOF'
#!/usr/bin/env python3
"""
Test script for EVOSEAL Ollama integration.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add EVOSEAL to path
sys.path.insert(0, str(Path(__file__).parent))

from evoseal.providers.ollama_provider import OllamaProvider

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_ollama_provider():
    """Test the Ollama provider functionality."""
    
    # Initialize provider with reasonable timeout
    provider = OllamaProvider(model="devstral:latest", timeout=90)
    
    # Test health check
    logger.info("Testing Ollama health check...")
    is_healthy = await provider.health_check()
    if not is_healthy:
        logger.error("Ollama health check failed!")
        return False
    
    logger.info("✅ Ollama health check passed")
    
    # Test model info
    model_info = provider.get_model_info()
    logger.info(f"Model info: {model_info}")
    
    # Test simple prompt
    logger.info("Testing simple prompt...")
    test_prompt = "Write a Python function to add two numbers."
    
    try:
        response = await provider.submit_prompt(test_prompt)
        logger.info(f"✅ Received response ({len(response)} characters)")
        
        # Parse response
        parsed = await provider.parse_response(response)
        logger.info(f"✅ Response parsed successfully")
        logger.info(f"Contains code: {parsed.get('contains_code', False)}")
        logger.info(f"Code blocks found: {len(parsed.get('code_blocks', []))}")
        
        # Show first 200 characters of response
        preview = response[:200] + "..." if len(response) > 200 else response
        logger.info(f"Response preview: {preview}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing prompt: {e}")
        return False

async def test_code_generation():
    """Test code generation capabilities."""
    
    provider = OllamaProvider(model="devstral:latest", timeout=90)
    
    logger.info("Testing code generation...")
    
    code_prompt = "Create a simple Python class with an __init__ method and one other method."
    
    try:
        response = await provider.submit_prompt(
            code_prompt,
            temperature=0.3,  # Lower temperature for more consistent code
            max_tokens=1500
        )
        
        parsed = await provider.parse_response(response)
        
        logger.info(f"✅ Code generation completed")
        logger.info(f"Response length: {len(response)} characters")
        logger.info(f"Contains code blocks: {len(parsed.get('code_blocks', []))}")
        
        # Save the generated code for review
        with open("/tmp/generated_code.py", "w") as f:
            f.write(response)
        logger.info("Generated code saved to /tmp/generated_code.py")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in code generation test: {e}")
        return False

async def main():
    """Run all tests."""
    logger.info("🚀 Starting EVOSEAL Ollama Provider Tests")
    
    tests = [
        ("Basic Provider Test", test_ollama_provider),
        ("Code Generation Test", test_code_generation),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} ---")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n=== Test Results ===")
    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        logger.info("🎉 All tests passed! Ollama integration is working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Check the logs above for details.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
EOF

# Run the test
log_info "Running Ollama provider tests..."
cd "$EVOSEAL_ROOT"

if python3 "$TEST_SCRIPT"; then
    log_info "✅ Ollama integration tests passed!"
    
    # Clean up test script
    rm -f "$TEST_SCRIPT"
    
    log_info "Next steps:"
    log_info "1. Update EVOSEAL configuration to use Ollama provider"
    log_info "2. Test integration with evolution cycles"
    log_info "3. Configure provider selection in EVOSEAL settings"
    
else
    log_error "❌ Ollama integration tests failed"
    log_info "Test script saved at: $TEST_SCRIPT"
    log_info "Check the output above for error details"
    exit 1
fi

log_info "Ollama integration test completed successfully!"
