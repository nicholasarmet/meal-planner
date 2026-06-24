---
name: find-recipe
description: Discover a recipe by natural language criteria — searches the vault first, then preferred sources
---

# Find Recipe

## What this skill does

Finds a recipe matching natural language criteria. Searches the vault for untried recipes
first, then searches the preferred sources list from `config.yaml` if the vault doesn't
have enough matches. If the user picks a web recipe, ingests it into the vault automatically.

## Process

1. **Ask what the user is looking for.** Accept free-form descriptions:
   > "something crunchy", "quick weeknight Asian", "paleo, Instant Pot, 30 minutes"

2. **Load config and vault path.**

   Read `/home/nickarmet/Desktop/Projects/MealPlanner/config.yaml` to get `vault_path`
   and `sources`.

3. **Search the vault for untried recipes.**

   Run:
   ```bash
   cd /home/nickarmet/Desktop/Projects/MealPlanner
   source venv/bin/activate
   python -c "
   import json
   from scripts.config import load_config, get_vault_path
   from scripts.vault import find_recipes
   config = load_config()
   vault = get_vault_path(config)
   recipes = find_recipes(vault, status='untried')
   print(json.dumps([{
       'title': r.title,
       'cuisine': r.cuisine,
       'effort': r.effort,
       'time_total': r.time_total,
       'dietary': r.dietary,
       'appliances': r.appliances,
   } for r in recipes], indent=2))
   "
   ```

   Filter the output by the user's criteria. Present up to 5 matching untried recipes as
   a numbered list with: title, cuisine, effort, time.

4. **If 3 or more vault matches found:** ask the user to pick one or ask for more options.
   - If they pick one: confirm it's in the vault and done (no ingest needed).
   - If they want more: proceed to step 5.

5. **If fewer than 3 vault matches:** search the web using DuckDuckGo.

   Tell the user: "I didn't find many vault matches — searching the web now."

   Run a live search using the user's criteria as the query:
   ```bash
   cd /home/nickarmet/Desktop/Projects/MealPlanner
   source venv/bin/activate
   python -c "
   import json
   from scripts.config import load_config
   from scripts.search_recipe import search_recipe_urls
   config = load_config()
   sources = config.get('sources', [])
   urls = search_recipe_urls('<user criteria as search query>', preferred_sources=sources, max_results=6)
   print(json.dumps(urls, indent=2))
   "
   ```

   Present up to 5 results as a numbered list showing: URL domain and page title
   (derive the title from the URL slug — replace hyphens with spaces).

6. **Present the options.** Show a numbered list of candidates with source site and a
   one-line description derived from the URL slug.

7. **User picks one.** Ingest it:

   ```bash
   cd /home/nickarmet/Desktop/Projects/MealPlanner
   source venv/bin/activate
   python scripts/ingest_recipe.py <url> \
     --config /home/nickarmet/Desktop/Projects/MealPlanner/config.yaml
   ```

   If the script errors, show the error and stop.

8. **Confirm.** Read the saved recipe file (path is printed by the script), show the
   user: title, cuisine, effort, time_total, and first 3 ingredients. Ask: "Does this
   look right?"
   - **Yes** → done. Recipe is in the vault with `status: untried`.
   - **No** → offer to edit the file directly or try a different URL.

## Notes

- Never change `status` away from `untried` — the user upgrades recipes themselves after making them.
- If the user wants to add a vault recipe to this week's plan instead of just finding it,
  direct them to `/meal-plan` to regenerate.
- For PDF recipes (cookbook, scan), use `python scripts/ingest_recipe.py <path-to-pdf>`.
