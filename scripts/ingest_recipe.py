from __future__ import annotations
import argparse, json, os, re, sys
from pathlib import Path
from urllib.parse import urlparse

import anthropic
import requests
from dotenv import load_dotenv

from scripts.config import get_vault_path, load_config
from scripts.models import Recipe
from scripts.vault import save_recipe

load_dotenv()

_MODEL = "claude-sonnet-4-6"

_PROMPT = """You are a recipe parser. Extract the recipe from the text below and return ONLY a JSON object with these exact fields:

{{
  "title": string,
  "source_url": string or null,
  "source_name": string or null,
  "cuisine": list[string],
  "meal_type": list[string]  — one or more of: breakfast, lunch, dinner, baking,
  "status": "untried",
  "effort": "easy" | "medium" | "hard",
  "time_active": integer (minutes) or null,
  "time_total": integer (minutes) or null,
  "servings": integer,
  "appliances": list[string]  — from: stovetop, oven, instant-pot, breville, stand-mixer, hand-mixer, immersion-blender,
  "dietary": list[string]  — from: gluten-free, paleo, whole30, dairy-free (only if clearly compatible),
  "ingredients": list[string]  (one item per element, include quantity and unit),
  "instructions": list[string]  (one step per element, no leading numbers),
  "notes": string
}}

Source URL: {source_url}
Source name: {source_name}

Recipe text:
{text}

Return ONLY the JSON object."""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\n(.*?)\n```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise ValueError(f"Could not parse JSON from Claude response: {text[:200]}")


def _normalize_with_claude(raw: str, source_url: str | None, source_name: str | None) -> Recipe:
    prompt = _PROMPT.format(
        text=raw,
        source_url=source_url or "unknown",
        source_name=source_name or "unknown",
    )
    data = _parse_json(_call_claude(prompt))
    return Recipe(
        title=data.get("title", "Untitled"),
        source_url=source_url or data.get("source_url"),
        source_name=source_name or data.get("source_name"),
        cuisine=data.get("cuisine") or [],
        meal_type=data.get("meal_type") or ["dinner"],
        status="untried",  # always untried on ingest
        effort=data.get("effort", "medium"),
        time_active=data.get("time_active"),
        time_total=data.get("time_total"),
        servings=data.get("servings", 4),
        appliances=data.get("appliances") or [],
        dietary=data.get("dietary") or [],
        ingredients=data.get("ingredients") or [],
        instructions=data.get("instructions") or [],
        notes=data.get("notes") or "",
    )


def _is_cf_challenge(html: str) -> bool:
    lower = html.lower()
    return (
        "just a moment" in lower
        or "cf-browser-verification" in lower
        or "enable javascript and cookies" in lower
        or len(html) < 3000
    )


def _playwright_fetch(url: str) -> str:
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            # inner_text extracts only visible text — avoids sending full HTML to Claude
            return page.inner_text("body")
        finally:
            browser.close()


def _fetch_raw(url: str) -> str:
    # Tier 1: recipe_scrapers — structured, fast, works for most sites
    try:
        from recipe_scrapers import scrape_me
        s = scrape_me(url)
        ingredients = s.ingredients()
        if ingredients:
            return (
                f"Title: {s.title()}\nIngredients:\n"
                + "\n".join(ingredients)
                + f"\nInstructions:\n"
                + "\n".join(s.instructions_list())
                + f"\nTotal time: {s.total_time()} min\nYields: {s.yields()}"
            )
    except Exception:
        pass

    # Tier 2: cloudscraper — handles basic Cloudflare challenges
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=15)
        if resp.status_code == 200 and not _is_cf_challenge(resp.text):
            return resp.text
    except Exception:
        pass

    # Tier 3: Playwright + stealth — full JS execution for aggressive CF protection
    return _playwright_fetch(url)


def ingest_from_url(url: str) -> Recipe:
    source_name = urlparse(url).netloc.replace("www.", "")
    raw = _fetch_raw(url)
    return _normalize_with_claude(raw, url, source_name)


def ingest_from_pdf(pdf_path: Path) -> Recipe:
    import pdfplumber
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return _normalize_with_claude("\n".join(parts), None, pdf_path.stem)


def ingest_from_text(text: str, source_hint: str = "") -> Recipe:
    return _normalize_with_claude(text, None, source_hint or None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ingest a recipe from URL or PDF")
    ap.add_argument("source", help="URL or path to PDF")
    ap.add_argument("--config", help="Path to config.yaml")
    args = ap.parse_args()
    config = load_config(args.config)
    vault_path = get_vault_path(config)
    if args.source.startswith("http://") or args.source.startswith("https://"):
        recipe = ingest_from_url(args.source)
    else:
        recipe = ingest_from_pdf(Path(args.source))
    path = save_recipe(recipe, vault_path)
    print(f"Saved: {recipe.title} → {path}")
