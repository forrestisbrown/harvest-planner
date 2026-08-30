"""
mealdb.py — TheMealDB recipe import (free test key '1').

Endpoints (V1, no signup needed):
  search by name:      /search.php?s=<query>
  lookup by id:        /lookup.php?i=<id>
  random:              /random.php
  list categories:     /list.php?c=list
  list areas/cuisines: /list.php?a=list
  filter by category:  /filter.php?c=<cat>   (returns id+name+thumb only)
  filter by area:      /filter.php?a=<area>  (returns id+name+thumb only)

TheMealDB returns ingredients as strIngredient1..20 + strMeasure1..20.
We map their data into Harvest's recipe shape. Nutrition is NOT provided by
TheMealDB — Harvest computes it from the measures via USDA, same as our own
recipes. Every call is wrapped so a network failure never breaks the app.

Attribution: TheMealDB asks that you credit it as the source of imported
recipes and images; we tag imported recipes and show the credit in the UI.
"""
import json, urllib.request, urllib.parse

BASE = "https://www.themealdb.com/api/json/v1/1"
KEY_NOTE = "Imported from TheMealDB"

def _get(path):
    try:
        req=urllib.request.Request(BASE+path, headers={"User-Agent":"Harvest/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except Exception:
        return None

# ---- discovery ----
def list_areas():
    d=_get("/list.php?a=list")
    if not d or not d.get("meals"): return []
    return sorted(m["strArea"] for m in d["meals"] if m.get("strArea"))

def list_categories():
    d=_get("/list.php?c=list")
    if not d or not d.get("meals"): return []
    return sorted(m["strCategory"] for m in d["meals"] if m.get("strCategory"))

# ---- browse (returns lightweight cards: id, name, thumb) ----
def by_area(area):
    d=_get("/filter.php?a="+urllib.parse.quote(area))
    return d.get("meals") or [] if d else []

def by_category(cat):
    d=_get("/filter.php?c="+urllib.parse.quote(cat))
    return d.get("meals") or [] if d else []

def search(query):
    d=_get("/search.php?s="+urllib.parse.quote(query))
    return d.get("meals") or [] if d else []

def random_meal():
    d=_get("/random.php")
    ms=d.get("meals") if d else None
    return ms[0] if ms else None

def lookup(meal_id):
    d=_get("/lookup.php?i="+urllib.parse.quote(str(meal_id)))
    ms=d.get("meals") if d else None
    return ms[0] if ms else None

# ---- convert a TheMealDB meal payload into Harvest's recipe shape ----
# Rough cuisine normalization to our set; unknowns pass through.
_AREA_TO_CUISINE = {
    "American":"American","Italian":"Italian","Mexican":"Mexican","Chinese":"Asian",
    "Japanese":"Asian","Thai":"Asian","Indian":"Indian","Greek":"Mediterranean",
    "Turkish":"Mediterranean","French":"Italian","British":"American","Canadian":"American",
    "Spanish":"Mediterranean","Moroccan":"Mediterranean","Vietnamese":"Asian",
}

# map TheMealDB category to our simple 'category' + a rough food-type profile
_CAT_TO_CATEGORY = {
    "Beef":"beef","Chicken":"chicken","Pork":"pork","Lamb":"beef","Goat":"beef",
    "Seafood":"seafood","Vegetarian":"vegetarian","Vegan":"vegetarian",
    "Pasta":"pasta","Breakfast":"breakfast","Side":"vegetarian","Starter":"vegetarian",
    "Dessert":"dessert","Miscellaneous":"dinner",
}

def _guess_profile(category, ingredients):
    from db_setup import FOOD_TYPES
    tp={t:0 for t in FOOD_TYPES}
    text=" ".join(i.lower() for i,_ in ingredients)
    def has(*words): return any(w in text for w in words)
    # Prefer the category signal first, then ingredient hints — and don't let a
    # generic word flip on a second meat the recipe doesn't actually contain.
    if category=="beef" or has("beef","steak","lamb "," mince","ground beef"): tp["red_meat"]=3
    if category=="chicken" or has("chicken","turkey"): tp["poultry"]=3
    if category=="pork" or has("pork","bacon","sausage","ham "): tp["pork"]=3
    if category=="seafood" or has("fish","salmon","shrimp","prawn","tuna","cod","tilapia"): tp["seafood"]=3
    if category=="vegetarian" or has("bean","lentil","chickpea"): tp["legumes"]=max(tp["legumes"],2)
    if has("pasta","spaghetti","noodle","penne","macaroni"): tp["pasta"]=max(tp["pasta"],2)
    if has("broccoli","spinach","pepper","tomato","onion","carrot","zucchini","kale","lettuce","cabbage"):
        tp["veg"]=max(tp["veg"],2)
    return tp

def to_harvest_recipe(meal):
    """Return dict ready for core.add_recipe, or None if unusable.
    Keys: name, category, cuisine, meal, minutes, type_profile, steps, items."""
    if not meal or not meal.get("strMeal"): return None
    name=meal["strMeal"].strip()
    area=meal.get("strArea") or ""
    cat_raw=meal.get("strCategory") or ""
    cuisine=_AREA_TO_CUISINE.get(area,"American")
    category=_CAT_TO_CATEGORY.get(cat_raw,"dinner")
    meal_slot="breakfast" if cat_raw=="Breakfast" else "dinner"
    # ingredients + measures
    items=[]
    for i in range(1,21):
        ing=(meal.get(f"strIngredient{i}") or "").strip()
        meas=(meal.get(f"strMeasure{i}") or "").strip()
        if ing and ing.lower() not in ("","null"):
            items.append((ing, meas, "shared"))
    if not items: return None
    tp=_guess_profile(category, [(i,m) for i,m,_ in items])
    steps=(meal.get("strInstructions") or "").strip()
    # TheMealDB has no time; leave a sensible default (not fake-precise)
    return {"name":name,"category":category,"cuisine":cuisine,"meal":meal_slot,
            "minutes":30,"type_profile":tp,"steps":steps,"items":items,
            "source_id":meal.get("idMeal"),"thumb":meal.get("strMealThumb")}
