"""
usda.py — USDA FoodData Central integration for per-serving calories.

Reads the API key from Streamlit secrets (USDA_API_KEY) or the USDA_API_KEY
env var; falls back to DEMO_KEY. Every network path is wrapped so a missing
key, a rate-limit, or an outage NEVER breaks the app — callers get None and
show "—" for calories.

Docs: https://fdc.nal.usda.gov/api-guide  (Energy nutrient is per 100 g)
"""
import json, urllib.request, urllib.parse, os, time

_CACHE = {}   # ingredient name -> kcal per 100g (or None)

def _api_key():
    # Prefer Streamlit secrets when available, then env, then DEMO_KEY.
    try:
        import streamlit as st
        if "USDA_API_KEY" in st.secrets:
            return st.secrets["USDA_API_KEY"]
    except Exception:
        pass
    return os.environ.get("USDA_API_KEY", "DEMO_KEY")

def kcal_per_100g(name):
    """Return calories per 100g for an ingredient, or None if unavailable.
    Cached per process to respect the 1,000 req/hr limit."""
    key_name = name.strip().lower()
    if key_name in _CACHE:
        return _CACHE[key_name]
    val = None
    try:
        api = _api_key()
        url = ("https://api.nal.usda.gov/fdc/v1/foods/search?"
               + urllib.parse.urlencode({
                    "query": name, "pageSize": 1,
                    "dataType": "Foundation,SR Legacy",
                    "api_key": api}))
        req = urllib.request.Request(url, headers={"User-Agent": "Harvest/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        foods = data.get("foods") or []
        if foods:
            for n in foods[0].get("foodNutrients", []):
                nm = (n.get("nutrientName") or "").lower()
                unit = (n.get("unitName") or "").upper()
                if nm.startswith("energy") and unit == "KCAL":
                    val = float(n.get("value")); break
    except Exception:
        val = None
    _CACHE[key_name] = val
    return val

def recipe_calories(ingredient_grams, servings=1):
    """ingredient_grams: list of (name, grams). Returns (total_kcal, per_serving,
    coverage) where coverage is the fraction of ingredients we could price.
    per_serving is None if we couldn't price anything."""
    total = 0.0; priced = 0; n = 0
    for name, grams in ingredient_grams:
        n += 1
        per100 = kcal_per_100g(name)
        if per100 is None or not grams:
            continue
        total += per100 * (grams / 100.0); priced += 1
    if priced == 0:
        return (None, None, 0.0)
    per_serving = total / max(servings, 1)
    return (round(total), round(per_serving), priced / n)
