from pathlib import Path

PROJECT = Path(__file__).parent.parent


def test_service_file_exists():
    assert (PROJECT / "systemd" / "meal-planner.service").exists()


def test_service_file_has_required_keys():
    text = (PROJECT / "systemd" / "meal-planner.service").read_text()
    assert "[Unit]" in text
    assert "[Service]" in text
    assert "[Install]" in text
    assert "ExecStart=" in text
    assert "WorkingDirectory=" in text
    assert "EnvironmentFile=" in text
    assert "Restart=on-failure" in text
    assert "recipe_server.py" in text


def test_ios_bridge_doc_exists():
    assert (PROJECT / "docs" / "setup" / "ios-bridge.md").exists()


def test_ios_bridge_doc_covers_required_topics():
    text = (PROJECT / "docs" / "setup" / "ios-bridge.md").read_text()
    assert "cloudflared" in text
    assert "X-API-Key" in text
    assert "5050" in text
    assert "iOS Shortcut" in text or "Shortcuts" in text
    assert "/add-recipe" in text
