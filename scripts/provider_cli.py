#!/usr/bin/env python3
"""
CLI tool for managing EVOSEAL providers.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add EVOSEAL to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evoseal.providers import provider_manager


async def list_providers():
    """List all available providers."""
    print("📋 EVOSEAL Provider Status:")
    print("=" * 50)
    
    provider_info = provider_manager.list_providers()
    
    for name, info in provider_info.items():
        status_icon = "✅" if info["enabled"] and info["available"] else "❌"
        print(f"\n{status_icon} {name.upper()}")
        print(f"   Enabled: {info['enabled']}")
        print(f"   Available: {info['available']}")
        print(f"   Priority: {info['priority']}")
        print(f"   Initialized: {info['initialized']}")
        
        if "healthy" in info:
            health_icon = "💚" if info["healthy"] else "💔"
            print(f"   Health: {health_icon} {'Healthy' if info['healthy'] else 'Unhealthy'}")
            
        if "health_error" in info:
            print(f"   Error: {info['health_error']}")
            
        if "health_note" in info:
            print(f"   Note: {info['health_note']}")
        
        if info["config"]:
            print(f"   Config: {json.dumps(info['config'], indent=6)}")


async def test_provider(provider_name=None):
    """Test a specific provider or the best available one."""
    try:
        if provider_name:
            print(f"🧪 Testing provider: {provider_name}")
            provider = provider_manager.get_provider(provider_name)
        else:
            print("🧪 Testing best available provider...")
            provider = provider_manager.get_best_available_provider()
            provider_name = type(provider).__name__
        
        print(f"✅ Using provider: {provider_name}")
        
        # Test simple prompt
        test_prompt = "Hello! Can you write a simple Python function?"
        print(f"📝 Sending test prompt: '{test_prompt}'")
        
        response = await provider.submit_prompt(test_prompt)
        print(f"✅ Response received ({len(response)} characters)")
        print(f"📄 Response preview:")
        print("-" * 40)
        print(response[:300] + "..." if len(response) > 300 else response)
        print("-" * 40)
        
        # Parse response
        parsed = await provider.parse_response(response)
        print(f"📊 Parsed response info:")
        print(f"   Contains code: {parsed.get('contains_code', False)}")
        print(f"   Code blocks: {len(parsed.get('code_blocks', []))}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True


async def health_check(provider_name=None):
    """Check health of a specific provider or all providers."""
    if provider_name:
        try:
            provider = provider_manager.get_provider(provider_name)
            if hasattr(provider, 'health_check'):
                print(f"🏥 Checking health of {provider_name}...")
                is_healthy = await provider.health_check()
                status = "✅ Healthy" if is_healthy else "❌ Unhealthy"
                print(f"Result: {status}")
            else:
                print(f"ℹ️ Provider {provider_name} doesn't support health checks")
        except Exception as e:
            print(f"❌ Health check failed: {e}")
    else:
        print("🏥 Checking health of all providers...")
        await list_providers()  # This includes health info


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="EVOSEAL Provider Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # List command
    subparsers.add_parser("list", help="List all providers")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test a provider")
    test_parser.add_argument("--provider", "-p", help="Provider name to test")
    
    # Health command
    health_parser = subparsers.add_parser("health", help="Check provider health")
    health_parser.add_argument("--provider", "-p", help="Provider name to check")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "list":
            asyncio.run(list_providers())
        elif args.command == "test":
            asyncio.run(test_provider(args.provider))
        elif args.command == "health":
            asyncio.run(health_check(args.provider))
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
