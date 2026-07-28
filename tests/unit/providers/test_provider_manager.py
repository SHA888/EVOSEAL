"""Tests for ProviderManager health-check await fix (issue: provider_manager.py)."""

from __future__ import annotations

import asyncio
import concurrent.futures
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evoseal.providers.provider_manager import ProviderManager, _run_coro_sync

# ---------------------------------------------------------------------------
# _run_coro_sync helper
# ---------------------------------------------------------------------------


class TestRunCoroSync:
    def test_runs_coroutine_from_sync_context(self):
        """Outside a running event loop, _run_coro_sync returns the result."""
        result = _run_coro_sync(asyncio.sleep(0, result=42))
        assert result == 42

    def test_raises_on_coroutine_error(self):
        async def _fail():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            _run_coro_sync(_fail())

    @pytest.mark.asyncio
    async def test_runs_coroutine_from_async_context(self):
        """Inside a running event loop, _run_coro_sync delegates to a thread."""
        result = _run_coro_sync(asyncio.sleep(0, result="ok"))
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_raises_on_coroutine_error_from_async_context(self):
        async def _fail():
            raise RuntimeError("async boom")

        with pytest.raises(RuntimeError, match="async boom"):
            _run_coro_sync(_fail())

    @pytest.mark.asyncio
    async def test_accepts_shared_executor(self):
        """When an executor is provided, it is reused instead of creating a new one."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            r1 = _run_coro_sync(asyncio.sleep(0, result=1), executor=pool)
            r2 = _run_coro_sync(asyncio.sleep(0, result=2), executor=pool)
        assert r1 == 1
        assert r2 == 2

    def test_shared_executor_ignored_in_sync_context(self):
        """Outside a running loop, the executor arg is ignored (asyncio.run is used)."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = _run_coro_sync(asyncio.sleep(0, result=99), executor=pool)
        assert result == 99

    def test_raises_on_timeout_from_sync_context(self):
        """A coroutine that exceeds the timeout raises asyncio.TimeoutError."""
        with pytest.raises(asyncio.TimeoutError):
            _run_coro_sync(asyncio.sleep(999), timeout=0.05)

    @pytest.mark.asyncio
    async def test_raises_on_timeout_from_async_context(self):
        """Timeout enforcement works inside a running event loop too."""
        with pytest.raises(asyncio.TimeoutError):
            _run_coro_sync(asyncio.sleep(999), timeout=0.05)

    def test_timeout_none_disables_enforcement(self):
        """Passing timeout=None disables the wait_for wrapper."""
        result = _run_coro_sync(asyncio.sleep(0, result=42), timeout=None)
        assert result == 42


# ---------------------------------------------------------------------------
# ProviderManager.get_best_available_provider — health check is awaited
# ---------------------------------------------------------------------------


def _make_provider(healthy: bool):
    """Return a mock provider whose async health_check returns *healthy*."""
    provider = MagicMock()
    provider.health_check = AsyncMock(return_value=healthy)
    return provider


def _mock_config(name: str, **kw):
    """Build a mock config whose ``.name`` attribute returns *name*.

    ``MagicMock(name=...)`` sets the mock's *repr*, not an attribute, so we
    assign ``.name`` explicitly after construction.
    """
    m = MagicMock(**kw)
    m.name = name
    return m


def _make_manager_with_providers(providers: dict[str, tuple]):
    """Build a ProviderManager whose `_providers` are pre-populated mocks.

    *providers* maps name → (provider_mock, priority).
    """
    mgr = ProviderManager.__new__(ProviderManager)
    mgr._providers = {}
    mgr._provider_classes = {}

    mock_settings_providers = {}
    for name, (prov, priority) in providers.items():
        mgr._providers[name] = prov
        config = MagicMock()
        config.enabled = True
        config.priority = priority
        mock_settings_providers[name] = config

    return mgr, mock_settings_providers


class TestGetBestAvailableProvider:
    def test_selects_healthy_provider(self):
        healthy_prov = _make_provider(True)
        mgr, mock_cfg = _make_manager_with_providers({"p": (healthy_prov, 10)})
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            result = mgr.get_best_available_provider()
        assert result is healthy_prov
        healthy_prov.health_check.assert_awaited_once()

    def test_skips_unhealthy_provider(self):
        bad_prov = _make_provider(False)
        good_prov = _make_provider(True)
        mgr, mock_cfg = _make_manager_with_providers(
            {
                "bad": (bad_prov, 10),
                "good": (good_prov, 5),
            }
        )
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            result = mgr.get_best_available_provider()
        assert result is good_prov
        bad_prov.health_check.assert_awaited_once()
        good_prov.health_check.assert_awaited_once()

    def test_raises_when_all_unhealthy(self):
        bad1 = _make_provider(False)
        bad2 = _make_provider(False)
        mgr, mock_cfg = _make_manager_with_providers(
            {
                "a": (bad1, 10),
                "b": (bad2, 5),
            }
        )
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            with pytest.raises(RuntimeError, match="No healthy"):
                mgr.get_best_available_provider()

    def test_skips_provider_on_health_check_exception(self):
        broken = _make_provider(True)  # won't matter — we'll raise
        broken.health_check = AsyncMock(side_effect=ConnectionError("unreachable"))
        good = _make_provider(True)
        mgr, mock_cfg = _make_manager_with_providers(
            {
                "broken": (broken, 10),
                "good": (good, 5),
            }
        )
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            result = mgr.get_best_available_provider()
        assert result is good


