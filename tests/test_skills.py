import re
from pathlib import Path

SKILLS = Path(__file__).parent.parent / "skills"


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    import yaml
    return yaml.safe_load(m.group(1)) or {}


def test_find_recipe_skill_exists():
    assert (SKILLS / "find-recipe.md").exists()


def test_find_recipe_skill_frontmatter():
    fm = _frontmatter(SKILLS / "find-recipe.md")
    assert fm.get("name") == "find-recipe"
    assert fm.get("description")


def test_find_recipe_skill_has_required_sections():
    text = (SKILLS / "find-recipe.md").read_text()
    assert "## What this skill does" in text
    assert "## Process" in text
    # Must mention vault search before web search
    vault_pos = text.find("vault")
    web_pos = text.find("source")
    assert vault_pos < web_pos, "Vault search must come before web source search"


def test_meal_config_skill_exists():
    assert (SKILLS / "meal-config.md").exists()


def test_meal_config_skill_frontmatter():
    fm = _frontmatter(SKILLS / "meal-config.md")
    assert fm.get("name") == "meal-config"
    assert fm.get("description")


def test_meal_config_skill_has_required_sections():
    text = (SKILLS / "meal-config.md").read_text()
    assert "## What this skill does" in text
    assert "## Process" in text
    # Must mention all editable config keys
    for key in ("dietary_mode", "preferred_cuisines", "weekday_effort_limit",
                "dedicated_lunch_days"):
        assert key in text, f"Missing config key: {key}"
