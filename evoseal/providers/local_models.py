"""Local (Ollama) model discovery and role resolution for EVOSEAL.

EVOSEAL originally targeted a single fine-tunable ``devstral:latest`` model. On a
CPU-only host (no GPU) weight-level fine-tuning is impractical, so the runnable
path uses two *installed* Ollama models in distinct roles and improves the agents
at the *prompt* level instead of the *weight* level. See
``docs/architecture/local_coevolution.md``.

Rather than hardcoding exact model tags (which break on a re-quantization or
rename), this module **queries Ollama for what is actually installed** and matches
by model *family* (case-insensitive substring). Resolution order per role:

1. An explicit ``override`` argument, if it is installed.
2. The role's environment override (``EVOSEAL_CODER_MODEL`` /
   ``EVOSEAL_REVIEWER_MODEL``), if it is installed.
3. The first installed model matching the role's family preferences.
4. A last-resort fallback tag (Ollama unreachable, or nothing suitable installed).

This keeps the co-evolution loop durable across model swaps: as long as *some*
coder/reviewer-family model is pulled, it will be found and used.

The installed-model query is cached with a TTL (see :data:`_CACHE_TTL_SECONDS` and
:func:`clear_model_cache`): it is a blocking HTTP call, and ``resolve_model`` is
reached from constructors and from async code, so re-querying per call would stall
the event loop.  Cached entries expire automatically after the TTL so a newly
pulled or removed model is discovered without manual intervention.

Only the standard library is imported here so the module stays cheap and free of
import cycles (it is loaded very early via ``ollama_provider``).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from enum import Enum

logger = logging.getLogger(__name__)

#: Default Ollama endpoint (native API, not the ``/v1`` OpenAI-compat shim).
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


class AgentRole(str, Enum):
    """Roles that participate in the local co-evolution loop."""

    #: Writes code for a task (prefers a DeepSeek-Coder-family model).
    CODER = "coder"
    #: Reviews / evaluates the coder's output (prefers a Qwen-Coder-family model).
    REVIEWER = "reviewer"
    #: General orchestrator/assistant (cloud model; prompt-only self-improvement).
    MAIN = "main"


#: Ordered family preferences matched (case-insensitive substring) against the
#: set of *installed* Ollama tags. Broad fallbacks ("-coder", "code") come last so
#: any coding model is still preferred over a generic chat model.
ROLE_MODEL_PREFERENCES: dict[AgentRole, tuple[str, ...]] = {
    AgentRole.CODER: (
        "deepseek-coder",
        "qwen2.5-coder",
        "codellama",
        "starcoder",
        "codegemma",
        "-coder",
        "code",
    ),
    AgentRole.REVIEWER: (
        "qwen2.5-coder",
        "deepseek-coder",
        "codellama",
        "starcoder",
        "-coder",
        "code",
    ),
}

#: Last-resort tags used when Ollama cannot be queried (offline/CI) or has no
#: suitable model. Runtime resolution always prefers what is actually installed.
FALLBACK_ROLE_MODELS: dict[AgentRole, str] = {
    AgentRole.CODER: "deepseek-coder-v2:16b-lite-instruct-q8_0",
    AgentRole.REVIEWER: "qwen2.5-coder:7b-instruct-q6_K",
}

#: Environment variable that pins the model for a role, bypassing preferences.
ROLE_ENV_OVERRIDES: dict[AgentRole, str] = {
    AgentRole.CODER: "EVOSEAL_CODER_MODEL",
    AgentRole.REVIEWER: "EVOSEAL_REVIEWER_MODEL",
}


def env_override_for(role: AgentRole) -> str | None:
    """Return the role's environment override (e.g. ``EVOSEAL_CODER_MODEL``)."""
    var = ROLE_ENV_OVERRIDES.get(role)
    if not var:
        return None
    value = os.environ.get(var, "").strip()
    return value or None


#: Seconds before a cached model-list entry is considered stale and re-queried.
#: A pull or remove between calls will be picked up within this window.
_CACHE_TTL_SECONDS: float = 120.0

#: TTL for cached failure results (shorter than success TTL so we retry sooner
#: after an outage, but long enough to prevent a flood of connection attempts).
_FAILURE_TTL_SECONDS: float = 60.0

# { (base_url, timeout): (monotonic_timestamp, last_access, result_tuple) }
# Bounded to avoid unbounded growth when callers pass varying timeout values.
# ``last_access`` is refreshed on every cache hit so eviction can prefer
# least-recently-used entries rather than just oldest-written.
_model_cache: dict[tuple[str, float], tuple[float, float, tuple[str, ...]]] = {}
_model_cache_lock: threading.Lock = threading.Lock()
# Per-key events used to coalesce concurrent requests for the same key.
# Only one thread performs the blocking HTTP call; others wait and reuse
# the cached result.  This is the key difference from the old ``lru_cache``
# which serialized the whole function — here we serialize per key only when
# there is an actual cache miss.
_in_flight: dict[tuple[str, float], threading.Event] = {}
_MAX_CACHE_SIZE: int = 64


