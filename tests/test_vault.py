from pathlib import Path
import pytest
from scripts.models import Recipe
from scripts.vault import find_recipes, load_recipe, save_recipe


def _recipe(**kwargs) -> Recipe:
    defaults = dict(
        title="Test Recipe",
        meal_type=["dinner"],
        status="untried",
        effort="easy",
        servings=4,
        ingredients=["1 cup flour"],
        instructions=["Mix everything"],
    )
    defaults.update(kwargs)
    return Recipe(**defaults)


def test_save_creates_file(tmp_vault):
    path = save_recipe(_recipe(title="Soup"), tmp_vault)
    assert path.exists()
    assert path.suffix == ".md"


def test_save_breakfast_goes_to_breakfast_folder(tmp_vault):
    path = save_recipe(_recipe(title="Pancakes", meal_type=["breakfast"]), tmp_vault)
    assert "Breakfast" in str(path)


def test_save_dinner_goes_to_dinner_folder(tmp_vault):
    path = save_recipe(_recipe(title="Steak", meal_type=["dinner"]), tmp_vault)
    assert "Dinner" in str(path)


def test_load_roundtrip(tmp_vault):
    recipe = _recipe(title="Roundtrip", meal_type=["dinner"], cuisine=["Italian"])
    path = save_recipe(recipe, tmp_vault)
    loaded = load_recipe(path)
    assert loaded.title == "Roundtrip"
    assert "Italian" in loaded.cuisine


def test_find_returns_all(tmp_vault):
    save_recipe(_recipe(title="D1", meal_type=["dinner"]), tmp_vault)
    save_recipe(_recipe(title="D2", meal_type=["dinner"]), tmp_vault)
    save_recipe(_recipe(title="B1", meal_type=["breakfast"]), tmp_vault)
    assert len(find_recipes(tmp_vault)) == 3


def test_find_filters_by_meal_type(tmp_vault):
    save_recipe(_recipe(title="Dinner", meal_type=["dinner"]), tmp_vault)
    save_recipe(_recipe(title="Breakfast", meal_type=["breakfast"]), tmp_vault)
    results = find_recipes(tmp_vault, meal_type="dinner")
    assert len(results) == 1
    assert results[0].title == "Dinner"


def test_find_filters_by_status(tmp_vault):
    save_recipe(_recipe(title="Loved", meal_type=["dinner"], status="loved"), tmp_vault)
    save_recipe(_recipe(title="Untried", meal_type=["dinner"], status="untried"), tmp_vault)
    results = find_recipes(tmp_vault, status="loved")
    assert len(results) == 1
    assert results[0].title == "Loved"


def test_save_sanitizes_filename(tmp_vault):
    path = save_recipe(_recipe(title="Chicken & Rice: Classic!", meal_type=["dinner"]), tmp_vault)
    assert "&" not in path.name
    assert ":" not in path.name
