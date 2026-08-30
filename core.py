"""core.py — v4 logic. Simple grocery list (no grams), USDA per-serving calories,
quick filter, night swap, custom recipes with steps, clean preference model."""
import json, random
from collections import defaultdict
from db_setup import connect, FOOD_TYPES, PREF_LEVELS, DIET_PRESETS
import units, usda

PREF_IDX={lv:i for i,lv in enumerate(PREF_LEVELS)}  # never0 sometimes1 often2 love3

# ---- settings ----
def get_setting(c,k,d=None):
    r=c.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone(); return r["value"] if r else d
def set_setting(c,k,v):
    c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=?",(k,str(v),str(v))); c.commit()
def is_onboarded(c): return get_setting(c,"onboarded","0")=="1"

# ---- members ----
def members(c, active_only=False):
    q="SELECT id,name,diet_label,prefs,active FROM members"
    if active_only: q+=" WHERE active=1"
    out=[]
    for r in c.execute(q+" ORDER BY id"):
        d=dict(r); d["prefs"]=json.loads(d["prefs"] or "{}"); out.append(d)
    return out
def active_member_names(c): return [m["name"] for m in members(c,active_only=True)]
def add_member(c,name,diet_label="Omnivore",prefs=None):
    if prefs is None: prefs=dict(DIET_PRESETS.get(diet_label,DIET_PRESETS["Omnivore"]))
    c.execute("INSERT OR IGNORE INTO members(name,diet_label,prefs) VALUES(?,?,?)",(name,diet_label,json.dumps(prefs))); c.commit()
def update_member_prefs(c,name,diet_label,prefs):
    c.execute("UPDATE members SET diet_label=?,prefs=? WHERE name=?",(diet_label,json.dumps(prefs),name)); c.commit()
def set_member_active(c,name,a): c.execute("UPDATE members SET active=? WHERE name=?",(1 if a else 0,name)); c.commit()
def remove_member(c,name): c.execute("DELETE FROM members WHERE name=?",(name,)); c.commit()

# ---- recipes ----
def recipes(c, favorites_only=False, cuisine=None, category=None, quick_only=False, meal=None):
    q="SELECT * FROM recipes WHERE 1=1"; p=[]
    if favorites_only: q+=" AND is_favorite=1"
    if quick_only: q+=" AND is_quick=1"
    if meal and meal!="All": q+=" AND meal=?"; p.append(meal)
    if cuisine and cuisine!="All": q+=" AND cuisine=?"; p.append(cuisine)
    if category and category!="All": q+=" AND category=?"; p.append(category)
    out=[]
    for r in c.execute(q+" ORDER BY name",p):
        d=dict(r); d["type_profile"]=json.loads(d["type_profile"] or "{}"); out.append(d)
    return out
def recipe_by_id(c,rid):
    r=c.execute("SELECT * FROM recipes WHERE id=?",(rid,)).fetchone()
    if not r: return None
    d=dict(r); d["type_profile"]=json.loads(d["type_profile"] or "{}"); return d
def cuisines(c): return [r["cuisine"] for r in c.execute("SELECT DISTINCT cuisine FROM recipes ORDER BY cuisine")]
def categories(c): return sorted({r["category"] for r in recipes(c)})
def toggle_favorite(c,rid): c.execute("UPDATE recipes SET is_favorite=1-is_favorite WHERE id=?",(rid,)); c.commit()
def recipe_lines(c,rid):
    return [dict(r) for r in c.execute("""SELECT i.name ingredient,i.aisle,i.kind,ri.amount,ri.branch
        FROM recipe_ingredients ri JOIN ingredients i ON i.id=ri.ingredient_id WHERE ri.recipe_id=?""",(rid,))]

