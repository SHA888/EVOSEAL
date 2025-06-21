import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../openevolve/openevolve/prompt")
    ),
)
from templates import TemplateManager

TEST_TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__), "../../../evoseal/prompt_templates/dgm"
)


def test_loads_templates_and_metadata():
    tm = TemplateManager(TEST_TEMPLATE_DIR)
    keys = tm.list_templates()
    assert "diagnose_improvement_prompt" in keys
    meta = tm.get_metadata("diagnose_improvement_prompt")
    assert meta["category"] == "evaluation"
    assert int(meta["version"]) == 1
    assert "description" in meta


def test_lookup_by_category():
    tm = TemplateManager(TEST_TEMPLATE_DIR)
    cat = tm.get_by_category("self-improvement")
    assert "self_improvement_prompt_emptypatches" in cat
    assert "self_improvement_prompt_stochasticity" in cat


def test_lookup_by_version():
    tm = TemplateManager(TEST_TEMPLATE_DIR)
    # Only v1 exists, but API should work
    prompt = tm.get_template("diagnose_improvement_prompt", version=1)
    assert "{md_log}" in prompt


def test_backward_compat():
    tm = TemplateManager(TEST_TEMPLATE_DIR)
    # Should still work for default OpenEvolve keys
    assert "diff_user" in tm.templates
    assert isinstance(tm.get_template("diff_user"), str)


MIN_TEMPLATE_LENGTH = 10


@pytest.mark.parametrize(
    "key",
    [
        "diagnose_improvement_prompt",
        "tooluse_prompt",
        "self_improvement_instructions",
        "testrepo_test_command",
    ],
)
def test_template_content(key):
    tm = TemplateManager(TEST_TEMPLATE_DIR)
    template = tm.get_template(key)
    assert isinstance(template, str)
    assert len(template) > MIN_TEMPLATE_LENGTH
