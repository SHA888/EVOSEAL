"""Versioned, on-disk storage of per-role system prompts with rollback.

Mirrors the design of :mod:`evoseal.fine_tuning.version_manager` (a JSON registry
plus per-version artifacts) but for *prompts* instead of model weights. Each role
(``coder``, ``reviewer``, ``main``) has:

    <base_dir>/<role>/registry.json         # active pointer + version metadata
    <base_dir>/<role>/versions/<id>.md      # the prompt text for each version

Lineage (``parent_id``) makes rollback a pointer move, never a destructive delete,
which matches EVOSEAL's "validate or roll back" safety premise.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from evoseal.providers.local_models import AgentRole

from .models import PromptVersion

logger = logging.getLogger(__name__)


def _role_value(role: AgentRole | str) -> str:
    return role.value if isinstance(role, AgentRole) else str(role)


class PromptStore:
    """Store and version system prompts per agent role."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else Path("data/prompt_evolution")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # -- paths ---------------------------------------------------------------

    def _role_dir(self, role: AgentRole | str) -> Path:
        path = self.base_dir / _role_value(role)
        (path / "versions").mkdir(parents=True, exist_ok=True)
        return path

    def _registry_path(self, role: AgentRole | str) -> Path:
        return self._role_dir(role) / "registry.json"

    def _prompt_path(self, role: AgentRole | str, version_id: str) -> Path:
        return self._role_dir(role) / "versions" / f"{version_id}.md"

    # -- registry io ---------------------------------------------------------

    def _load_registry(self, role: AgentRole | str) -> dict[str, Any]:
        path = self._registry_path(role)
        if not path.exists():
            return {"active": None, "versions": {}}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Corrupt prompt registry %s: %s; starting fresh", path, exc)
            return {"active": None, "versions": {}}

    def _save_registry(self, role: AgentRole | str, registry: dict[str, Any]) -> None:
        """Write the registry atomically.

        The registry is what rollback depends on, so it must never be left
        half-written: serialize first, write to a temp file in the same
        directory, then os.replace() (atomic on POSIX and Windows).
        """
        path = self._registry_path(role)
        payload = json.dumps(registry, indent=2, default=str)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

    # -- public api ----------------------------------------------------------

    def register(
        self,
        role: AgentRole | str,
        prompt_text: str,
        *,
        parent_id: str | None = None,
        rationale: str = "",
        score: float | None = None,
        metrics: dict[str, Any] | None = None,
        make_active: bool = True,
    ) -> PromptVersion:
        """Persist a new prompt version and (by default) make it active."""
        if not prompt_text or not prompt_text.strip():
            raise ValueError("Cannot register an empty prompt")

        registry = self._load_registry(role)
        # An explicitly supplied parent must reference a real version; a dangling
        # parent_id would break rollback lineage. (None falls back to the active id.)
        if parent_id is not None and parent_id not in registry["versions"]:
            raise KeyError(f"Unknown parent version: {parent_id}")
        role_name = _role_value(role)
        # Monotonic counter rather than len(versions): if a version is ever pruned
        # the length drops and ids could collide with an existing one (the
        # timestamp only has second granularity). Older registries lack the key.
        seq = int(registry.get("next_seq") or len(registry["versions"]) + 1)
        version_id = f"{role_name}-v{seq}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        version = PromptVersion(
            version_id=version_id,
            role=role_name,
            prompt_text=prompt_text,
            parent_id=parent_id if parent_id is not None else registry.get("active"),
            rationale=rationale,
            score=score,
            metrics=metrics or {},
        )

        self._prompt_path(role, version_id).write_text(prompt_text, encoding="utf-8")
        meta = version.to_dict()
        meta.pop("prompt_text")  # text lives in the .md file, not the registry
        registry["versions"][version_id] = meta
        registry["next_seq"] = seq + 1
        if make_active:
            registry["active"] = version_id
        self._save_registry(role, registry)

        logger.info("Registered prompt %s (parent=%s)", version_id, version.parent_id)
        return version

    def seed(
        self, role: AgentRole | str, prompt_text: str, *, rationale: str = "seed"
    ) -> PromptVersion:
        """Register ``prompt_text`` as the initial version iff none exists yet."""
        active = self.get_active(role)
        if active is not None:
            return active
        return self.register(role, prompt_text, rationale=rationale)

    def get_version(self, role: AgentRole | str, version_id: str) -> PromptVersion | None:
        registry = self._load_registry(role)
        meta = registry["versions"].get(version_id)
        if meta is None:
            return None
        prompt_path = self._prompt_path(role, version_id)
        prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
        return PromptVersion.from_dict({**meta, "prompt_text": prompt_text})

    def get_active(self, role: AgentRole | str) -> PromptVersion | None:
        registry = self._load_registry(role)
        active_id = registry.get("active")
        if not active_id:
            return None
        return self.get_version(role, active_id)

    def set_active(self, role: AgentRole | str, version_id: str) -> PromptVersion:
        registry = self._load_registry(role)
        if version_id not in registry["versions"]:
            raise KeyError(f"Unknown prompt version: {version_id}")
        registry["active"] = version_id
        self._save_registry(role, registry)
        logger.info("Active prompt for %s -> %s", _role_value(role), version_id)
        version = self.get_version(role, version_id)
        assert version is not None
        return version

    def rollback(self, role: AgentRole | str) -> PromptVersion | None:
        """Revert the active prompt to its parent. Returns the now-active version."""
        active = self.get_active(role)
        if active is None or not active.parent_id:
            logger.warning("No parent to roll back to for %s", _role_value(role))
            return active
        return self.set_active(role, active.parent_id)

    def list_versions(self, role: AgentRole | str) -> list[PromptVersion]:
        registry = self._load_registry(role)
        versions = [self.get_version(role, vid) for vid in registry["versions"]]  # noqa: E501
        return [v for v in versions if v is not None]
