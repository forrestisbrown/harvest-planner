"""
usda.py — USDA FoodData Central: calories + macros (protein/carbs/fat).
Key from st.secrets['USDA_API_KEY'] or env; falls back to DEMO_KEY.
Every path is guarded so the app never breaks on a missing key or outage.
"""
import json, urllib.request, urllib.parse, os

_CACHE = {}   # name -> dict(kcal, protein, carbs, fat) per 100g, or None

# USDA nutrient names we care about (per 100 g)
_WANT = {
    "energy": ("kcal", "KCAL"),
    "protein": ("protein", None),
    "carbohydrate, by difference": ("carbs", None),
    "total lipid (fat)": ("fat", None),
}

def _api_key():
    try:
        import streamlit as st
        if "USDA_API_KEY" in st.secrets: return st.secrets["USDA_API_KEY"]
    except Exception: pass
    return os.environ.get("USDA_API_KEY", "DEMO_KEY")

def nutrients_per_100g(name):
    """Return {kcal,protein,carbs,fat} per 100g or None. Cached per process."""
    key=name.strip().lower()
    if key in _CACHE: return _CACHE[key]
    result=None
    try:
        url=("https://api.nal.usda.gov/fdc/v1/foods/search?"
             +urllib.parse.urlencode({"query":name,"pageSize":1,
                "dataType":"Foundation,SR Legacy","api_key":_api_key()}))
        req=urllib.request.Request(url, headers={"User-Agent":"Harvest/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data=json.load(r)
        foods=data.get("foods") or []
        if foods:
            out={}
            for n in foods[0].get("foodNutrients", []):
                nm=(n.get("nutrientName") or "").lower()
                unit=(n.get("unitName") or "").upper()
                val=n.get("value")
                if val is None: continue
                if nm.startswith("energy") and unit=="KCAL": out["kcal"]=float(val)
                elif nm=="protein": out["protein"]=float(val)
                elif nm.startswith("carbohydrate"): out["carbs"]=float(val)
                elif nm.startswith("total lipid"): out["fat"]=float(val)
            if out.get("kcal") is not None:
                result={"kcal":out.get("kcal"),"protein":out.get("protein",0.0),
                        "carbs":out.get("carbs",0.0),"fat":out.get("fat",0.0),
                        "desc":foods[0].get("description","")}
    except Exception:
        result=None
    _CACHE[key]=result
    return result

def kcal_per_100g(name):
    n=nutrients_per_100g(name)
    return n["kcal"] if n else None

def recipe_macros(ingredient_grams, servings=1):
    """ingredient_grams: [(name,grams)]. Returns dict per serving:
    {kcal,protein,carbs,fat,coverage} or {...None...} if nothing priced."""
    tot={"kcal":0.0,"protein":0.0,"carbs":0.0,"fat":0.0}; priced=0; n=0
    for name,grams in ingredient_grams:
        n+=1
        macros=nutrients_per_100g(name)
        if not macros or not grams: continue
        f=grams/100.0
        tot["kcal"]+=macros["kcal"]*f
        tot["protein"]+=macros.get("protein",0)*f
        tot["carbs"]+=macros.get("carbs",0)*f
        tot["fat"]+=macros.get("fat",0)*f
        priced+=1
    if priced==0:
        return {"kcal":None,"protein":None,"carbs":None,"fat":None,"coverage":0.0}
    s=max(servings,1)
    return {"kcal":round(tot["kcal"]/s),"protein":round(tot["protein"]/s),
            "carbs":round(tot["carbs"]/s),"fat":round(tot["fat"]/s),
            "coverage":priced/n}

# convenience for the lookup tab: nutrition for a typed food at a given grams
def lookup(name, grams=100):
    m=nutrients_per_100g(name)
    if not m: return None
    f=grams/100.0
    return {"desc":m.get("desc",name),"grams":grams,
            "kcal":round(m["kcal"]*f),"protein":round(m.get("protein",0)*f,1),
            "carbs":round(m.get("carbs",0)*f,1),"fat":round(m.get("fat",0)*f,1)}
