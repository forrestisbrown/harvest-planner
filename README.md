# 🍂 Harvest — Household Meal Planner (v5)

Warm, single-theme meal planner with real per-person dietary targeting,
breakfast/lunch/dinner planning, honest data, and USDA-powered nutrition.

## Run locally
```bash
python3 -m pip install -r requirements.txt
python3 db_setup.py --reset       # first time only
python3 -m streamlit run app.py
```
First launch shows onboarding — add your household and set preferences.

## USDA nutrition (optional but recommended)
Recipe cards show calories + protein/carbs/fat per serving, and the Lookup tab
lets you check any food. Data comes from the free USDA FoodData Central API.
Without a key the app still works; nutrition just shows "—".

**Get a free key:** https://fdc.nal.usda.gov/api-key-signup/
**Streamlit Cloud:** Manage app → Settings → Secrets, paste:
```
USDA_API_KEY = "your-key"
```
**Locally:** copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
and add your key. Never commit the real secrets file (`.gitignore` blocks it).

Nutrition is estimated. Weights convert exactly (1 lb → grams); volumes (cups,
tbsp) are approximate, since a cup of rice ≠ a cup of spinach by weight.

## What's new in v5
- **Breakfast, lunch & dinner** — 63 recipes across all three meals (12/12/39),
  each with cuisines, cook times, and preference targeting.
- **Flexible planning grid** — pick how many days (1–7) and which meals to plan;
  it fills only the slots you choose.
- **Steer the plan** — a Mood/cuisine filter, Quick-only, and Favorites, applied
  to the whole generation.
- **Per-meal re-roll & swap** — don't like one meal? Re-roll just that slot (🎲)
  or pick a specific replacement, without regenerating everything.
- **Full macros on cards** — calories, protein, carbs, fat per serving (USDA).
- **Food Lookup tab** — type any food + grams, get USDA nutrition.
- **Grocery de-dupe** — an ingredient used across multiple meals appears once.
- **Custom recipes** — add your own with a meal type, amounts, and steps.

Plus everything from before: per-person Never/Sometimes/Often/Love preferences,
Together vs. Individual targeting, multi-store shared list, receipts + spend,
household (non-food) items.

## Files
`app.py` UI · `core.py` logic · `db_setup.py` data + schema · `theme.py` warm theme ·
`usda.py` nutrition API · `units.py` amount→grams · `cli.py` optional terminal.