def _query_installed_models(base_url: str, timeout: float) -> tuple[str, ...]:
    """Cached Ollama /api/tags query with TTL-based expiry.

    Returns a tuple so the cache stays immutable.  Entries older than
    :data:`_CACHE_TTL_SECONDS` are silently re-queried.

    Concurrent callers for the same ``(base_url, timeout)`` key are coalesced:
    only one thread performs the blocking HTTP query while the others wait and
    reuse the result.  This matches the old ``lru_cache`` serialization guarantee
    but without blocking callers that use *different* keys.
    """
    # Normalize timeout to 1 decimal place so callers passing 5.0 and 5.01
    # share the same cache entry instead of growing the dict unboundedly.
    # Normalize base_url the same way the request URL is built so that
    # "http://host:11434" and "http://host:11434/" share one cache entry.
    key = (base_url.rstrip("/"), round(timeout, 1))
    now = time.monotonic()
    with _model_cache_lock:
        cached = _model_cache.get(key)
        if cached is not None:
            ts, _last_access, result = cached
            if now - ts < _CACHE_TTL_SECONDS:
                # Refresh access time for LRU eviction.
                _model_cache[key] = (ts, now, result)
                return result

        # Cache miss (or stale).  Check whether another thread is already
        # fetching this key.
        event = _in_flight.get(key)
        if event is not None:
            # Another thread is in-flight — wait for it, then re-check cache.
            lock = _model_cache_lock
            lock.release()
            try:
                event.wait()
            finally:
                lock.acquire()
            cached = _model_cache.get(key)
            if cached is not None:
                ts, _last_access, result = cached
                _model_cache[key] = (ts, now, result)
                return result
            # If still missing (e.g. clear_model_cache ran), fall through.

        # We are the fetching thread for this key.
        event = threading.Event()
        _in_flight[key] = event

    # Perform the blocking HTTP call without holding the global lock so that
    # callers for *different* keys are not serialized against us.
    url = f"{key[0]}/api/tags"
    try:
        # Fixed http(s) Ollama endpoint from config, not user input.
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        logger.warning("Could not query Ollama at %s: %s", url, exc)
        # Cache failures so a down Ollama doesn't generate a flood of
        # connection attempts, but with a shorter TTL than successes.
        # Always cache an empty result on failure — never reuse a stale
        # *success* entry, which would silently mask an outage.
        _cache_write(key, now, (), failure=True)
        event.set()
        with _model_cache_lock:
            _in_flight.pop(key, None)
        return ()
    result = tuple(m.get("name", "") for m in payload.get("models", []) if m.get("name"))
    _cache_write(key, now, result)
    event.set()
    with _model_cache_lock:
        _in_flight.pop(key, None)
    return result


def _cache_write(
    key: tuple[str, float],
    now: float,
    result: tuple[str, ...],
    *,
    failure: bool = False,
) -> None:
    """Write to ``_model_cache`` with eviction and TTL bookkeeping.

    When *failure* is ``True`` the entry is backdated so it expires after
    :data:`_FAILURE_TTL_SECONDS` instead of :data:`_CACHE_TTL_SECONDS`.

    Protected by :data:`_model_cache_lock` for thread safety — this module
    is reached from constructors and from async code (via thread-pool).
    """
    with _model_cache_lock:
        if len(_model_cache) >= _MAX_CACHE_SIZE and key not in _model_cache:
            # Evict the least-recently-accessed entry to keep the dict
            # bounded.  ``_last_access`` is refreshed on every read so a
            # frequently-hit entry survives even if it was written long ago.
            lru_key = min(_model_cache, key=lambda k: _model_cache[k][1])
            del _model_cache[lru_key]
        if failure:
            # Backdate so the entry expires after _FAILURE_TTL_SECONDS.
            ts = now - _CACHE_TTL_SECONDS + _FAILURE_TTL_SECONDS
        else:
            ts = now
        _model_cache[key] = (ts, now, result)


def clear_model_cache() -> None:
    """Drop the cached installed-model list (call after pulling a new model)."""
    with _model_cache_lock:
        _model_cache.clear()


def list_installed_models(
    base_url: str = DEFAULT_OLLAMA_BASE_URL, timeout: float = 5.0
) -> list[str]:
    """Return the names of models installed in the local Ollama instance.

    The underlying HTTP query is cached with a TTL (see :data:`_CACHE_TTL_SECONDS`
    and :func:`clear_model_cache`) because this is blocking I/O reached from
    constructors and from async code.

    Returns an empty list (and logs a warning) if Ollama cannot be reached, so
    callers can fall back gracefully instead of crashing.
    """
    return list(_query_installed_models(base_url, timeout))


