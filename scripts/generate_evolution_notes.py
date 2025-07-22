#!/usr/bin/env python3
"""
Generate release notes and changelog excerpts based on evolution metrics and git history.
"""
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import yaml

def get_git_changes(since_tag: str) -> List[Dict]:
    """Get commit history since the last release."""
    cmd = [
        "git", "log", 
        f"{since_tag}..HEAD",
        "--pretty=format:%H|%an|%ad|%s",
        "--date=short",
        "--no-merges"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    changes = []
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        commit_hash, author, date, message = line.split('|', 3)
        changes.append({
            'hash': commit_hash,
            'author': author,
            'date': date,
            'message': message
        })
    return changes

def load_evolution_metrics() -> Dict:
    """Load evolution metrics from the metrics directory."""
    metrics_dir = Path("metrics")
    metrics = {
        'iterations': 0,
        'improvements': 0,
        'regressions': 0,
        'features': [],
        'fixes': []
    }
    
    if not metrics_dir.exists():
        return metrics
        
    for metric_file in metrics_dir.glob("evolution_*.json"):
        try:
            with open(metric_file, 'r') as f:
                data = json.load(f)
                metrics['iterations'] += data.get('iterations', 0)
                metrics['improvements'] += data.get('improvements', 0)
                metrics['regressions'] += data.get('regressions', 0)
                metrics['features'].extend(data.get('new_features', []))
                metrics['fixes'].extend(data.get('bug_fixes', []))
        except (json.JSONDecodeError, FileNotFoundError):
            continue
            
    return metrics

def generate_changelog_excerpt(version: str, metrics: Dict, changes: List[Dict]) -> str:
    """Generate changelog excerpt with evolution highlights."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Categorize changes
    features = [c for c in changes if c['message'].lower().startswith(('feat', 'add', 'new'))]
    fixes = [c for c in changes if c['message'].lower().startswith(('fix', 'bug', 'issue'))]
    
    output = [
        f"# EVOSEAL {version} - Release Notes\n",
        f"*Released on: {today}*\n",
        "## 🚀 Evolution Highlights\n"
    ]
    
    # Add evolution metrics
    output.append(f"- **Evolution Cycles**: {metrics['iterations']} iterations completed")
    output.append(f"- **Improvements**: {metrics['improvements']} significant improvements")
    output.append(f"- **Issues Resolved**: {metrics['regressions']} regressions detected and addressed\n")
    
    # Add features from evolution
    if metrics['features']:
        output.append("## ✨ New Features (AI-Generated)")
        for feature in set(metrics['features']):  # Remove duplicates
            output.append(f"- {feature}")
        output.append("")
    
    # Add fixes from evolution
    if metrics['fixes']:
        output.append("## 🐛 Fixes (AI-Validated)")
        for fix in set(metrics['fixes']):  # Remove duplicates
            output.append(f"- {fix}")
        output.append("")
    
    # Add notable commits
    if features:
        output.append("## 📝 Notable Commits")
        for commit in features[:5]:  # Limit to top 5 features
            output.append(f"- {commit['message']} (*{commit['author']}*)")
    
    return "\n".join(output)

def generate_release_notes(version: str, metrics: Dict, changes: List[Dict]) -> str:
    """Generate comprehensive release notes."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    output = [
        f"# EVOSEAL {version} Release Notes\n",
        f"*Released on: {today}*\n",
        "## 📊 Evolution Summary\n"
    ]
    
    # Evolution metrics
    output.append("### Evolution Metrics")
    output.append(f"- **Total Evolution Cycles**: {metrics['iterations']}")
    output.append(f"- **Successful Improvements**: {metrics['improvements']}")
    output.append(f"- **Addresses Regressions**: {metrics['regressions']}\n")
    
    # Detailed changes
    output.append("## 🛠️ Changes")
    
    # Features from evolution
    if metrics['features']:
        output.append("\n### ✨ New Features (AI-Generated)")
        for feature in set(metrics['features']):
            output.append(f"- {feature}")
    
    # Fixes from evolution
    if metrics['fixes']:
        output.append("\n### 🐛 Fixes (AI-Validated)")
        for fix in set(metrics['fixes']):
            output.append(f"- {fix}")
    
    # Commit history
    output.append("\n## 📝 Commit History")
    for change in changes[:20]:  # Limit to 20 most recent commits
        output.append(f"- `{change['hash'][:7]}` {change['message']} (*{change['date']}*)")
    
    if len(changes) > 20:
        output.append(f"\n*... and {len(changes) - 20} more changes*")
    
    # Footer
    output.extend([
        "\n## 🔗 Useful Links",
        "- [Documentation](https://sha888.github.io/EVOSEAL/)",
        "- [GitHub Repository](https://github.com/SHA888/EVOSEAL)",
        "- [Report Issues](https://github.com/SHA888/EVOSEAL/issues)",
        "\n*This release was automatically generated by the EVOSEAL release process.*"
    ])
    
    return "\n".join(output)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate release notes and changelog excerpts')
    parser.add_argument('version', help='Version number (e.g., v0.2.0)')
    parser.add_argument('--since', default=None, help='Previous version tag (default: auto-detect)')
    parser.add_argument('--output-dir', default='releases', help='Output directory for release files')
    
    args = parser.parse_args()
    
    # Auto-detect previous version if not specified
    if not args.since:
        cmd = ["git", "describe", "--tags", "--abbrev=0", f"{args.version}^"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            args.since = result.stdout.strip()
        except subprocess.CalledProcessError:
            args.since = "HEAD"  # Fallback if no previous tag found
    
    # Get changes and metrics
    changes = get_git_changes(args.since)
    metrics = load_evolution_metrics()
    
    # Create output directory
    output_dir = Path(args.output_dir) / args.version
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate and save files
    changelog = generate_changelog_excerpt(args.version, metrics, changes)
    (output_dir / 'CHANGELOG_EXCERPT.md').write_text(changelog)
    
    release_notes = generate_release_notes(args.version, metrics, changes)
    (output_dir / 'RELEASE_NOTES.md').write_text(release_notes)
    
    print(f"Generated release notes in {output_dir}/")

if __name__ == "__main__":
    main()
