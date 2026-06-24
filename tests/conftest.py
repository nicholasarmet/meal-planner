from pathlib import Path
import pytest


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_vault(tmp_path):
    for folder in [
        "Recipes/Breakfast",
        "Recipes/Lunch",
        "Recipes/Dinner",
        "Recipes/Baking",
        "Meal Plans",
        "Grocery Lists",
    ]:
        (tmp_path / folder).mkdir(parents=True)
    return tmp_path
