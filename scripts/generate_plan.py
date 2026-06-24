from __future__ import annotations
import argparse
import json
import os
import random
import re
from datetime import date, timedelta
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from scripts.config import load_config, get_vault_path
from scripts.ingest_recipe import ingest_from_url
from scripts.models import DayPlan, MealPlan, Recipe
from scripts.search_recipe import search_recipe_urls
from scripts.vault import find_recipes, save_recipe

load_dotenv()

_MODEL = "claude-sonnet-4-6"
_WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

_BREAKFASTS_WEEKDAY = [
    "Scrambled eggs",
    "Fried eggs with toast",
    "Smoothie",
    "Yogurt parfait",
    "Avocado toast",
    "Hard-boiled eggs",
    "Breakfast burrito",
]
_BREAKFASTS_WEEKEND = [
    "Frittata",
    "Pancakes",
    "French toast",
    "Baked eggs",
    "Breakfast tacos",
    "Omelette",
]
_LUNCH_OPTIONS = ["Sandwich day", "Wrap day", "Salad day", "Grain bowl day"]


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _next_sunday(ref: date | None = None) -> date:
    d = ref or date.today()
    days_ahead = (6 - d.weekday()) % 7
    return d + timedelta(days=days_ahead)


def _contains_disliked(recipe: Recipe, disliked: list[str]) -> bool:
    if not disliked:
        return False
    combined = (recipe.title + " " + " ".join(recipe.ingredients)).lower()
    return any(d.lower() in combined for d in disliked)


def _filter_dinner_pool(
    recipes: list[Recipe],
    config: dict,
    reference_date: date | None = None,
) -> list[Recipe]:
    mode = config.get("dietary_mode", "normal")
    ref = reference_date or date.today()
    cutoff = ref - timedelta(weeks=4)
    disliked = config.get("preferences", {}).get("disliked", [])
    result = []
    for r in recipes:
        if r.status not in ("loved", "tried"):
            continue
        if mode != "normal" and mode not in r.dietary:
            continue
        if _contains_disliked(r, disliked):
            continue
        if r.last_made:
            try:
                if date.fromisoformat(r.last_made) > cutoff:
                    continue
            except ValueError:
                pass
        result.append(r)
    return result


def _validate_lineup(
    recipes: list[Recipe],
    spare_pool: list[Recipe],
    config: dict,
) -> list[Recipe]:
    """Ask Claude to review the dinner lineup for coherence; swap flagged slots from spare_pool."""
    disliked = config.get("preferences", {}).get("disliked", [])
    preferred = config.get("preferred_cuisines", [])

    summary_lines = []
    for i, r in enumerate(recipes):
        key_ingredients = ", ".join(r.ingredients[:5]) if r.ingredients else "unknown"
        summary_lines.append(
            f"{i + 1}. {r.title} | cuisine: {', '.join(r.cuisine) or '?'} | "
            f"effort: {r.effort} | key ingredients: {key_ingredients}"
        )

    prompt = (
        f"Review this weekly dinner lineup for a family (2 adults, 1 child).\n\n"
        f"{''.join(line + chr(10) for line in summary_lines)}\n"
        f"Disliked ingredients (must not appear): {', '.join(disliked) or 'none'}\n"
        f"Preferred cuisines: {', '.join(preferred) or 'any'}\n\n"
        f"Check for:\n"
        f"1. Any entry that is NOT a complete, well-rounded dinner "
        f"(must have protein + built-in components — not a side dish, salad dressing, "
        f"condiment, drink, or rice/grain preparation)\n"
        f"2. The same main protein appearing more than 3 nights\n"
        f"3. The same cuisine appearing more than 3 nights\n"
        f"4. Any recipe likely to contain a disliked ingredient based on the key ingredients shown\n\n"
        f"If everything looks good, return: {{\"ok\": true}}\n"
        f"If some slots need replacing, return: {{\"ok\": false, \"replace\": [1, 3]}} (1-based positions)\n"
        f"Return ONLY the JSON."
    )

    try:
        raw = _call_claude(prompt).strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return recipes
        result = json.loads(m.group())
        if result.get("ok"):
            return recipes
        to_replace = [i - 1 for i in result.get("replace", []) if isinstance(i, int)]
        already_selected = set(id(r) for r in recipes)
        spares = [r for r in spare_pool if id(r) not in already_selected]
        for idx in sorted(to_replace):
            if 0 <= idx < len(recipes) and spares:
                recipes[idx] = spares.pop(0)
    except Exception:
        pass
    return recipes


