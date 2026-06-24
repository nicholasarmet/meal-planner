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
    recipe = Recipe(
        title="Test Recipe",
        source_url="https://example.com",
        source_name="Example Site",
        cuisine=["Italian"],
        meal_type=["dinner"],
        status="loved",
        effort="hard",
        time_active=30,
        time_total=90,
        servings=6,
        appliances=["oven", "stovetop"],
        dietary=["gluten-free"],
        last_made="2026-01-15",
        rating=5,
        ingredients=["1 cup flour", "2 eggs"],
        instructions=["Mix", "Bake"],
        notes="This is a great recipe.\n## Storage\nKeep refrigerated.",
    )
    restored = Recipe.from_markdown(recipe.to_markdown())
    assert restored.title == recipe.title
    assert restored.source_url == recipe.source_url
    assert restored.source_name == recipe.source_name
    assert restored.cuisine == recipe.cuisine
    assert restored.meal_type == recipe.meal_type
    assert restored.status == recipe.status
    assert restored.effort == recipe.effort
    assert restored.time_active == recipe.time_active
    assert restored.time_total == recipe.time_total
    assert restored.servings == recipe.servings
    assert restored.appliances == recipe.appliances
    assert restored.dietary == recipe.dietary
    assert restored.last_made == recipe.last_made
    assert restored.rating == recipe.rating
    assert restored.ingredients == recipe.ingredients
    assert restored.instructions == recipe.instructions
    assert restored.notes == recipe.notes


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
