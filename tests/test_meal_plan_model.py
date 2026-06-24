import pytest
from scripts.models import DayPlan, MealPlan


def test_dayplan_stores_fields():
    d = DayPlan(
        weekday="Monday",
        breakfast="Scrambled eggs",
        lunch="Leftovers — Chicken Adobo",
        dinner="[[Chicken Adobo]] · Filipino · Easy · 45 min",
    )
    assert d.weekday == "Monday"
    assert d.breakfast == "Scrambled eggs"
    assert d.lunch == "Leftovers — Chicken Adobo"
    assert d.dinner == "[[Chicken Adobo]] · Filipino · Easy · 45 min"


def test_mealplan_to_markdown_format():
    plan = MealPlan(
        week_of="2026-06-29",
        days=[
            DayPlan(
                weekday="Sunday",
                breakfast="Shakshuka",
                lunch="Wrap day",
                dinner="[[Chicken Adobo]] · Filipino · Easy · 45 min",
            ),
            DayPlan(
                weekday="Monday",
                breakfast="Scrambled eggs",
                lunch="Leftovers — Chicken Adobo",
                dinner="Leftovers — Chicken Adobo",
            ),
        ],
    )
    md = plan.to_markdown()
    assert "# Meal Plan — Week of 2026-06-29" in md
    assert "## Sunday" in md
    assert "**Breakfast:** Shakshuka" in md
    assert "**Lunch:** Wrap day" in md
    assert "**Dinner:** [[Chicken Adobo]] · Filipino · Easy · 45 min" in md
    assert "## Monday" in md
    assert "**Dinner:** Leftovers — Chicken Adobo" in md


def test_mealplan_to_markdown_starts_with_heading():
    plan = MealPlan(week_of="2026-07-06", days=[])
    assert plan.to_markdown().startswith("# Meal Plan — Week of 2026-07-06")


def test_mealplan_to_markdown_all_seven_days():
    from datetime import date, timedelta
    days = []
    for i in range(7):
        d = date(2026, 6, 29) + timedelta(days=i)
        days.append(DayPlan(
            weekday=d.strftime("%A"),
            breakfast="Eggs",
            lunch="Leftovers",
            dinner="[[Pasta]] · Italian · Easy · 30 min",
        ))
    plan = MealPlan(week_of="2026-06-29", days=days)
    md = plan.to_markdown()
    for name in ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]:
        assert f"## {name}" in md
