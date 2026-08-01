```yaml
id: "001-checkpoint-traversal-fix"
title: "Fix directory traversal in checkpoint identifiers/paths"
date: 2026-07-22
type: safety
status: stable
pr:
  - "#74"
authors:
  - agent: evoseal-dev
files_changed:
  - evoseal/core/checkpoint_manager.py
  - evoseal/core/version_tracker.py
```

## Description

`CheckpointManager.create_checkpoint()`, `restore_checkpoint()`, and `get_checkpoint_path()`
all built paths via `self.checkpoint_dir / f"checkpoint_{version_id}"` with zero validation
of `version_id`. A `version_id` like `"../../../../etc/cron.d/evil"` resolved outside
`checkpoint_dir`, enabling arbitrary file writes when the checkpoint was later restored.

The same class also joined attacker-controlled `changes` dict keys (from evolution-pipeline
results) onto the checkpoint path unsanitized — a full arbitrary-path + arbitrary-bytes
write primitive. `EditScopeValidator` (which implements the correct `.resolve()` +
`relative_to()` containment check) was never called on this path.

## Metrics Before

| Metric | Value |
|--------|-------|
| `version_id` sanitization | None — raw string concatenated into path |
| `changes` key sanitization | None — attacker-controlled keys joined onto checkpoint path |
| `EditScopeValidator` usage | Not called from `CheckpointManager` |
| `tests/safety/` traversal tests | 0 covering checkpoint paths |

## Metrics After

| Metric | Value |
|--------|-------|
| `version_id` sanitization | `Path(version_id).name` strips traversal; `relative_to()` containment check |
| `changes` key sanitization | Keys resolved and validated against checkpoint directory |
| `EditScopeValidator` usage | Wired into `SafetyIntegration.create_safety_checkpoint()` |
| `tests/safety/` traversal tests | 3 new test functions covering `..` traversal, absolute paths, nested traversal |

## Validation

- `ruff format --check .` — pass
- `ruff check evoseal/ tests/` — pass
- `pytest tests/safety/ -q` — all pass
- Manual `grep` confirms no unsanitized path joins remain in `checkpoint_manager.py`

## Rollback

```bash
git revert 4975940
```

Side effect: re-opens the directory traversal vulnerability. Do not rollback without an
alternative fix in place.

## Config Snapshot

No config changes required. The fix is purely in Python path-validation logic.

## Notes

This was one of six critical bugs found in a whole-repo code review on 2026-07-22. The
`EditScopeValidator` containment pattern is the canonical approach for all future path
validation in EVOSEAL.
