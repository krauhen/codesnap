"""Tests for configuration functionality (aligned with simplified codesnap.config)."""

import json
import tempfile
import pytest
from pathlib import Path

from codesnap.config import (
    Config,
    Language,
    DEFAULT_IGNORE_PATTERNS,
    DEFAULT_INCLUDE_EXTENSIONS,
    ProfileManager,
)


def test_config_defaults():
    """Test default configuration values."""
    config = Config()
    assert isinstance(config.ignore_patterns, list)
    assert isinstance(config.include_extensions, list)
    assert isinstance(config.whitelist_patterns, list)
    assert isinstance(config.exclude_patterns, list)
    assert config.max_file_lines is None
    assert config.max_line_length is None


def test_config_from_file(tmp_path):
    """Test loading configuration from file."""
    data = {
        "ignore": ["*.log", "temp/"],
        "include_extensions": [".py", ".md"],
        "whitelist": ["src/*.py"],
        "exclude": ["tests/"],
        "max_file_lines": 100,
        "max_line_length": 80,
        "search_terms": ["foo"],
    }
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(data))

    cfg = Config.from_file(cfg_path)

    assert "*.log" in cfg.ignore_patterns
    assert ".py" in cfg.include_extensions
    assert "src/*.py" in cfg.whitelist_patterns
    assert "tests/" in cfg.exclude_patterns
    assert cfg.max_file_lines == 100
    assert cfg.max_line_length == 80
    assert "foo" in cfg.search_terms


def test_config_to_dict_and_update():
    """Test converting config to dict and updating."""
    config = Config(ignore_patterns=["*.log"], max_file_lines=100)
    dct = config.to_dict()
    assert dct["ignore"] == ["*.log"]
    assert dct["max_file_lines"] == 100

    # Update
    config.update({"ignore_patterns": ["*.tmp"], "search_terms": ["bar"]})
    assert config.ignore_patterns == ["*.tmp"]
    assert "bar" in config.search_terms


def test_default_patterns():
    """Test default patterns for different languages exist and are non-empty."""
    for lang in Language:
        assert lang in DEFAULT_IGNORE_PATTERNS
        assert lang in DEFAULT_INCLUDE_EXTENSIONS
        assert DEFAULT_IGNORE_PATTERNS[lang]
        assert DEFAULT_INCLUDE_EXTENSIONS[lang]


def test_invalid_config_file(tmp_path):
    """Test handling of invalid config file raises JSON error."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{invalid}")
    with pytest.raises(json.JSONDecodeError):
        Config.from_file(bad_file)


def test_config_from_missing_file_returns_default():
    """Test when no file is found, returns default config."""
    cfg = Config.from_file(None)
    assert isinstance(cfg, Config)


def test_profile_manager_save_and_load(tmp_path):
    """Test saving, loading, listing, and deleting profiles."""
    cfg = Config(ignore_patterns=["*.log"])
    pm = ProfileManager(tmp_path / "profiles.json")

    # Save profile
    pm.save_profile("test", cfg)

    # Load it
    loaded = pm.load_profile("test")
    assert loaded["ignore"] == ["*.log"]

    # List profiles
    profiles = pm.list_profiles()
    assert "test" in profiles

    # Delete it
    assert pm.delete_profile("test") is True
    assert pm.delete_profile("missing") is False


def test_profile_manager_list_profiles_empty(tmp_path):
    """An empty config file should yield [] profiles."""
    pm = ProfileManager(tmp_path / "none.json")
    assert pm.list_profiles() == []
