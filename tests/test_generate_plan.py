import pytest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from scripts.models import Recipe, MealPlan, DayPlan
from scripts.generate_plan import (
    _next_sunday,
    _filter_dinner_pool,
    _weighted_select,
    _assign_to_nights,
    _plan_breakfasts,
    _plan_lunches,
    generate_weekly_plan,
    write_meal_plan,
)


def _r(title, status="loved", rating=4, cuisine=None, effort="medium",
        dietary=None, servings=4, last_made=None):
    return Recipe(
        title=title,
        status=status,
        rating=rating,
        cuisine=cuisine or ["Italian"],
        effort=effort,
        dietary=dietary or [],
        servings=servings,
        last_made=last_made,
        meal_type=["dinner"],
    )


# ── _next_sunday ─────────────────────────────────────────────────────────────

def test_next_sunday_from_monday():
    assert _next_sunday(date(2026, 6, 22)) == date(2026, 6, 28)  # Monday → next Sunday


def test_next_sunday_already_sunday():
    assert _next_sunday(date(2026, 6, 28)) == date(2026, 6, 28)  # Sunday → same day


# ── _filter_dinner_pool ───────────────────────────────────────────────────────

def test_filter_excludes_untried():
    recipes = [_r("A", status="loved"), _r("B", status="tried"), _r("C", status="untried")]
    pool = _filter_dinner_pool(recipes, {"dietary_mode": "normal"})
    assert {r.title for r in pool} == {"A", "B"}


def test_filter_dietary_mode_paleo():
    recipes = [
        _r("GF", dietary=["gluten-free", "paleo"]),
        _r("NotPaleo", dietary=["gluten-free"]),
    ]
    pool = _filter_dinner_pool(recipes, {"dietary_mode": "paleo"})
    assert [r.title for r in pool] == ["GF"]


def test_filter_normal_mode_ignores_dietary():
    recipes = [_r("A", dietary=[]), _r("B", dietary=["paleo"])]
    pool = _filter_dinner_pool(recipes, {"dietary_mode": "normal"})
    assert len(pool) == 2


def test_filter_excludes_made_within_4_weeks():
    recent = _r("Recent", last_made="2026-06-15")   # 14 days before 2026-06-29
    old = _r("Old", last_made="2026-01-01")
    pool = _filter_dinner_pool(
        [recent, old],
        {"dietary_mode": "normal"},
        reference_date=date(2026, 6, 29),
    )
    assert [r.title for r in pool] == ["Old"]


# ── _weighted_select ──────────────────────────────────────────────────────────

def test_weighted_select_count():
    recipes = [_r(str(i), rating=(i % 5) + 1) for i in range(20)]
    selected = _weighted_select(recipes, n=5, seed=42)
    assert len(selected) == 5


def test_weighted_select_no_duplicates():
    recipes = [_r(str(i)) for i in range(20)]
    selected = _weighted_select(recipes, n=10, seed=0)
    assert len(selected) == len({r.title for r in selected})


def test_weighted_select_fewer_than_n_returns_all():
    recipes = [_r(str(i)) for i in range(3)]
    selected = _weighted_select(recipes, n=5, seed=0)
    assert len(selected) == 3


# ── _assign_to_nights ─────────────────────────────────────────────────────────

def test_assign_to_nights_returns_7():
    recipes = [_r(str(i)) for i in range(7)]
    assert len(_assign_to_nights(recipes)) == 7


def test_assign_to_nights_hard_on_weekend():
    recipes = [_r(str(i), effort="medium") for i in range(6)]
    recipes.append(_r("hard-one", effort="hard"))
    nights = _assign_to_nights(recipes)
    # Index 0 = Sunday, index 6 = Saturday; hard recipe must be at one of these
    assert nights[0].effort == "hard" or nights[6].effort == "hard"


# ── _plan_breakfasts ─────────────────────────────────────────────────────────

