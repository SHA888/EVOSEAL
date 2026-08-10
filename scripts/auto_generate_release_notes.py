#!/usr/bin/env python3
"""Generate release notes from git history since the last release tag.

Usage:
    python scripts/auto_generate_release_notes.py <version> [--output-dir releases]

Produces ``releases/<version>/RELEASE_NOTES.md`` with commits categorised by
conventional-commit prefix (feat, fix, docs, ci, refactor, test, chore, etc.).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Commit category mapping (conventional-commit type → display heading)
# Order matters – first match wins when a commit has multiple prefixes.
# ---------------------------------------------------------------------------
CATEGORY_MAP: list[tuple[str, str, str]] = [
    # (prefix, emoji, heading)
    ("feat", "✨", "New Features"),
    ("fix", "🐛", "Bug Fixes"),
    ("security", "🔒", "Security Improvements"),
    ("perf", "⚡", "Performance Improvements"),
    ("docs", "📝", "Documentation"),
    ("ci", "👷", "CI/CD & Infrastructure"),
    ("refactor", "♻️", "Code Improvements"),
    ("test", "🧪", "Testing"),
    ("chore", "🔧", "Other Changes"),
]

DEFAULT_OUTPUT_DIR = "releases"


def run(cmd: list[str], **kwargs) -> str:
    """Run a command and return stripped stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)
    if result.returncode != 0:
        print(f"⚠️  Command failed: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
    return result.stdout.strip()


def get_last_tag() -> str | None:
    """Return the most recent version tag, or None if there are no tags."""
    tag = run(["git", "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"])
    return tag if tag else None


def get_commits_since(tag: str | None) -> list[tuple[str, str, str]]:
    """Return ``[(hash, subject, body), …]`` since *tag* (or all history)."""
    # Use NUL bytes as both field and record separators.
    # Git prohibits NUL in commit messages, so this is safe — unlike a
    # text sentinel (e.g. "END") which could appear in commit subjects.
    fmt = "%H%x00%s%x00%b%x00"
    if tag:
        log = run(["git", "log", f"{tag}..HEAD", f"--pretty=format:{fmt}"])
    else:
        log = run(["git", "log", f"--pretty=format:{fmt}"])

    if not log:
        return []

    # Each commit produces exactly 3 NUL-separated fields (hash, subject,
    # body) followed by a trailing NUL.  Split on NUL and group by 3.
    parts = log.split("\x00")
    commits: list[tuple[str, str, str]] = []
    for i in range(0, len(parts) - 2, 3):
        sha = parts[i][:7]
        subject = parts[i + 1]
        body = parts[i + 2]
        if sha:
            commits.append((sha, subject, body))
    return commits


def categorise(commits: list[tuple[str, str, str]]) -> dict[str, list[str]]:
    """Map each commit to a category heading based on its subject prefix."""
    buckets: dict[str, list[str]] = {}
    uncategorised: list[str] = []

    for sha, subject, _body in commits:
        # Skip merge commits and release-version bumps
        if subject.startswith("Merge ") or subject.startswith("Bump version to"):
            continue

        matched = False
        for prefix, emoji, heading in CATEGORY_MAP:
            # Match "feat:", "feat(scope):", "feat!:", case-insensitive
            if subject.lower().startswith(f"{prefix}:") or subject.lower().startswith(f"{prefix}("):
                line = (
                    f"- {emoji} {subject} ([{sha}](https://github.com/SHA888/EVOSEAL/commit/{sha}))"
                )
                buckets.setdefault(heading, []).append(line)
                matched = True
                break

        if not matched:
            line = f"- {subject} ([{sha}](https://github.com/SHA888/EVOSEAL/commit/{sha}))"
            uncategorised.append(line)

    if uncategorised:
        buckets.setdefault("Other Changes", []).extend(uncategorised)
    return buckets


def build_notes(version: str, categories: dict[str, list[str]]) -> str:
    """Build the full release notes markdown."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = sum(len(v) for v in categories.values())
    lines = [
        f"# EVOSEAL v{version} Release Notes",
        "",
        "## 🎉 Release Highlights",
        "",
        f"This release includes {total} change(s) since the previous release.",
        "",
        "## 📅 Release Information",
        f"- **Version**: {version}",
        f"- **Release Date**: {date}",
        f"- **Total Changes**: {total}",
        "",
    ]

    for _prefix, emoji, heading in CATEGORY_MAP:
        if heading in categories:
            lines.append(f"## {emoji} {heading}")
            lines.append("")
            lines.extend(categories[heading])
            lines.append("")

    # Append any headings we added dynamically (e.g. "Other Changes")
    for heading, items in categories.items():
        if heading not in {h for _, _, h in CATEGORY_MAP}:
            lines.append(f"## {heading}")
            lines.append("")
            lines.extend(items)
            lines.append("")

    lines.extend(
        [
            "## 🔗 Useful Links",
            "",
            "- [📚 Documentation](https://sha888.github.io/EVOSEAL/)",
            "- [🐙 GitHub Repository](https://github.com/SHA888/EVOSEAL)",
            "- [🐛 Report Issues](https://github.com/SHA888/EVOSEAL/issues)",
            "- [📋 Full Changelog](https://github.com/SHA888/EVOSEAL/blob/main/CHANGELOG.md)",
            "",
            "---",
            "",
            "**Installation:**",
            "```bash",
            f"pip install evoseal=={version}",
            "```",
            "",
            "**Upgrade:**",
            "```bash",
            "pip install --upgrade evoseal",
            "```",
            "",
            f"*This release was automatically generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate EVOSEAL release notes")
    parser.add_argument("version", help="Version string (e.g. 0.3.5)")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Root directory for release notes (default: releases)",
    )
    args = parser.parse_args()

    version = args.version.lstrip("v")
    output_dir = Path(args.output_dir) / version
    output_dir.mkdir(parents=True, exist_ok=True)

    last_tag = get_last_tag()
    print(f"ℹ️  Last tag: {last_tag or '(none — full history)'}")

    commits = get_commits_since(last_tag)
    print(f"ℹ️  Found {len(commits)} commit(s) since {last_tag or 'beginning'}")

    if not commits:
        print("⚠️  No commits found — generating minimal release notes")

    categories = categorise(commits)
    notes = build_notes(version, categories)

    out_path = output_dir / "RELEASE_NOTES.md"
    out_path.write_text(notes)
    print(f"✅ Wrote {out_path} ({len(notes)} bytes)")


if __name__ == "__main__":
    main()
