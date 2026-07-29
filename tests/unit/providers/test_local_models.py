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


def test_cache_expires_after_ttl(monkeypatch):
    """A stale cache entry triggers a fresh HTTP query."""
    calls: list[str] = []
    with _fake_ollama(monkeypatch, [DEEPSEEK, QWEN], calls=calls):
        list_installed_models()
        assert len(calls) == 1
        # Simulate TTL expiry by advancing the monotonic clock.
        import time

        original_monotonic = time.monotonic
        monkeypatch.setattr(time, "monotonic", lambda: original_monotonic() + 999)
        list_installed_models()
        assert len(calls) == 2


def test_cache_returns_a_copy(monkeypatch):
    """Callers must not be able to mutate the cached list."""
    with _fake_ollama(monkeypatch, [DEEPSEEK]):
        first = list_installed_models()
        first.append("mutated")
        assert list_installed_models() == [DEEPSEEK]


def test_failure_result_is_cached(monkeypatch):
    """A failed query must cache its result to prevent request floods."""
    calls: list[str] = []
    with _fake_ollama(monkeypatch, [], calls=calls, error=urllib.error.URLError("refused")):
        list_installed_models()  # 1st call: fails, should cache the failure
        list_installed_models()  # 2nd call: should use cached failure
        list_installed_models()  # 3rd call: should use cached failure
    assert len(calls) == 1


def test_failure_with_no_prior_cache_is_cached(monkeypatch):
    """First-ever call that fails must still cache the empty result."""
    calls: list[str] = []
    with _fake_ollama(monkeypatch, [], calls=calls, error=urllib.error.URLError("refused")):
        assert list_installed_models() == []
        assert list_installed_models() == []
    assert len(calls) == 1


def test_failure_cache_uses_shorter_ttl(monkeypatch):
    """Failure cache entries expire sooner than success entries."""
    from evoseal.providers.local_models import _CACHE_TTL_SECONDS, _FAILURE_TTL_SECONDS

    assert _FAILURE_TTL_SECONDS < _CACHE_TTL_SECONDS

    calls: list[str] = []
    with _fake_ollama(monkeypatch, [], calls=calls, error=urllib.error.URLError("refused")):
        list_installed_models()
        assert len(calls) == 1
        # Advance past the failure TTL but not past the success TTL.
        import time

        original_monotonic = time.monotonic
        monkeypatch.setattr(
            time, "monotonic", lambda: original_monotonic() + _FAILURE_TTL_SECONDS + 1
        )
        list_installed_models()  # Should retry since failure TTL expired
        assert len(calls) == 2


def test_success_then_expiry_then_failure_returns_empty(monkeypatch):
    """Success → TTL expiry → failure must return empty, not stale models."""
    calls: list[str] = []
    # First call: Ollama is up, returns models.
    with _fake_ollama(monkeypatch, [DEEPSEEK, QWEN], calls=calls):
        result = list_installed_models()
        assert result == [DEEPSEEK, QWEN]
        assert len(calls) == 1

    import time

    original_monotonic = time.monotonic
    # Advance past the success TTL so the cache entry is stale.
    monkeypatch.setattr(time, "monotonic", lambda: original_monotonic() + 999)

    # Second call: Ollama is down.  Must return empty, not the stale models.
    with _fake_ollama(monkeypatch, [], calls=calls, error=urllib.error.URLError("refused")):
        result = list_installed_models()
        assert result == [], f"Expected empty on outage, got {result}"
        assert len(calls) == 2


def test_cache_is_bounded(monkeypatch):
    """_model_cache does not grow without bound."""
    from evoseal.providers.local_models import _MAX_CACHE_SIZE, _model_cache

    calls: list[str] = []
    with _fake_ollama(monkeypatch, [DEEPSEEK], calls=calls):
        # Fill the cache with entries using different keys.
        for i in range(_MAX_CACHE_SIZE + 10):
            list_installed_models(timeout=1.0 + i * 0.1)
        assert len(_model_cache) <= _MAX_CACHE_SIZE


def test_malformed_response_returns_empty(monkeypatch):
    """A non-dict JSON response must not crash — returns empty list."""

    class _BadPayloadResponse:
        def read(self):
            return json.dumps(["not", "a", "dict"]).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _urlopen_bad(url, timeout=None):
        return _BadPayloadResponse()

    monkeypatch.setattr(local_models.urllib.request, "urlopen", _urlopen_bad)
    assert list_installed_models() == []


