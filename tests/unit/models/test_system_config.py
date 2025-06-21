import os
import tempfile

import pytest
import yaml

from evoseal.models.system_config import SystemConfig


def test_from_yaml_and_validate():
    config = {
        "dgm": {},
        "openevolve": {},
        "seal": {},
        "integration": {"foo": 1},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.dump(config, f)
        yaml_path = f.name
    try:
        sys_config = SystemConfig.from_yaml(yaml_path)
        assert sys_config.validate() is True
    finally:
        os.remove(yaml_path)


TEST_VALUE = 123
DEFAULT_VALUE = 42


def test_get_dot_notation():
    config = {"a": {"b": {"c": TEST_VALUE}}, "x": 1}
    sys_config = SystemConfig(config)
    assert sys_config.get("a.b.c") == TEST_VALUE
    assert sys_config.get("x") == 1
    assert sys_config.get("missing", DEFAULT_VALUE) == DEFAULT_VALUE
    assert sys_config.get("a.b.missing", "foo") == "foo"


def test_validate_missing_keys():
    config = {"dgm": {}, "seal": {}}
    sys_config = SystemConfig(config)
    with pytest.raises(ValueError) as e:
        sys_config.validate()
    assert "Missing required configuration section" in str(e.value)
