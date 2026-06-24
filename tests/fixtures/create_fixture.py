"""Run once: python tests/fixtures/create_fixture.py"""
import gzip, json, zipfile
from pathlib import Path

RECIPES = [
    {
        "uid": "abc123",
        "name": "Test Chicken",
        "ingredients": "2 lbs chicken thighs\n1 cup soy sauce",
        "directions": "1. Cook the chicken.\n2. Add soy sauce.",
        "notes": "Family favorite",
        "categories": ["Tried and Tested"],
        "rating": 4,
        "source": "Serious Eats",
        "source_url": "https://www.seriouseats.com/test",
        "created": "2023-01-01 12:00:00",
    },
    {
        "uid": "def456",
        "name": "Test Salad",
        "ingredients": "3 cups mixed greens\n1 lemon",
        "directions": "1. Toss greens.\n2. Squeeze lemon.",
        "notes": "",
        "categories": [],
        "rating": 0,
        "source": "",
        "source_url": "",
        "created": "2023-06-15 08:00:00",
    },
]

out = Path(__file__).parent / "sample.paprikarecipes"
with zipfile.ZipFile(out, "w") as zf:
    for r in RECIPES:
        zf.writestr(f"{r['uid']}.paprika", gzip.compress(json.dumps(r).encode()))
print(f"Created {out}")