def select_model(
    role: AgentRole,
    available: list[str],
    *,
    override: str | None = None,
    registry_model: str | None = None,
) -> str | None:
    """Pick the best installed model for ``role`` from ``available``.

    Resolution order: explicit ``override`` -> the role's environment override
    (``EVOSEAL_CODER_MODEL`` / ``EVOSEAL_REVIEWER_MODEL``) -> fine-tuning
    registry (``registry_model``) -> family preferences.

    Each override wins only when it is actually installed (exact or substring
    match).  ``registry_model`` is the Ollama model name of the currently
    deployed fine-tuned model from :class:`ModelVersionManager` — when
    provided and installed it is preferred over raw family-based discovery so
    the generation loop actually uses the fine-tuned weights.

    Returns ``None`` when nothing suitable is installed, so the caller can
    fall back to a known-good tag rather than pick an arbitrary model: an
    embedding model, say, must never be selected to write code.
    """
    for candidate, source in ((override, "argument"), (env_override_for(role), "env")):
        if not candidate:
            continue
        if candidate in available:
            return candidate
        for name in available:
            if candidate.lower() in name.lower():
                return name
        logger.warning(
            "Requested %s model %r (%s) is not installed; using preference order instead",
            role.value,
            candidate,
            source,
        )

    # Prefer the fine-tuned model from the version registry when it is
    # actually installed in Ollama.  This is the key wiring that makes the
    # bidirectional co-evolution loop close: the generator consults the
    # registry instead of only looking at raw installed tags.
    if registry_model:
        registry_lower = registry_model.lower()
        role_families = ROLE_MODEL_PREFERENCES.get(role, ())

        def _family_ok(name_lower: str) -> bool:
            """Return True if *name_lower* belongs to this role's families.

            When *role_families* is empty (e.g. MAIN has no preferences)
            the match is rejected rather than silently bypassing the guard.
            """
            if not role_families:
                return False
            return any(fam.lower() in name_lower for fam in role_families)

        # Two-pass matching: prefer an exact tag match over a substring
        # match so that e.g. ``deepseek-coder-finetuned:v2`` is not
        # shadowed by a similarly-named ``deepseek-coder-finetuned:v2-old``
        # that happens to appear earlier in the installed list.
        substring_candidate: str | None = None
        for name in available:
            name_lower = name.lower()
            if name_lower == registry_lower:
                if _family_ok(name_lower):
                    logger.info(
                        "Using registry-deployed model %s for role %s",
                        name,
                        role.value,
                    )
                    return name
                # Exact match but wrong family — still record as a
                # candidate so we can warn rather than silently fall
                # through.
                logger.warning(
                    "Registry model %s matches installed tag %s but does "
                    "not belong to role %s families; skipping",
                    registry_model,
                    name,
                    role.value,
                )
            elif substring_candidate is None and registry_lower in name_lower:
                # Remember the first substring match; keep scanning for
                # an exact match that may appear later.
                if _family_ok(name_lower):
                    substring_candidate = name

        if substring_candidate is not None:
            logger.info(
                "Using registry-deployed model %s (matched %s) for role %s",
                substring_candidate,
                registry_model,
                role.value,
            )
            return substring_candidate

        logger.warning(
            "Registry model %r is not installed or not suitable for role %s; "
            "falling back to family discovery",
            registry_model,
            role.value,
        )

    for family in ROLE_MODEL_PREFERENCES.get(role, ()):
        for name in available:
            if family.lower() in name.lower():
                return name

    return None


def resolve_model(
    role: AgentRole,
    *,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    override: str | None = None,
    available: list[str] | None = None,
    registry_model: str | None = None,
) -> str:
    """Resolve the concrete Ollama model name to use for ``role``.

    Queries Ollama (cached) when ``available`` is not supplied. Honors the role's
    environment override. When *registry_model* is given (the Ollama tag of the
    currently deployed fine-tuned model from the version registry) it is preferred
    over raw family-based discovery. Falls back to a canonical tag when Ollama is
    unreachable or has no suitable model installed.
    """
    if available is None:
        available = list_installed_models(base_url)

    chosen = select_model(role, available, override=override, registry_model=registry_model)
    if chosen:
        logger.info("Resolved %s model -> %s", role.value, chosen)
        return chosen

    fallback = FALLBACK_ROLE_MODELS.get(role, FALLBACK_ROLE_MODELS[AgentRole.CODER])
    logger.warning(
        "No suitable %s model installed (available: %s); falling back to %s",
        role.value,
        available or "none",
        fallback,
    )
    return fallback


def resolve_role_models(
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    overrides: dict[AgentRole, str] | None = None,
    roles: tuple[AgentRole, ...] = (AgentRole.CODER, AgentRole.REVIEWER),
    registry_models: dict[AgentRole, str] | None = None,
) -> dict[AgentRole, str]:
    """Resolve models for several roles with a single Ollama query."""
    overrides = overrides or {}
    registry_models = registry_models or {}
    available = list_installed_models(base_url)
    return {
        role: resolve_model(
            role,
            base_url=base_url,
            override=overrides.get(role),
            available=available,
            registry_model=registry_models.get(role),
        )
        for role in roles
    }
