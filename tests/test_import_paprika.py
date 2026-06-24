from pathlib import Path
from scripts.import_paprika import paprika_to_recipe, parse_paprika_export

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_returns_two_recipes():
    recipes = parse_paprika_export(FIXTURES / "sample.paprikarecipes")
    assert len(recipes) == 2


def test_parse_has_required_fields():
    recipes = parse_paprika_export(FIXTURES / "sample.paprikarecipes")
    assert "name" in recipes[0]
    assert "ingredients" in recipes[0]
    assert "directions" in recipes[0]


def test_tried_and_tested_sets_tried_status():
    raw = {"name": "R", "ingredients": "1 cup flour", "directions": "1. Mix.",
           "categories": ["Tried and Tested"], "rating": 5, "source": "", "source_url": "", "notes": ""}
    assert paprika_to_recipe(raw).status == "tried"


def test_no_category_sets_untried_status():
    raw = {"name": "R", "ingredients": "1 cup water", "directions": "1. Boil.",
           "categories": [], "rating": 0, "source": "", "source_url": "", "notes": ""}
    assert paprika_to_recipe(raw).status == "untried"


def test_nonzero_rating_is_preserved():
    raw = {"name": "R", "ingredients": "1 lb beef", "directions": "1. Cook.",
           "categories": [], "rating": 4, "source": "", "source_url": "", "notes": ""}
    assert paprika_to_recipe(raw).rating == 4


def test_zero_rating_maps_to_none():
    raw = {"name": "R", "ingredients": "1 egg", "directions": "1. Fry.",
           "categories": [], "rating": 0, "source": "", "source_url": "", "notes": ""}
    assert paprika_to_recipe(raw).rating is None


def test_multiline_ingredients_parsed_as_list():
    raw = {"name": "R", "ingredients": "2 lbs chicken\n1 cup soy sauce\n3 cloves garlic",
           "directions": "1. Cook.", "categories": [], "rating": 0, "source": "", "source_url": "", "notes": ""}
    r = paprika_to_recipe(raw)
    assert len(r.ingredients) == 3
    assert "2 lbs chicken" in r.ingredients


def test_numbered_directions_stripped():
    raw = {"name": "R", "ingredients": "1 egg", "directions": "1. Fry the egg.\n2. Plate it.",
           "categories": [], "rating": 0, "source": "", "source_url": "", "notes": ""}
    r = paprika_to_recipe(raw)
    assert r.instructions[0] == "Fry the egg."
    assert r.instructions[1] == "Plate it."
