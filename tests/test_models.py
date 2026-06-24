from pathlib import Path
from scripts.models import Recipe

FIXTURES = Path(__file__).parent / "fixtures"


def test_from_markdown_parses_frontmatter():
    recipe = Recipe.from_markdown((FIXTURES / "sample_recipe.md").read_text())
    assert recipe.title == "Chicken Adobo"
    assert recipe.status == "untried"
    assert recipe.effort == "easy"
    assert recipe.time_active == 20
    assert recipe.time_total == 45
    assert recipe.servings == 4
    assert "Filipino" in recipe.cuisine
    assert "Asian" in recipe.cuisine
    assert "dinner" in recipe.meal_type
    assert "stovetop" in recipe.appliances
    assert "gluten-free" in recipe.dietary
    assert recipe.rating is None
    assert recipe.last_made is None


def test_from_markdown_parses_ingredients():
    recipe = Recipe.from_markdown((FIXTURES / "sample_recipe.md").read_text())
    assert len(recipe.ingredients) == 6
    assert "2 lbs chicken thighs" in recipe.ingredients


def test_from_markdown_parses_instructions():
    recipe = Recipe.from_markdown((FIXTURES / "sample_recipe.md").read_text())
    assert len(recipe.instructions) == 5
    assert recipe.instructions[0].startswith("Combine chicken")


def test_roundtrip_preserves_all_fields():
    original = Recipe.from_markdown((FIXTURES / "sample_recipe.md").read_text())
    restored = Recipe.from_markdown(original.to_markdown())
    assert original.title == restored.title
    assert original.ingredients == restored.ingredients
    assert original.instructions == restored.instructions
    assert original.cuisine == restored.cuisine
    assert original.dietary == restored.dietary


def test_to_markdown_includes_all_sections():
    recipe = Recipe.from_markdown((FIXTURES / "sample_recipe.md").read_text())
    output = recipe.to_markdown()
    assert "## Ingredients" in output
    assert "## Instructions" in output
    assert "## Notes" in output
    assert "title:" in output


def test_valid_status_values():
    recipe = Recipe.from_markdown((FIXTURES / "sample_recipe.md").read_text())
    assert recipe.status in {"loved", "tried", "untried"}
