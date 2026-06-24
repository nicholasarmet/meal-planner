from pathlib import Path
from unittest.mock import patch
import pytest
from scripts.ingest_recipe import _normalize_with_claude, ingest_from_text
from scripts.models import Recipe

_CLAUDE_JSON = """{
  "title": "Quick Garlic Noodles",
  "source_url": "https://www.seriouseats.com/garlic-noodles",
  "source_name": "Serious Eats",
  "cuisine": ["Asian"],
  "meal_type": ["dinner"],
  "status": "untried",
  "effort": "easy",
  "time_active": 15,
  "time_total": 20,
  "servings": 4,
  "appliances": ["stovetop"],
  "dietary": [],
  "ingredients": ["8 oz noodles", "6 cloves garlic", "2 tbsp butter", "2 tbsp oyster sauce"],
  "instructions": ["Cook noodles.", "Sauté garlic in butter.", "Toss with sauce."],
  "notes": ""
}"""


def test_normalize_parses_claude_json():
    with patch("scripts.ingest_recipe._call_claude", return_value=_CLAUDE_JSON):
        recipe = _normalize_with_claude("raw text", "https://example.com", "Example")
    assert recipe.title == "Quick Garlic Noodles"
    assert recipe.status == "untried"
    assert len(recipe.ingredients) == 4


def test_normalize_handles_fenced_json():
    fenced = f"```json\n{_CLAUDE_JSON}\n```"
    with patch("scripts.ingest_recipe._call_claude", return_value=fenced):
        recipe = _normalize_with_claude("raw text", None, None)
    assert recipe.title == "Quick Garlic Noodles"


def test_normalize_always_sets_status_untried():
    modified = _CLAUDE_JSON.replace('"untried"', '"loved"')
    with patch("scripts.ingest_recipe._call_claude", return_value=modified):
        recipe = _normalize_with_claude("raw text", None, None)
    assert recipe.status == "untried"


def test_ingest_from_text_returns_recipe():
    with patch("scripts.ingest_recipe._call_claude", return_value=_CLAUDE_JSON):
        recipe = ingest_from_text("Some recipe text")
    assert isinstance(recipe, Recipe)
    assert recipe.title == "Quick Garlic Noodles"


def test_ingest_from_text_passes_source_hint():
    with patch("scripts.ingest_recipe._call_claude") as mock:
        mock.return_value = _CLAUDE_JSON
        ingest_from_text("recipe text", source_hint="My Cookbook")
    prompt = mock.call_args[0][0]
    assert "My Cookbook" in prompt
