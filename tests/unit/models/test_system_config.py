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


def test_from_yaml_empty_file_raises():
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write("")
        yaml_path = f.name
    try:
        with pytest.raises(ValueError, match="did not produce a mapping"):
            SystemConfig.from_yaml(yaml_path)
    finally:
        os.remove(yaml_path)


def test_from_yaml_scalar_raises():
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write("just a string")
        yaml_path = f.name
    try:
        with pytest.raises(ValueError, match="did not produce a mapping"):
            SystemConfig.from_yaml(yaml_path)
    finally:
        os.remove(yaml_path)


def test_from_yaml_list_raises():
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.dump([1, 2, 3], f)
        yaml_path = f.name
    try:
        with pytest.raises(ValueError, match="did not produce a mapping"):
            SystemConfig.from_yaml(yaml_path)
    finally:
        os.remove(yaml_path)


def test_from_yaml_malformed_syntax_raises():
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        # Invalid YAML: bad indentation triggers yaml.YAMLError
        f.write("key:\n  - item\n bad_indent")
        yaml_path = f.name
    try:
        with pytest.raises(ValueError, match="invalid YAML syntax"):
            SystemConfig.from_yaml(yaml_path)
    finally:
        os.remove(yaml_path)


# --- Regression tests for config validation edge cases ---


def test_from_yaml_file_not_found():
    """from_yaml raises FileNotFoundError for a nonexistent path."""
    with pytest.raises(FileNotFoundError, match="not found"):
        SystemConfig.from_yaml("/nonexistent/path/config.yaml")


def test_from_yaml_comments_only_raises():
    """A YAML file with only comments parses as None → rejected as non-mapping."""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write("# just a comment\n# another comment\n")
        yaml_path = f.name
    try:
        with pytest.raises(ValueError, match="did not produce a mapping"):
            SystemConfig.from_yaml(yaml_path)
    finally:
        os.remove(yaml_path)


def test_validate_with_none_values_for_required_keys():
    """Required keys present but set to None should still validate (section exists)."""
    config = {"dgm": None, "openevolve": None, "seal": None, "integration": None}
    sys_config = SystemConfig(config)
    assert sys_config.validate() is True


def test_validate_extra_keys_accepted():
    """Extra keys beyond REQUIRED_KEYS should not cause validation failure."""
    config = {
        "dgm": {},
        "openevolve": {},
        "seal": {},
        "integration": {},
        "custom_section": {"foo": 1},
        "another": [1, 2, 3],
    }
    sys_config = SystemConfig(config)
    assert sys_config.validate() is True


def test_get_through_non_dict_intermediate_returns_default():
    """Dot-notation access through a non-dict intermediate value returns default."""
    config = {"a": "a_string_value"}
    sys_config = SystemConfig(config)
    # "a" exists but is a string, not a dict — accessing "a.b" should return default
    assert sys_config.get("a.b", "fallback") == "fallback"


def test_get_with_numeric_key_in_path():
    """Dot notation with numeric-looking string keys works correctly."""
    config = {"port": 8080, "servers": {"0": {"host": "localhost"}}}
    sys_config = SystemConfig(config)
    assert sys_config.get("port") == 8080
    assert sys_config.get("servers.0.host") == "localhost"


def test_get_none_value_vs_missing():
    """An explicitly-set None value is returned; a missing key returns the default."""
    config = {"key": None}
    sys_config = SystemConfig(config)
    assert sys_config.get("key") is None
    assert sys_config.get("key", "default") is None  # key exists, value is None
    assert sys_config.get("missing", "default") == "default"  # key absent


def test_validate_multiple_missing_sections():
    """Multiple missing sections are all reported in the error message."""
    config = {"dgm": {}}
    sys_config = SystemConfig(config)
    with pytest.raises(ValueError) as e:
        sys_config.validate()
    msg = str(e.value)
    for section in ["openevolve", "seal", "integration"]:
        assert section in msg


def test_from_yaml_deeply_nested_config():
    """A deeply nested but valid YAML config loads and dot-notation traverses it."""
    config = {
        "dgm": {"settings": {"mutation": {"rate": 0.1, "strategy": "uniform"}}},
        "openevolve": {},
        "seal": {},
        "integration": {},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.dump(config, f)
        yaml_path = f.name
    try:
        sys_config = SystemConfig.from_yaml(yaml_path)
        assert sys_config.validate() is True
        assert sys_config.get("dgm.settings.mutation.rate") == 0.1
        assert sys_config.get("dgm.settings.mutation.strategy") == "uniform"
        assert sys_config.get("dgm.settings.mutation.unknown", "x") == "x"
    finally:
        os.remove(yaml_path)