def test_models_list_with_non_dict_entries_returns_empty(monkeypatch):
    """A response where 'models' contains non-dict entries must not crash."""

    class _BadModelsResponse:
        def read(self):
            return json.dumps({"models": ["string", 42, None]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _urlopen_bad(url, timeout=None):
        return _BadModelsResponse()

    monkeypatch.setattr(local_models.urllib.request, "urlopen", _urlopen_bad)
    assert list_installed_models() == []


def test_http_exception_returns_empty(monkeypatch):
    """http.client.HTTPException (e.g. IncompleteRead) is handled gracefully."""
    import http.client

    with _fake_ollama(monkeypatch, [], error=http.client.IncompleteRead(partial=b"", expected=100)):
        assert list_installed_models() == []


def test_failure_ttl_invariant_enforced():
    """Module asserts _FAILURE_TTL_SECONDS < _CACHE_TTL_SECONDS at import time."""
    from evoseal.providers.local_models import _CACHE_TTL_SECONDS, _FAILURE_TTL_SECONDS

    assert _FAILURE_TTL_SECONDS < _CACHE_TTL_SECONDS


def test_concurrent_calls_coalesce(monkeypatch):
    """Multiple threads for the same key must fire only one HTTP request."""
    import threading
    import time as _time

    calls: list[str] = []
    # Barrier ensures all 4 threads are ready before any checks the cache.
    ready_barrier = threading.Barrier(4, timeout=5)

    class _SlowResponse:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _slow_urlopen(url, timeout=None):
        calls.append(url)
        # Simulate slow network so the fetching thread doesn't complete
        # before the others have a chance to check the cache.
        _time.sleep(0.2)
        return _SlowResponse({"models": [{"name": DEEPSEEK}]})

    monkeypatch.setattr(local_models.urllib.request, "urlopen", _slow_urlopen)

    results: list[list[str]] = [[] for _ in range(4)]

    def worker(idx):
        # Wait for all threads to be ready so they all see a cache miss.
        ready_barrier.wait()
        results[idx] = list_installed_models()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    # Only one thread should have performed the HTTP call.
    assert len(calls) == 1, f"Expected 1 HTTP call, got {len(calls)}"
    # All threads must get the correct result.
    for r in results:
        assert r == [DEEPSEEK]


def test_trailing_slash_normalized_in_cache_key(monkeypatch):
    """'http://host:11434' and 'http://host:11434/' share one cache entry."""
    calls: list[str] = []
    with _fake_ollama(monkeypatch, [DEEPSEEK], calls=calls):
        list_installed_models(base_url="http://localhost:11434")
        list_installed_models(base_url="http://localhost:11434/")
    assert len(calls) == 1, f"Expected 1 call, got {len(calls)}"


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


# -- registry_model (fine-tuning registry integration) -------------------


FINETUNED = "deepseek-coder-finetuned:v2"


def test_select_model_prefers_registry_over_family():
    """Registry-deployed model beats family-based discovery."""
    # When the fine-tuned model is NOT installed, family discovery still works.
    assert select_model(AgentRole.CODER, [DEEPSEEK, QWEN], registry_model=FINETUNED) == DEEPSEEK
    # When the fine-tuned model is installed, it wins over family.
    assert (
        select_model(AgentRole.CODER, [DEEPSEEK, QWEN, FINETUNED], registry_model=FINETUNED)
        == FINETUNED
    )


def test_select_model_registry_substring_match():
    """Registry model matches by substring against installed tags."""
    installed_tag = "deepseek-coder-finetuned:v2-quantized"
    assert (
        select_model(AgentRole.CODER, [DEEPSEEK, installed_tag], registry_model=FINETUNED)
        == installed_tag
    )


def test_select_model_registry_exact_beats_substring():
    """An exact tag match is preferred over a substring match that appears earlier."""
    stale_tag = "deepseek-coder-finetuned:v2-old"
    exact_tag = "deepseek-coder-finetuned:v2"
    # stale (substring) match appears first — exact match must still win.
    assert (
        select_model(AgentRole.CODER, [stale_tag, exact_tag], registry_model=FINETUNED) == exact_tag
    )
    # exact match appears first — still works.
    assert (
        select_model(AgentRole.CODER, [exact_tag, stale_tag], registry_model=FINETUNED) == exact_tag
    )


def test_select_model_override_beats_registry():
    """Explicit override still takes priority over registry model."""
    assert (
        select_model(
            AgentRole.CODER,
            [DEEPSEEK, QWEN, FINETUNED],
            override=QWEN,
            registry_model=FINETUNED,
        )
        == QWEN
    )


def test_select_model_env_override_beats_registry(monkeypatch):
    """Environment override still takes priority over registry model."""
    monkeypatch.setenv("EVOSEAL_CODER_MODEL", QWEN)
    assert (
        select_model(AgentRole.CODER, [DEEPSEEK, QWEN, FINETUNED], registry_model=FINETUNED) == QWEN
    )


def test_select_model_registry_not_installed_falls_through():
    """When the registry model is not installed, family discovery runs."""
    assert (
        select_model(AgentRole.CODER, [DEEPSEEK, QWEN], registry_model="not-installed:latest")
        == DEEPSEEK
    )


def test_select_model_registry_rejects_wrong_role():
    """Registry model matching a tag outside the role's families is skipped."""
    embedding_tag = "nomic-embed-text:latest"
    # The tag exists but is not a CODER-family model — must not be returned.
    assert (
        select_model(AgentRole.CODER, [DEEPSEEK, embedding_tag], registry_model=embedding_tag)
        == DEEPSEEK
    )


def test_resolve_model_uses_registry_model(monkeypatch):
    """resolve_model threads registry_model through to select_model."""
    with _fake_ollama(monkeypatch, [DEEPSEEK, QWEN, FINETUNED]):
        assert resolve_model(AgentRole.CODER, registry_model=FINETUNED) == FINETUNED


def test_resolve_role_models_threads_registry(monkeypatch):
    """resolve_role_models passes per-role registry models."""
    with _fake_ollama(monkeypatch, [DEEPSEEK, QWEN, FINETUNED]):
        resolved = resolve_role_models(registry_models={AgentRole.CODER: FINETUNED})
    assert resolved == {AgentRole.CODER: FINETUNED, AgentRole.REVIEWER: QWEN}
