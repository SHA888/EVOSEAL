#!/usr/bin/env bash
# EVOSEAL Unified Release Script
# Automates the entire release process with safety checks and validation
# Usage: ./scripts/release.sh [major|minor|patch|vX.Y.Z] [--dry-run] [--skip-safety]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="${REPO_ROOT}/evoseal/__version__.py"
PYPROJECT_FILE="${REPO_ROOT}/pyproject.toml"
CHANGELOG_FILE="${REPO_ROOT}/CHANGELOG.md"
RELEASE_NOTES_DIR="${REPO_ROOT}/releases"

# Default options
DRY_RUN=false
SKIP_SAFETY=false
VERSION_BUMP=""

# Print functions
print_status()  { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Show usage information
show_usage() {
    cat << EOF
EVOSEAL Release Script

Usage: $0 [OPTIONS] [VERSION]

Options:
  major               Bump major version (X.0.0)
  minor               Bump minor version (0.X.0)
  patch               Bump patch version (0.0.X)
  vX.Y.Z              Use specific version (e.g., v0.3.4)
  --dry-run           Run without making changes
  --skip-safety       Skip safety checks (not recommended)
  -h, --help          Show this help message

Examples:
  $0 patch --dry-run    # Preview next patch release
  $0 minor              # Create a minor release
  $0 v0.3.4             # Create specific version release

EOF
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --skip-safety)
                SKIP_SAFETY=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            major|minor|patch)
                VERSION_BUMP=$1
                shift
                ;;
            v*.*.*)
                if [[ $1 =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                    VERSION_BUMP=${1#v}
                    shift
                else
                    print_error "Invalid version format. Use vX.Y.Z"
                fi
                ;;
            *)
                print_error "Unknown argument: $1"
                ;;
        esac
    done

    if [ -z "$VERSION_BUMP" ]; then
        print_error "Please specify a version or bump type (major|minor|patch|vX.Y.Z)"
    fi
}

# Get current version from __version__.py
get_current_version() {
    grep -Eo '"([0-9]+\.){2}[0-9]+"' "$VERSION_FILE" | tr -d '"'
}

# Calculate next version
calculate_next_version() {
    local current_version=$1
    local bump_type=$2

    IFS='.' read -r -a version_parts <<< "$current_version"
    local major=${version_parts[0]}
    local minor=${version_parts[1]}
    local patch=${version_parts[2]}

    case $bump_type in
        major)
            echo "$((major + 1)).0.0"
            ;;
        minor)
            echo "${major}.$((minor + 1)).0"
            ;;
        patch)
            echo "${major}.${minor}.$((patch + 1))"
            ;;
        *)
            echo "$bump_type"  # Specific version provided
            ;;
    esac
}

# Update version in all relevant files
update_version() {
    local old_version=$1
    local new_version=$2

    print_status "Updating version from ${YELLOW}${old_version}${NC} to ${GREEN}${new_version}${NC}"

    # Update __version__.py
    sed -i.bak -E "s/\"${old_version}\"/\"${new_version}\"/" "$VERSION_FILE"

    # Update pyproject.toml
    sed -i.bak -E "s/version\s*=\s*\"${old_version}\"/version = \"${new_version}\"/" "$PYPROJECT_FILE"

    # Clean up backups
    rm -f "${VERSION_FILE}.bak" "${PYPROJECT_FILE}.bak"

    print_success "Updated version to ${GREEN}${new_version}${NC} in all files"
}

# Check for uncommitted changes (ignoring submodules)
check_uncommitted_changes() {
    local changes
    changes=$(git status --porcelain | grep -v '^ M' | grep -v '^??' | grep -v '^ M SEAL' | grep -v '^ M dgm' | grep -v '^ M openevolve')

    if [ -n "$changes" ]; then
        print_error "Uncommitted changes detected (excluding submodules). Please commit or stash them before releasing:\n$changes"
    fi
}

# Run safety checks
run_safety_checks() {
    if [ "$SKIP_SAFETY" = true ]; then
        print_warning "Skipping safety checks (--skip-safety flag used)"
        return 0
    fi

    print_status "Running safety checks..."

    # Check for uncommitted changes (ignoring submodules)
    check_uncommitted_changes

    # Check if on main branch
    local current_branch
    current_branch=$(git branch --show-current)
    if [ "$current_branch" != "main" ]; then
        print_error "Must be on 'main' branch to release. Current branch: $current_branch"
    fi

    # Check if remote is up to date
    git fetch
    local local_commit
    local_commit=$(git rev-parse @)
    local remote_commit
    remote_commit=$(git rev-parse @{u})

    if [ "$local_commit" != "$remote_commit" ]; then
        print_error "Local branch is not up to date with remote. Please pull the latest changes."
    fi

    # Run tests if available
    if [ -f "$REPO_ROOT/scripts/run_tests.sh" ]; then
        print_status "Running tests..."
        "$REPO_ROOT/scripts/run_tests.sh" || print_error "Tests failed. Please fix them before releasing."
    fi

    print_success "All safety checks passed!"
}

