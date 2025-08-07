#!/usr/bin/env python3
"""
DEPRECATED: This script has been moved to scripts/lib/release/generate_evolution_notes.py

Please update your scripts to use the new location:
  ./scripts/evoseal release generate-notes --help

This file is kept for backward compatibility and will be removed in a future release.
"""

import os
import sys


def main():
    print("This script has been moved to scripts/lib/release/generate_evolution_notes.py")
    print("Please update your scripts to use the new location or run:")
    print("  ./scripts/evoseal release generate-notes --help")
    sys.exit(1)


if __name__ == "__main__":
    main()
