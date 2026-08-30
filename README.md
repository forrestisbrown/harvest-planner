# 🍂 Harvest — Household Meal Planner (v4)

Warm, single-theme meal planner with real per-person dietary targeting,
honest data (no fake gram precision), and per-serving calories from the
USDA FoodData Central database.

## Run locally
```bash
python3 -m pip install -r requirements.txt
python3 db_setup.py --reset       # first time only
python3 -m streamlit run app.py
```
First launch shows onboarding — add your household and set preferences.

## Calories (USDA) — optional but recommended
Recipes show ~calories per serving, pulled live from the free USDA
FoodData Central API. Without a key the app still works; calories just show "—".

**Get a free key:** https://fdc.nal.usda.gov/api-key-signup/

**On Streamlit Cloud:** Manage app → Settings → Secrets, paste:
```
USDA_API_KEY = "your-key"
```
**Locally:** copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
and put your key in it. Never commit the real secrets file (`.gitignore` blocks it).

Note: calories are estimates. Weights convert exactly (1 lb → grams); volumes
(cups, tbsp) are approximate and flagged, since a cup of rice ≠ a cup of spinach.

## What's in v4
- **Onboarding first** — no preset members; you build the household.
- **Clean preferences** — each food type set to Never / Sometimes / Often / Love it,
  across red meat, poultry, pork, seafood, veg, legumes, pasta. Targets the menu.
- **Together or Individual** per week — one shared meal, or each person their own dish.
- **Simple grocery list** — plain item names (you buy by the pack); amounts live
  on the recipe card only.
- **Real recipe cards** — amounts, short steps, cook time, and ~calories/serving.
- **Quick filter** — meals about 20 min or less.
- **Swap a night** — replace any generated meal from the dropdown.
- **Add your own recipes** — with amounts, steps, and a type profile; calories
  auto-calc when you open the card.
- **Multi-store shared list, receipts + spend, household (non-food) items** — as before.

## Files
`app.py` UI · `core.py` logic · `db_setup.py` data + schema · `theme.py` warm theme ·
`usda.py` calorie API · `units.py` amount→grams · `cli.py` optional terminal.