def _weighted_select(recipes: list[Recipe], n: int, seed: int | None = None) -> list[Recipe]:
    if not recipes:
        return []
    n = min(n, len(recipes))
    rng = random.Random(seed)
    pool = [(r.rating if r.rating else 3, r) for r in recipes]
    selected: list[Recipe] = []
    while len(selected) < n and pool:
        total = sum(w for w, _ in pool)
        pick = rng.uniform(0, total)
        cumulative = 0.0
        for i, (w, r) in enumerate(pool):
            cumulative += w
            if cumulative >= pick:
                selected.append(r)
                pool.pop(i)
                break
    return selected


def _assign_to_nights(recipes: list[Recipe]) -> list[Recipe]:
    hard = [r for r in recipes if r.effort == "hard"]
    soft = [r for r in recipes if r.effort != "hard"]
    slots: list[Recipe | None] = [None] * 7
    weekend_slots = [0, 6]
    weekday_slots = list(range(1, 6))

    for i, r in enumerate(hard):
        if i < len(weekend_slots):
            slots[weekend_slots[i]] = r
        else:
            for idx in weekday_slots:
                if slots[idx] is None:
                    slots[idx] = r
                    break

    for r in soft:
        for idx in weekday_slots + weekend_slots:
            if slots[idx] is None:
                slots[idx] = r
                break

    result = [s for s in slots if s is not None]

    # Best-effort cuisine variety: one swap pass
    for i in range(len(result) - 1):
        if set(result[i].cuisine) & set(result[i + 1].cuisine):
            for j in range(i + 2, len(result)):
                if not (set(result[i].cuisine) & set(result[j].cuisine)):
                    result[i + 1], result[j] = result[j], result[i + 1]
                    break
    return result


def _plan_breakfasts(week_of: date, seed: int | None = None) -> list[str]:
    rng = random.Random(seed)
    breakfasts: list[str] = []
    egg_streak = 0
    for i in range(7):
        if i in (0, 6):  # Sunday, Saturday
            breakfasts.append(rng.choice(_BREAKFASTS_WEEKEND))
            egg_streak = 0
        else:
            pool = list(_BREAKFASTS_WEEKDAY)
            if egg_streak >= 3:
                pool = [b for b in pool if "egg" not in b.lower()]
            choice = rng.choice(pool) if pool else "Yogurt parfait"
            egg_streak = egg_streak + 1 if "egg" in choice.lower() else 0
            breakfasts.append(choice)
    return breakfasts


def _plan_lunches(dinners: list[str], dedicated_days: int = 2) -> list[str]:
    dedicated_indices = set(range(min(dedicated_days, len(dinners))))
    lunches: list[str] = []
    for i in range(len(dinners)):
        if i in dedicated_indices:
            option = _LUNCH_OPTIONS[i % len(_LUNCH_OPTIONS)]
            lunches.append(f"Dedicated lunch — {option}")
        else:
            prev_idx = (i - 1) % len(dinners)
            prev = dinners[prev_idx]
            title = re.sub(r"\[\[([^\]]+)\]\].*", r"\1", prev).strip()
            if title.startswith("Leftovers"):
                for k in range(2, len(dinners) + 1):
                    candidate = dinners[(i - k) % len(dinners)]
                    candidate_title = re.sub(r"\[\[([^\]]+)\]\].*", r"\1", candidate).strip()
                    if not candidate_title.startswith("Leftovers"):
                        title = candidate_title
                        break
            lunches.append(f"Leftovers — {title}")
    return lunches


