---
name: meal-plan
description: Generate or regenerate the weekly meal plan interactively
---

# Meal Plan

## What this skill does

Generates a weekly meal plan covering breakfast, lunch, and dinner for 7 days. Draws from the Obsidian recipe vault and sources one new recipe from the web. Writes the plan to `Meal Plans/Week of YYYY-MM-DD.md` in the vault.

## Process

1. **Ask what week to plan for.** Default: the next Sunday. Accept ISO dates (`2026-06-29`) or natural language ("this Sunday", "next week"). Convert to `YYYY-MM-DD`.

2. **Run the plan generator:**
   ```
   python /home/nickarmet/Desktop/Projects/MealPlanner/scripts/generate_plan.py \
     --config /home/nickarmet/Desktop/Projects/MealPlanner/config.yaml \
     --week-of <YYYY-MM-DD>
   ```
   Show the command output. If it errors, show the full error and stop.

3. **Read and display the generated plan.** Get `vault_path` from `config.yaml`, then read:
   `<vault_path>/Meal Plans/Week of <YYYY-MM-DD>.md`
   Display the full plan to the user.

4. **Ask for feedback.** "Does this plan look good, or would you like to regenerate or make changes?"
   - **Looks good** → confirm the plan is saved and offer to generate the grocery list now (invoke `/grocery-list`).
   - **Regenerate** → run the script again with the same `--week-of` date. It overwrites the file.
   - **Specific change** → edit the plan file directly with Read + Edit, then show the updated plan.

## Notes

- Newly sourced recipes always get `status: untried` — do not change this.
- The plan file overwrites any existing plan for the same week.
- To change dietary mode or preferences, use the `/meal-config` skill.
- The script requires `ANTHROPIC_API_KEY` set in `/home/nickarmet/Desktop/Projects/MealPlanner/.env`.
