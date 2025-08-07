#!/usr/bin/env python3
"""
Generate release notes and changelog excerpts based on evolution metrics and git history.
"""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml


def get_git_changes(since_tag: str) -> List[Dict]:
    """Get commit history since the last release."""
    cmd = [
        "git",
        "log",
        f"{since_tag}..HEAD",
        "--pretty=format:%H|%an|%ad|%s",
        "--date=short",
        "--no-merges",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    changes = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        commit_hash, author, date, message = line.split("|", 3)
        changes.append({"hash": commit_hash, "author": author, "date": date, "message": message})
    return changes


def load_evolution_metrics() -> Dict:
    """Load evolution metrics from the metrics directory."""
    metrics_dir = Path("metrics")
    metrics = {
        "iterations": 0,
        "improvements": 0,
        "regressions": 0,
        "features": [],
        "fixes": [],
    }

    if not metrics_dir.exists():
        return metrics

    for metric_file in metrics_dir.glob("evolution_*.json"):
        try:
            with open(metric_file) as f:
                data = json.load(f)
                metrics["iterations"] += data.get("iterations", 0)
                metrics["improvements"] += data.get("improvements", 0)
                metrics["regressions"] += data.get("regressions", 0)
                metrics["features"].extend(data.get("new_features", []))
                metrics["fixes"].extend(data.get("bug_fixes", []))
        except (json.JSONDecodeError, FileNotFoundError):
            continue

    return metrics


def generate_changelog_excerpt(version: str, metrics: Dict, changes: List[Dict]) -> str:
    """Generate changelog excerpt with evolution highlights."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Categorize changes
    features = [c for c in changes if c["message"].lower().startswith(("feat", "add", "new"))]
    fixes = [c for c in changes if c["message"].lower().startswith(("fix", "bug", "issue"))]

    output = [
        f"# EVOSEAL {version} - Release Notes\n",
        f"*Released on: {today}*\n",
        "## 🚀 Evolution Highlights\n",
    ]

    # Add evolution metrics
    output.append(f"- **Evolution Cycles**: {metrics['iterations']} iterations completed")
    output.append(f"- **Improvements**: {metrics['improvements']} significant improvements")
    output.append(
        f"- **Issues Resolved**: {metrics['regressions']} regressions detected and addressed\n"
    )

    # Add features from evolution
    if metrics["features"]:
        output.append("## ✨ New Features (AI-Generated)")
        for feature in set(metrics["features"]):  # Remove duplicates
            output.append(f"- {feature}")
        output.append("")

    # Add fixes from evolution
    if metrics["fixes"]:
        output.append("## 🐛 Fixes (AI-Validated)")
        for fix in set(metrics["fixes"]):  # Remove duplicates
            output.append(f"- {fix}")
        output.append("")

    # Add notable commits
    if features:
        output.append("## 📝 Notable Commits")
        for commit in features[:5]:  # Limit to top 5 features
            output.append(f"- {commit['message']} (*{commit['author']}*)")


def generate_release_notes(version: str, metrics: Dict, changes: List[Dict]) -> str:
    """Generate comprehensive release notes."""
    today = datetime.now().strftime("%Y-%m-%d")
    output = [
        f"# EVOSEAL {version}\n",
        f"*Released on: {today}*\n",
        "## 🚀 Release Highlights\n",
    ]

    # Add metrics if available
    if metrics.get("metrics"):
        m = metrics["metrics"]
        output.append(
            f"- **Code Changes**: {m.get('code_size', {}).get('added', 0)} lines added, "
            f"{m.get('code_size', {}).get('deleted', 0)} lines removed"
        )
        output.append(
            f"- **Files Changed**: {m.get('code_size', {}).get('files_changed', 0)} files"
        )
        if "test_coverage" in m:
            output.append(f"- **Test Coverage**: {float(m['test_coverage']) * 100:.1f}%")

    # Add changes by category
    if metrics.get("changes"):
        changes = metrics["changes"]

        # New Features
        if changes.get("features"):
            output.append("\n## ✨ New Features")
            for feature in changes["features"]:
                if feature.strip():
                    output.append(f"- {feature.strip()}")

        # Bug Fixes
        if changes.get("fixes"):
            output.append("\n## 🐛 Bug Fixes")
            for fix in changes["fixes"]:
                if fix.strip():
                    output.append(f"- {fix.strip()}")

        # Performance Improvements
        if changes.get("performance_improvements"):
            output.append("\n## ⚡ Performance Improvements")
            for perf in changes["performance_improvements"]:
                if perf.strip():
                    output.append(f"- {perf.strip()}")

    # Add notable commits if no other changes found
    if changes and not metrics.get("changes"):
        output.append("\n## 📝 Notable Changes")
        for change in changes[:5]:
            output.append(f"- `{change['hash'][:7]}` {change['message']} (*{change['date']}*)")

    # Add footer
    output.extend(
        [
            "",
            "## 📋 Release Checklist",
            "- [ ] Update version in pyproject.toml",
            "- [ ] Run tests",
            "- [ ] Update documentation",
            "- [ ] Create GitHub release",
            "- [ ] Verify PyPI upload",
            "",
            "## 📝 Notes",
            "Add any additional notes here.",
        ]
    )

    return "\n".join(output)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate release notes")
    parser.add_argument("version", help="Version number (e.g., v0.2.0)")
    parser.add_argument("--since", default=None, help="Previous version tag (default: auto-detect)")
    parser.add_argument(
        "--output-dir", default="releases", help="Output directory for release files"
    )

    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    version_dir = os.path.join(args.output_dir, args.version)
    os.makedirs(version_dir, exist_ok=True)

    # Auto-detect previous version if not specified
    if not args.since:
        try:
            args.since = (
                subprocess.check_output(
                    ["git", "describe", "--tags", "--abbrev=0", f"{args.version}^"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except subprocess.CalledProcessError:
            args.since = "HEAD"  # Fallback if no previous tag found

    # Get changes and metrics
    changes = get_git_changes(args.since)
    metrics = load_evolution_metrics()

    # If no metrics found, extract from git changes
    if not metrics and changes:
        metrics = {
            "changes": {
                "features": [
                    c["message"]
                    for c in changes
                    if c["message"].lower().startswith(("feat", "add", "new"))
                ],
                "fixes": [
                    c["message"]
                    for c in changes
                    if c["message"].lower().startswith(("fix", "bug", "issue"))
                ],
                "performance_improvements": [
                    c["message"]
                    for c in changes
                    if c["message"].lower().startswith(("perf", "optimize"))
                ],
            }
        }

    # Generate and save release notes
    release_notes = generate_release_notes(args.version, metrics, changes)
    with open(os.path.join(version_dir, "RELEASE_NOTES.md"), "w") as f:
        f.write(release_notes)

    print(f"Generated release notes in {version_dir}/")


if __name__ == "__main__":
    main()
