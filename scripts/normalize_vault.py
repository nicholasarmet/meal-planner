"""Batch-normalize Paprika-imported dinner recipes.

For each recipe in Recipes/Dinner/:
  - Determines whether it is a complete, well-rounded dinner
  - Corrects cuisine, effort, time_active, time_total
  - Moves non-complete-meals to Recipes/Sides/

Usage:
    python -m scripts.normalize_vault [--config PATH] [--dry-run]
"""
from __future__ import annotations

import argparse, json, os, re
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from scripts.config import load_config, get_vault_path
from scripts.models import Recipe
from scripts.vault import load_recipe, save_recipe

load_dotenv()

_MODEL = "claude-haiku-4-5-20251001"
_BATCH = 15

_SYSTEM = """You are a recipe classifier and metadata validator.

For each recipe, decide:
1. Is it a COMPLETE DINNER? A complete dinner is a well-rounded meal — either a one-pot/one-pan meal OR a protein-centred dish with built-in components (vegetables, sauce, starch).

MEAT RULE: If a recipe contains any meat (chicken, beef, pork, lamb, turkey, duck, sausage, bacon, ham, veal, venison, bison, or any other animal flesh), classify it as a complete dinner UNLESS it is clearly a salad or slaw (category: "lunch") or a condiment/sauce made with meat (category: "side").

NOT complete dinner: salad dressings, sauces, condiments, drinks, single vegetables or grains with no protein, rice/grain preparation techniques, dips, chips, nuts.

2. If complete dinner: correct cuisine (list), effort, time_active (min), time_total (min).
3. If not complete dinner: what category? (side, lunch, sauce, drink, snack, technique)

Effort rubric:
- easy: one pan/pot, ≤8 steps, ≤45 min total
- medium: multiple methods or 9–14 steps or 45–60 min
- hard: 15+ steps OR advance prep required OR >60 min with other complexity

Return a JSON ARRAY — one object per recipe, same order as input:
[
  {
    "title": "exact title",
    "is_complete_meal": true,
    "cuisine": ["Thai"],
    "effort": "medium",
    "time_active": 20,
    "time_total": 45
  },
  {
    "title": "exact title",
    "is_complete_meal": false,
    "category": "side"
  }
]
Return ONLY the JSON array."""


def _recipe_snippet(r: Recipe) -> str:
    ingredients = "\n".join(f"  - {i}" for i in r.ingredients[:12])
    return f'Title: {r.title}\nIngredients:\n{ingredients}'


def _classify_batch(client: anthropic.Anthropic, recipes: list[Recipe]) -> list[dict]:
    payload = "\n\n---\n\n".join(_recipe_snippet(r) for r in recipes)
    msg = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": f"{_SYSTEM}\n\nRecipes:\n\n{payload}"}],
    )
    raw = msg.content[0].text.strip()
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON array in response: {raw[:300]}")
    return json.loads(m.group())


def _apply(recipe: Recipe, info: dict) -> Recipe:
    if info.get("cuisine"):
        recipe.cuisine = [c for c in info["cuisine"] if isinstance(c, str)]
    if info.get("effort") in ("easy", "medium", "hard"):
        recipe.effort = info["effort"]
    if isinstance(info.get("time_active"), int) and info["time_active"] > 0:
        recipe.time_active = info["time_active"]
    if isinstance(info.get("time_total"), int) and info["time_total"] > 0:
        recipe.time_total = info["time_total"]
    return recipe


def run(vault_path: Path, dry_run: bool = False) -> None:
    dinner_dir = vault_path / "Recipes" / "Dinner"
    sides_dir  = vault_path / "Recipes" / "Sides"

    md_files = sorted(dinner_dir.glob("*.md"))
    print(f"Found {len(md_files)} dinner recipes")

    recipes: list[tuple[Path, Recipe]] = []
    for p in md_files:
        try:
            recipes.append((p, load_recipe(p)))
        except Exception as e:
            print(f"  SKIP {p.name}: {e}")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    moved_to_sides: list[str] = []
    normalized: list[str] = []
    errors: list[str] = []

    for i in range(0, len(recipes), _BATCH):
        batch_items = recipes[i:i + _BATCH]
        batch_recipes = [r for _, r in batch_items]
        print(f"  Batch {i + 1}–{i + len(batch_items)}...")

        try:
            results = _classify_batch(client, batch_recipes)
        except Exception as e:
            print(f"    ERROR: {e}")
            errors.extend(r.title for r in batch_recipes)
            continue

        # align by index (same order guaranteed)
        for (src_path, recipe), info in zip(batch_items, results):
            try:
                if not info.get("is_complete_meal"):
                    recipe.meal_type = ["side"]
                    if not dry_run:
                        sides_dir.mkdir(parents=True, exist_ok=True)
                        dest = sides_dir / src_path.name
                        counter = 2
                        while dest.exists():
                            dest = sides_dir / f"{src_path.stem}-{counter}.md"
                            counter += 1
                        dest.write_text(recipe.to_markdown(), encoding="utf-8")
                        src_path.unlink()
                    moved_to_sides.append(recipe.title)
                else:
                    _apply(recipe, info)
                    if not dry_run:
                        src_path.write_text(recipe.to_markdown(), encoding="utf-8")
                    normalized.append(recipe.title)
            except Exception as e:
                print(f"    ERROR applying {recipe.title}: {e}")
                errors.append(recipe.title)

    print(f"\nResults {'(dry run) ' if dry_run else ''}:")
    print(f"  Normalized in Dinner: {len(normalized)}")
    print(f"  Moved to Sides:       {len(moved_to_sides)}")
    print(f"  Errors:               {len(errors)}")

    if moved_to_sides:
        print(f"\nMoved to Sides ({len(moved_to_sides)}):")
        for t in moved_to_sides[:20]:
            print(f"  {t}")
        if len(moved_to_sides) > 20:
            print(f"  ... and {len(moved_to_sides) - 20} more")

    if errors:
        print(f"\nErrors:")
        for t in errors:
            print(f"  {t}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Normalize dinner vault metadata")
    ap.add_argument("--config", help="Path to config.yaml")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    config = load_config(args.config)
    run(get_vault_path(config), dry_run=args.dry_run)
