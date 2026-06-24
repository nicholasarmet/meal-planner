import json
import pytest
from pathlib import Path
from unittest.mock import patch
from scripts.models import Recipe
from scripts.aggregate_grocery import (
    SECTION_ORDER,
    parse_recipe_titles,
    aggregate_ingredients,
    generate_grocery_list,
)


def _r(title: str, ingredients: list[str]) -> Recipe:
    return Recipe(title=title, ingredients=ingredients, meal_type=["dinner"])


_MOCK_RESPONSE = json.dumps({
    "sections": {
        "Produce": ["Garlic — 3 heads", "Ginger — 4-inch knob"],
        "Pantry": ["Soy sauce — 1/4 cup"],
    },
    "check_stock": ["Kosher salt", "Black pepper"],
    "review": [],
})


def test_section_order_exact():
    assert SECTION_ORDER == [
        "Produce", "Pantry", "Snacks", "Cereal", "Frozen Goods",
        "Spices", "Baking Supplies", "Refrigerated", "Dairy", "Cheese & Cured Meats",
    ]


def test_parse_recipe_titles_extracts_links():
    text = (
        "**Dinner:** [[Chicken Adobo]] · Filipino · Easy · 45 min\n"
        "**Dinner:** [[Beef Stew]] · American · Medium · 90 min\n"
    )
    titles = parse_recipe_titles(text)
    assert "Chicken Adobo" in titles
    assert "Beef Stew" in titles


def test_parse_recipe_titles_deduplicates():
    text = "[[Chicken Adobo]]\n[[Chicken Adobo]]"
    assert parse_recipe_titles(text).count("Chicken Adobo") == 1


def test_parse_recipe_titles_empty_for_leftovers():
    text = "**Dinner:** Leftovers — Chicken Adobo"
    assert parse_recipe_titles(text) == []


def test_aggregate_ingredients_combines_all():
    recipes = [
        _r("A", ["2 cups flour", "1 tsp salt"]),
        _r("B", ["3 cloves garlic", "1 cup flour"]),
    ]
    result = aggregate_ingredients(recipes)
    assert "2 cups flour" in result
    assert "1 tsp salt" in result
    assert "3 cloves garlic" in result
    assert "1 cup flour" in result
    assert len(result) == 4


def test_aggregate_ingredients_empty():
    assert aggregate_ingredients([]) == []


def test_generate_grocery_list_writes_file(tmp_path):
    vault = tmp_path / "vault"
    plan_dir = vault / "Meal Plans"
    plan_dir.mkdir(parents=True)
    plan_path = plan_dir / "Week of 2026-06-29.md"
    plan_path.write_text("**Dinner:** [[Chicken Adobo]] · Filipino\n", encoding="utf-8")

    r = _r("Chicken Adobo", ["2 lbs chicken thighs", "1/4 cup soy sauce"])

    with patch("scripts.aggregate_grocery._call_claude", return_value=_MOCK_RESPONSE), \
         patch("scripts.aggregate_grocery.find_recipes", return_value=[r]):
        result = generate_grocery_list(plan_path, vault, config={})

    assert result.exists()
    assert result.name == "2026-06-29.md"
    content = result.read_text()
    assert "# Grocery List — Week of 2026-06-29" in content
    assert "## Produce" in content
    assert "- [ ] Garlic — 3 heads" in content
    assert "## Check Stock" in content
    assert "- [ ] Kosher salt" in content


def test_generate_grocery_list_sections_in_order(tmp_path):
    vault = tmp_path / "vault"
    plan_dir = vault / "Meal Plans"
    plan_dir.mkdir(parents=True)
    plan_path = plan_dir / "Week of 2026-06-29.md"
    plan_path.write_text("**Dinner:** [[Pasta]]\n", encoding="utf-8")

    full_response = json.dumps({
        "sections": {
            "Dairy": ["Butter — 1 stick"],
            "Produce": ["Onion — 1 medium"],
            "Pantry": ["Pasta — 1 lb"],
        },
        "check_stock": [],
        "review": [],
    })
    r = _r("Pasta", ["1 lb pasta"])

    with patch("scripts.aggregate_grocery._call_claude", return_value=full_response), \
         patch("scripts.aggregate_grocery.find_recipes", return_value=[r]):
        result = generate_grocery_list(plan_path, vault, config={})

    content = result.read_text()
    produce_pos = content.index("## Produce")
    pantry_pos = content.index("## Pantry")
    dairy_pos = content.index("## Dairy")
    assert produce_pos < pantry_pos < dairy_pos