# Generate release notes
generate_release_notes() {
    local version=$1
    local release_notes_dir="${RELEASE_NOTES_DIR}/${version}"

    print_status "Generating release notes for v${version}..."

    # Create release directory if it doesn't exist
    mkdir -p "$release_notes_dir"

    # Generate release notes using the existing script
    if [ -f "$REPO_ROOT/scripts/auto_generate_release_notes.py" ]; then
        python3 "$REPO_ROOT/scripts/auto_generate_release_notes.py" "v${version}" --output-dir "$release_notes_dir"
    else
        print_warning "auto_generate_release_notes.py not found. Creating minimal release notes."
        cat > "${release_notes_dir}/RELEASE_NOTES.md" << EOF
# EVOSEAL v${version} Release Notes

## 🎉 Release Highlights

This release includes various improvements and bug fixes.

## 📅 Release Information
- **Version**: ${version}
- **Release Date**: $(date +"%Y-%m-%d")

## 🔗 Useful Links
- [📚 Documentation](https://sha888.github.io/EVOSEAL/)
- [🐙 GitHub Repository](https://github.com/SHA888/EVOSEAL)
- [🐛 Report Issues](https://github.com/SHA888/EVOSEAL/issues)
- [📋 Full Changelog](https://github.com/SHA888/EVOSEAL/blob/main/CHANGELOG.md)

## 📦 Installation

\`\`\`bash
pip install evoseal==${version}
\`\`\`

*This release was automatically generated on $(date -u +"%Y-%m-%d %H:%M:%S UTC")*
EOF
    fi

    print_success "Release notes generated: ${release_notes_dir}/RELEASE_NOTES.md"
}

# Create git tag and push
git_tag_and_push() {
    local version=$1
    local tag="v${version}"

    print_status "Creating and pushing git tag ${GREEN}${tag}${NC}..."

    if [ "$DRY_RUN" = true ]; then
        print_warning "[DRY RUN] Would create and push tag: ${tag}"
    else
        # Commit version updates
        git add "$VERSION_FILE" "$PYPROJECT_FILE"
        git commit -m "🚀 Release ${tag}"

        # Create annotated tag
        git tag -a "${tag}" -m "Release ${tag}"

        # Push changes and tags
        git push origin main
        git push origin "${tag}"

        print_success "Successfully pushed tag ${GREEN}${tag}${NC} to remote"
    fi
}

# Main function
main() {
    # Parse command line arguments
    parse_arguments "$@"

    # Get current version
    local current_version
    current_version=$(get_current_version)

    # Calculate next version
    local next_version
    next_version=$(calculate_next_version "$current_version" "$VERSION_BUMP")

    # Show dry run header
    if [ "$DRY_RUN" = true ]; then
        echo -e "\n${YELLOW}=== DRY RUN MODE ===${NC}\n"
    fi

    # Show release plan
    echo -e "${BLUE}=== EVOSEAL Release Plan ===${NC}"
    echo -e "Current version: ${YELLOW}${current_version}${NC}"
    echo -e "Next version:    ${GREEN}${next_version}${NC}"
    echo -e "Branch:          $(git branch --show-current)"
    echo -e "Clean working copy: $([ -z "$(git status --porcelain)" ] && echo "✅" || echo "❌")"
    echo -e "\n${BLUE}The following actions will be performed:${NC}"
    echo "1. Run safety checks (unless --skip-safety is used)"
    echo "2. Update version in all files to ${next_version}"
    echo "3. Generate release notes in releases/${next_version}/"
    echo "4. Create and push git tag v${next_version}"
    echo -e "\n${YELLOW}GitHub Actions will then automatically:${NC}"
    echo "- Run tests and checks"
    echo "- Build and publish the package to PyPI"
    echo "- Create a GitHub release with the generated notes"

    # Confirm before proceeding
    echo -e "\n${BLUE}=== Ready to proceed? ===${NC}"
    if [ "$DRY_RUN" = false ]; then
        read -p "This will modify files and push to the remote repository. Continue? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "\n${YELLOW}Release canceled.${NC}"
            exit 0
        fi
    fi

    # Run safety checks
    run_safety_checks

    # Update version in files
    update_version "$current_version" "$next_version"

    # Generate release notes
    generate_release_notes "$next_version"

    # Create and push git tag
    git_tag_and_push "$next_version"

    # Final message
    echo -e "\n${GREEN}=== Release Process Started Successfully! ===${NC}"
    echo -e "\n${BLUE}Next Steps:${NC}"
    echo "1. Monitor the GitHub Actions workflow for completion"
    echo "2. Review the generated release notes at: releases/${next_version}/RELEASE_NOTES.md"
    echo "3. Celebrate! 🎉"

    if [ "$DRY_RUN" = true ]; then
        echo -e "\n${YELLOW}=== DRY RUN COMPLETE - No changes were made ===${NC}"
    fi
}

# Run the script
main "$@"
