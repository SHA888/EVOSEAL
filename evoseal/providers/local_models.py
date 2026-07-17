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

The installed-model query is cached (see :func:`clear_model_cache`): it is a
blocking HTTP call, and ``resolve_model`` is reached from constructors and from
async code, so re-querying per call would stall the event loop.

Only the standard library is imported here so the module stays cheap and free of
import cycles (it is loaded very early via ``ollama_provider``).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from enum import Enum
from functools import lru_cache

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


@lru_cache(maxsize=8)
def _query_installed_models(base_url: str, timeout: float) -> tuple[str, ...]:
    """Cached Ollama /api/tags query. Returns a tuple so the cache stays immutable."""
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        # Fixed http(s) Ollama endpoint from config, not user input.
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        logger.warning("Could not query Ollama at %s: %s", url, exc)
        return ()
    return tuple(m.get("name", "") for m in payload.get("models", []) if m.get("name"))


def clear_model_cache() -> None:
    """Drop the cached installed-model list (call after pulling a new model)."""
    _query_installed_models.cache_clear()


def list_installed_models(
    base_url: str = DEFAULT_OLLAMA_BASE_URL, timeout: float = 5.0
) -> list[str]:
    """Return the names of models installed in the local Ollama instance.

    The underlying HTTP query is cached (see :func:`clear_model_cache`) because
    this is blocking I/O reached from constructors and from async code.

    Returns an empty list (and logs a warning) if Ollama cannot be reached, so
    callers can fall back gracefully instead of crashing.
    """
    return list(_query_installed_models(base_url, timeout))


def select_model(
    role: AgentRole, available: list[str], *, override: str | None = None
) -> str | None:
    """Pick the best installed model for ``role`` from ``available``.

    Resolution order: explicit ``override`` -> the role's environment override
    (``EVOSEAL_CODER_MODEL`` / ``EVOSEAL_REVIEWER_MODEL``) -> family preferences.
    Each override wins only when it is actually installed (exact or substring
    match). Returns ``None`` when nothing suitable is installed, so the caller can
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
) -> str:
    """Resolve the concrete Ollama model name to use for ``role``.

    Queries Ollama (cached) when ``available`` is not supplied. Honors the role's
    environment override. Falls back to a canonical tag when Ollama is unreachable
    or has no suitable model installed.
    """
    if available is None:
        available = list_installed_models(base_url)

    chosen = select_model(role, available, override=override)
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
) -> dict[AgentRole, str]:
    """Resolve models for several roles with a single Ollama query."""
    overrides = overrides or {}
    available = list_installed_models(base_url)
    return {
        role: resolve_model(
            role, base_url=base_url, override=overrides.get(role), available=available
        )
        for role in roles
    }
