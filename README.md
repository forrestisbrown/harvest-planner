# 🍂 Harvest — Household Meal Planner

Warm, self-hosted meal planning for a household. Plan a week, favorite meals,
remix them, build a multi-store shared shopping list, log receipts and track
spend, and keep household (non-food) items in the same place. Light & dark mode.

Runs free on your PC, or free online for you + Lizzy via Streamlit Community Cloud.

## Files
| File | Role |
|------|------|
| `db_setup.py` | Schema + seed (28 recipes, stores, members). Run once. |
| `core.py` | All logic: planner, favorites, remix, shopping list, receipts, spend. |
| `app.py` | The web app (Streamlit). This is the main interface. |
| `theme.py` | Warm fall palette + light/dark styling. |
| `cli.py` | Optional terminal access. |
| `.streamlit/config.toml` | Theme colors. |
| `requirements.txt` | For cloud deploy. |

## Run locally
```bash
python3 -m pip install -r requirements.txt
python3 db_setup.py --reset      # first time only
python3 -m streamlit run app.py
```
Opens in your browser. Use the sidebar to pick who you are, toggle dark mode,
manage members and stores.

## Put it online for you + Lizzy (free)

This is the Streamlit Community Cloud path. ~15 minutes, no server to manage.

1. **Make a GitHub account** (github.com) if you don't have one.
2. **Create a new repository** — name it anything, e.g. `harvest-planner`. Set it
   to Private if you like; Streamlit Cloud works with private repos.
3. **Upload these files** to the repo (GitHub's "Add file → Upload files" works
   fine — drag in everything EXCEPT `mealplanner.db`, `uploads/`, and
   `__pycache__/`; the `.gitignore` already excludes them).
4. Go to **share.streamlit.io**, sign in with GitHub, click **New app**, pick
   your repo, and set the main file to `app.py`. Deploy.
5. You'll get a URL like `https://harvest-planner.streamlit.app`. Open it on
   your phone and Lizzy's — both of you use the same live app.

### One thing to know about cloud data
On Streamlit Community Cloud the SQLite file resets when the app restarts
(their storage is temporary). For two people sharing a list that needs to
persist, the clean upgrade is a free hosted database — **Supabase** or **Neon**
(both have free Postgres tiers). When you're ready for that, it's a small change
to `core.py`'s connection setup; everything else stays the same. Locally, your
data persists fine in `mealplanner.db`.

## How the household "branch" system works
Each recipe ingredient is tagged `shared` or a member's name. Shared items are
cooked for everyone and split evenly for calories; a member-tagged item (e.g.
cheese for You, extra veggies for Lizzy) only shows up on the list and in the
calories when that member is active. Toggle someone off and their extras vanish
from the list automatically.

## Features at a glance
- **Plan** — generate a 3–7 dinner week, swap any night, favorites-only mode,
  live grocery preview + calorie split, push the whole week to the shopping list.
- **Recipes** — 28 to start across American/Mexican/Asian/Italian/Indian/
  Mediterranean. Filter by cuisine/type/favorites. Each recipe shows related
  dishes (by shared ingredients + cuisine) and a remix/variation idea. Add your
  own recipes.
- **Shopping List** — shared, multi-store. Filter by store, by person, or
  food vs household. Move an item to another store so you don't forget the
  second stop. Check items off, clear checked, share the list as text.
- **Receipts & Spend** — photo + total (optionally itemize). Tracks total spend,
  spend by store, and most-bought items.
- **Household** — non-food items (paper towels, detergent) on the same list.
