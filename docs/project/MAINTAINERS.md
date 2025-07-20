# Maintainer's Guide

This document provides guidelines and procedures for EVOSEAL maintainers.

## Table of Contents

- [Maintainer Responsibilities](#maintainer-responsibilities)
- [Review Process](#review-process)
- [Release Process](#release-process)
- [Handling Security Issues](#handling-security-issues)
- [Managing Dependencies](#managing-dependencies)
- [Community Management](#community-management)
- [Decision Making](#decision-making)
- [Onboarding New Maintainers](#onboarding-new-maintainers)
- [Stepping Down](#stepping-down)

## Maintainer Responsibilities

As a maintainer, you are expected to:

1. **Review Pull Requests**
   - Ensure code quality and consistency
   - Verify tests pass
   - Check for proper documentation
   - Enforce code of conduct

2. **Triage Issues**
   - Label and categorize issues
   - Identify duplicates
   - Help reproduce bugs
   - Guide contributors

3. **Release Management**
   - Follow the release process
   - Update changelog
   - Create release notes

4. **Community Engagement**
   - Answer questions
   - Welcome new contributors
   - Moderate discussions

## Review Process

### Code Review Guidelines

1. **First Pass**
   - Check for obvious issues
   - Verify tests exist
   - Check documentation

2. **In-Depth Review**
   - Understand the changes
   - Check for edge cases
   - Consider performance implications
   - Verify security

3. **Final Check**
   - Squash and merge
   - Update documentation
   - Close related issues

### Review Labels

- `needs-tests`: Missing test coverage
- `needs-docs`: Missing documentation
- `needs-changelog`: Changelog entry required
- `blocked`: Waiting on other changes
- `do-not-merge`: Do not merge until resolved

## Release Process

### Patch Release (x.y.Z)

1. Create release branch from `main`
2. Update version in `__version__.py`
3. Update `CHANGELOG.md`
4. Create PR and get approval
5. Merge to `main`
6. Create GitHub release
7. Publish to PyPI

### Minor Release (x.Y.0)

1. Create `release-x.y` branch from `main`
2. Follow patch release process
3. Update `main` version to next development version

### Major Release (X.0.0)

1. Create RFC (Request for Comments)
2. Get community feedback
3. Follow minor release process

## Handling Security Issues

### Reporting Process

1. Acknowledge receipt within 3 days
2. Verify the vulnerability
3. Work on a fix in private
4. Prepare a security advisory
5. Release fixed version
6. Disclose vulnerability

### Security Team

- Primary: security@example.com
- Backup: maintainers@example.com

## Managing Dependencies

### Adding Dependencies

1. Add to appropriate requirements file:
   - `requirements/base.txt` for core deps
   - `requirements/dev.txt` for dev tools
   - `requirements/requirements.txt` for pinned versions

2. Justify the addition
3. Consider security implications
4. Document in `CHANGELOG.md`

### Updating Dependencies

1. Test updates locally
2. Check for breaking changes
3. Update documentation if needed
4. Update `CHANGELOG.md`

## Community Management

### Communication Channels

- GitHub Issues: Feature requests and bug reports
- Discussions: General questions and ideas
- Chat: Real-time discussions

### Handling Conflicts

1. Stay neutral and professional
2. Refer to code of conduct
3. Escalate if needed
4. Document decisions

## Decision Making

### Process

1. Open an issue for discussion
2. Allow time for feedback (minimum 72 hours)
3. Seek consensus
4. Make decision if no consensus
5. Document the decision

### Decision Records

Maintain a `docs/decisions` directory with:
- Context
- Decision
- Consequences

## Onboarding New Maintainers

### Criteria

1. Consistent contributions
2. Quality of contributions
3. Understanding of project
4. Community involvement

### Process

1. Nomination by existing maintainer
2. Discussion in private
3. Vote among current maintainers
4. Onboarding tasks
5. Announcement

## Stepping Down

### Process

1. Notify other maintainers
2. Transfer responsibilities
3. Update documentation
4. Announce departure

### Emeritus Status

- Retain read access
- Welcome to return
- Acknowledged in `MAINTAINERS.md`

---

*Last Updated: June 17, 2025*
