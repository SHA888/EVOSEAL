# Improvement Unit Template

Copy this file and fill in all required fields. Delete the instructional comments (lines
starting with `>`) in your completed unit.

Filename: `NNN-short-slug.md` (e.g., `001-checkpoint-traversal-fix.md`)

---

```yaml
id: NNN-short-slug
title: >
  Short descriptive title of the improvement
date: YYYY-MM-DD
type: bug-fix | safety | performance | feature | refactor | docs
status: candidate | beta | stable | rolled-back
pr:
  - "#NNN"
authors:
  - agent: evoseal-dev
files_changed:
  - path/to/file.py
  - path/to/other.py
```

## Description

> What changed and why. One to three paragraphs. Link to the issue or audit finding that
> motivated this change.

## Metrics Before

> Key measurements taken *before* the change. Include whatever is relevant:
> - Test pass rate
> - Specific test failures
> - Benchmark scores
> - Security scan findings
> - Manual verification results
>
> Use a table or bullet list. Be specific — "all tests pass" is not useful if you don't
> record which tests.

| Metric | Value |
|--------|-------|
| ... | ... |

## Metrics After

> Same format as above, taken *after* the change.

| Metric | Value |
|--------|-------|
| ... | ... |

## Validation

> How was this change verified? List every check that was run:
> - `ruff format --check .` — pass/fail
> - `ruff check evoseal/ tests/` — pass/fail
> - `pytest tests/path/to/test.py -q` — N passed, 0 failed
> - Manual review / grep verification
> - CI run URL if available

## Rollback

> Exact steps to revert this change if it causes regression. Be specific:
> - `git revert <commit-sha>` — or —
> - `git checkout main -- path/to/file.py` for selective revert
> - Any config changes that also need reverting
> - Side effects of rollback (e.g., "re-opens the traversal vulnerability")

## Config Snapshot

> Relevant configuration at the time of the change. If the change depends on a specific
> `configs/safety.yaml` setting, `pyproject.toml` dependency version, or environment variable,
> record it here. This lets a future auditor reproduce the exact conditions.

```yaml
# Paste relevant config excerpts here
```

## Notes

> Optional. Open questions, known limitations, follow-up work, or links to related
> improvement units.
```
