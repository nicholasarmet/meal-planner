#!/usr/bin/env bash
# Weekly meal planning run: generate meal plan then grocery list.
# Cron: 0 8 * * 0  (Sundays at 8am)
set -euo pipefail

PROJECT="/home/nickarmet/Desktop/Projects/MealPlanner"
CONFIG="$PROJECT/config.yaml"
LOG_DIR="$HOME/.local/share/meal-planner"
mkdir -p "$LOG_DIR"

source "$PROJECT/venv/bin/activate"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') — Starting weekly meal plan ===" >> "$LOG_DIR/weekly.log"

# Step 1: Generate meal plan (defaults to next Sunday)
python "$PROJECT/scripts/generate_plan.py" --config "$CONFIG" \
    >> "$LOG_DIR/weekly.log" 2>&1

# Step 2: Resolve vault path and plan date from config
VAULT_PATH=$(python -c "
import yaml
with open('$CONFIG') as f:
    print(yaml.safe_load(f)['vault_path'])
")

PLAN_DATE=$(python -c "
from datetime import date, timedelta
d = date.today()
days = (6 - d.weekday()) % 7
print((d + timedelta(days=days)).isoformat())
")

# Step 3: Generate grocery list from the just-created plan
python "$PROJECT/scripts/aggregate_grocery.py" \
    --config "$CONFIG" \
    "$VAULT_PATH/Meal Plans/Week of $PLAN_DATE.md" \
    >> "$LOG_DIR/weekly.log" 2>&1

echo "=== $(date '+%Y-%m-%d %H:%M:%S') — Done ===" >> "$LOG_DIR/weekly.log"
