from __future__ import annotations
import re
from pathlib import Path

from scripts.models import Recipe


def _title_words(title: str) -> set[str]:
    return set(re.sub(r"[^\w\s]", "", title.lower()).split())


def _is_duplicate(recipe: Recipe, vault_path: Path) -> Path | None:
    """Return path of an existing recipe that is substantially the same, or None."""
    root = vault_path / "Recipes"
    if not root.exists():
        return None
    new_words = _title_words(recipe.title)
    for md in root.rglob("*.md"):
        try:
            existing = load_recipe(md)
        except Exception:
            continue
        # Exact source URL match
        if recipe.source_url and existing.source_url and recipe.source_url == existing.source_url:
            return md
        # Same source domain + highly similar title (≥75% word overlap by Jaccard)
        if recipe.source_name and existing.source_name and recipe.source_name == existing.source_name:
            ex_words = _title_words(existing.title)
            if new_words and ex_words:
                overlap = len(new_words & ex_words) / len(new_words | ex_words)
                if overlap >= 0.75:
                    return md
    return None

_FOLDER_MAP = {
    "breakfast": "Recipes/Breakfast",
    "lunch": "Recipes/Lunch",
    "dinner": "Recipes/Dinner",
    "baking": "Recipes/Baking",
    "snack": "Recipes/Snacks",
    "side": "Recipes/Sides",
    "drink": "Recipes/Drinks",
    "dessert": "Recipes/Desserts",
}


def _sanitize(title: str) -> str:
    s = re.sub(r"[^\w\s-]", "", title)
    s = re.sub(r"\s+", "-", s.strip())
    return s[:100]


def save_recipe(recipe: Recipe, vault_path: Path) -> Path:
    existing = _is_duplicate(recipe, vault_path)
    if existing:
        print(f"[vault] duplicate detected, skipping save: '{recipe.title}' matches '{existing.name}'")
        return existing

    key = (recipe.meal_type[0].lower() if recipe.meal_type else "dinner")
    folder = _FOLDER_MAP.get(key, "Recipes/Dinner")
    dest = vault_path / folder
    dest.mkdir(parents=True, exist_ok=True)
    base = _sanitize(recipe.title)
    path = dest / (base + ".md")
    if path.exists() and recipe.source_name:
        source_slug = _sanitize(recipe.source_name.replace(".", ""))
        path = dest / (f"{base}-{source_slug}.md")
    counter = 2
    while path.exists():
        path = dest / (f"{base}-{counter}.md")
        counter += 1
    path.write_text(recipe.to_markdown(), encoding="utf-8")
    return path


def load_recipe(path: Path) -> Recipe:
    return Recipe.from_markdown(path.read_text(encoding="utf-8"))


def find_recipes(
    vault_path: Path,
    meal_type: str | None = None,
    status: str | None = None,
) -> list[Recipe]:
    root = vault_path / "Recipes"
    if not root.exists():
        return []
    results = []
    for md in root.rglob("*.md"):
        try:
            r = load_recipe(md)
        except Exception:
            continue
        if meal_type and meal_type.lower() not in [m.lower() for m in r.meal_type]:
            continue
        if status and r.status != status:
            continue
        results.append(r)
    return results
