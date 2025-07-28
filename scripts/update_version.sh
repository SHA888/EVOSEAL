#!/bin/bash
# EVOSEAL Version Update Script
# Updates version numbers across all project files consistently

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if version is provided
if [ $# -eq 0 ]; then
    print_error "Please provide a version number (e.g., 0.3.3 or v0.3.3)"
    echo "Usage: $0 <version>"
    echo "Examples:"
    echo "  $0 0.3.3"
    echo "  $0 v0.3.3"
    exit 1
fi

VERSION_INPUT=$1
VERSION_NUMBER=${VERSION_INPUT#v}  # Remove 'v' prefix if present

print_status "Updating EVOSEAL version to $VERSION_NUMBER"

# Validate version format (SemVer)
if ! [[ $VERSION_NUMBER =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    print_error "Version must follow SemVer format (e.g., 0.3.3)"
    exit 1
fi

# Get project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT" || { 
    print_error "Failed to change to project root directory"
    exit 1
}

print_status "Working in project directory: $PROJECT_ROOT"

# Check if working directory is clean
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    print_warning "Working directory has uncommitted changes."
    read -p "Do you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Function to update version in file with backup
update_version_in_file() {
    local file=$1
    local pattern=$2
    local replacement=$3
    local description=$4
    
    if [ -f "$file" ]; then
        print_status "Updating $description in $file..."
        
        # Create backup
        cp "$file" "$file.bak"
        
        # Update version
        if sed -i "$pattern" "$file"; then
            print_success "✓ Updated $file"
            rm "$file.bak"  # Remove backup if successful
        else
            print_error "Failed to update $file"
            mv "$file.bak" "$file"  # Restore backup
            return 1
        fi
    else
        print_warning "File not found: $file"
    fi
}

# Update all version files
print_status "Updating version numbers across all files..."

# 1. Update pyproject.toml
update_version_in_file "pyproject.toml" \
    "s/version = \".*\"/version = \"$VERSION_NUMBER\"/" \
    "project version"

# 2. Update main package __init__.py
update_version_in_file "evoseal/__init__.py" \
    "s/__version__ = \".*\"/__version__ = \"$VERSION_NUMBER\"/" \
    "main package version"

# 3. Update dedicated version file
update_version_in_file "evoseal/__version__.py" \
    "s/__version__ = \".*\"/__version__ = \"$VERSION_NUMBER\"/" \
    "dedicated version module"

# 4. Update README.md version badge and text
if [ -f "README.md" ]; then
    print_status "Updating version references in README.md..."
    cp "README.md" "README.md.bak"
    
    # Update version badge
    sed -i "s/version-v[0-9]\+\.[0-9]\+\.[0-9]\+/version-v$VERSION_NUMBER/" README.md
    
    # Update version text references
    sed -i "s/Latest version: v[0-9]\+\.[0-9]\+\.[0-9]\+/Latest version: v$VERSION_NUMBER/" README.md
    sed -i "s/Version [0-9]\+\.[0-9]\+\.[0-9]\+/Version $VERSION_NUMBER/" README.md
    
    print_success "✓ Updated README.md"
    rm "README.md.bak"
fi

# 5. Update CHANGELOG.md with today's date for unreleased version
if [ -f "CHANGELOG.md" ]; then
    print_status "Updating CHANGELOG.md..."
    cp "CHANGELOG.md" "CHANGELOG.md.bak"
    
    TODAY=$(date +%Y-%m-%d)
    
    # Look for unreleased version and update it
    if grep -q "## \[Unreleased\]" CHANGELOG.md; then
        sed -i "s/## \[Unreleased\]/## [$VERSION_NUMBER] - $TODAY/" CHANGELOG.md
        print_success "✓ Updated unreleased version in CHANGELOG.md"
    elif grep -q "## \[$VERSION_NUMBER\]" CHANGELOG.md; then
        # Update existing version with today's date
        sed -i "s/## \[$VERSION_NUMBER\] - [0-9-]*/## [$VERSION_NUMBER] - $TODAY/" CHANGELOG.md
        print_success "✓ Updated existing version date in CHANGELOG.md"
    else
        print_warning "No unreleased version found in CHANGELOG.md"
        print_status "Consider adding a new version entry manually"
    fi
    
    rm "CHANGELOG.md.bak"
fi

# 6. Check for any hardcoded version references in documentation
print_status "Checking for other version references..."

# Find files that might contain version references (excluding git, node_modules, etc.)
VERSION_FILES=$(find . -type f \( -name "*.md" -o -name "*.rst" -o -name "*.txt" -o -name "*.py" \) \
    -not -path "./.git/*" \
    -not -path "./node_modules/*" \
    -not -path "./.venv/*" \
    -not -path "./venv/*" \
    -not -path "./releases/*" \
    -not -path "./data/*" \
    -not -path "./reports/*" \
    -exec grep -l "version.*[0-9]\+\.[0-9]\+\.[0-9]\+" {} \; 2>/dev/null || true)

if [ -n "$VERSION_FILES" ]; then
    print_warning "Found files with version references that may need manual review:"
    echo "$VERSION_FILES" | while read -r file; do
        echo "  - $file"
    done
    echo
    print_status "These files may contain version references that need manual updates"
fi

# Show summary of changes
print_status "Summary of version updates:"
echo "  ✓ pyproject.toml: version = \"$VERSION_NUMBER\""
echo "  ✓ evoseal/__init__.py: __version__ = \"$VERSION_NUMBER\""
echo "  ✓ evoseal/__version__.py: __version__ = \"$VERSION_NUMBER\""
echo "  ✓ README.md: version references updated"
echo "  ✓ CHANGELOG.md: version date updated"

# Check git status
print_status "Git status after version updates:"
git status --porcelain

# Offer to commit changes
echo
read -p "Do you want to commit these version changes? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Committing version updates..."
    
    git add pyproject.toml evoseal/__init__.py evoseal/__version__.py README.md CHANGELOG.md
    
    git commit -m "🔖 Bump version to v$VERSION_NUMBER

✨ Version Update:
- Updated pyproject.toml: version = \"$VERSION_NUMBER\"
- Updated evoseal/__init__.py: __version__ = \"$VERSION_NUMBER\"
- Updated evoseal/__version__.py: __version__ = \"$VERSION_NUMBER\"
- Updated README.md: version references
- Updated CHANGELOG.md: release date

🎯 Consistency:
- All core version files synchronized
- Package metadata updated
- Documentation reflects new version
- Ready for release tagging"
    
    print_success "✓ Version changes committed"
    
    # Offer to create git tag
    echo
    read -p "Do you want to create a git tag v$VERSION_NUMBER? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Creating git tag v$VERSION_NUMBER..."
        git tag -a "v$VERSION_NUMBER" -m "Release v$VERSION_NUMBER"
        print_success "✓ Git tag v$VERSION_NUMBER created"
        
        # Offer to push
        echo
        read -p "Do you want to push changes and tag to origin? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Pushing to origin..."
            git push origin main
            git push origin "v$VERSION_NUMBER"
            print_success "✓ Changes and tag pushed to origin"
        fi
    fi
else
    print_status "Version files updated but not committed"
    print_status "You can review the changes and commit manually when ready"
fi

echo
print_success "🎉 Version update to v$VERSION_NUMBER complete!"
echo
echo "Next steps:"
echo "1. Review all changed files for accuracy"
echo "2. Run tests to ensure everything works: pytest tests/"
echo "3. Build and test the package: python -m build"
echo "4. Create GitHub release if not done automatically"
echo "5. Update any deployment configurations if needed"
echo
print_status "Use 'scripts/prepare_release.sh v$VERSION_NUMBER' for full release preparation"
