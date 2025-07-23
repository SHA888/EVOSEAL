#!/usr/bin/env python3
"""
Cleanup script for EVOSEAL metrics and release files.

This script:
1. Archives old metrics files (keeping only the last N per version)
2. Removes duplicate or temporary release notes
3. Maintains a clean directory structure
"""
import os
import shutil
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
METRICS_DIR = Path("metrics")
RELEASES_DIR = Path("releases")
ARCHIVE_DIR = Path("archived_metrics")
KEEP_LAST_N = 3  # Number of metrics files to keep per version
KEEP_DAYS = 30   # Keep files newer than this many days

def parse_version_timestamp(filename: str) -> Optional[tuple]:
    """Parse version and timestamp from filename."""
    if not filename.startswith("evolution_") or not filename.endswith(".json"):
        return None
    
    try:
        # Handle both formats: evolution_X.Y.Z_*.json and evolution_vX.Y.Z.json
        if filename.startswith("evolution_v"):
            version = filename[10:-5]  # Remove 'evolution_' and '.json'
            return (version, 0)  # No timestamp in this format
        else:
            parts = filename[9:-5].split("_")  # Remove 'evolution_' and '.json'
            version = parts[0]
            timestamp = int("".join(filter(str.isdigit, "_".join(parts[1:]))))
            return (version, timestamp)
    except (IndexError, ValueError):
        return None

def cleanup_metrics():
    """Clean up metrics files, keeping only the most recent N per version."""
    # Create archive directory if it doesn't exist
    ARCHIVE_DIR.mkdir(exist_ok=True)
    
    # Group files by version
    version_files: Dict[str, List[Path]] = {}
    
    for file in METRICS_DIR.glob("evolution_*.json"):
        parsed = parse_version_timestamp(file.name)
        if parsed:
            version, timestamp = parsed
            version_files.setdefault(version, []).append((timestamp, file))
    
    # Keep only the last N files per version and archive the rest
    for version, files in version_files.items():
        # Sort by timestamp (newest first)
        files.sort(reverse=True)
        
        # Keep the most recent N files
        for i, (timestamp, file) in enumerate(files):
            if i >= KEEP_LAST_N:
                # Move to archive
                archive_path = ARCHIVE_DIR / f"{file.stem}_{timestamp}.json"
                shutil.move(str(file), str(archive_path))
                print(f"Archived: {file.name} -> {archive_path}")


def cleanup_release_notes():
    """Clean up duplicate or temporary release notes."""
    # Keep only the most recent release notes in the root releases directory
    for file in RELEASES_DIR.glob("release_notes_*.md"):
        version = file.stem.split("_")[-1]
        version_dir = RELEASES_DIR / version
        
        # If there's a version-specific directory, move the file there
        if version_dir.exists():
            target = version_dir / "RELEASE_NOTES.md"
            if not target.exists():
                shutil.move(str(file), str(target))
                print(f"Moved to version dir: {file.name} -> {target}")
            else:
                # Remove duplicate
                file.unlink()
                print(f"Removed duplicate: {file.name}")


def cleanup_old_files():
    """Remove files older than KEEP_DAYS from the archive."""
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    
    for file in ARCHIVE_DIR.glob("*.json"):
        mtime = datetime.fromtimestamp(file.stat().st_mtime)
        if mtime < cutoff:
            file.unlink()
            print(f"Removed old file: {file.name}")

def cleanup_release_directories():
    """Clean up old release directories, keeping only the last N versions."""
    KEEP_LAST_VERSIONS = 5  # Number of most recent versions to keep
    
    # Get all version directories and sort them by version
    version_dirs = []
    for d in RELEASES_DIR.iterdir():
        if not d.is_dir():
            continue
            
        # Handle both vX.Y.Z and X.Y.Z formats
        version_str = d.name[1:] if d.name.startswith('v') else d.name
        try:
            version = tuple(map(int, version_str.split('.')))
            version_dirs.append((version, d))
        except (ValueError, AttributeError):
            continue
    
    # Sort by version (newest first)
    version_dirs.sort(reverse=True, key=lambda x: x[0])
    
    # Keep only the last N versions
    for version, dir_path in version_dirs[KEEP_LAST_VERSIONS:]:
        # Archive the directory
        archive_path = ARCHIVE_DIR / f"release_{'.'.join(map(str, version))}"
        if archive_path.exists():
            shutil.rmtree(str(archive_path))
        shutil.move(str(dir_path), str(archive_path))
        print(f"Archived old release: {dir_path.name} -> {archive_path}")
        
        # Remove any corresponding release notes in the root
        release_note = RELEASES_DIR / f"release_notes_{'.'.join(map(str, version))}.md"
        if release_note.exists():
            release_note.unlink()
            print(f"Removed old release note: {release_note.name}")


def main():
    print("Starting EVOSEAL cleanup...")
    
    # Run cleanup tasks
    cleanup_metrics()
    cleanup_release_notes()
    cleanup_old_files()
    cleanup_release_directories()
    
    print("Cleanup complete!")


if __name__ == "__main__":
    main()
