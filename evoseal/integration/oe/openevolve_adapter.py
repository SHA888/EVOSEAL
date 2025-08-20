"""
OpenEvolve Component Adapter for EVOSEAL Integration

This adapter integrates OpenEvolve via either its Python package (in-process)
or a remote HTTP service, conforming to BaseComponentAdapter.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, Optional

from ..base_adapter import BaseComponentAdapter, ComponentConfig, ComponentResult, ComponentType

try:
    import aiohttp  # For optional remote mode
except Exception:  # pragma: no cover
    aiohttp = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class _OEStats:
    evolutions_started: int = 0
    evolutions_succeeded: int = 0
    evolutions_failed: int = 0


class OpenEvolveAdapter(BaseComponentAdapter):
    """
    Adapter for integrating OpenEvolve into EVOSEAL.

    Supported operations:
    - evolve: run an OpenEvolve evolution session

    Config keys (self.config.config):
    - mode: "package" or "remote" (default: "package")
    - package:
        - initial_program_path: str
        - evaluation_file: str
        - output_dir: str
        - config_path: Optional[str]
        - iterations: Optional[int]
        - target_score: Optional[float]
        - checkpoint: Optional[str]
    - remote:
        - base_url: str
        - auth_token: Optional[str]
        - request_timeout: int (seconds, default 300)
        - poll_interval: float (seconds, default 2.0)
    """

    def __init__(self, config: ComponentConfig):
        if config.component_type != ComponentType.OPENEVOLVE:
            raise ValueError("OpenEvolveAdapter requires ComponentType.OPENEVOLVE")
        super().__init__(config)
        self._mode: str = str(self.config.config.get("mode", "package"))
        self._stats = _OEStats()

    async def _initialize_impl(self) -> bool:
        try:
            self._mode = str(self.config.config.get("mode", "package"))
            if self._mode not in ("package", "remote"):
                raise ValueError(f"Unsupported mode: {self._mode}")
            # No heavy init. Validate minimal remote deps if needed
            if self._mode == "remote" and aiohttp is None:
                raise RuntimeError("aiohttp is required for remote mode but not installed")
            return True
        except Exception as e:
            self.logger.exception("Failed to initialize OpenEvolve adapter")
            self.status.error = str(e)
            return False

    async def _start_impl(self) -> bool:
        # Nothing persistent to start
        return True

    async def _stop_impl(self) -> bool:
        # Nothing persistent to stop
        return True

    async def execute(self, operation: str, data: Any = None, **kwargs) -> ComponentResult:
        if operation != "evolve":
            return ComponentResult(success=False, error=f"Unknown operation: {operation}")

        start = asyncio.get_event_loop().time()
        try:
            self._stats.evolutions_started += 1
            if self._mode == "remote":
                result = await self._evolve_remote(data or {}, **kwargs)
            else:
                result = await self._evolve_package(data or {}, **kwargs)
            exec_time = asyncio.get_event_loop().time() - start
            if result.get("success", False):
                self._stats.evolutions_succeeded += 1
                return ComponentResult(success=True, data=result, execution_time=exec_time)
            else:
                self._stats.evolutions_failed += 1
                return ComponentResult(
                    success=False,
                    data=result,
                    error=result.get("error", "Evolution failed"),
                    execution_time=exec_time,
                )
        except Exception as e:
            exec_time = asyncio.get_event_loop().time() - start
            self._stats.evolutions_failed += 1
            self.logger.exception("OpenEvolve evolve operation error")
            return ComponentResult(success=False, error=str(e), execution_time=exec_time)

    async def get_metrics(self) -> Dict[str, Any]:
        return {
            "mode": self._mode,
            "evolutions_started": self._stats.evolutions_started,
            "evolutions_succeeded": self._stats.evolutions_succeeded,
            "evolutions_failed": self._stats.evolutions_failed,
        }

    # --- Implementation helpers ---

    async def _evolve_package(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        cfg = {**self.config.config.get("package", {}), **data, **kwargs}
        initial_program_path = cfg.get("initial_program_path")
        evaluation_file = cfg.get("evaluation_file")
        output_dir = cfg.get("output_dir")
        config_path = cfg.get("config_path")
        iterations = cfg.get("iterations")
        target_score = cfg.get("target_score")
        checkpoint = cfg.get("checkpoint")

        if not (initial_program_path and evaluation_file and output_dir):
            return {
                "success": False,
                "error": "Missing required fields: initial_program_path, evaluation_file, output_dir",
            }

        # Try to import OpenEvolve package API lazily
        try:
            controller = import_module("openevolve.controller")
        except Exception as e:
            return {
                "success": False,
                "error": f"OpenEvolve package not available: {e}. Install openevolve and provide a valid config.",
            }

        OpenEvolve = getattr(controller, "OpenEvolve", None)
        if OpenEvolve is None:
            return {"success": False, "error": "openevolve.controller.OpenEvolve not found"}

        # Load config if possible
        config_obj = None
        if config_path:
            try:
                cfg_mod = import_module("openevolve.config")
                load_fn = getattr(cfg_mod, "load_config", None)
                if load_fn is not None:
                    config_obj = load_fn(config_path)
                else:
                    # Fallback: try Config.from_file if present
                    ConfigCls = getattr(cfg_mod, "Config", None)
                    if ConfigCls and hasattr(ConfigCls, "from_file"):
                        config_obj = ConfigCls.from_file(config_path)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to load OpenEvolve config from {config_path}: {e}",
                }

        if config_obj is None:
            return {
                "success": False,
                "error": "OpenEvolve configuration could not be loaded. Provide 'config_path' pointing to a valid YAML config.",
            }

        try:
            oe = OpenEvolve(
                initial_program_path=initial_program_path,
                evaluation_file=evaluation_file,
                config=config_obj,
                output_dir=output_dir,
            )
            if checkpoint:
                # Best-effort checkpoint load if available
                try:
                    if hasattr(oe, "database") and hasattr(oe.database, "load"):
                        oe.database.load(checkpoint)
                except Exception:
                    logger.warning(
                        "Checkpoint load failed; continuing without resume", exc_info=True
                    )

            best_program = await oe.run(iterations=iterations, target_score=target_score)
            # best_program is likely a Program object; represent minimally
            summary = {
                "program_id": getattr(best_program, "id", None),
                "score": (
                    getattr(getattr(best_program, "metrics", None), "get", lambda *_: None)("score")
                    if best_program is not None
                    else None
                ),
            }
            return {"success": True, "result": summary}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _evolve_remote(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        if aiohttp is None:
            return {"success": False, "error": "aiohttp not installed; remote mode unavailable"}

        cfg = {**self.config.config.get("remote", {}), **data, **kwargs}
        base_url = cfg.get("base_url")
        if not base_url:
            return {
                "success": False,
                "error": "remote.base_url is required for OpenEvolve remote mode",
            }
        auth_token = cfg.get("auth_token")
        timeout_s: int = int(cfg.get("request_timeout", self.config.timeout))
        poll_interval: float = float(cfg.get("poll_interval", 2.0))

        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        # Submit job
        job_payload = cfg.get("job", {})
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout_s)
            ) as session:
                async with session.post(
                    f"{base_url.rstrip('/')}/openevolve/jobs/evolve",
                    json=job_payload,
                    headers=headers,
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        return {"success": False, "error": f"Submit failed: {resp.status} {text}"}
                    submit = await resp.json()
                    job_id = submit.get("job_id")
                    if not job_id:
                        return {"success": False, "error": "No job_id returned from submit"}

                # Poll
                while True:
                    await asyncio.sleep(poll_interval)
                    async with session.get(
                        f"{base_url.rstrip('/')}/openevolve/jobs/{job_id}/status", headers=headers
                    ) as sresp:
                        if sresp.status != 200:
                            text = await sresp.text()
                            return {
                                "success": False,
                                "error": f"Status failed: {sresp.status} {text}",
                            }
                        status = await sresp.json()
                        if status.get("status") in ("completed", "failed"):
                            break

                # Fetch result
                async with session.get(
                    f"{base_url.rstrip('/')}/openevolve/jobs/{job_id}/result", headers=headers
                ) as rresp:
                    if rresp.status != 200:
                        text = await rresp.text()
                        return {"success": False, "error": f"Result failed: {rresp.status} {text}"}
                    result = await rresp.json()
                    return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


def create_openevolve_adapter(**kwargs) -> OpenEvolveAdapter:
    """
    Factory to create an OpenEvolveAdapter.
    Accepts keyword args matching ComponentConfig plus nested adapter config.
    Example:
        create_openevolve_adapter(
            enabled=True,
            timeout=600,
            config={
                "mode": "package",
                "package": {
                    "initial_program_path": "examples/foo.py",
                    "evaluation_file": "examples/eval.py",
                    "config_path": "configs/openevolve.yaml",
                    "output_dir": "./outputs/openevolve",
                },
            },
        )
    """
    comp_cfg = ComponentConfig(
        component_type=ComponentType.OPENEVOLVE,
        enabled=kwargs.get("enabled", True),
        timeout=kwargs.get("timeout", 300),
        max_retries=kwargs.get("max_retries", 3),
        retry_delay=kwargs.get("retry_delay", 1.0),
        config=kwargs.get("config", {}),
    )
    return OpenEvolveAdapter(comp_cfg)
