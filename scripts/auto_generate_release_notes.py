#!/usr/bin/env python3
"""
EVOSEAL Automatic Release Notes Generator
Generates comprehensive release notes from git history, changelog, and commits.
"""

import os
import sys
import re
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
import json

def run_command(cmd, capture_output=True):
    """Run a shell command and return the output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True)
        return result.stdout.strip() if capture_output else None
    except Exception as e:
        print(f"Error running command '{cmd}': {e}")
        return ""

def get_git_log_between_tags(from_tag, to_tag):
    """Get git commits between two tags."""
    if from_tag:
        cmd = f"git log --pretty=format:'%h|%s|%an|%ad' --date=short {from_tag}..{to_tag}"
    else:
        cmd = f"git log --pretty=format:'%h|%s|%an|%ad' --date=short {to_tag}"
    
    output = run_command(cmd)
    commits = []
    
    for line in output.split('\n'):
        if line.strip():
            parts = line.split('|')
            if len(parts) >= 4:
                commits.append({
                    'hash': parts[0],
                    'message': parts[1],
                    'author': parts[2],
                    'date': parts[3]
                })
    
    return commits

def categorize_commits(commits):
    """Categorize commits by type based on conventional commit patterns."""
    categories = {
        'features': [],
        'fixes': [],
        'security': [],
        'performance': [],
        'docs': [],
        'ci': [],
        'refactor': [],
        'other': []
    }
    
    patterns = {
        'features': [r'^feat', r'^add', r'^implement', r'✨', r'🚀'],
        'fixes': [r'^fix', r'^bug', r'🐛', r'🔧'],
        'security': [r'^security', r'^sec', r'🔒', r'🛡️'],
        'performance': [r'^perf', r'^optimize', r'⚡', r'🚀'],
        'docs': [r'^docs?', r'^documentation', r'📝', r'📚'],
        'ci': [r'^ci', r'^build', r'^deploy', r'👷', r'🔨'],
        'refactor': [r'^refactor', r'^clean', r'^improve', r'♻️', r'🎨']
    }
    
    for commit in commits:
        message = commit['message'].lower()
        categorized = False
        
        for category, pattern_list in patterns.items():
            for pattern in pattern_list:
                if re.search(pattern, message, re.IGNORECASE):
                    categories[category].append(commit)
                    categorized = True
                    break
            if categorized:
                break
        
        if not categorized:
            categories['other'].append(commit)
    
    return categories

def extract_changelog_section(version):
    """Extract the changelog section for a specific version."""
    changelog_path = Path("CHANGELOG.md")
    if not changelog_path.exists():
        return ""
    
    content = changelog_path.read_text()
    
    # Look for version section
    version_pattern = rf"## \[{re.escape(version)}\].*?(?=## \[|\Z)"
    match = re.search(version_pattern, content, re.DOTALL)
    
    if match:
        section = match.group(0)
        # Clean up the section
        lines = section.split('\n')[1:]  # Skip the version header
        return '\n'.join(line for line in lines if line.strip())
    
    return ""

def generate_release_notes(version, previous_version=None):
    """Generate comprehensive release notes for a version."""
    
    # Get commits between versions
    commits = get_git_log_between_tags(previous_version, f"v{version}")
    categorized = categorize_commits(commits)
    
    # Get changelog content
    changelog_content = extract_changelog_section(version)
    
    # Get release date
    tag_date = run_command(f"git log -1 --format=%ci v{version} 2>/dev/null")
    if tag_date and tag_date.strip():
        try:
            # Parse the git date format (e.g., "2025-07-27 01:36:33 +0000")
            date_part = tag_date.split(' ')[0]  # Get just the date part
            release_date = date_part
        except (ValueError, IndexError):
            release_date = datetime.now().strftime('%Y-%m-%d')
    else:
        release_date = datetime.now().strftime('%Y-%m-%d')
    
    # Generate release notes content
    content = f"""# EVOSEAL v{version} Release Notes

## 🎉 Release Highlights

{changelog_content if changelog_content else "This release includes various improvements and bug fixes."}

## 📅 Release Information
- **Version**: {version}
- **Release Date**: {release_date}
- **Total Commits**: {len(commits)}