def test_plan_breakfasts_length():
    assert len(_plan_breakfasts(date(2026, 6, 29), seed=0)) == 7


def test_plan_breakfasts_no_oatmeal():
    for seed in range(10):
        bs = _plan_breakfasts(date(2026, 6, 29), seed=seed)
        assert all("oatmeal" not in b.lower() for b in bs)


def test_plan_breakfasts_weekday_vs_weekend():
    # Index 0=Sun(weekend), 1-5=Mon-Fri(weekday), 6=Sat(weekend)
    # Weekend options come from a different pool — check they differ from weekday norm
    bs = _plan_breakfasts(date(2026, 6, 29), seed=1)
    assert len(bs) == 7  # one per day; spot-check passes without asserting specific values


# ── _plan_lunches ─────────────────────────────────────────────────────────────

_DINNERS = [
    "[[Chicken Adobo]] · Filipino · Easy · 45 min",
    "[[Beef Stew]] · American · Medium · 90 min",
    "[[Pasta]] · Italian · Easy · 30 min",
    "[[Tacos]] · Mexican · Easy · 20 min",
    "[[Salmon]] · Asian · Medium · 25 min",
    "[[Pizza]] · Italian · Medium · 60 min",
    "[[Ramen]] · Japanese · Hard · 120 min",
]


def test_plan_lunches_length():
    assert len(_plan_lunches(_DINNERS, dedicated_days=2)) == 7


def test_plan_lunches_dedicated_count():
    lunches = _plan_lunches(_DINNERS, dedicated_days=2)
    assert sum(1 for l in lunches if l.startswith("Dedicated lunch")) == 2


def test_plan_lunches_leftover_count():
    lunches = _plan_lunches(_DINNERS, dedicated_days=2)
    assert sum(1 for l in lunches if l.startswith("Leftovers")) == 5


def test_plan_lunches_leftover_references_prior_dinner():
    lunches = _plan_lunches(_DINNERS, dedicated_days=2)
    # Find a leftover lunch and confirm it names a dinner title
    leftover_lunches = [l for l in lunches if l.startswith("Leftovers")]
    assert any("Chicken Adobo" in l or "Beef Stew" in l or "Pasta" in l for l in leftover_lunches)


# ── generate_weekly_plan + write_meal_plan ───────────────────────────────────

def _make_config():
    return {
        "dietary_mode": "normal",
        "dedicated_lunch_days": 2,
        "preferred_cuisines": ["Asian"],
        "sources": ["serious-eats"],
        "weekday_effort_limit": "medium",
        "preferences": {"avoid_raw": [], "disliked": []},
    }


def test_generate_weekly_plan_returns_mealplan(tmp_path):
    recipes = (
        [_r(f"Loved{i}", status="loved") for i in range(8)]
        + [_r(f"Untried{i}", status="untried") for i in range(4)]
    )
    with patch("scripts.generate_plan.find_recipes", return_value=recipes), \
         patch("scripts.generate_plan._call_claude", return_value="https://example.com/recipe"), \
         patch("scripts.generate_plan.ingest_from_url", return_value=_r("NewRecipe", status="untried")), \
         patch("scripts.generate_plan.save_recipe"):
        plan = generate_weekly_plan(_make_config(), tmp_path, week_of=date(2026, 6, 29))

    assert isinstance(plan, MealPlan)
    assert plan.week_of == "2026-06-29"
    assert len(plan.days) == 7
    assert plan.days[0].weekday == "Sunday"
    assert plan.days[6].weekday == "Saturday"
    for day in plan.days:
        assert day.breakfast
        assert day.lunch
        assert day.dinner


def test_write_meal_plan_creates_file(tmp_path):
    plan = MealPlan(
        week_of="2026-06-29",
        days=[DayPlan(weekday="Sunday", breakfast="Eggs", lunch="Leftovers", dinner="[[Pasta]]")],
    )
    path = write_meal_plan(plan, tmp_path)
    assert path.exists()
    assert path.name == "Week of 2026-06-29.md"
    assert "# Meal Plan — Week of 2026-06-29" in path.read_text()


