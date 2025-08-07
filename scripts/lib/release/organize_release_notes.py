#!/usr/bin/env python3
"""
Organize release notes into their respective version directories.
Moves files from metrics/ to releases/<version>/RELEASE_NOTES.md
"""
import os
import re
import shutil
from pathlib import Path

# Configuration
METRICS_DIR = Path("metrics")
RELEASES_DIR = Path("releases")


def extract_version(filename):
    """Extract version number from filename."""
    match = re.search(r"release_notes_(\d+\.\d+\.\d+)\.md", filename)
    return match.group(1) if match else None


def organize_release_notes():
    """Organize release notes into versioned directories."""
    # Create releases directory if it doesn't exist
    RELEASES_DIR.mkdir(exist_ok=True)

    # Find all release note files in metrics directory
    for note_file in METRICS_DIR.glob("release_notes_*.md"):
        version = extract_version(note_file.name)
        if not version:
            print(f"Skipping invalid filename format: {note_file.name}")
            continue

        # Create version directory if it doesn't exist
        version_dir = RELEASES_DIR / version
        version_dir.mkdir(exist_ok=True)

        # Define target path
        target_path = version_dir / "RELEASE_NOTES.md"

        # Move the file
        shutil.move(str(note_file), str(target_path))
        print(f"Moved: {note_file} -> {target_path}")

        # If there's a corresponding changelog, move it too
        changelog_src = METRICS_DIR / f"changelog_{version}.md"
        if changelog_src.exists():
            changelog_dest = version_dir / "CHANGELOG.md"
            shutil.move(str(changelog_src), str(changelog_dest))
            print(f"Moved: {changelog_src} -> {changelog_dest}")


if __name__ == "__main__":
    print("Organizing release notes...")
    organize_release_notes()
    print("Done!")