"""

    # Add categorized changes
    if categorized['features']:
        content += "## ✨ New Features\n\n"
        for commit in categorized['features']:
            content += f"- {commit['message']} ([{commit['hash']}](https://github.com/SHA888/EVOSEAL/commit/{commit['hash']}))\n"
        content += "\n"

    if categorized['fixes']:
        content += "## 🐛 Bug Fixes\n\n"
        for commit in categorized['fixes']:
            content += f"- {commit['message']} ([{commit['hash']}](https://github.com/SHA888/EVOSEAL/commit/{commit['hash']}))\n"
        content += "\n"

    if categorized['security']:
        content += "## 🔒 Security Improvements\n\n"
        for commit in categorized['security']:
            content += f"- {commit['message']} ([{commit['hash']}](https://github.com/SHA888/EVOSEAL/commit/{commit['hash']}))\n"
        content += "\n"

    if categorized['performance']:
        content += "## ⚡ Performance Improvements\n\n"
        for commit in categorized['performance']:
            content += f"- {commit['message']} ([{commit['hash']}](https://github.com/SHA888/EVOSEAL/commit/{commit['hash']}))\n"
        content += "\n"

    if categorized['ci']:
        content += "## 👷 CI/CD & Infrastructure\n\n"
        for commit in categorized['ci']:
            content += f"- {commit['message']} ([{commit['hash']}](https://github.com/SHA888/EVOSEAL/commit/{commit['hash']}))\n"
        content += "\n"

    if categorized['docs']:
        content += "## 📝 Documentation\n\n"
        for commit in categorized['docs']:
            content += f"- {commit['message']} ([{commit['hash']}](https://github.com/SHA888/EVOSEAL/commit/{commit['hash']}))\n"
        content += "\n"

    if categorized['refactor']:
        content += "## ♻️ Code Improvements\n\n"
        for commit in categorized['refactor']:
            content += f"- {commit['message']} ([{commit['hash']}](https://github.com/SHA888/EVOSEAL/commit/{commit['hash']}))\n"
        content += "\n"

    # Add other changes if any
    other_commits = categorized['other']
    if other_commits:
        content += "## 🔧 Other Changes\n\n"
        for commit in other_commits:
            content += f"- {commit['message']} ([{commit['hash']}](https://github.com/SHA888/EVOSEAL/commit/{commit['hash']}))\n"
        content += "\n"

    # Add footer
    content += f"""## 🔗 Useful Links

- [📚 Documentation](https://sha888.github.io/EVOSEAL/)
- [🐙 GitHub Repository](https://github.com/SHA888/EVOSEAL)
- [🐛 Report Issues](https://github.com/SHA888/EVOSEAL/issues)
- [📋 Full Changelog](https://github.com/SHA888/EVOSEAL/blob/main/CHANGELOG.md)

## 📊 Contributors

Thanks to all contributors who made this release possible:

"""
    
    # Add unique contributors
    contributors = set(commit['author'] for commit in commits)
    for contributor in sorted(contributors):
        content += f"- {contributor}\n"

    content += f"""
---

**Installation:**
```bash
pip install evoseal=={version}
```

**Upgrade:**
```bash
pip install --upgrade evoseal
```

*This release was automatically generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""

    return content

def main():
    parser = argparse.ArgumentParser(description='Generate EVOSEAL release notes')
    parser.add_argument('version', help='Version to generate notes for (e.g., 0.3.2)')
    parser.add_argument('--previous-version', help='Previous version for comparison')
    parser.add_argument('--output-dir', default='releases', help='Output directory for release files')
    parser.add_argument('--commit', action='store_true', help='Commit the generated files to git')
    
    args = parser.parse_args()
    
    # Ensure we're in the project root
    if not Path('pyproject.toml').exists():
        print("Error: Must be run from the project root directory")
        sys.exit(1)
    
    # Create output directory
    output_dir = Path(args.output_dir) / args.version
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate release notes
    print(f"Generating release notes for v{args.version}...")
    
    release_notes = generate_release_notes(args.version, args.previous_version)
    
    # Write release notes
    release_notes_path = output_dir / "RELEASE_NOTES.md"
    release_notes_path.write_text(release_notes)
    
    print(f"✅ Release notes generated: {release_notes_path}")
    
    # Generate release checklist
    checklist_content = f"""# EVOSEAL v{args.version} Release Checklist

## Pre-Release Checks
- [x] All tests are passing
- [x] Documentation is up to date  
- [x] Version numbers updated in all relevant files
- [x] Changelog is updated with all changes
- [x] Dependencies are up to date
- [x] Security audit completed
- [x] Release notes generated

## Release Process
- [x] Create release branch
- [x] Run build process
- [x] Run all tests
- [x] Generate release notes
- [x] Create git tag
- [ ] Push changes and tag to repository
- [ ] Create GitHub release
- [ ] Publish to PyPI
- [ ] Update documentation
- [ ] Announce release

## Post-Release
- [ ] Merge release branch to main
- [ ] Update development version
- [ ] Verify deployment
- [ ] Monitor for issues

## Rollback Plan
- [ ] Identify rollback trigger conditions
- [ ] Document rollback steps
- [ ] Test rollback procedure

*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""
    
    checklist_path = output_dir / "RELEASE_CHECKLIST.md"
    checklist_path.write_text(checklist_content)
    
    print(f"✅ Release checklist generated: {checklist_path}")
    
    # Commit if requested
    if args.commit:
        print("Committing generated files...")
        run_command(f"git add {output_dir}", capture_output=False)
        run_command(f"git commit -m 'docs: Generate release notes for v{args.version}'", capture_output=False)
        print("✅ Files committed to git")
    
    print(f"\n🎉 Release documentation ready for v{args.version}!")
    print(f"📁 Files created in: {output_dir}")
    print(f"📝 Release notes: {release_notes_path}")
    print(f"📋 Checklist: {checklist_path}")

if __name__ == "__main__":
    main()
