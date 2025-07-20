"""
Example usage of SEALInterface with DummySEALProvider.
"""

import asyncio

from evoseal.seal_interface import SEALInterface
from evoseal.seal_providers import DummySEALProvider


async def main() -> None:
    provider = DummySEALProvider()
    interface = SEALInterface(provider, rate_limit_per_sec=5.0)
    result = await interface.submit("Hello, SEAL (Self-Adapting Language Models)!")
    print("SEAL (Self-Adapting Language Models) response:", result)


if __name__ == "__main__":
    asyncio.run(main())
