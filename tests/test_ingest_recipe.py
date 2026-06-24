from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from scripts.ingest_recipe import (
    _is_cf_challenge,
    _normalize_with_claude,
    _fetch_raw,
    ingest_from_text,
    ingest_from_url,
)
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


def test_parse_json_handles_prose_prefix():
    from scripts.ingest_recipe import _parse_json
    text = 'Here is the recipe: {"title": "Tacos", "ingredients": [], "instructions": []}'
    result = _parse_json(text)
    assert result["title"] == "Tacos"


# --- _is_cf_challenge ---

def test_is_cf_challenge_detects_just_a_moment():
    assert _is_cf_challenge("<html>Just a moment...</html>" * 100)


def test_is_cf_challenge_detects_short_page():
    assert _is_cf_challenge("<html>tiny</html>")


def test_is_cf_challenge_passes_real_page():
    assert not _is_cf_challenge("<html>" + "x" * 5000 + "</html>")


# --- _fetch_raw tier selection ---

def test_fetch_raw_uses_recipe_scrapers_when_ingredients_present():
    mock_scraper = MagicMock()
    mock_scraper.ingredients.return_value = ["1 cup flour"]
    mock_scraper.title.return_value = "Cake"
    mock_scraper.instructions_list.return_value = ["Mix."]
    mock_scraper.total_time.return_value = 30
    mock_scraper.yields.return_value = "8 servings"

    with patch("scripts.ingest_recipe.scrape_me" if False else "recipe_scrapers.scrape_me"):
        pass  # scrape_me is imported inside the function

    # Patch at the module level where it's called
    with patch("builtins.__import__", wraps=__import__) as mock_import:
        import recipe_scrapers as rs_module
        with patch.object(rs_module, "scrape_me", return_value=mock_scraper):
            # Need to reload the import inside the function
            pass

    # Direct approach: patch the import inside the function
    import importlib
    import sys
    fake_rs = MagicMock()
    fake_rs.scrape_me.return_value = mock_scraper
    with patch.dict(sys.modules, {"recipe_scrapers": fake_rs}):
        result = _fetch_raw("https://example.com/recipe")
    assert "1 cup flour" in result
    assert "Cake" in result


def test_fetch_raw_falls_through_to_cloudscraper_when_recipe_scrapers_empty():
    mock_scraper = MagicMock()
    mock_scraper.ingredients.return_value = []

    import sys
    fake_rs = MagicMock()
    fake_rs.scrape_me.return_value = mock_scraper

    fake_cs = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = "<html>" + "real content " * 500 + "</html>"
    fake_cs.create_scraper.return_value.get.return_value = fake_resp

    with patch.dict(sys.modules, {"recipe_scrapers": fake_rs, "cloudscraper": fake_cs}):
        result = _fetch_raw("https://example.com/recipe")
    assert "real content" in result


def test_fetch_raw_falls_through_to_playwright_when_cloudscraper_returns_cf_page():
    mock_rs_scraper = MagicMock()
    mock_rs_scraper.ingredients.return_value = []

    import sys
    fake_rs = MagicMock()
    fake_rs.scrape_me.return_value = mock_rs_scraper

    fake_cs = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = "Just a moment..."  # CF challenge
    fake_cs.create_scraper.return_value.get.return_value = fake_resp

    with patch("scripts.ingest_recipe._playwright_fetch", return_value="<html>playwright content</html>") as mock_pw:
        with patch.dict(sys.modules, {"recipe_scrapers": fake_rs, "cloudscraper": fake_cs}):
            result = _fetch_raw("https://example.com/recipe")
    mock_pw.assert_called_once_with("https://example.com/recipe")
    assert result == "<html>playwright content</html>"


def test_ingest_from_url_uses_fetch_raw():
    with patch("scripts.ingest_recipe._fetch_raw", return_value="raw page html"):
        with patch("scripts.ingest_recipe._call_claude", return_value=_CLAUDE_JSON):
            recipe = ingest_from_url("https://www.seriouseats.com/garlic-noodles")
    assert recipe.title == "Quick Garlic Noodles"
    assert recipe.source_name == "seriouseats.com"
