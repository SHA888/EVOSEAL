# EVOSEAL Adapter Configuration Guide

This document describes configuration keys for the new adapters introduced for replacing local submodules with package/remote modes.

Components covered:
- DGM (remote HTTP adapter)
- OpenEvolve (package and remote modes)

See also: `evoseal/integration/README.md` for broader integration architecture, and example runner in `examples/minimal_workflow.py`.

## Common adapter parameters

Factory helpers accept common `ComponentConfig` keys:
- `enabled`: bool (default True)
- `timeout`: int seconds (request/process timeout)
- `max_retries`: int (adapter-level retries on failures)
- `retry_delay`: float seconds between retries
- `config`: dict with adapter-specific options (below)

---

## DGM Remote Adapter

Module: `evoseal.integration.dgmr.dgm_adapter.DGMAdapter`
Factory: `create_dgm_adapter(**kwargs)`

Adapter requires a remote HTTP service with endpoints:
- POST `/dgm/jobs/advance` -> `{ job_id }`
- GET `/dgm/jobs/{job_id}/status` -> `{ status: completed|failed|... }`
- GET `/dgm/jobs/{job_id}/result` -> `{ result: ... }`
- POST `/dgm/archive/update` -> `{ ok: true, ... }`

Adapter-specific config (under `config.remote`):
- `base_url`: string (required)
- `auth_token`: string (optional, Bearer token)
- `request_timeout`: int seconds (defaults to `timeout`)
- `poll_interval`: float seconds between status polls (default 2.0)

Example:
```python
from evoseal.integration.dgmr.dgm_adapter import create_dgm_adapter

adapter = create_dgm_adapter(
    enabled=True,
    timeout=300,
    config={
        "remote": {
            "base_url": "https://dgm.example.com",
            "auth_token": "<token>",
            "request_timeout": 120,
            "poll_interval": 1.5,
        }
    },
)
```

Operations:
- `advance_generation`: payload placed in POST body
- `update_archive`: accepts list of run IDs or an object; sent to `/dgm/archive/update`

Metrics (`get_metrics()`):
- `mode`: "remote"
- `base_url_set`: bool
- `timeout`: int
- `poll_interval`: float

---

## OpenEvolve Adapter

Module: `evoseal.integration.oe.openevolve_adapter.OpenEvolveAdapter`
Factory: `create_openevolve_adapter(**kwargs)`

Supported modes:
- `package`: use the official `openevolve` Python package in-process
- `remote`: call a remote HTTP service

### Package mode

Keys (under `config.package`):
- `initial_program_path`: str (required)
- `evaluation_file`: str (required)
- `output_dir`: str (required)
- `config_path`: str path to OpenEvolve YAML config (required by adapter)
- `iterations`: int (optional)
- `target_score`: float (optional)
- `checkpoint`: str path to checkpoint to resume (optional)

Notes:
- The adapter lazily imports `openevolve.controller.OpenEvolve` and `openevolve.config`.
- `config_path` is loaded via `load_config()` if available, falling back to `Config.from_file()`.
- `oe.run()` is awaited; result summarized to `{ program_id, score }` if available.

Example:
```python
adapter = create_openevolve_adapter(
    enabled=True,
    timeout=600,
    config={
        "mode": "package",
        "package": {
            "initial_program_path": "examples/hello.py",
            "evaluation_file": "examples/eval.py",
            "config_path": "configs/openevolve.yaml",
            "output_dir": "./outputs/openevolve",
            "iterations": 10,
            "target_score": 0.95,
            "checkpoint": "./outputs/openevolve/ckpt.db",
        },
    },
)
```

### Remote mode

HTTP endpoints expected:
- POST `/openevolve/jobs/evolve` -> `{ job_id }`
- GET `/openevolve/jobs/{job_id}/status` -> `{ status: completed|failed|... }`
- GET `/openevolve/jobs/{job_id}/result` -> `{ result: ... }`

Keys (under `config.remote`):
- `base_url`: str (required)
- `auth_token`: str (optional, Bearer token)
- `request_timeout`: int seconds (defaults to `timeout`)
- `poll_interval`: float seconds (default 2.0)
- `job`: dict, payload to POST on evolve submit (optional; can also be passed via `data` when calling `execute("evolve")`)

Example:
```python
adapter = create_openevolve_adapter(
    enabled=True,
    timeout=600,
    config={
        "mode": "remote",
        "remote": {
            "base_url": "https://oe.example.com",
            "auth_token": "<token>",
            "request_timeout": 300,
            "poll_interval": 2.0,
            "job": {"initial_program": "..."},
        }
    },
)
```

Metrics (`get_metrics()`):
- `mode`: "package" or "remote"
- `evolutions_started`, `evolutions_succeeded`, `evolutions_failed`

---

## Orchestrator usage

Create orchestrator using factories and pass component configs:
```python
from evoseal.integration import create_integration_orchestrator, ComponentType

orch = create_integration_orchestrator(
    dgm_config={
        "enabled": True,
        "timeout": 120,
        "config": {"remote": {"base_url": "https://dgm.example.com"}},
    },
    openevolve_config={
        "enabled": True,
        "timeout": 300,
        "config": {"mode": "remote", "remote": {"base_url": "https://oe.example.com"}},
    },
)

# then initialize/start and execute operations
```

---

## Testing and examples

- Unit tests mock `aiohttp` and `openevolve` imports; see:
  - `tests/unit/test_dgm_adapter_remote.py`
  - `tests/unit/test_openevolve_adapter_remote.py`
  - `tests/unit/test_openevolve_adapter_package.py`
- Orchestrator smoke test: `tests/integration/test_orchestrator_smoke.py` (mocks remote services)
- Minimal example runner: `examples/minimal_workflow.py` with `--mock` flag to run without services.