def _source_new_recipe(config: dict, vault_path: Path, exclude: list[str]) -> Recipe | None:
    cuisines = ", ".join(config.get("preferred_cuisines", []))
    mode = config.get("dietary_mode", "normal")
    sources = config.get("sources", [])
    prompt = (
        f"Suggest a dinner recipe search query (3–6 words, no URLs, no site names).\n"
        f"Requirements:\n"
        f"- Must be a COMPLETE, well-rounded dinner — a main dish with protein, not a side dish, "
        f"salad dressing, condiment, sauce, drink, or single vegetable.\n"
        f"- Dietary mode: {mode}\n"
        f"- Preferred cuisines: {cuisines}\n"
        f"- Do NOT suggest anything similar to: {', '.join(exclude) or 'nothing'}\n"
        f"- Pick something varied — rotate through different cuisines and styles.\n"
        f"Return ONLY the search query. Example: crispy Thai basil chicken"
    )
    query = _call_claude(prompt).strip().strip("\"'")
    if not query:
        print("[meal-planner] _source_new_recipe: Claude returned empty query — skipping")
        return None

    urls = search_recipe_urls(query, preferred_sources=sources)
    for url in urls:
        try:
            recipe = ingest_from_url(url)
            recipe.status = "untried"
            save_recipe(recipe, vault_path)
            return recipe
        except Exception as exc:
            print(f"[meal-planner] _source_new_recipe: failed to ingest {url[:80]!r}: {exc}")
            continue
    print(f"[meal-planner] _source_new_recipe: exhausted {len(urls)} URLs for query {query!r}")
    return None


def generate_weekly_plan(
    config: dict,
    vault_path: Path,
    week_of: date | None = None,
) -> MealPlan:
    week_start = week_of or _next_sunday()
    week_str = week_start.isoformat()

    all_dinner_recipes = find_recipes(vault_path, meal_type="dinner")
    disliked = config.get("preferences", {}).get("disliked", [])

    # 5 loved/tried (weighted by rating)
    pool = _filter_dinner_pool(all_dinner_recipes, config, reference_date=week_start)
    loved_tried = _weighted_select(pool, n=5)

    # 1 untried from vault — also filter disliked
    untried_pool = [
        r for r in all_dinner_recipes
        if r.status == "untried" and not _contains_disliked(r, disliked)
    ]
    untried = random.sample(untried_pool, 1) if untried_pool else []

    # 1 new from web via Claude
    exclude_titles = [r.title for r in loved_tried + untried]
    new_recipe = _source_new_recipe(config, vault_path, exclude_titles)

    all_seven = (loved_tried + untried + ([new_recipe] if new_recipe else []))[:7]
    # Pad if vault is sparse (e.g. brand new install)
    while len(all_seven) < 7 and pool:
        all_seven.append(pool[len(all_seven) % len(pool)])

    # Validate and swap out any incoherent selections
    spare_pool = [r for r in pool if r not in all_seven]
    all_seven = _validate_lineup(all_seven, spare_pool, config)

    assigned = _assign_to_nights(all_seven)

    # Determine leftover nights (recipe with servings >= 6 → next night is leftovers)
    leftover_nights: set[int] = set()
    for i, r in enumerate(assigned):
        if r.servings >= 6 and i + 1 < len(assigned):
            leftover_nights.add(i + 1)

    dinner_strings: list[str] = []
    for i, r in enumerate(assigned):
        if i in leftover_nights:
            prev_title = assigned[i - 1].title
            dinner_strings.append(f"Leftovers — {prev_title}")
        else:
            cuisine = ", ".join(r.cuisine) if r.cuisine else "—"
            timing = f"{r.time_total} min" if r.time_total else "—"
            dinner_strings.append(f"[[{r.title}]] · {cuisine} · {r.effort.capitalize()} · {timing}")

    breakfasts = _plan_breakfasts(week_start)
    lunches = _plan_lunches(dinner_strings, dedicated_days=config.get("dedicated_lunch_days", 2))

    days = [
        DayPlan(weekday=_WEEKDAYS[i], breakfast=breakfasts[i], lunch=lunches[i], dinner=dinner_strings[i])
        for i in range(len(assigned))
    ]
    return MealPlan(week_of=week_str, days=days)


def write_meal_plan(plan: MealPlan, vault_path: Path) -> Path:
    folder = vault_path / "Meal Plans"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"Week of {plan.week_of}.md"
    path.write_text(plan.to_markdown(), encoding="utf-8")
    return path


def _run() -> None:
    parser = argparse.ArgumentParser(description="Generate weekly meal plan")
    parser.add_argument("--config", help="Path to config.yaml")
    parser.add_argument("--week-of", help="ISO date for week start (YYYY-MM-DD)")
    args = parser.parse_args()
    config = load_config(args.config)
    vault_path = get_vault_path(config)
    week_of = date.fromisoformat(args.week_of) if args.week_of else None
    plan = generate_weekly_plan(config, vault_path, week_of=week_of)
    path = write_meal_plan(plan, vault_path)
    print(f"Meal plan written to {path}")


if __name__ == "__main__":
    _run()
