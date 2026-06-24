from __future__ import annotations
import re
from pathlib import Path

from scripts.models import Recipe

_FOLDER_MAP = {
    "breakfast": "Recipes/Breakfast",
    "lunch": "Recipes/Lunch",
    "dinner": "Recipes/Dinner",
    "baking": "Recipes/Baking",
    "snack": "Recipes/Snacks",
}


def _sanitize(title: str) -> str:
    s = re.sub(r"[^\w\s-]", "", title)
    s = re.sub(r"\s+", "-", s.strip())
    return s[:100]


def save_recipe(recipe: Recipe, vault_path: Path) -> Path:
    key = (recipe.meal_type[0].lower() if recipe.meal_type else "dinner")
    folder = _FOLDER_MAP.get(key, "Recipes/Dinner")
    dest = vault_path / folder
    dest.mkdir(parents=True, exist_ok=True)
    base = _sanitize(recipe.title)
    path = dest / (base + ".md")
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