def add_recipe(c,name,category,cuisine,servings,minutes,type_profile,steps,items,cal=None,meal="dinner"):
    quick=1 if minutes<=20 else 0
    rid=c.execute("""INSERT INTO recipes(name,category,cuisine,servings,minutes,meal,is_quick,is_custom,type_profile,steps,cal_per_serving)
                     VALUES(?,?,?,?,?,?,?,1,?,?,?)""",
                  (name,category,cuisine,servings,minutes,meal,quick,json.dumps(type_profile),steps,cal)).lastrowid
    for iname,amount,branch in items:
        row=c.execute("SELECT id FROM ingredients WHERE name=?",(iname,)).fetchone()
        if not row:
            c.execute("INSERT INTO ingredients(name) VALUES(?)",(iname,))
            row=c.execute("SELECT id FROM ingredients WHERE name=?",(iname,)).fetchone()
        c.execute("INSERT OR REPLACE INTO recipe_ingredients(recipe_id,ingredient_id,amount,branch) VALUES(?,?,?,?)",
                  (rid,row["id"],amount,branch))
    c.commit(); return rid

def recipe_name_exists(c, name):
    return c.execute("SELECT 1 FROM recipes WHERE lower(name)=lower(?)",(name,)).fetchone() is not None

def import_recipe(c, hr):
    """Save a recipe dict from mealdb.to_harvest_recipe(). Skips if name exists.
    Returns (rid or None, status) where status in {'added','duplicate','bad'}."""
    if not hr or not hr.get("name") or not hr.get("items"):
        return None, "bad"
    if recipe_name_exists(c, hr["name"]):
        return None, "duplicate"
    rid=add_recipe(c, hr["name"], hr["category"], hr["cuisine"], 4,
                   hr.get("minutes",30), hr["type_profile"], hr.get("steps",""),
                   hr["items"], meal=hr.get("meal","dinner"))
    return rid, "added"

def delete_recipe(c,rid): c.execute("DELETE FROM recipes WHERE id=?",(rid,)); c.commit()

# ---- USDA per-serving calories (cached in the recipes row once known) ----
def recipe_macros(c, rid):
    """Return {kcal,protein,carbs,fat,coverage} per serving from USDA (live).
    Caches kcal in the recipes row; macros are computed each call (cheap, cached
    in usda module per process)."""
    row=c.execute("SELECT servings FROM recipes WHERE id=?",(rid,)).fetchone()
    grams=[]
    for l in recipe_lines(c,rid):
        g,_=units.to_grams(l["amount"], l["ingredient"])
        if g: grams.append((l["ingredient"], g))
    m=usda.recipe_macros(grams, row["servings"] or 1)
    if m.get("kcal") is not None:
        c.execute("UPDATE recipes SET cal_per_serving=? WHERE id=?",(m["kcal"],rid)); c.commit()
    return m

def recipe_calories(c, rid, force=False):
    """Back-compat: just the kcal + coverage."""
    row=c.execute("SELECT cal_per_serving FROM recipes WHERE id=?",(rid,)).fetchone()
    if row and row["cal_per_serving"] is not None and not force:
        return row["cal_per_serving"], 1.0
    m=recipe_macros(c,rid)
    return m.get("kcal"), m.get("coverage",0.0)

# ---- preference scoring ----
def score_recipe_for_person(recipe, prefs):
    tp=recipe["type_profile"]; score=0.0
    for t in FOOD_TYPES:
        inten=tp.get(t,0)
        if inten==0: continue
        lvl=PREF_IDX.get(prefs.get(t,"often"),2)
        if lvl==0:   score-=3*inten     # never + featured -> down-rank (still allowed)
        elif lvl==1: score-=0.5*inten   # sometimes
        elif lvl==2: score+=1*inten     # often
        else:        score+=2*inten     # love
    return score
def score_for_household(c, recipe, ms=None):
    ms=ms if ms is not None else members(c,active_only=True)
    if not ms: return 0.0
    return sum(score_recipe_for_person(recipe,m["prefs"]) for m in ms)/len(ms)
def best_for_person(c, prefs, k=5, favorites_only=False, quick_only=False):
    s=[(score_recipe_for_person(r,prefs),r) for r in recipes(c,favorites_only=favorites_only,quick_only=quick_only)]
    s.sort(key=lambda x:-x[0]); return [r for _,r in s[:k]]

