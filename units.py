"""
units.py — parse human amounts ("1 lb", "2 cups rice", "3 cloves") into grams.

Weight units are exact. Volume->grams depends on the ingredient, so we keep a
small density table (grams per cup) for common items and fall back to a generic
value, flagging when we've estimated. Counts ("3 cloves", "2 eggs") use a
per-item gram table. Anything unparseable returns (None, note).
"""
import re

# exact weight conversions to grams
_WEIGHT = {"g":1,"gram":1,"grams":1,"kg":1000,"oz":28.35,"ounce":28.35,
           "ounces":28.35,"lb":453.6,"lbs":453.6,"pound":453.6,"pounds":453.6}

# grams per cup, by ingredient keyword (approximate but realistic)
_CUP_G = {
    "rice":185,"flour":120,"sugar":200,"milk":240,"water":240,"broth":240,
    "yogurt":245,"marinara":245,"sauce":245,"beans":180,"chickpeas":164,
    "lentils":192,"spinach":30,"greens":30,"lettuce":36,"broccoli":91,
    "cheese":113,"pasta":100,"oats":90,"butter":227,"oil":218,"tomato":180,
    "onion":160,"pepper":150,"mushroom":70,"corn":165,"quinoa":170,
}
_GENERIC_CUP = 150  # fallback grams/cup

_TBSP = 15.0/240   # fraction of a cup
_TSP  = 5.0/240

# grams per single item, by keyword
_ITEM_G = {
    "egg":50,"clove":3,"garlic":3,"onion":110,"tomato":123,"potato":170,
    "pepper":120,"lemon":58,"lime":67,"avocado":150,"carrot":61,"zucchini":196,
    "tortilla":30,"bun":50,"naan":90,"pita":60,"roll":60,"banana":118,"sausage":75,
    "chop":180,"fillet":170,"breast":170,"thigh":90,
}

def _density_cup(name):
    n=name.lower()
    for k,v in _CUP_G.items():
        if k in n: return v
    return _GENERIC_CUP

def _item_grams(name):
    n=name.lower()
    for k,v in _ITEM_G.items():
        if k in n: return v
    return None

def to_grams(amount_text, ingredient_name):
    """Return (grams, note). note is '' if exact, else a short estimate flag.
    amount_text like '1 lb', '2 cups', '3', '1/2 cup', '400 g'."""
    if not amount_text: return (None, "no amount")
    t=amount_text.strip().lower()
    # pull leading quantity (supports fractions like 1/2 and mixed 1 1/2)
    m=re.match(r'^\s*(\d+\s+\d+/\d+|\d+/\d+|\d*\.?\d+)\s*(.*)$', t)
    if not m: return (None, "unparsed")
    qtxt, unit = m.group(1), m.group(2).strip()
    # value
    if " " in qtxt and "/" in qtxt:
        whole,frac=qtxt.split(); a,b=frac.split("/"); qty=float(whole)+float(a)/float(b)
    elif "/" in qtxt:
        a,b=qtxt.split("/"); qty=float(a)/float(b)
    else:
        qty=float(qtxt)
    unit_word=unit.split()[0] if unit else ""
    # weight
    if unit_word in _WEIGHT:
        return (round(qty*_WEIGHT[unit_word]), "")
    # volume
    if unit_word in ("cup","cups"):
        return (round(qty*_density_cup(ingredient_name)), "est. (volume)")
    if unit_word in ("tbsp","tablespoon","tablespoons"):
        return (round(qty*_TBSP*_density_cup(ingredient_name)), "est. (volume)")
    if unit_word in ("tsp","teaspoon","teaspoons"):
        return (round(qty*_TSP*_density_cup(ingredient_name)), "est. (volume)")
    # count / no unit -> per-item grams
    ig=_item_grams(ingredient_name)
    if ig: return (round(qty*ig), "est. (count)")
    return (None, "unknown unit")
