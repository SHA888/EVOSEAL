# GitHub Pages Setup Guide

This guide explains how to set up GitHub Pages for EVOSEAL documentation.

## 🎯 Current Setup

EVOSEAL uses **MkDocs with GitHub Actions** for documentation deployment:

- **Source**: Documentation files in `docs/` directory
- **Build**: MkDocs generates static site in `site/` directory
- **Deploy**: GitHub Actions automatically deploys to `gh-pages` branch
- **URL**: https://sha888.github.io/EVOSEAL/

## 📁 Project Structure

```
EVOSEAL/
├── docs/                    # Documentation source files
│   ├── index.md            # Homepage
│   ├── safety/             # Safety documentation
│   ├── core/               # Core system docs
│   ├── guides/             # User guides
│   ├── project/            # Project management
│   └── api/                # API reference
├── mkdocs.yml              # MkDocs configuration
├── .github/workflows/      # GitHub Actions
│   └── docs.yml           # Documentation deployment
├── requirements/
│   └── docs.txt           # Documentation dependencies
└── site/                  # Generated site (ignored)
```

## 🚀 GitHub Pages Configuration

### 1. Repository Settings

In your GitHub repository settings:

1. Go to **Settings** → **Pages**
2. Set **Source** to "GitHub Actions"
3. The workflow will automatically deploy to `gh-pages` branch

### 2. Custom Domain (Optional)

To use a custom domain:

1. Add your domain to the workflow in `.github/workflows/docs.yml`:
   ```yaml
   - name: Build documentation
     run: |
       mkdocs build --clean --strict
       echo "your-domain.com" > site/CNAME
   ```

2. Configure DNS records for your domain:
   - **A Record**: Point to GitHub Pages IPs
   - **CNAME Record**: Point to `username.github.io`

### 3. Branch Protection

Protect the `gh-pages` branch:
- Go to **Settings** → **Branches**
- Add rule for `gh-pages`
- Enable "Restrict pushes that create files"

## 🔧 Local Development

### Setup

1. Install documentation dependencies:
   ```bash
   pip install -r requirements/docs.txt
   ```

2. Serve documentation locally:
   ```bash
   mkdocs serve
   ```

3. Access at: http://localhost:8000

### Building

Build the documentation:
```bash
mkdocs build --clean --strict
```

## 📝 Content Management

### Adding New Pages

1. Create markdown file in appropriate `docs/` subdirectory
2. Add to navigation in `mkdocs.yml`:
   ```yaml
   nav:
     - Section:
         - Page Title: path/to/file.md
   ```

### Organizing Content

- **Safety docs**: `docs/safety/`
- **Core systems**: `docs/core/`
- **User guides**: `docs/guides/`
- **Project info**: `docs/project/`
- **API docs**: `docs/api/`

### Link References

Use relative links between documentation files:
```markdown
[Link to guide](../guides/setup.md)
[Link to API](../api/reference.md)
```

## 🎨 Theming

EVOSEAL uses **Material for MkDocs** theme with:

- **Navigation tabs**: Top-level sections as tabs
- **Dark/light mode**: Automatic theme switching
- **Search**: Full-text search functionality
- **Git integration**: Last modified dates
- **Code highlighting**: Syntax highlighting for code blocks

### Customization

Theme settings in `mkdocs.yml`:
```yaml
theme:
  name: material
  features:
    - navigation.tabs
    - navigation.sections
    - search.highlight
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
```

## 🔍 SEO and Analytics

### Meta Information

Configure in `mkdocs.yml`:
```yaml
site_name: EVOSEAL Documentation
site_description: Evolutionary Self-Improving AI Agent
site_url: https://sha888.github.io/EVOSEAL/
```

### Analytics (Optional)

Add Google Analytics:
```yaml
extra:
  analytics:
    provider: google
    property: G-XXXXXXXXXX
```

## 🚨 Troubleshooting

### Common Issues

1. **Build Failures**
   - Check `mkdocs build --strict` locally
   - Verify all linked files exist
   - Check YAML syntax in `mkdocs.yml`

2. **Missing Pages**
   - Ensure files are in `docs/` directory
   - Add to navigation in `mkdocs.yml`
   - Check file paths and extensions

3. **Broken Links**
   - Use relative paths: `../section/page.md`
   - Verify target files exist
   - Check for typos in filenames

4. **Plugin Errors**
   - Update plugin versions in `requirements/docs.txt`
   - Check plugin compatibility with MkDocs version

### GitHub Actions Debugging

Check workflow logs:
1. Go to **Actions** tab in GitHub
2. Click on failed workflow run
3. Expand job steps to see errors
4. Common fixes:
   - Update Python/dependency versions
   - Fix broken links in strict mode
   - Verify file permissions

## 📚 Resources

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## 🔄 Maintenance

### Regular Tasks

1. **Update Dependencies**: Keep MkDocs and plugins updated
2. **Link Checking**: Regularly verify internal/external links
3. **Content Review**: Keep documentation current with code changes
4. **Performance**: Monitor build times and optimize if needed

### Automation

The GitHub Actions workflow automatically:
- Builds documentation on every push to main
- Deploys to GitHub Pages
- Caches dependencies for faster builds
- Runs in strict mode to catch errors

This setup provides a robust, automated documentation system that scales with your project!