def blended_search(c, query, include_mealdb=True):
    """Search saved recipes AND TheMealDB, return one merged list of dicts each
    like {name, source, id (if saved), meal_id (if mealdb), cuisine, meal}.
    Saved recipes first, then MealDB results not already in the library."""
    out=[]
    ql=query.lower().strip()
    for r in recipes(c):
        if ql in r["name"].lower():
            out.append({"name":r["name"],"source":"library","id":r["id"],
                        "cuisine":r["cuisine"],"meal":r["meal"]})
    have={o["name"].lower() for o in out}
    if include_mealdb:
        try:
            import mealdb
            for m in (mealdb.search(query) or []):
                nm=(m.get("strMeal") or "").strip()
                if nm and nm.lower() not in have:
                    out.append({"name":nm,"source":"mealdb","meal_id":m["idMeal"],
                                "cuisine":(m.get("strArea") or ""),"meal":"dinner",
                                "thumb":m.get("strMealThumb")})
                    have.add(nm.lower())
        except Exception:
            pass
    return out

def save_mealdb_by_id(c, meal_id):
    """Fetch a MealDB meal by id, save to library, return recipe dict or None."""
    try:
        import mealdb
        hr=mealdb.to_harvest_recipe(mealdb.lookup(meal_id))
        if not hr: return None
        if recipe_name_exists(c, hr["name"]):
            ex=[r for r in recipes(c) if r["name"].lower()==hr["name"].lower()]
            return ex[0] if ex else None
        rid,_=import_recipe(c, hr)
        return recipe_by_id(c, rid) if rid else None
    except Exception:
        return None

# ---- weekly plan ----
def plan_week(c, n=5, mode="together", favorites_only=False, quick_only=False, seed=None):
    if seed is not None: random.seed(seed)
    active=members(c,active_only=True)
    pool=recipes(c,favorites_only=favorites_only,quick_only=quick_only)
    if not pool: return []
    if mode=="individual":
        nights=[]
        for i in range(n):
            per={}
            for m in active:
                ranked=sorted(pool,key=lambda r:-(score_recipe_for_person(r,m["prefs"])+random.random()*2))
                per[m["name"]]=ranked[i%len(ranked)]
            nights.append({"mode":"individual","per_member":per})
        return nights
    scored=sorted(pool,key=lambda r:-(score_for_household(c,r,active)+random.random()*2))
    picked=[]; seen=set()
    for r in scored:
        if r["category"] not in seen: picked.append(r); seen.add(r["category"])
        if len(picked)>=n: break
    for r in scored:
        if len(picked)>=n: break
        if r not in picked: picked.append(r)
    return [{"mode":"together","recipe":r} for r in picked[:n]]


# ---- meal-grid planning (breakfast/lunch/dinner over N days) ----
def pick_one(c, meal, prefs_list=None, cuisine=None, quick_only=False, favorites_only=False, exclude=None):
    """Choose one recipe for a meal slot, scored for the household, with a little
    randomness. exclude = set of recipe ids to avoid (so re-roll gives something new)."""
    import random
    pool=recipes(c, meal=meal, cuisine=cuisine, quick_only=quick_only, favorites_only=favorites_only)
    if exclude: pool=[r for r in pool if r["id"] not in exclude] or pool
    if not pool: return None
    ms=members(c,active_only=True) if prefs_list is None else prefs_list
    scored=sorted(pool, key=lambda r:-(score_for_household(c,r,ms)+random.random()*2.5))
    return scored[0]

def plan_grid(c, days, meals, cuisine=None, quick_only=False, favorites_only=False):
    """days: int. meals: list subset of ['breakfast','lunch','dinner'].
    Returns grid[day][meal] = recipe dict (or None). Avoids repeating the same
    recipe within a meal type across the week."""
    grid=[]
    used={m:set() for m in meals}
    for d in range(days):
        day={}
        for m in meals:
            r=pick_one(c, m, cuisine=cuisine, quick_only=quick_only,
                       favorites_only=favorites_only, exclude=used[m])
            if r: used[m].add(r["id"])
            day[m]=r
        grid.append(day)
    return grid

