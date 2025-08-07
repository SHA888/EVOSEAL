#!/bin/bash

# Test script for EVOSEAL Provider Manager
# Tests provider configuration, selection, and management

set -e

# Source the logging utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/utils/_logging.sh"

# Set up environment
EVOSEAL_ROOT="${EVOSEAL_ROOT:-$(dirname "$SCRIPT_DIR")}"
EVOSEAL_VENV="${EVOSEAL_VENV:-$EVOSEAL_ROOT/venv}"

log_info "Starting EVOSEAL Provider Manager test..."

# Check if Ollama is running
log_info "Checking Ollama status..."
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    log_warn "Ollama is not running - some tests may fail"
else
    log_info "✅ Ollama is accessible"
fi

# Activate virtual environment if available
if [[ -f "$EVOSEAL_VENV/bin/activate" ]]; then
    log_info "Activating EVOSEAL virtual environment..."
    source "$EVOSEAL_VENV/bin/activate"
else
    log_warn "Virtual environment not found at $EVOSEAL_VENV"
fi

# Create test script
TEST_SCRIPT="$EVOSEAL_ROOT/test_provider_manager.py"
cat > "$TEST_SCRIPT" << 'EOF'
#!/usr/bin/env python3
"""
Test script for EVOSEAL Provider Manager.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add EVOSEAL to path
sys.path.insert(0, str(Path(__file__).parent))

from evoseal.providers import provider_manager
from config.settings import settings

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_configuration():
    """Test provider configuration loading."""
    logger.info("Testing provider configuration...")

    # Check SEAL configuration
    seal_config = settings.seal
    logger.info(f"SEAL enabled: {seal_config.enabled}")
    logger.info(f"Default provider: {seal_config.default_provider}")
    logger.info(f"Configured providers: {list(seal_config.providers.keys())}")

    # Check provider details
    for name, config in seal_config.providers.items():
        logger.info(f"Provider {name}: enabled={config.enabled}, priority={config.priority}")
        logger.info(f"  Config: {config.config}")

    return True

async def test_provider_listing():
    """Test provider listing functionality."""
    logger.info("Testing provider listing...")

    provider_info = provider_manager.list_providers()

    for name, info in provider_info.items():
        status = "✅" if info["enabled"] and info["available"] else "❌"
        logger.info(f"{status} Provider {name}:")
        logger.info(f"  Enabled: {info['enabled']}")
        logger.info(f"  Available: {info['available']}")
        logger.info(f"  Priority: {info['priority']}")
        logger.info(f"  Initialized: {info['initialized']}")
        if "healthy" in info:
            health_status = "✅ Healthy" if info["healthy"] else "❌ Unhealthy"
            logger.info(f"  Health: {health_status}")

    return True

async def test_provider_selection():
    """Test provider selection and instantiation."""
    logger.info("Testing provider selection...")

    try:
        # Test getting default provider
        logger.info("Getting default provider...")
        default_provider = provider_manager.get_provider()
        logger.info(f"✅ Default provider: {type(default_provider).__name__}")

        # Test getting specific provider
        logger.info("Getting Ollama provider...")
        ollama_provider = provider_manager.get_provider("ollama")
        logger.info(f"✅ Ollama provider: {type(ollama_provider).__name__}")

        # Test provider health if available
        if hasattr(ollama_provider, 'health_check'):
            logger.info("Testing Ollama provider health...")
            is_healthy = await ollama_provider.health_check()
            health_status = "✅ Healthy" if is_healthy else "❌ Unhealthy"
            logger.info(f"Ollama health: {health_status}")

        return True

    except Exception as e:
        logger.error(f"❌ Provider selection failed: {e}")
        return False

async def test_best_provider_selection():
    """Test best available provider selection."""
    logger.info("Testing best provider selection...")

    try:
        best_provider = provider_manager.get_best_available_provider()
        logger.info(f"✅ Best provider: {type(best_provider).__name__}")

        # Test a simple prompt with the best provider
        logger.info("Testing simple prompt with best provider...")
        response = await best_provider.submit_prompt("Hello, test!")
        logger.info(f"✅ Response received ({len(response)} chars)")
        logger.info(f"Response preview: {response[:100]}...")

        return True

    except Exception as e:
        logger.error(f"❌ Best provider selection failed: {e}")
        return False

async def test_provider_fallback():
    """Test provider fallback functionality."""
    logger.info("Testing provider fallback...")

    # Temporarily disable high-priority provider to test fallback
    original_providers = settings.seal.providers.copy()

    try:
        # Disable Ollama temporarily
        if "ollama" in settings.seal.providers:
            settings.seal.providers["ollama"].enabled = False
            provider_manager.reload_providers()

            logger.info("Disabled Ollama provider, testing fallback...")
            fallback_provider = provider_manager.get_best_available_provider()
            logger.info(f"✅ Fallback provider: {type(fallback_provider).__name__}")

            return True

    except Exception as e:
        logger.error(f"❌ Provider fallback test failed: {e}")
        return False
    finally:
        # Restore original configuration
        settings.seal.providers.update(original_providers)
        provider_manager.reload_providers()
        logger.info("Restored original provider configuration")

async def main():
    """Run all tests."""
    logger.info("🚀 Starting EVOSEAL Provider Manager Tests")

    tests = [
        ("Configuration Test", test_configuration),
        ("Provider Listing Test", test_provider_listing),
        ("Provider Selection Test", test_provider_selection),
        ("Best Provider Selection Test", test_best_provider_selection),
        ("Provider Fallback Test", test_provider_fallback),
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
        logger.info("🎉 All tests passed! Provider Manager is working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Check the logs above for details.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
EOF

# Run the test
log_info "Running Provider Manager tests..."
cd "$EVOSEAL_ROOT"

if python3 "$TEST_SCRIPT"; then
    log_info "✅ Provider Manager tests passed!"

    # Clean up test script
    rm -f "$TEST_SCRIPT"

    log_info "Provider Manager is ready for use!"

else
    log_error "❌ Provider Manager tests failed"
    log_info "Test script saved at: $TEST_SCRIPT"
    log_info "Check the output above for error details"
    exit 1
fi

log_info "Provider Manager test completed successfully!"
