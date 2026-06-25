from __future__ import annotations
import argparse
import json
import os
import random
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from scripts.config import load_config, get_vault_path
from scripts.ingest_recipe import ingest_from_url
from scripts.models import DayPlan, MealPlan, Recipe
from scripts.search_recipe import search_recipe_urls
from scripts.vault import find_recipe_paths, find_recipes, save_recipe

load_dotenv()

_MODEL = "claude-sonnet-4-6"
_WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

_BREAKFASTS_WEEKDAY = [
    "Scrambled eggs",
    "Fried eggs with toast",
    "Smoothie",
    "Yogurt parfait",
    "Avocado toast",
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


def _detect_protein(recipe: Recipe) -> str:
    combined = (recipe.title + " " + " ".join(recipe.ingredients[:15])).lower()
    if any(k in combined for k in ("chicken", "poultry", "turkey", "duck")):
        return "poultry"
    if any(k in combined for k in (
        "beef", "steak", "brisket", "chuck", "sirloin", "ribeye",
        "ground beef", "short rib", "meatloaf", "burger", "bulgogi", "gyudon",
    )):
        return "beef"
    if any(k in combined for k in ("pork", "bacon", "ham", "prosciutto", "sausage", "chorizo", "carnitas")):
        return "pork"
    if any(k in combined for k in ("lamb", "mutton")):
        return "lamb"
    if any(k in combined for k in ("salmon", "tuna", "cod", "shrimp", "scallop", "seafood", "halibut", "tilapia", "mahi")):
        return "seafood"
    return "other"


def _enforce_protein_diversity(
    recipes: list[Recipe],
    spare_pool: list[Recipe],
    max_per_protein: int = 2,
) -> list[Recipe]:
    result = list(recipes)
    protein_counts = Counter(_detect_protein(r) for r in result)
    over_limit = {p for p, n in protein_counts.items() if n > max_per_protein}
    if not over_limit:
        return result

    # Mark slots beyond the limit for replacement (keep the first N)
    seen: Counter[str] = Counter()
    to_replace: list[int] = []
    for i, r in enumerate(result):
        p = _detect_protein(r)
        seen[p] += 1
        if p in over_limit and seen[p] > max_per_protein:
            to_replace.append(i)

    already_selected = {id(r) for r in result}
    spares = [r for r in spare_pool if id(r) not in already_selected]

    for idx in to_replace:
        current_counts = Counter(_detect_protein(r) for r in result)
        for j, spare in enumerate(spares):
            if current_counts[_detect_protein(spare)] < max_per_protein:
                result[idx] = spare
                spares.pop(j)
                already_selected.add(id(spare))
                break

    return result


def _contains_disliked(recipe: Recipe, disliked: list[str]) -> bool:
    if not disliked:
        return False
    combined = (recipe.title + " " + " ".join(recipe.ingredients)).lower()
    return any(d.lower() in combined for d in disliked)


_SOUP_KEYWORDS = ("soup", "stew", "chowder", "bisque", "broth", "chili", "ramen", "pho")
_SUMMER_MONTHS = (6, 7, 8)

# keyword → months when the recipe is appropriate (None means wraps across year-end)
_HOLIDAY_WINDOWS: dict[str, tuple[int, ...]] = {
    "thanksgiving": (11,),
    "christmas": (12,),
    "xmas": (12,),
    "easter": (3, 4),
    "halloween": (10,),
    "new year": (12, 1),
    "4th of july": (7,),
    "independence day": (7,),
    "valentine": (2,),
    "st. patrick": (3,),
    "st patrick": (3,),
}


def _is_soup(recipe: Recipe) -> bool:
    combined = (recipe.title + " " + " ".join(recipe.ingredients[:6])).lower()
    return any(k in combined for k in _SOUP_KEYWORDS)


def _is_holiday_mismatch(recipe: Recipe, month: int) -> bool:
    title = recipe.title.lower()
    for keyword, valid_months in _HOLIDAY_WINDOWS.items():
        if keyword in title:
            return month not in valid_months
    return False


def _filter_dinner_pool(
    recipes: list[Recipe],
    config: dict,
    reference_date: date | None = None,
) -> list[Recipe]:
    mode = config.get("dietary_mode", "normal")
    ref = reference_date or date.today()
    cutoff = ref - timedelta(weeks=4)
    disliked = config.get("preferences", {}).get("disliked", [])
    is_summer = ref.month in _SUMMER_MONTHS
    month = ref.month
    result = []
    for r in recipes:
        if r.status not in ("loved", "tried"):
            continue
        if mode != "normal" and mode not in r.dietary:
            continue
        if _contains_disliked(r, disliked):
            continue
        if is_summer and _is_soup(r):
            continue
        if _is_holiday_mismatch(r, month):
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
        f"2. The same main protein appearing more than 2 nights\n"
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


def _weighted_select(
    recipes: list[Recipe],
    n: int,
    seed: int | None = None,
    max_per_protein: int | None = None,
) -> list[Recipe]:
    if not recipes:
        return []
    n = min(n, len(recipes))
    rng = random.Random(seed)
    pool = [(r.rating if r.rating else 3, r) for r in recipes]
    selected: list[Recipe] = []
    protein_counts: Counter[str] = Counter()

    while len(selected) < n and pool:
        total = sum(w for w, _ in pool)
        pick = rng.uniform(0, total)
        cumulative = 0.0
        for i, (w, r) in enumerate(pool):
            cumulative += w
            if cumulative >= pick:
                pool.pop(i)
                p = _detect_protein(r)
                if max_per_protein is None or protein_counts[p] < max_per_protein:
                    selected.append(r)
                    protein_counts[p] += 1
                # if over cap, recipe is discarded and we try again next iteration
                break

    # Fallback: if protein cap made us short, fill remaining without cap
    if len(selected) < n and pool:
        remaining = [(w, r) for w, r in pool if r not in selected]
        while len(selected) < n and remaining:
            total = sum(w for w, _ in remaining)
            pick = rng.uniform(0, total)
            cumulative = 0.0
            for i, (w, r) in enumerate(remaining):
                cumulative += w
                if cumulative >= pick:
                    selected.append(r)
                    remaining.pop(i)
                    break

    return selected


_FRIDAY = 5  # 0=Sun … 6=Sat
_EAT_OUT = "Eat out"


def _assign_to_nights(recipes: list[Recipe]) -> list[Recipe]:
    """Assign recipes to the 6 non-Friday dinner slots (Sun–Thu + Sat)."""
    hard = [r for r in recipes if r.effort == "hard"]
    soft = [r for r in recipes if r.effort != "hard"]
    slots: list[Recipe | None] = [None] * 7
    weekend_slots = [0, 6]
    weekday_slots = [i for i in range(1, 6) if i != _FRIDAY]  # Mon–Thu only

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


def _plan_breakfasts(
    week_of: date,
    vault_path: Path | None = None,
    seed: int | None = None,
) -> list[str]:
    rng = random.Random(seed)
    breakfasts: list[str] = []
    egg_streak = 0
    used_weekend: list[str] = []
    used_weekday: list[str] = []

    # Occasionally substitute a vault breakfast recipe (weekend ~40%, weekday ~10%)
    vault_breakfast_titles: list[str] = []
    if vault_path:
        from scripts.vault import find_recipes as _find
        vault_breakfasts = _find(vault_path, meal_type="breakfast")
        vault_breakfast_titles = [r.title for r in vault_breakfasts]

    used_vault: list[str] = []

    def _pick_vault_breakfast() -> str | None:
        available = [t for t in vault_breakfast_titles if t not in used_vault]
        if not available:
            return None
        pick = rng.choice(available)
        used_vault.append(pick)
        return pick

    for i in range(7):
        if i in (0, 6):  # Sunday, Saturday — higher chance of vault recipe
            if vault_breakfast_titles and rng.random() < 0.4:
                choice = _pick_vault_breakfast() or rng.choice(_BREAKFASTS_WEEKEND)
            else:
                pool = [b for b in _BREAKFASTS_WEEKEND if b not in used_weekend]
                if not pool:
                    pool = list(_BREAKFASTS_WEEKEND)
                choice = rng.choice(pool)
            if choice in _BREAKFASTS_WEEKEND:
                used_weekend.append(choice)
            egg_streak = 0
        else:
            if vault_breakfast_titles and rng.random() < 0.1:
                choice = _pick_vault_breakfast() or rng.choice(_BREAKFASTS_WEEKDAY)
            else:
                pool = [b for b in _BREAKFASTS_WEEKDAY if b not in used_weekday]
                if not pool:
                    pool = list(_BREAKFASTS_WEEKDAY)
                if egg_streak >= 2:
                    pool = [b for b in pool if "egg" not in b.lower()] or pool
                choice = rng.choice(pool) if pool else "Yogurt parfait"
            if choice in _BREAKFASTS_WEEKDAY:
                used_weekday.append(choice)
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
            # Extract plain title from either "[Title](path)" or "[[Title]]" or raw text
            def _plain(s: str) -> str:
                m = re.match(r"\[([^\]]+)\]\([^)]+\)", s)
                if m:
                    return m.group(1)
                m = re.search(r"\[\[([^\]]+)\]\]", s)
                if m:
                    return m.group(1)
                return s.split(" · ")[0].strip()

            title = _plain(prev)
            link = prev.split(" · ")[0].strip()  # preserve the link markup for lunch line

            # Look back past leftovers AND eat-out nights to find a real dinner
            if title.startswith("Leftovers") or title == _EAT_OUT:
                for k in range(2, len(dinners) + 1):
                    candidate = dinners[(i - k) % len(dinners)]
                    candidate_title = _plain(candidate)
                    if not candidate_title.startswith("Leftovers") and candidate_title != _EAT_OUT:
                        link = candidate.split(" · ")[0].strip()
                        break
            lunches.append(f"Leftovers — {link}")
    return lunches


def _source_new_recipe(
    config: dict,
    vault_path: Path,
    exclude: list[str],
    avoid_proteins: list[str] | None = None,
) -> Recipe | None:
    cuisines = ", ".join(config.get("preferred_cuisines", []))
    mode = config.get("dietary_mode", "normal")
    sources = config.get("sources", [])
    avoid_str = (
        f"- Avoid recipes whose main protein is: {', '.join(avoid_proteins)} "
        f"(already on the menu this week)\n"
        if avoid_proteins else ""
    )
    prompt = (
        f"Suggest a dinner recipe search query (3–6 words, no URLs, no site names).\n"
        f"Requirements:\n"
        f"- Must be a COMPLETE, well-rounded dinner — a main dish with protein, not a side dish, "
        f"salad dressing, condiment, sauce, drink, or single vegetable.\n"
        f"- Dietary mode: {mode}\n"
        f"- Preferred cuisines: {cuisines}\n"
        f"{avoid_str}"
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

    # Build title→path lookup for all recipes so we can produce markdown links
    _all_recipe_paths: dict[str, Path] = {
        r.title: p for p, r in find_recipe_paths(vault_path)
    }

    def _recipe_link(title: str) -> str:
        """Return a markdown link to the recipe file, or plain title if not found."""
        path = _all_recipe_paths.get(title)
        if path:
            # Plan lives at <vault>/Meal Plans/…, so recipes are one level up
            rel = f"../{path.relative_to(vault_path)}"
            return f"[{title}]({rel})"
        return title

    all_dinner_recipes = find_recipes(vault_path, meal_type="dinner")
    disliked = config.get("preferences", {}).get("disliked", [])

    # 5 loved/tried (weighted by rating, max 2 of any protein)
    pool = _filter_dinner_pool(all_dinner_recipes, config, reference_date=week_start)
    loved_tried = _weighted_select(pool, n=5, max_per_protein=2)

    # Track proteins already committed so untried + new recipe add variety
    current_proteins = Counter(_detect_protein(r) for r in loved_tried)
    overloaded = [p for p, n in current_proteins.items() if n >= 2]

    # 1 untried from vault — prefer proteins not already at the cap
    is_summer = week_start.month in _SUMMER_MONTHS
    month = week_start.month
    untried_pool = [
        r for r in all_dinner_recipes
        if r.status == "untried"
        and not _contains_disliked(r, disliked)
        and not (is_summer and _is_soup(r))
        and not _is_holiday_mismatch(r, month)
    ]
    preferred_untried = [r for r in untried_pool if _detect_protein(r) not in overloaded]
    untried_candidate = preferred_untried if preferred_untried else untried_pool
    untried = random.sample(untried_candidate, 1) if untried_candidate else []

    # 1 new from web via Claude — pass overloaded proteins so the query avoids them
    exclude_titles = [r.title for r in loved_tried + untried]
    new_recipe = _source_new_recipe(config, vault_path, exclude_titles, avoid_proteins=overloaded if overloaded else None)

    # 6 dinners — Friday is always eat-out
    all_six = (loved_tried + untried + ([new_recipe] if new_recipe else []))[:6]
    while len(all_six) < 6 and pool:
        all_six.append(pool[len(all_six) % len(pool)])

    # Enforce protein diversity across all 6
    selected_ids = {id(r) for r in all_six}
    broad_spares = (
        [r for r in pool if id(r) not in selected_ids]
        + [r for r in untried_pool if id(r) not in selected_ids]
    )
    all_six = _enforce_protein_diversity(all_six, broad_spares, max_per_protein=2)

    # Claude coherence check
    selected_ids = {id(r) for r in all_six}
    spare_pool = [r for r in broad_spares if id(r) not in selected_ids]
    all_six = _validate_lineup(all_six, spare_pool, config)

    # Re-enforce after Claude's pass
    selected_ids = {id(r) for r in all_six}
    remaining_spares = [r for r in broad_spares if id(r) not in selected_ids]
    all_six = _enforce_protein_diversity(all_six, remaining_spares, max_per_protein=2)

    assigned = _assign_to_nights(all_six)  # fills Sun–Thu + Sat (skips Fri)

    # Map assigned recipes to actual day slots (skipping Friday)
    day_slots = [i for i in range(7) if i != _FRIDAY]
    leftover_day_slots: set[int] = set()
    for i, r in enumerate(assigned):
        if r.servings >= 6 and i + 1 < len(assigned):
            leftover_day_slots.add(day_slots[i + 1])

    dinner_strings: list[str] = [""] * 7
    dinner_strings[_FRIDAY] = _EAT_OUT
    for i, r in enumerate(assigned):
        day = day_slots[i]
        if day in leftover_day_slots:
            prev_title = assigned[i - 1].title
            dinner_strings[day] = f"Leftovers — {_recipe_link(prev_title)}"
        else:
            parts = [_recipe_link(r.title)]
            if r.cuisine:
                parts.append(", ".join(r.cuisine))
            parts.append(r.effort.capitalize())
            if r.time_total:
                parts.append(f"{r.time_total} min")
            dinner_strings[day] = " · ".join(parts)

    raw_breakfasts = _plan_breakfasts(week_start, vault_path=vault_path)
    breakfasts = [_recipe_link(b) for b in raw_breakfasts]
    lunches = _plan_lunches(dinner_strings, dedicated_days=config.get("dedicated_lunch_days", 2))

    days = [
        DayPlan(weekday=_WEEKDAYS[i], breakfast=breakfasts[i], lunch=lunches[i], dinner=dinner_strings[i])
        for i in range(7)
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
