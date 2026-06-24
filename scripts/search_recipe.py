from __future__ import annotations

from ddgs import DDGS

_SOURCE_DOMAINS: dict[str, str] = {
    "serious-eats": "seriouseats.com",
    "nom-nom-paleo": "nomnompaleo.com",
    "bon-appetit": "bonappetit.com",
    "milk-street": "177milkstreet.com",
    "nyt-cooking": "cooking.nytimes.com",
    "cooks-country": "cookscountry.com",
    "cooks-illustrated": "cooksillustrated.com",
    "atk": "americastestkitchen.com",
    "king-arthur-baking": "kingarthurbaking.com",
    "allrecipes": "allrecipes.com",
    "simply-recipes": "simplyrecipes.com",
    "food52": "food52.com",
    "epicurious": "epicurious.com",
    "skinnytaste": "skinnytaste.com",
    "half-baked-harvest": "halfbakedharvest.com",
}


def source_to_domain(slug: str) -> str | None:
    return _SOURCE_DOMAINS.get(slug.lower())


def search_recipe_urls(
    query: str,
    preferred_sources: list[str] | None = None,
    max_results: int = 8,
) -> list[str]:
    """Return deduplicated recipe URLs from DuckDuckGo.

    Searches preferred sources first (site-scoped queries), then falls back
    to a general search so the caller always gets something to try.
    """
    seen: set[str] = set()
    urls: list[str] = []

    def _collect(q: str, n: int) -> None:
        try:
            for hit in DDGS().text(q, max_results=n):
                url = hit.get("href", "")
                if url.startswith("http") and url not in seen:
                    seen.add(url)
                    urls.append(url)
        except Exception:
            pass

    base_query = query if "recipe" in query.lower() else f"{query} recipe"

    if preferred_sources:
        domains = [source_to_domain(s) for s in preferred_sources if source_to_domain(s)]
        for domain in domains:
            _collect(f"{base_query} site:{domain}", 3)
            if len(urls) >= max_results:
                break

    if len(urls) < max_results:
        _collect(base_query, max_results - len(urls))

    return urls