# ---------------------------------------------------------------------------
# ProviderManager.list_providers — health check is awaited
# ---------------------------------------------------------------------------


class TestListProviders:
    def test_reports_actual_health_status(self):
        """list_providers must await health_check and report the real result."""
        healthy = _make_provider(True)
        unhealthy = _make_provider(False)
        mgr = ProviderManager.__new__(ProviderManager)
        mgr._providers = {"healthy": healthy, "unhealthy": unhealthy}
        mgr._provider_classes = {}

        mock_cfg = {
            "healthy": _mock_config("h", enabled=True, priority=10, config={}),
            "unhealthy": _mock_config("u", enabled=True, priority=5, config={}),
        }
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            result = mgr.list_providers()

        assert result["healthy"]["healthy"] is True
        assert result["unhealthy"]["healthy"] is False
        healthy.health_check.assert_awaited_once()
        unhealthy.health_check.assert_awaited_once()

    def test_health_check_exception_is_reported(self):
        broken = _make_provider(True)
        broken.health_check = AsyncMock(side_effect=TimeoutError("timed out"))
        mgr = ProviderManager.__new__(ProviderManager)
        mgr._providers = {"broken": broken}
        mgr._provider_classes = {}

        mock_cfg = {
            "broken": _mock_config("b", enabled=True, priority=10, config={}),
        }
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            result = mgr.list_providers()

        assert result["broken"]["healthy"] is False
        assert "timed out" in result["broken"]["health_error"]


# ---------------------------------------------------------------------------
# Async-native methods: aget_best_available_provider / alist_providers
# ---------------------------------------------------------------------------


class TestAGetBestAvailableProvider:
    @pytest.mark.asyncio
    async def test_selects_healthy_provider(self):
        healthy_prov = _make_provider(True)
        mgr, mock_cfg = _make_manager_with_providers({"p": (healthy_prov, 10)})
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            result = await mgr.aget_best_available_provider()
        assert result is healthy_prov
        healthy_prov.health_check.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_unhealthy_provider(self):
        bad_prov = _make_provider(False)
        good_prov = _make_provider(True)
        mgr, mock_cfg = _make_manager_with_providers(
            {"bad": (bad_prov, 10), "good": (good_prov, 5)}
        )
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            result = await mgr.aget_best_available_provider()
        assert result is good_prov

    @pytest.mark.asyncio
    async def test_raises_when_all_unhealthy(self):
        bad = _make_provider(False)
        mgr, mock_cfg = _make_manager_with_providers({"a": (bad, 10)})
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            with pytest.raises(RuntimeError, match="No healthy"):
                await mgr.aget_best_available_provider()

    @pytest.mark.asyncio
    async def test_respects_timeout(self):
        slow = _make_provider(True)
        slow.health_check = AsyncMock(side_effect=asyncio.TimeoutError)
        fast = _make_provider(True)
        mgr, mock_cfg = _make_manager_with_providers({"slow": (slow, 10), "fast": (fast, 5)})
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            result = await mgr.aget_best_available_provider(health_check_timeout=0.1)
        assert result is fast


class TestAListProviders:
    @pytest.mark.asyncio
    async def test_reports_actual_health_status(self):
        healthy = _make_provider(True)
        unhealthy = _make_provider(False)
        mgr = ProviderManager.__new__(ProviderManager)
        mgr._providers = {"healthy": healthy, "unhealthy": unhealthy}
        mgr._provider_classes = {}
        mock_cfg = {
            "healthy": _mock_config("h", enabled=True, priority=10, config={}),
            "unhealthy": _mock_config("u", enabled=True, priority=5, config={}),
        }
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            result = await mgr.alist_providers()
        assert result["healthy"]["healthy"] is True
        assert result["unhealthy"]["healthy"] is False
        healthy.health_check.assert_awaited_once()
        unhealthy.health_check.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_check_exception_is_reported(self):
        broken = _make_provider(True)
        broken.health_check = AsyncMock(side_effect=TimeoutError("timed out"))
        mgr = ProviderManager.__new__(ProviderManager)
        mgr._providers = {"broken": broken}
        mgr._provider_classes = {}
        mock_cfg = {
            "broken": _mock_config("b", enabled=True, priority=10, config={}),
        }
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            result = await mgr.alist_providers()
        assert result["broken"]["healthy"] is False
        assert "timed out" in result["broken"]["health_error"]

    @pytest.mark.asyncio
    async def test_respects_timeout(self):
        slow = _make_provider(True)
        slow.health_check = AsyncMock(side_effect=asyncio.TimeoutError)
        mgr = ProviderManager.__new__(ProviderManager)
        mgr._providers = {"slow": slow}
        mgr._provider_classes = {}
        mock_cfg = {
            "slow": _mock_config("s", enabled=True, priority=10, config={}),
        }
        with patch("evoseal.providers.provider_manager.settings") as mock_settings:
            mock_settings.seal.providers = mock_cfg
            result = await mgr.alist_providers(health_check_timeout=0.1)
        assert result["slow"]["healthy"] is False
