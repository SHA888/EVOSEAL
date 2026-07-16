"""Unit tests for the versioned prompt store."""

from __future__ import annotations

import pytest

from evoseal.prompt_evolution import AgentRole, PromptStore


@pytest.fixture
def store(tmp_path):
    return PromptStore(tmp_path / "prompts")


def test_seed_creates_first_version(store):
    version = store.seed(AgentRole.CODER, "# ROLE: coder\nWrite good code.")
    assert version.version_id.startswith("coder-v1")
    assert version.parent_id is None
    assert store.get_active(AgentRole.CODER).version_id == version.version_id


def test_seed_is_idempotent(store):
    first = store.seed(AgentRole.CODER, "prompt one")
    second = store.seed(AgentRole.CODER, "prompt two (ignored)")
    assert first.version_id == second.version_id
    assert store.get_active(AgentRole.CODER).prompt_text == "prompt one"


def test_register_sets_parent_and_active(store):
    v1 = store.seed(AgentRole.CODER, "v1 prompt")
    v2 = store.register(AgentRole.CODER, "v2 prompt", rationale="improve")
    assert v2.parent_id == v1.version_id
    assert store.get_active(AgentRole.CODER).version_id == v2.version_id
    assert {v.version_id for v in store.list_versions(AgentRole.CODER)} == {
        v1.version_id,
        v2.version_id,
    }


def test_register_empty_prompt_rejected(store):
    with pytest.raises(ValueError):
        store.register(AgentRole.CODER, "   ")


def test_rollback_reverts_to_parent(store):
    v1 = store.seed(AgentRole.CODER, "v1 prompt")
    v2 = store.register(AgentRole.CODER, "v2 prompt")
    assert store.get_active(AgentRole.CODER).version_id == v2.version_id

    now_active = store.rollback(AgentRole.CODER)
    assert now_active.version_id == v1.version_id
    assert store.get_active(AgentRole.CODER).version_id == v1.version_id


def test_rollback_at_root_is_noop(store):
    v1 = store.seed(AgentRole.CODER, "only version")
    result = store.rollback(AgentRole.CODER)
    assert result.version_id == v1.version_id


def test_set_active_unknown_version_raises(store):
    store.seed(AgentRole.CODER, "v1")
    with pytest.raises(KeyError):
        store.set_active(AgentRole.CODER, "does-not-exist")


def test_versions_are_isolated_per_role(store):
    store.seed(AgentRole.CODER, "coder prompt")
    store.seed(AgentRole.REVIEWER, "reviewer prompt")
    assert store.get_active(AgentRole.CODER).prompt_text == "coder prompt"
    assert store.get_active(AgentRole.REVIEWER).prompt_text == "reviewer prompt"


def test_persistence_across_instances(tmp_path):
    base = tmp_path / "prompts"
    store_a = PromptStore(base)
    v1 = store_a.seed(AgentRole.CODER, "persisted prompt")

    store_b = PromptStore(base)
    active = store_b.get_active(AgentRole.CODER)
    assert active is not None
    assert active.version_id == v1.version_id
    assert active.prompt_text == "persisted prompt"
