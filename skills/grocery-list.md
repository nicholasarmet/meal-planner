---
name: grocery-list
description: Generate or regenerate the grocery list from the current week's meal plan
---

# Grocery List

## What this skill does

Reads the week's meal plan from the vault, loads all linked recipes' ingredients, sends them to Claude for normalization and section assignment, and writes the grocery list to `Grocery Lists/YYYY-MM-DD.md`.

## Process

1. **Identify the meal plan.** Ask: "Which week? (default: most recent plan in Meal Plans/)". If "this week" or "current", find the most recently modified file in `<vault_path>/Meal Plans/`. Extract the `YYYY-MM-DD` date from the filename.

2. **Run the grocery list generator:**
   ```
   python /home/nickarmet/Desktop/Projects/MealPlanner/scripts/aggregate_grocery.py \
     --config /home/nickarmet/Desktop/Projects/MealPlanner/config.yaml \
     "<vault_path>/Meal Plans/Week of <YYYY-MM-DD>.md"
   ```
   Show the command output. If it errors, show the full error and stop.

3. **Read and display the grocery list.** Find it at `<vault_path>/Grocery Lists/<YYYY-MM-DD>.md`. Display the full list.

4. **Ask for feedback.** "Does this list look complete?"
   - **Looks good** → done.
   - **Missing item** → ask what to add and what section it belongs to; edit the file with Edit tool.
   - **Wrong section** → move the item using Edit tool.
   - **Review items** → items in `## Review` are near-matches Claude was unsure about; ask the user which to merge.

## Notes

- Store sections appear in this exact order: Produce, Pantry, Snacks, Cereal, Frozen Goods, Spices, Baking Supplies, Refrigerated, Dairy, Cheese & Cured Meats.
- `## Check Stock` items are pantry staples likely already on hand — review before shopping.
- `## Review` items are near-matches needing manual resolution before shopping.
- The script requires `ANTHROPIC_API_KEY` set in `/home/nickarmet/Desktop/Projects/MealPlanner/.env`.
