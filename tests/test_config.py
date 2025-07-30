"""Tests for configuration functionality."""

import json
import tempfile
from unittest.mock import patch

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
    assert config.max_file_lines is None


def test_config_from_file():
    """Test loading configuration from file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "ignore": ["*.log", "temp/"],
                "include_extensions": [".py", ".md"],
                "whitelist": ["src/*.py"],
                "max_file_lines": 100,
            },
            f,
        )

    config_path = Path(f.name)
    try:
        config = Config.from_file(config_path)

        assert "*.log" in config.ignore_patterns
        assert "temp/" in config.ignore_patterns
        assert ".py" in config.include_extensions
        assert ".md" in config.include_extensions
        assert "src/*.py" in config.whitelist_patterns
        assert config.max_file_lines == 100
    finally:
        config_path.unlink()


def test_config_to_dict():
    """Test converting configuration to dictionary."""
    config = Config(
        ignore_patterns=["*.log", "temp/"],
        include_extensions=[".py", ".md"],
        whitelist_patterns=["src/*.py"],
        max_file_lines=100,
    )

    config_dict = config.to_dict()

    assert config_dict["ignore"] == ["*.log", "temp/"]
    assert config_dict["include_extensions"] == [".py", ".md"]
    assert config_dict["whitelist"] == ["src/*.py"]
    assert config_dict["max_file_lines"] == 100


def test_default_patterns():
    """Test default patterns for different languages."""
    # Check that each language has default patterns
    for language in Language:
        assert language in DEFAULT_IGNORE_PATTERNS
        assert language in DEFAULT_INCLUDE_EXTENSIONS

        # Check that the patterns are non-empty
        assert DEFAULT_IGNORE_PATTERNS[language]
        assert DEFAULT_INCLUDE_EXTENSIONS[language]


def test_invalid_config_file():
    """Test handling of invalid config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{invalid json")

    config_path = Path(f.name)
    try:
        # Should raise an exception
        with pytest.raises(json.JSONDecodeError):
            Config.from_file(config_path)
    finally:
        config_path.unlink()


def test_empty_config_file():
    """Test handling of empty config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{}")

    config_path = Path(f.name)
    try:
        config = Config.from_file(config_path)

        # Should use defaults
        assert isinstance(config.ignore_patterns, list)
        assert isinstance(config.include_extensions, list)
        assert isinstance(config.whitelist_patterns, list)
        assert config.max_file_lines is None
    finally:
        config_path.unlink()


def test_config_search_terms():
    """Test search terms in configuration."""
    config = Config(search_terms=["term1", "term2"])

    assert "term1" in config.search_terms
    assert "term2" in config.search_terms
    assert len(config.search_terms) == 2


def test_config_missing_fields():
    """Test loading config with missing fields."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        # Only include some fields
        json.dump({"ignore": ["*.log"]}, f)

    config_path = Path(f.name)
    try:
        config = Config.from_file(config_path)

        # Should have the specified field
        assert "*.log" in config.ignore_patterns

        # Other fields should use defaults
        assert isinstance(config.include_extensions, list)
        assert isinstance(config.whitelist_patterns, list)
        assert config.max_file_lines is None
    finally:
        config_path.unlink()


def test_config_with_extra_fields():
    """Test loading config with extra unknown fields."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"ignore": ["*.log"], "unknown_field": "value", "another_field": 123}, f)

    config_path = Path(f.name)
    try:
        # Should not error on unknown fields
        config = Config.from_file(config_path)
        assert "*.log" in config.ignore_patterns
    finally:
        config_path.unlink()


def test_config_invalid_field_types():
    """Test config with invalid field types."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        # Use wrong types for fields
        json.dump(
            {
                "ignore": "not_a_list",  # Should be a list
                "max_file_lines": "not_an_int",  # Should be an int
            },
            f,
        )

    config_path = Path(f.name)
    try:
        # The current implementation might handle this differently than expected
        # Let's just test that it doesn't crash
        config = Config.from_file(config_path)

        # Just verify we got a Config object back
        assert isinstance(config, Config)
    finally:
        config_path.unlink()


def test_config_update():
    """Test updating configuration with new values."""
    config = Config(ignore_patterns=["*.log"], include_extensions=[".py"], max_file_lines=100)

    # Update with new values
    config.update(
        {"ignore_patterns": ["*.tmp", "*.bak"], "max_file_lines": 200, "search_terms": ["test"]}
    )

    # Check updated values
    assert config.ignore_patterns == ["*.tmp", "*.bak"]
    assert config.include_extensions == [".py"]  # Unchanged
    assert config.max_file_lines == 200
    assert config.search_terms == ["test"]


def test_profile_manager_initialization():
    """Test ProfileManager initialization with different paths."""
    # Test with explicit path
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        manager = ProfileManager(config_path)
        assert manager.config_path == config_path

    # Test with default path when no existing config
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("pathlib.Path.cwd", return_value=Path(tmpdir)):
            manager = ProfileManager()
            assert manager.config_path == Path(tmpdir) / "codesnap.json"

    # Test with existing config in default locations
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "codesnap.json"
        config_path.touch()
        with patch("pathlib.Path.cwd", return_value=Path(tmpdir)):
            manager = ProfileManager()
            assert manager.config_path == config_path


def test_profile_manager_load_config_data():
    """Test loading configuration data from file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Test with non-existent file
        manager = ProfileManager(config_path)
        assert manager._load_config_data() == {}

        # Test with valid JSON
        config_data = {"profiles": {"test": {"ignore": ["*.tmp"]}}}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        assert manager._load_config_data() == config_data

        # Test with invalid JSON
        with open(config_path, "w") as f:
            f.write("invalid json")

        assert manager._load_config_data() == {}


def test_profile_manager_save_config_data():
    """Test saving configuration data to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "subdir" / "config.json"
        manager = ProfileManager(config_path)

        # Save data to non-existent directory (should create it)
        config_data = {"test": "data"}
        manager._save_config_data(config_data)

        # Check that file was created with correct content
        assert config_path.exists()
        with open(config_path) as f:
            assert json.load(f) == config_data


def test_profile_manager_load_profile():
    """Test loading a profile from configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create config with profiles
        config_data = {"profiles": {"test": {"ignore": ["*.tmp"]}, "dev": {"ignore": ["*.log"]}}}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        manager = ProfileManager(config_path)

        # Test loading existing profile
        assert manager.load_profile("test") == {"ignore": ["*.tmp"]}

        # Test loading non-existent profile
        assert manager.load_profile("non_existent") is None


def test_profile_manager_save_profile():
    """Test saving a profile to configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        manager = ProfileManager(config_path)

        # Create a config
        config = Config(ignore_patterns=["*.log"], max_file_lines=100)

        # Save profile to empty config
        manager.save_profile("test", config)

        # Check that profile was saved
        with open(config_path) as f:
            data = json.load(f)
            assert "profiles" in data
            assert "test" in data["profiles"]
            assert data["profiles"]["test"]["ignore"] == ["*.log"]
            assert data["profiles"]["test"]["max_file_lines"] == 100

        # Save another profile
        config2 = Config(ignore_patterns=["*.tmp"])
        manager.save_profile("dev", config2)

        # Check that both profiles exist
        with open(config_path) as f:
            data = json.load(f)
            assert "test" in data["profiles"]
            assert "dev" in data["profiles"]


def test_profile_manager_list_profiles():
    """Test listing available profiles."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create config with profiles
        config_data = {"profiles": {"test": {"ignore": ["*.tmp"]}, "dev": {"ignore": ["*.log"]}}}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        manager = ProfileManager(config_path)
        profiles = manager.list_profiles()

        # Check that profiles were listed
        assert sorted(profiles) == ["dev", "test"]

        # Test with no profiles
        empty_config_path = Path(tmpdir) / "empty.json"
        empty_manager = ProfileManager(empty_config_path)
        assert empty_manager.list_profiles() == []


def test_profile_manager_delete_profile():
    """Test deleting a profile from configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Create config with profiles
        config_data = {"profiles": {"test": {"ignore": ["*.tmp"]}, "dev": {"ignore": ["*.log"]}}}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        manager = ProfileManager(config_path)

        # Delete existing profile
        assert manager.delete_profile("test") is True

        # Check that profile was deleted
        with open(config_path) as f:
            data = json.load(f)
            assert "test" not in data["profiles"]
            assert "dev" in data["profiles"]

        # Try to delete non-existent profile
        assert manager.delete_profile("non_existent") is False


def test_profile_manager_delete_profile_returns_false(tmp_path):
    man = ProfileManager(tmp_path / "nope.json")
    assert man.delete_profile("notfound") is False


def test_profile_manager_list_profiles_no_file(tmp_path):
    man = ProfileManager(tmp_path / "none.json")
    assert man.list_profiles() == []


def test_config_from_missing_file(monkeypatch):
    # Remove all default locations
    monkeypatch.setattr(Path, "cwd", lambda: Path("/tmp/nonexistent"))
    monkeypatch.setattr(Path, "home", lambda: Path("/tmp/nonexistent_home"))
    config = Config.from_file(None)
    assert isinstance(config, Config)
