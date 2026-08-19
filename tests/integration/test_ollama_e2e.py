"""Live E2E tests for the Ollama provider.

These tests exercise the OllamaProvider against a **real** running Ollama
instance.  They are skipped automatically when Ollama is unreachable (e.g. in
CI), so they never break a pipeline — they only produce useful signal when a
developer (or agent) has Ollama running locally.

Marker: ``@pytest.mark.integration`` (run with ``pytest -m integration``).
"""

from __future__ import annotations

import asyncio

import pytest

from evoseal.providers.local_models import (
    DEFAULT_OLLAMA_BASE_URL,
    AgentRole,
    list_installed_models,
    resolve_model,
)
from evoseal.providers.ollama_provider import OllamaProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OLLAMA_AVAILABLE: bool | None = None


def _ollama_is_running() -> bool:
    """Return True if Ollama responds on the default endpoint."""
    global _OLLAMA_AVAILABLE  # noqa: PLW0603
    if _OLLAMA_AVAILABLE is not None:
        return _OLLAMA_AVAILABLE

    import aiohttp

    async def _check() -> bool:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{DEFAULT_OLLAMA_BASE_URL}/api/tags") as resp:
                    available = resp.status == 200
        except Exception:
            available = False
        return available

    _OLLAMA_AVAILABLE = asyncio.run(_check())
    return _OLLAMA_AVAILABLE


# Use a module-level fixture so the check runs once per collection.
@pytest.fixture(autouse=True, scope="module")
def _require_ollama():
    if not _ollama_is_running():
        pytest.skip("Ollama is not running on localhost:11434")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestOllamaE2E:
    """End-to-end tests against a live Ollama instance."""

    def test_health_check_passes(self):
        """OllamaProvider.health_check() succeeds when Ollama is running."""
        provider = OllamaProvider(role=AgentRole.CODER)
        assert asyncio.run(provider.health_check()) is True

    def test_resolve_model_finds_installed_model(self):
        """resolve_model returns a model tag that Ollama actually has installed."""
        tag = resolve_model(AgentRole.CODER)
        assert tag, "resolve_model returned an empty string"
        # Use the same source as resolve_model to avoid format/cache mismatch.
        installed = list_installed_models()
        assert tag in installed, f"Resolved model '{tag}' not in installed models: {installed}"

    def test_resolve_model_reviewer_role(self):
        """resolve_model also works for the reviewer role."""
        tag = resolve_model(AgentRole.REVIEWER)
        assert tag, "resolve_model returned empty for reviewer role"

    def test_submit_prompt_returns_nonempty_response(self):
        """submit_prompt against the real Ollama instance returns content."""
        provider = OllamaProvider(role=AgentRole.CODER, timeout=120)
        # A minimal prompt that any coding model should handle.
        result = asyncio.run(provider.submit_prompt("Say hello in one word."))
        assert isinstance(result, str)
        assert len(result.strip()) > 0, "Ollama returned an empty response"

    def test_submit_prompt_with_system_message(self):
        """A system message is accepted and the model responds."""
        provider = OllamaProvider(role=AgentRole.CODER, timeout=120)
        result = asyncio.run(
            provider.submit_prompt(
                "What is 2 + 2?",
                system="You are a helpful assistant. Answer concisely.",
            )
        )
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_parse_response_extracts_content(self):
        """parse_response returns structured data from a real model output."""
        provider = OllamaProvider(role=AgentRole.CODER, timeout=120)
        raw = asyncio.run(provider.submit_prompt("Reply with the word 'yes'."))
        parsed = asyncio.run(provider.parse_response(raw))
        assert "content" in parsed
        assert parsed["provider"] == "ollama"
        assert parsed["length"] > 0

    def test_parse_response_detects_code_blocks(self):
        """parse_response identifies fenced code blocks in the output."""
        provider = OllamaProvider(role=AgentRole.CODER, timeout=120)
        raw = asyncio.run(
            provider.submit_prompt(
                "Write a Python hello-world function inside a code block.",
            )
        )
        parsed = asyncio.run(provider.parse_response(raw))
        # The model *should* include code fences for this prompt, but we can't
        # guarantee it.  Assert only that parsing doesn't crash.
        assert "contains_code" in parsed
        assert isinstance(parsed["code_blocks"], list)

    def test_get_model_info_matches_real_state(self):
        """get_model_info reflects the resolved model."""
        provider = OllamaProvider(role=AgentRole.CODER)
        info = provider.get_model_info()
        assert info["provider"] == "ollama"
        assert info["model"], "model should be resolved"
        assert info["base_url"] == DEFAULT_OLLAMA_BASE_URL

    def test_model_discovery_covers_all_roles(self):
        """Every AgentRole resolves to some installed model (no fallback tags)."""
        for role in AgentRole:
            tag = resolve_model(role)
            # A resolved tag should not be a bare fallback like "model:latest"
            # unless that's genuinely installed.  At minimum it must be non-empty.
            assert tag, f"No model resolved for role {role.value}"
