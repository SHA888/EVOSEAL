"""Unit tests for Ollama model discovery and per-role resolution."""

from __future__ import annotations

import json
import urllib.error
from contextlib import contextmanager

import pytest

from evoseal.providers import local_models
from evoseal.providers.local_models import (
    FALLBACK_ROLE_MODELS,
    AgentRole,
    clear_model_cache,
    env_override_for,
    list_installed_models,
    resolve_model,
    resolve_role_models,
    select_model,
)

DEEPSEEK = "deepseek-coder-v2:16b-lite-instruct-q8_0"
QWEN = "qwen2.5-coder:7b-instruct-q6_K"


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """Discovery is cached and env-driven; isolate both for every test."""
    monkeypatch.delenv("EVOSEAL_CODER_MODEL", raising=False)
    monkeypatch.delenv("EVOSEAL_REVIEWER_MODEL", raising=False)
    clear_model_cache()
    yield
    clear_model_cache()


@contextmanager
def _fake_ollama(monkeypatch, names, calls=None, error=None):
    """Stub the Ollama /api/tags HTTP call."""

    class _Response:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _urlopen(url, timeout=None):
        if calls is not None:
            calls.append(url)
        if error is not None:
            raise error
        return _Response({"models": [{"name": n} for n in names]})

    monkeypatch.setattr(local_models.urllib.request, "urlopen", _urlopen)
    yield


# -- select_model ---------------------------------------------------------


def test_coder_prefers_deepseek_over_qwen():
    assert select_model(AgentRole.CODER, [QWEN, DEEPSEEK]) == DEEPSEEK


def test_reviewer_prefers_qwen_over_deepseek():
    assert select_model(AgentRole.REVIEWER, [DEEPSEEK, QWEN]) == QWEN


def test_family_match_survives_requantization():
    """A re-quantized/renamed tag still matches by family."""
    requantized = "deepseek-coder-v2:16b-lite-instruct-q4_K_M"
    assert select_model(AgentRole.CODER, [requantized]) == requantized


def test_explicit_override_exact_match_wins():
    assert select_model(AgentRole.CODER, [DEEPSEEK, QWEN], override=QWEN) == QWEN


def test_explicit_override_substring_match_wins():
    assert select_model(AgentRole.CODER, [DEEPSEEK, QWEN], override="qwen2.5-coder") == QWEN


def test_override_not_installed_falls_back_to_preference():
    assert select_model(AgentRole.CODER, [DEEPSEEK], override="not-installed") == DEEPSEEK


def test_env_override_is_honored(monkeypatch):
    """EVOSEAL_CODER_MODEL is documented as an override -- it must actually work."""
    monkeypatch.setenv("EVOSEAL_CODER_MODEL", QWEN)
    assert select_model(AgentRole.CODER, [DEEPSEEK, QWEN]) == QWEN


def test_reviewer_env_override_is_honored(monkeypatch):
    monkeypatch.setenv("EVOSEAL_REVIEWER_MODEL", DEEPSEEK)
    assert select_model(AgentRole.REVIEWER, [DEEPSEEK, QWEN]) == DEEPSEEK


def test_explicit_override_beats_env_override(monkeypatch):
    monkeypatch.setenv("EVOSEAL_CODER_MODEL", QWEN)
    assert select_model(AgentRole.CODER, [DEEPSEEK, QWEN], override=DEEPSEEK) == DEEPSEEK


def test_env_override_not_installed_falls_back_to_preference(monkeypatch):
    monkeypatch.setenv("EVOSEAL_CODER_MODEL", "never-pulled")
    assert select_model(AgentRole.CODER, [DEEPSEEK]) == DEEPSEEK


def test_blank_env_override_ignored(monkeypatch):
    monkeypatch.setenv("EVOSEAL_CODER_MODEL", "   ")
    assert env_override_for(AgentRole.CODER) is None
    assert select_model(AgentRole.CODER, [DEEPSEEK]) == DEEPSEEK


def test_unsuitable_models_are_not_selected():
    """An embedding model must never be picked to write code."""
    assert select_model(AgentRole.CODER, ["nomic-embed-text:latest"]) is None


def test_no_models_returns_none():
    assert select_model(AgentRole.CODER, []) is None


# -- list_installed_models / caching --------------------------------------


def test_list_installed_models_parses_names(monkeypatch):
    with _fake_ollama(monkeypatch, [DEEPSEEK, QWEN]):
        assert list_installed_models() == [DEEPSEEK, QWEN]


def test_unreachable_ollama_returns_empty(monkeypatch):
    with _fake_ollama(monkeypatch, [], error=urllib.error.URLError("refused")):
        assert list_installed_models() == []


def test_query_is_cached(monkeypatch):
    """Blocking HTTP must not run per call -- it is reached from async code."""
    calls: list[str] = []
    with _fake_ollama(monkeypatch, [DEEPSEEK], calls=calls):
        list_installed_models()
        list_installed_models()
        list_installed_models()
    assert len(calls) == 1


def test_clear_model_cache_forces_requery(monkeypatch):
    calls: list[str] = []
    with _fake_ollama(monkeypatch, [DEEPSEEK], calls=calls):
        list_installed_models()
        clear_model_cache()
        list_installed_models()
    assert len(calls) == 2


def test_cache_returns_a_copy(monkeypatch):
    """Callers must not be able to mutate the cached list."""
    with _fake_ollama(monkeypatch, [DEEPSEEK]):
        first = list_installed_models()
        first.append("mutated")
        assert list_installed_models() == [DEEPSEEK]


# -- resolve_model --------------------------------------------------------


def test_resolve_model_discovers_installed(monkeypatch):
    with _fake_ollama(monkeypatch, [DEEPSEEK, QWEN]):
        assert resolve_model(AgentRole.CODER) == DEEPSEEK
        assert resolve_model(AgentRole.REVIEWER) == QWEN


def test_resolve_model_uses_env_override(monkeypatch):
    monkeypatch.setenv("EVOSEAL_CODER_MODEL", QWEN)
    with _fake_ollama(monkeypatch, [DEEPSEEK, QWEN]):
        assert resolve_model(AgentRole.CODER) == QWEN


def test_resolve_model_falls_back_when_ollama_unreachable(monkeypatch):
    with _fake_ollama(monkeypatch, [], error=urllib.error.URLError("refused")):
        assert resolve_model(AgentRole.CODER) == FALLBACK_ROLE_MODELS[AgentRole.CODER]
        assert resolve_model(AgentRole.REVIEWER) == FALLBACK_ROLE_MODELS[AgentRole.REVIEWER]


def test_resolve_model_falls_back_when_nothing_suitable(monkeypatch):
    with _fake_ollama(monkeypatch, ["nomic-embed-text:latest"]):
        assert resolve_model(AgentRole.CODER) == FALLBACK_ROLE_MODELS[AgentRole.CODER]


def test_resolve_model_accepts_supplied_available_without_querying(monkeypatch):
    calls: list[str] = []
    with _fake_ollama(monkeypatch, [DEEPSEEK], calls=calls):
        assert resolve_model(AgentRole.CODER, available=[QWEN, DEEPSEEK]) == DEEPSEEK
    assert calls == []


def test_resolve_role_models_queries_once(monkeypatch):
    calls: list[str] = []
    with _fake_ollama(monkeypatch, [DEEPSEEK, QWEN], calls=calls):
        resolved = resolve_role_models()
    assert resolved == {AgentRole.CODER: DEEPSEEK, AgentRole.REVIEWER: QWEN}
    assert len(calls) == 1
