from pathlib import Path
import pytest
from scripts.config import load_config, get_vault_path

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_config_reads_yaml():
    config = load_config(str(FIXTURES / "test_config.yaml"))
    assert config["dietary_mode"] == "normal"
    assert config["adults"] == 2
    assert config["child"] is True


def test_load_config_has_sources():
    config = load_config(str(FIXTURES / "test_config.yaml"))
    assert "serious-eats" in config["sources"]


def test_load_config_has_preferences():
    config = load_config(str(FIXTURES / "test_config.yaml"))
    assert "tomato" in config["preferences"]["avoid_raw"]


def test_get_vault_path_returns_path():
    config = load_config(str(FIXTURES / "test_config.yaml"))
    assert get_vault_path(config) == Path("/tmp/test-vault")


def test_load_config_raises_on_missing_vault_path(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("dietary_mode: normal\n")
    with pytest.raises(ValueError, match="vault_path"):
        load_config(str(bad))
