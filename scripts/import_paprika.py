from __future__ import annotations
import argparse, gzip, json, re, sys, zipfile
from pathlib import Path

from scripts.config import get_vault_path, load_config
from scripts.models import Recipe
from scripts.vault import save_recipe


def parse_paprika_export(path: Path) -> list[dict]:
    recipes = []
    with zipfile.ZipFile(path, "r") as zf:
        for name in zf.namelist():
            with zf.open(name) as f:
                recipes.append(json.loads(gzip.decompress(f.read()).decode("utf-8")))
    return recipes


def paprika_to_recipe(raw: dict) -> Recipe:
    categories = [c.lower() for c in (raw.get("categories") or [])]
    status = "tried" if "tried and tested" in categories else "untried"

    raw_rating = raw.get("rating", 0)
    rating = int(raw_rating) if raw_rating else None

    ingredients = [
        line.strip()
        for line in (raw.get("ingredients") or "").splitlines()
        if line.strip()
    ]

    instructions = [
        re.sub(r"^\d+[.)]\s*", "", line).strip()
        for line in (raw.get("directions") or "").splitlines()
        if line.strip()
    ]

    return Recipe(
        title=raw.get("name", "Untitled"),
        source_url=raw.get("source_url") or None,
        source_name=raw.get("source") or None,
        status=status,
        rating=rating,
        ingredients=ingredients,
        instructions=instructions,
        notes=raw.get("notes") or "",
        meal_type=["dinner"],  # Paprika has no meal_type; defaults to dinner
    )


def _run(paprikarecipes: Path, vault_path: Path, dry_run: bool = False) -> int:
    raws = parse_paprika_export(paprikarecipes)
    print(f"Found {len(raws)} recipes in {paprikarecipes.name}")
    for i, raw in enumerate(raws, 1):
        recipe = paprika_to_recipe(raw)
        if not dry_run:
            save_recipe(recipe, vault_path)
        if i % 50 == 0:
            print(f"  {i}/{len(raws)}...")
    print(f"Done. {'Dry run — ' if dry_run else ''}Imported {len(raws)} recipes.")
    return len(raws)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Import Paprika recipes into Obsidian vault")
    ap.add_argument("paprikarecipes", help="Path to .paprikarecipes export file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config", help="Path to config.yaml")
    args = ap.parse_args()
    config = load_config(args.config)
    _run(Path(args.paprikarecipes), get_vault_path(config), args.dry_run)
