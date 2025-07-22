# EVOSEAL v0.2.0 Release Checklist

## ✅ Automated Checks (Handled by CI/CD)
- [x] Version numbers updated in `pyproject.toml` and `evoseal/__init__.py`
- [x] All unit and integration tests passing
- [x] Code quality checks (linting, type checking)
- [x] Security vulnerability scan completed
- [x] Documentation built successfully

## 📋 Manual Verification

### Code Quality
- [ ] Review all changes since last release
- [ ] Verify all new features have tests
- [ ] Check for any remaining TODOs or FIXMEs
- [ ] Verify all environment variables are documented

### Documentation
- [ ] Update `CHANGELOG.md`
- [ ] Verify all new features are documented
- [ ] Check all examples in documentation are working
- [ ] Update version-specific documentation if needed

### Release Artifacts
- [ ] Verify `CHANGELOG_EXCERPT.md` is comprehensive
- [ ] Check `RELEASE_NOTES.md` for accuracy
- [ ] Ensure all release files are properly formatted
- [ ] Verify links in documentation are working

## 🚀 Release Process

### Preparation
- [ ] Create release branch: `git checkout -b release/v0.2.0`
- [ ] Run final test suite: `pytest tests/`
- [ ] Verify version consistency: `grep -r "0.2.0" --include="*.py" --include="*.md" --include="*.toml" .`

### Tagging & Pushing
- [ ] Create annotated tag: `git tag -a v0.2.0 -m "Release v0.2.0"`
- [ ] Push branch: `git push origin release/v0.2.0`
- [ ] Push tags: `git push --tags`

### GitHub Release
- [ ] Draft new release on GitHub
- [ ] Use tag `v0.2.0`
- [ ] Title: "EVOSEAL v0.2.0 - Automated Release Management"
- [ ] Copy contents from `releases/v0.2.0/RELEASE_NOTES.md`
- [ ] Attach any additional release assets
- [ ] Publish release

## 🔄 Post-Release

### Cleanup
- [ ] Merge release branch to main
- [ ] Delete release branch after successful merge
- [ ] Update development version to next planned release

### Verification
- [ ] Verify GitHub release page
- [ ] Check automated documentation update
- [ ] Test installation from PyPI (if applicable)
- [ ] Verify systemd service starts correctly

## 🛡️ Rollback Plan

### Conditions for Rollback
- [ ] Critical bugs found in production
- [ ] Security vulnerabilities discovered
- [ ] Major performance regressions
- [ ] Data corruption issues

### Rollback Steps
1. Revert to previous tag: `git checkout v0.1.3`
2. Create hotfix branch: `git checkout -b hotfix/rollback-v0.2.0`
3. Force push to main: `git push -f origin v0.1.3:main`
4. Delete any problematic tags: `git push --delete origin v0.2.0`
5. Notify users about the rollback

## 📊 Monitoring
- [ ] Monitor system logs for 24 hours post-release
- [ ] Track error rates and performance metrics
- [ ] Watch for new issues on GitHub
- [ ] Monitor system resource usage

## 📝 Post-Mortem (If Needed)
- [ ] Document any issues encountered
- [ ] Update runbooks and checklists
- [ ] Schedule follow-up actions
- [ ] Test rollback procedure

*Last updated: 2025-07-22 06:14:27*
