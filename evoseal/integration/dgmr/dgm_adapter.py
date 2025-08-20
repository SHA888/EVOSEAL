"""
DGM Remote Adapter for EVOSEAL Integration

This adapter integrates a remote DGM service via HTTP, implementing the
BaseComponentAdapter interface. It supports submitting generation jobs
and updating the archive remotely.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..base_adapter import BaseComponentAdapter, ComponentConfig, ComponentResult, ComponentType

try:
    import aiohttp
except Exception:  # pragma: no cover
    aiohttp = None  # type: ignore

logger = logging.getLogger(__name__)


class DGMAdapter(BaseComponentAdapter):
    """
    Remote DGM adapter.

    Supported operations:
    - advance_generation: Submit a generation job and poll until completion
    - update_archive: Update archive entries with new artifacts

    Config keys under self.config.config:
    remote:
      base_url: str (required)
      auth_token: Optional[str]
      request_timeout: int seconds (default from ComponentConfig.timeout)
      poll_interval: float seconds (default 2.0)
    """

    def __init__(self, config: ComponentConfig):
        if config.component_type != ComponentType.DGM:
            raise ValueError("DGMAdapter requires ComponentType.DGM")
        super().__init__(config)

        self._base_url: Optional[str] = None
        self._auth_token: Optional[str] = None
        self._timeout: int = config.timeout
        self._poll_interval: float = 2.0

    async def _initialize_impl(self) -> bool:
        try:
            if aiohttp is None:
                raise RuntimeError("aiohttp is required for DGM remote adapter but not installed")

            rcfg = self.config.config.get("remote", {})
            self._base_url = rcfg.get("base_url")
            if not self._base_url:
                raise ValueError("remote.base_url is required for DGM remote adapter")
            self._auth_token = rcfg.get("auth_token")
            self._timeout = int(rcfg.get("request_timeout", self.config.timeout))
            self._poll_interval = float(rcfg.get("poll_interval", 2.0))
            return True
        except Exception as e:
            self.logger.exception("Failed to initialize DGM remote adapter")
            self.status.error = str(e)
            return False

    async def _start_impl(self) -> bool:
        return True

    async def _stop_impl(self) -> bool:
        return True

    async def execute(self, operation: str, data: Any = None, **kwargs) -> ComponentResult:
        start = asyncio.get_event_loop().time()
        try:
            if operation == "advance_generation":
                payload = data or {}
                result = await self._advance_generation(payload, **kwargs)
            elif operation == "update_archive":
                # data expected: list of run_ids or dict with entries
                result = await self._update_archive(data, **kwargs)
            else:
                return ComponentResult(success=False, error=f"Unknown operation: {operation}")

            exec_time = asyncio.get_event_loop().time() - start
            if result.get("success"):
                return ComponentResult(success=True, data=result, execution_time=exec_time)
            return ComponentResult(
                success=False, data=result, error=result.get("error"), execution_time=exec_time
            )
        except Exception as e:
            exec_time = asyncio.get_event_loop().time() - start
            self.logger.exception("DGM operation error")
            return ComponentResult(success=False, error=str(e), execution_time=exec_time)

    async def get_metrics(self) -> Dict[str, Any]:
        return {
            "mode": "remote",
            "base_url_set": bool(self._base_url),
            "timeout": self._timeout,
            "poll_interval": self._poll_interval,
        }

    # --- Remote helpers ---

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers

    async def _advance_generation(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        if aiohttp is None:
            return {"success": False, "error": "aiohttp not available"}
        base = self._base_url.rstrip("/")  # type: ignore
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base}/dgm/jobs/advance", json=payload, headers=self._headers()
                ) as resp:
                    if resp.status != 200:
                        return {
                            "success": False,
                            "error": f"submit failed: {resp.status} {await resp.text()}",
                        }
                    submit = await resp.json()
                    job_id = submit.get("job_id")
                    if not job_id:
                        return {"success": False, "error": "No job_id returned"}
                # poll
                while True:
                    await asyncio.sleep(self._poll_interval)
                    async with session.get(
                        f"{base}/dgm/jobs/{job_id}/status", headers=self._headers()
                    ) as sresp:
                        if sresp.status != 200:
                            return {
                                "success": False,
                                "error": f"status failed: {sresp.status} {await sresp.text()}",
                            }
                        status = await sresp.json()
                        if status.get("status") in ("completed", "failed"):
                            break
                # result
                async with session.get(
                    f"{base}/dgm/jobs/{job_id}/result", headers=self._headers()
                ) as rresp:
                    if rresp.status != 200:
                        return {
                            "success": False,
                            "error": f"result failed: {rresp.status} {await rresp.text()}",
                        }
                    result = await rresp.json()
                    return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _update_archive(self, data: Any, **kwargs) -> Dict[str, Any]:
        if aiohttp is None:
            return {"success": False, "error": "aiohttp not available"}
        base = self._base_url.rstrip("/")  # type: ignore
        timeout = aiohttp.ClientTimeout(total=self._timeout)

        # Normalize payload
        payload: Dict[str, Any]
        if isinstance(data, list):
            payload = {"run_ids": data}
        elif isinstance(data, dict):
            payload = data
        else:
            payload = {"entries": data}

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base}/dgm/archive/update", json=payload, headers=self._headers()
                ) as resp:
                    if resp.status != 200:
                        return {
                            "success": False,
                            "error": f"archive update failed: {resp.status} {await resp.text()}",
                        }
                    j = await resp.json()
                    return {"success": True, "result": j}
        except Exception as e:
            return {"success": False, "error": str(e)}


def create_dgm_adapter(**kwargs) -> DGMAdapter:
    """Factory for DGMAdapter (remote)."""
    comp_cfg = ComponentConfig(
        component_type=ComponentType.DGM,
        enabled=kwargs.get("enabled", True),
        timeout=kwargs.get("timeout", 300),
        max_retries=kwargs.get("max_retries", 3),
        retry_delay=kwargs.get("retry_delay", 1.0),
        config=kwargs.get("config", {}),
    )
    return DGMAdapter(comp_cfg)