# ---- blended discovery (saved library + fresh TheMealDB) ----
def discover_meal(c, meal, cuisine=None, exclude=None):
    """Try to pull a fresh TheMealDB meal for this slot, save it, and return it.
    Returns a recipe dict (already saved to the library) or None on any failure.
    Kept separate so generation can mix in discoveries without depending on the
    network for the whole plan."""
    try:
        import mealdb, random
        m=None
        if cuisine and cuisine!="Any":
            cards=mealdb.by_area(cuisine) or []
            if cards:
                pick=random.choice(cards)
                m=mealdb.lookup(pick["idMeal"])
        if m is None:
            m=mealdb.random_meal()
        if not m: return None
        hr=mealdb.to_harvest_recipe(m)
        if not hr: return None
        # respect the requested slot loosely: only breakfast maps specially
        if meal!="breakfast" and hr.get("meal")=="breakfast": return None
        if recipe_name_exists(c, hr["name"]):
            existing=[r for r in recipes(c) if r["name"].lower()==hr["name"].lower()]
            return existing[0] if existing else None
        rid,status=import_recipe(c, hr)
        return recipe_by_id(c, rid) if rid else None
    except Exception:
        return None

def plan_grid_blended(c, days, meals, cuisine=None, quick_only=False,
                      favorites_only=False, discover=True, discover_rate=0.30):
    """Like plan_grid but, when discover=True, occasionally seeds a fresh
    TheMealDB meal into a slot instead of a saved one (~discover_rate of slots).
    Discoveries are saved to the library so they behave like any other recipe."""
    import random
    grid=[]; used={m:set() for m in meals}
    for d in range(days):
        day={}
        for m in meals:
            r=None
            if discover and m!="breakfast" and random.random()<discover_rate:
                r=discover_meal(c, m, cuisine=cuisine, exclude=used[m])
                if r and r["id"] in used[m]: r=None
            if r is None:
                r=pick_one(c, m, cuisine=cuisine, quick_only=quick_only,
                           favorites_only=favorites_only, exclude=used[m])
            if r: used[m].add(r["id"])
            day[m]=r
        grid.append(day)
    return grid

def grid_recipe_ids(grid):
    ids=[]
    for day in grid:
        for m,r in day.items():
            if r: ids.append(r["id"])
    return list(dict.fromkeys(ids))

def plan_recipe_ids(nights):
    ids=[]
    for nt in nights:
        if nt["mode"]=="together": ids.append(nt["recipe"]["id"])
        else: ids+=[r["id"] for r in nt["per_member"].values()]
    return list(dict.fromkeys(ids))

# ---- grocery: SIMPLE list, no grams/amounts ----
def _branch_applies(branch, active_names, prefs):
    if branch=="shared": return True
    if branch.endswith("_branch"):
        key=branch[:-7]
        if key in active_names: return True
        if key in FOOD_TYPES:
            return any(PREF_IDX.get(prefs[n].get(key,"often"),2)>=1 for n in active_names)  # anyone who eats it at all
    return True
def grocery_items(c, recipe_ids):
    active=members(c,active_only=True)
    names=[m["name"] for m in active]; prefs={m["name"]:m["prefs"] for m in active}
    seen=set(); rows=[]
    order={r["aisle"]:r["sort_pos"] for r in c.execute("SELECT aisle,sort_pos FROM aisle_order")}
    for rid in recipe_ids:
        for l in recipe_lines(c,rid):
            if not _branch_applies(l["branch"],names,prefs): continue
            key=l["ingredient"].lower()
            if key in seen: continue
            seen.add(key); rows.append({"ingredient":l["ingredient"],"aisle":l["aisle"],"kind":l["kind"]})
    rows.sort(key=lambda r:(order.get(r["aisle"],98),r["ingredient"])); return rows

# ---- stores ----
def stores(c): return [dict(r) for r in c.execute("SELECT id,name,sort_pos FROM stores ORDER BY sort_pos,name")]
def add_store(c,name): c.execute("INSERT OR IGNORE INTO stores(name) VALUES(?)",(name,)); c.commit()

