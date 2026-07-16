"""Local (Ollama) model discovery and role resolution for EVOSEAL.

EVOSEAL originally targeted a single fine-tunable ``devstral:latest`` model. On a
CPU-only host (no GPU) weight-level fine-tuning is impractical, so the runnable
path uses two *installed* Ollama models in distinct roles and improves the agents
at the *prompt* level instead of the *weight* level. See
``docs/architecture/local_coevolution.md``.

Rather than hardcoding exact model tags (which break on a re-quantization or
rename), this module **queries Ollama for what is actually installed** and matches
by model *family* (case-insensitive substring). Resolution order per role:

1. An explicit ``override`` (env var / config), if it is installed.
2. The first installed model matching the role's family preferences.
3. Any installed model (with a warning).
4. A last-resort fallback tag (only when Ollama cannot be queried at all).

This keeps the co-evolution loop durable across model swaps: as long as *some*
coder/reviewer-family model is pulled, it will be found and used.

Only the standard library is imported here so the module stays cheap and free of
import cycles (it is loaded very early via ``ollama_provider``).
"""

from __future__ import annotations

import json
import logging
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

#: Last-resort tags used ONLY when Ollama cannot be queried (offline/CI). Runtime
#: resolution always prefers whatever is actually installed over these.
FALLBACK_ROLE_MODELS: dict[AgentRole, str] = {
    AgentRole.CODER: "deepseek-coder-v2:16b-lite-instruct-q8_0",
    AgentRole.REVIEWER: "qwen2.5-coder:7b-instruct-q6_K",
}


def list_installed_models(
    base_url: str = DEFAULT_OLLAMA_BASE_URL, timeout: float = 5.0
) -> list[str]:
    """Return the names of models installed in the local Ollama instance.

    Returns an empty list (and logs a warning) if Ollama cannot be reached, so
    callers can fall back gracefully instead of crashing.
    """
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (local URL)
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        logger.warning("Could not query Ollama at %s: %s", url, exc)
        return []
    return [m.get("name", "") for m in payload.get("models", []) if m.get("name")]


def select_model(
    role: AgentRole, available: list[str], *, override: str | None = None
) -> str | None:
    """Pick the best installed model for ``role`` from ``available``.

    ``override`` wins when it is installed (exact or substring match). Returns
    ``None`` when ``available`` is empty.
    """
    if override:
        if override in available:
            return override
        for name in available:
            if override.lower() in name.lower():
                return name
        logger.warning(
            "Requested %s model %r is not installed; using preference order instead",
            role.value,
            override,
        )

    for family in ROLE_MODEL_PREFERENCES.get(role, ()):
        for name in available:
            if family.lower() in name.lower():
                return name

    if available:
        logger.warning(
            "No preferred %s-family model installed; using first available: %s",
            role.value,
            available[0],
        )
        return available[0]

    return None


def resolve_model(
    role: AgentRole,
    *,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    override: str | None = None,
    available: list[str] | None = None,
) -> str:
    """Resolve the concrete Ollama model name to use for ``role``.

    Queries Ollama when ``available`` is not supplied. Falls back to a canonical
    tag only if nothing can be discovered (Ollama unreachable and no models).
    """
    if available is None:
        available = list_installed_models(base_url)

    chosen = select_model(role, available, override=override)
    if chosen:
        logger.info("Resolved %s model -> %s", role.value, chosen)
        return chosen

    fallback = FALLBACK_ROLE_MODELS.get(role, FALLBACK_ROLE_MODELS[AgentRole.CODER])
    logger.warning("No Ollama models discovered; falling back to %s for %s", fallback, role.value)
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
