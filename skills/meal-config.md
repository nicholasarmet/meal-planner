---
name: meal-config
description: Update dietary mode, preferences, and effort limits in config.yaml without editing it manually
---

# Meal Config

## What this skill does

Shows the current meal planning configuration and lets you update any field interactively.
Writes changes directly to `config.yaml` and validates the result. Use this instead of
manually editing the YAML file.

## Editable Fields

| Field | Current value | What it controls |
|---|---|---|
| `dietary_mode` | — | `normal` \| `low-gluten` \| `paleo` \| `whole30` |
| `preferred_cuisines` | — | List of cuisine tags to prefer in meal selection |
| `weekday_effort_limit` | — | `easy` \| `medium` — hard recipes only on weekends |
| `dedicated_lunch_days` | — | How many explicit lunch days per week (0–7) |
| `new_recipes_per_week` | — | How many new recipes to source weekly (0–2) |
| `preferences.avoid_raw` | — | Ingredients to avoid raw (cooked form is fine) |

## Process

1. **Read the current config.**

   Read `/home/nickarmet/Desktop/Projects/MealPlanner/config.yaml` and display the
   editable fields in a clear table, filling in the "Current value" column from the file.

2. **Ask what to change.**

   > "Which field(s) would you like to update?"

   Accept natural language: "Switch to paleo mode", "Add Italian to preferred cuisines",
   "Set weekday effort to easy".

3. **Apply the change.**

   Load config.yaml with Read tool, make the edit with the Edit tool. Follow these rules:
   - `dietary_mode`: must be one of `normal`, `low-gluten`, `paleo`, `whole30`
   - `preferred_cuisines`: must be a YAML list (use `- item` syntax)
   - `weekday_effort_limit`: must be `easy` or `medium`
   - `dedicated_lunch_days`: must be an integer 0–7
   - `new_recipes_per_week`: must be an integer 0–2
   - `preferences.avoid_raw`: must be a YAML list under the `preferences:` key

   If the user's request is ambiguous, confirm the exact new value before editing.

4. **Validate the edit.**

   Run:
   ```bash
   cd /home/nickarmet/Desktop/Projects/MealPlanner
   source venv/bin/activate
   python -c "from scripts.config import load_config; c = load_config(); print('OK:', c['dietary_mode'])"
   ```

   If this errors, show the error, restore the original value with Edit, and stop.

5. **Confirm.**

   Show the updated config table. Ask: "Anything else to change?"
   - **Yes** → return to step 2.
   - **No** → done. The next `/meal-plan` run will pick up the new settings.

## Notes

- Never change `vault_path` — that's a one-time setup value.
- `sources` (the preferred recipe sources list) can be edited manually in the file;
  it's not exposed here to keep the interaction focused.
- Changes take effect on the next `/meal-plan` or `/grocery-list` run — no restart needed.
- If the user asks to add a dietary restriction that paleo doesn't cover (e.g., nut-free),
  explain that the `dietary` field on individual recipes handles this — there's no global
  nut-free mode. They can filter manually using `/find-recipe`.
