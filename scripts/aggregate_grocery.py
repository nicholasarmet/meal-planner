from __future__ import annotations
import argparse
import json
import os
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from scripts.config import load_config, get_vault_path
from scripts.models import Recipe
from scripts.vault import find_recipes

load_dotenv()

_MODEL = "claude-sonnet-4-6"

SECTION_ORDER = [
    "Produce",
    "Pantry",
    "Snacks",
    "Cereal",
    "Frozen Goods",
    "Spices",
    "Baking Supplies",
    "Refrigerated",
    "Dairy",
    "Cheese & Cured Meats",
]


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def parse_recipe_titles(plan_text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\[\[([^\]]+)\]\]", plan_text)))


def aggregate_ingredients(recipes: list[Recipe]) -> list[str]:
    result: list[str] = []
    for r in recipes:
        result.extend(r.ingredients)
    return result


def _build_prompt(ingredients: list[str]) -> str:
    items = "\n".join(f"- {i}" for i in ingredients)
    sections = ", ".join(SECTION_ORDER)
    return (
        "You are building a grocery list. Here are all ingredients from this week's recipes:\n\n"
        f"{items}\n\n"
        "Instructions:\n"
        "1. Merge equivalent ingredients (e.g. 'garlic cloves' and 'cloves of garlic' → 'Garlic cloves').\n"
        "2. Sum quantities. Conversions: 3 tsp = 1 tbsp, 16 tbsp = 1 cup, 16 oz = 1 lb.\n"
        f"3. Assign each ingredient to exactly one section from: {sections}\n"
        "4. Common staples likely already in stock (kosher salt, black pepper, olive oil, "
        "common dry spices) go in 'check_stock'.\n"
        "5. Near-matches you are unsure about merging go in 'review'.\n\n"
        "Return ONLY valid JSON:\n"
        '{"sections": {"Produce": ["item — qty"], ...}, "check_stock": ["item"], "review": ["note"]}'
    )


def _parse_response(text: str) -> dict:
    stripped = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
    if m:
        stripped = m.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        obj = re.search(r"\{.*\}", stripped, re.DOTALL)
        if obj:
            return json.loads(obj.group())
        raise


def _render(data: dict, week_of: str) -> str:
    lines = [f"# Grocery List — Week of {week_of}", ""]
    for section in SECTION_ORDER:
        items = data.get("sections", {}).get(section, [])
        if items:
            lines.append(f"## {section}")
            lines.extend(f"- [ ] {item}" for item in items)
            lines.append("")
    check = data.get("check_stock", [])
    if check:
        lines.append("## Check Stock")
        lines.extend(f"- [ ] {item}" for item in check)
        lines.append("")
    review = data.get("review", [])
    if review:
        lines.append("## Review")
        lines.extend(f"- [ ] {item}" for item in review)
        lines.append("")
    return "\n".join(lines)


def generate_grocery_list(
    plan_path: Path,
    vault_path: Path,
    config: dict,
) -> Path:
    plan_text = plan_path.read_text(encoding="utf-8")
    titles = parse_recipe_titles(plan_text)

    all_recipes = find_recipes(vault_path)
    by_title = {r.title: r for r in all_recipes}
    selected = [by_title[t] for t in titles if t in by_title]
    if len(selected) < len(titles):
        missing = [t for t in titles if t not in by_title]
        print(f"Warning: recipes not found in vault: {missing}", flush=True)

    ingredients = aggregate_ingredients(selected)
    data = _parse_response(_call_claude(_build_prompt(ingredients)))

    m = re.search(r"Week of (\d{4}-\d{2}-\d{2})", plan_path.name)
    week_of = m.group(1) if m else "unknown"

    folder = vault_path / "Grocery Lists"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{week_of}.md"
    out.write_text(_render(data, week_of), encoding="utf-8")
    return out


def _run() -> None:
    parser = argparse.ArgumentParser(description="Generate grocery list from meal plan")
    parser.add_argument("plan", help="Path to meal plan markdown file")
    parser.add_argument("--config", help="Path to config.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    vault_path = get_vault_path(config)
    out = generate_grocery_list(Path(args.plan), vault_path, config)
    print(f"Grocery list written to {out}")


if __name__ == "__main__":
    _run()