# ---- shopping list (no quantities now) ----
def add_shopping_item(c,name,aisle="Other",store_id=None,kind="food",added_by=""):
    c.execute("INSERT INTO shopping_items(name,aisle,store_id,kind,added_by) VALUES(?,?,?,?,?)",
              (name,aisle,store_id,kind,added_by)); c.commit()
def push_items_to_list(c,items,store_id=None,added_by=""):
    for it in items: add_shopping_item(c,it["ingredient"],it["aisle"],store_id,it["kind"],added_by)
def shopping_list(c,store_id=None,added_by=None,kind=None):
    q="""SELECT s.id,s.name,s.aisle,s.kind,s.added_by,s.checked,st.name store,s.store_id
         FROM shopping_items s LEFT JOIN stores st ON st.id=s.store_id WHERE 1=1"""; p=[]
    if store_id is not None: q+=" AND s.store_id=?"; p.append(store_id)
    if added_by: q+=" AND s.added_by=?"; p.append(added_by)
    if kind: q+=" AND s.kind=?"; p.append(kind)
    order={r["aisle"]:r["sort_pos"] for r in c.execute("SELECT aisle,sort_pos FROM aisle_order")}
    rows=[dict(r) for r in c.execute(q,p)]; rows.sort(key=lambda r:(order.get(r["aisle"],98),r["name"])); return rows
def toggle_checked(c,i): c.execute("UPDATE shopping_items SET checked=1-checked WHERE id=?",(i,)); c.commit()
def clear_checked(c): c.execute("DELETE FROM shopping_items WHERE checked=1"); c.commit()
def clear_list(c): c.execute("DELETE FROM shopping_items"); c.commit()
def move_item_store(c,i,s): c.execute("UPDATE shopping_items SET store_id=? WHERE id=?",(s,i)); c.commit()
def list_as_text(c,store_id=None):
    rows=shopping_list(c,store_id=store_id)
    if not rows: return "(empty list)"
    lines=[]; cur=None
    for r in rows:
        head=f"{r['store'] or 'Any store'} - {r['aisle']}"
        if head!=cur: cur=head; lines.append(f"\n[{head}]")
        lines.append(f"  {'[x]' if r['checked'] else '[ ]'} {r['name']}")
    return "\n".join(lines).strip()

# ---- receipts ----
def add_receipt(c,store_id,total,visit_date=None,photo_path="",added_by="",note="",items=None):
    rid=c.execute("INSERT INTO receipts(store_id,total,visit_date,photo_path,added_by,note) VALUES(?,?,COALESCE(?,date('now')),?,?,?)",
                  (store_id,total,visit_date,photo_path,added_by,note)).lastrowid
    for it in (items or []):
        c.execute("INSERT INTO receipt_items(receipt_id,name,qty,price) VALUES(?,?,?,?)",(rid,it["name"],it.get("qty",1),it.get("price",0)))
    c.commit(); return rid
def receipts(c,limit=100):
    return [dict(r) for r in c.execute("""SELECT r.id,r.total,r.visit_date,r.photo_path,r.added_by,r.note,st.name store
        FROM receipts r LEFT JOIN stores st ON st.id=r.store_id ORDER BY r.visit_date DESC,r.id DESC LIMIT ?""",(limit,))]
def spend_summary(c):
    total=c.execute("SELECT COALESCE(SUM(total),0) t FROM receipts").fetchone()["t"]
    by_store=[dict(r) for r in c.execute("""SELECT st.name store,COALESCE(SUM(r.total),0) spent,COUNT(*) visits
        FROM receipts r LEFT JOIN stores st ON st.id=r.store_id GROUP BY r.store_id ORDER BY spent DESC""")]
    return {"total":round(total,2),"by_store":by_store}
def most_bought(c,top=10):
    return [dict(r) for r in c.execute("SELECT name,SUM(qty) q FROM receipt_items GROUP BY lower(name) ORDER BY q DESC LIMIT ?",(top,))]