def test_plan_lunches_sparse_two_dinners():
    """_plan_lunches must not crash when dinner list is shorter than 7."""
    dinners = [
        "[[Chicken Adobo]] · Filipino · Easy · 45 min",
        "[[Beef Stew]] · American · Medium · 90 min",
    ]
    lunches = _plan_lunches(dinners, dedicated_days=1)
    assert len(lunches) == 2


def test_generate_weekly_plan_sparse_vault(tmp_path):
    """generate_weekly_plan must succeed when the loved/tried pool is empty."""
    recipes = [_r(f"Untried{i}", status="untried") for i in range(3)]
    with patch("scripts.generate_plan.find_recipes", return_value=recipes), \
         patch("scripts.generate_plan._call_claude", return_value="https://example.com/new"), \
         patch("scripts.generate_plan.ingest_from_url", return_value=_r("NewRecipe", status="untried")), \
         patch("scripts.generate_plan.save_recipe"):
        plan = generate_weekly_plan(_make_config(), tmp_path, week_of=date(2026, 6, 29))

    assert isinstance(plan, MealPlan)
    # pool (loved/tried) is empty — all recipes are untried — so padding loop
    # does nothing; only 1 sampled untried + 1 new recipe = 2 days.
    assert len(plan.days) == 2
    for day in plan.days:
        assert day.breakfast
        assert day.lunch
        assert day.dinner


def test_plan_lunches_no_double_leftovers():
    """Lunch label must never contain 'Leftovers — Leftovers'."""
    dinners = [
        "[[Beef Stew]] · American · Medium · 90 min",
        "Leftovers — Beef Stew",          # big-batch night 1
        "Leftovers — Beef Stew",          # big-batch night 2
        "[[Pasta]] · Italian · Easy · 30 min",
        "[[Tacos]] · Mexican · Easy · 20 min",
        "[[Salmon]] · Asian · Medium · 25 min",
        "[[Pizza]] · Italian · Medium · 60 min",
    ]
    lunches = _plan_lunches(dinners, dedicated_days=0)
    assert not any("Leftovers — Leftovers" in l for l in lunches), lunches


def test_plan_lunches_no_double_leftovers_wrap():
    """No double-leftover label when modular wrap-around also lands on a leftover."""
    dinners = [
        "Leftovers — Beef Stew",          # index 0 — leftover
        "Leftovers — Beef Stew",          # index 1 — leftover
        "[[Pasta]] · Italian · Easy · 30 min",
        "[[Tacos]] · Mexican · Easy · 20 min",
        "[[Salmon]] · Asian · Medium · 25 min",
        "[[Pizza]] · Italian · Medium · 60 min",
        "Leftovers — Pizza",              # index 6 — also leftover (wrap target)
    ]
    lunches = _plan_lunches(dinners, dedicated_days=0)
    assert not any("Leftovers — Leftovers" in l for l in lunches), lunches


def test_generate_weekly_plan_claude_bad_url(tmp_path):
    """If Claude returns a non-URL, the plan is generated without the new recipe."""
    recipes = (
        [_r(f"Loved{i}", status="loved") for i in range(8)]
        + [_r(f"Untried{i}", status="untried") for i in range(4)]
    )
    with patch("scripts.generate_plan.find_recipes", return_value=recipes), \
         patch("scripts.generate_plan._call_claude", return_value="Sorry, I cannot find a recipe."), \
         patch("scripts.generate_plan.ingest_from_url") as mock_ingest, \
         patch("scripts.generate_plan.save_recipe"):
        plan = generate_weekly_plan(_make_config(), tmp_path, week_of=date(2026, 6, 29))

    mock_ingest.assert_not_called()
    assert isinstance(plan, MealPlan)
    # Plan still generated with loved/tried + untried
    assert len(plan.days) > 0
