---
name: add-recipe
description: Capture a recipe from a URL, PDF, or pasted text into the Obsidian vault with consistent formatting
---

# Add Recipe

## What this skill does

Ingests a recipe from any source into the Obsidian vault, using Claude to extract and normalize it into the standard format. Always shows the extracted fields to the user before saving so they can correct anything.

## Process

1. **Ask the user for the source:**
   - If a URL: `python /home/nickarmet/Desktop/Projects/MealPlanner/scripts/ingest_recipe.py <url>`
   - If a PDF path: `python /home/nickarmet/Desktop/Projects/MealPlanner/scripts/ingest_recipe.py <path>`
   - If pasted text: call `ingest_from_text()` directly with the pasted content

2. **Read the saved recipe file** from the vault path printed by the script.

3. **Show the user the key extracted fields:**
   - title, cuisine, meal_type, effort, time_total, dietary, servings
   - First 3 ingredients

4. **Ask:** "Does everything look right? Any fields to correct?"
   - If yes → done, confirm path
   - If corrections needed → edit the markdown file with the corrected values, confirm

5. **Set a reminder:** If the recipe is from a paid site (NYT Cooking, ATK, Cook's Illustrated, King Arthur Baking), note that a subscription may be required to view the original.

## Notes

- `status` is always set to `untried` on ingest — never change this
- `rating` is always null on ingest
- If the user provides a cookbook source, ask for: book title, author, page number
