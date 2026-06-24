from unittest.mock import MagicMock, patch
from scripts.search_recipe import search_recipe_urls, source_to_domain


def test_source_to_domain_known():
    assert source_to_domain("serious-eats") == "seriouseats.com"
    assert source_to_domain("nom-nom-paleo") == "nomnompaleo.com"
    assert source_to_domain("king-arthur-baking") == "kingarthurbaking.com"


def test_source_to_domain_unknown_returns_none():
    assert source_to_domain("some-unknown-blog") is None


def _make_hits(*urls):
    return [{"href": u, "title": "Recipe", "body": "..."} for u in urls]


def _mock_ddgs(side_effect=None, return_value=None):
    instance = MagicMock()
    if side_effect is not None:
        instance.text.side_effect = side_effect
    else:
        instance.text.return_value = return_value or []
    return MagicMock(return_value=instance)


def test_search_recipe_urls_returns_preferred_sources_first():
    preferred_hits = _make_hits(
        "https://seriouseats.com/garlic-noodles",
        "https://nomnompaleo.com/some-dish",
    )
    general_hits = _make_hits(
        "https://allrecipes.com/recipe/123",
        "https://seriouseats.com/garlic-noodles",  # duplicate — should be dropped
    )

    def fake_text(query, max_results=5):
        return preferred_hits if "site:" in query else general_hits

    with patch("scripts.search_recipe.DDGS", _mock_ddgs(side_effect=fake_text)):
        urls = search_recipe_urls("garlic noodles", preferred_sources=["serious-eats", "nom-nom-paleo"])

    assert urls[0] == "https://seriouseats.com/garlic-noodles"
    assert urls.count("https://seriouseats.com/garlic-noodles") == 1
    assert "https://allrecipes.com/recipe/123" in urls


def test_search_recipe_urls_no_preferred_sources():
    hits = _make_hits("https://allrecipes.com/recipe/1", "https://food52.com/recipe/2")
    with patch("scripts.search_recipe.DDGS", _mock_ddgs(return_value=hits)):
        urls = search_recipe_urls("quick pasta")

    assert "https://allrecipes.com/recipe/1" in urls
    assert "https://food52.com/recipe/2" in urls


def test_search_recipe_urls_appends_recipe_to_query_if_missing():
    mock_cls = _mock_ddgs(return_value=[])
    with patch("scripts.search_recipe.DDGS", mock_cls):
        search_recipe_urls("chicken soup")

    all_queries = [str(c) for c in mock_cls.return_value.text.call_args_list]
    assert any("recipe" in q for q in all_queries)


def test_search_recipe_urls_ddgs_exception_returns_empty():
    with patch("scripts.search_recipe.DDGS", _mock_ddgs(side_effect=Exception("network error"))):
        urls = search_recipe_urls("chicken soup")

    assert urls == []
