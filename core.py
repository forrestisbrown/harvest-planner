"""
core.py — v3 logic with per-person preference scoring.
"""
import json, random
from collections import defaultdict
from db_setup import connect, FOOD_TYPES, LEVELS, DIET_PRESETS

LEVEL_IDX = {lv:i for i,lv in enumerate(LEVELS)}  # none0 flavor1 balanced2 heavy3

# ---------- Settings / onboarding ----------
def get_setting(conn, key, default=None):
    r=conn.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
    return r["value"] if r else default
def set_setting(conn, key, value):
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=?",
                 (key,str(value),str(value))); conn.commit()
def is_onboarded(conn): return get_setting(conn,"onboarded","0")=="1"

# ---------- Members + preferences ----------
def members(conn, active_only=False):
    q="SELECT id,name,diet_label,prefs,active FROM members"
    if active_only: q+=" WHERE active=1"
    out=[]
    for r in conn.execute(q+" ORDER BY id"):
        d=dict(r); d["prefs"]=json.loads(d["prefs"] or "{}"); out.append(d)
    return out
def active_member_names(conn): return [m["name"] for m in members(conn, active_only=True)]

def add_member(conn, name, diet_label="Omnivore", prefs=None):
    if prefs is None: prefs=dict(DIET_PRESETS.get(diet_label, DIET_PRESETS["Omnivore"]))
    conn.execute("INSERT OR IGNORE INTO members(name,diet_label,prefs) VALUES(?,?,?)",
                 (name,diet_label,json.dumps(prefs))); conn.commit()
def update_member_prefs(conn, name, diet_label, prefs):
    conn.execute("UPDATE members SET diet_label=?, prefs=? WHERE name=?",
                 (diet_label,json.dumps(prefs),name)); conn.commit()
def set_member_active(conn, name, active):
    conn.execute("UPDATE members SET active=? WHERE name=?",(1 if active else 0,name)); conn.commit()
def remove_member(conn, name):
    conn.execute("DELETE FROM members WHERE name=?",(name,)); conn.commit()
def preset_for(label): return dict(DIET_PRESETS.get(label, DIET_PRESETS["Omnivore"]))

# ---------- Recipes ----------
def recipes(conn, favorites_only=False, cuisine=None, category=None):
    q="SELECT id,name,category,cuisine,servings,is_favorite,type_profile,notes FROM recipes WHERE 1=1"; p=[]
    if favorites_only: q+=" AND is_favorite=1"
    if cuisine and cuisine!="All": q+=" AND cuisine=?"; p.append(cuisine)
    if category and category!="All": q+=" AND category=?"; p.append(category)
    out=[]
    for r in conn.execute(q+" ORDER BY name",p):
        d=dict(r); d["type_profile"]=json.loads(d["type_profile"] or "{}"); out.append(d)
    return out
def cuisines(conn): return [r["cuisine"] for r in conn.execute("SELECT DISTINCT cuisine FROM recipes ORDER BY cuisine")]
def toggle_favorite(conn, rid): conn.execute("UPDATE recipes SET is_favorite=1-is_favorite WHERE id=?",(rid,)); conn.commit()
def recipe_lines(conn, rid):
    return [dict(r) for r in conn.execute("""
        SELECT i.name ingredient,i.aisle,i.unit_type,i.calories_per_unit,i.kind,ri.quantity,ri.branch
        FROM recipe_ingredients ri JOIN ingredients i ON i.id=ri.ingredient_id WHERE ri.recipe_id=?""",(rid,))]

def add_recipe(conn, name, category, cuisine, servings, type_profile, items):
    rid=conn.execute("INSERT INTO recipes(name,category,cuisine,servings,type_profile) VALUES(?,?,?,?,?)",
                     (name,category,cuisine,servings,json.dumps(type_profile))).lastrowid
    for iname,qty,branch in items:
        row=conn.execute("SELECT id FROM ingredients WHERE name=?",(iname,)).fetchone()
        if not row:
            conn.execute("INSERT INTO ingredients(name) VALUES(?)",(iname,))
            row=conn.execute("SELECT id FROM ingredients WHERE name=?",(iname,)).fetchone()
        conn.execute("INSERT OR REPLACE INTO recipe_ingredients(recipe_id,ingredient_id,quantity,branch) VALUES(?,?,?,?)",
                     (rid,row["id"],float(qty),branch))
    conn.commit(); return rid

# ---------- Preference scoring ----------
def score_recipe_for_person(recipe, prefs):
    """Higher = better fit. Rewards matches with 'heavy' likes, penalizes types
    the recipe features that the person rated 'none' (ranked low, not excluded)."""
    tp=recipe["type_profile"]; score=0.0
    for t in FOOD_TYPES:
        intensity=tp.get(t,0)                 # 0..3 how much the recipe features it
        level=LEVEL_IDX.get(prefs.get(t,"balanced"),2)  # 0..3 person's appetite
        if intensity==0: continue
        if level==0:      score-=3*intensity  # 'none' + featured -> strong down-rank
        elif level==1:    score-=1*intensity  # 'flavor-only' + plated -> mild down-rank
        elif level==2:    score+=1*intensity  # balanced -> mild reward
        else:             score+=2*intensity  # heavy -> strong reward
    return score

def score_recipe_for_household(conn, recipe, member_list=None):
    ms=member_list if member_list is not None else members(conn, active_only=True)
    if not ms: return 0.0
    return sum(score_recipe_for_person(recipe, m["prefs"]) for m in ms)/len(ms)

def best_recipes_for_person(conn, prefs, k=5, favorites_only=False):
    scored=[(score_recipe_for_person(r,prefs), r) for r in recipes(conn, favorites_only=favorites_only)]
    scored.sort(key=lambda x:-x[0]); return [r for _,r in scored[:k]]

# ---------- Weekly plan ----------
def plan_week(conn, n=5, mode="together", variety=True, favorites_only=False, seed=None):
    """mode 'together' scores by household avg; 'individual' returns, per night,
    the best dish for EACH active member. Returns list of night dicts."""
    if seed is not None: random.seed(seed)
    active=members(conn, active_only=True)
    pool=recipes(conn, favorites_only=favorites_only)
    if not pool: return []

    if mode=="individual":
        nights=[]
        for i in range(n):
            per={}
            for m in active:
                ranked=sorted(pool, key=lambda r:-(score_recipe_for_person(r,m["prefs"])+random.random()*2))
                per[m["name"]]=ranked[i % len(ranked)]
            nights.append({"mode":"individual","per_member":per})
        return nights

    # together: score by household, keep variety across categories
    scored=sorted(pool, key=lambda r:-(score_recipe_for_household(conn,r,active)+random.random()*2))
    picked=[]
    if variety:
        seen=set()
        for r in scored:
            if r["category"] not in seen:
                picked.append(r); seen.add(r["category"])
            if len(picked)>=n: break
        for r in scored:
            if len(picked)>=n: break
            if r not in picked: picked.append(r)
    else:
        picked=scored[:n]
    return [{"mode":"together","recipe":r} for r in picked[:n]]

# ---------- Grocery aggregation ----------
def _branch_applies(branch, active_names, prefs_by_name):
    """A 'shared' line always applies. A '<type>_branch' line applies unless ALL
    active members rate that type 'none' or 'flavor' (flavor => aromatic only,
    still cooked, so we keep it). A '<Name>_branch' applies if that member active."""
    if branch=="shared": return True
    if branch.endswith("_branch"):
        key=branch[:-7]
        if key in active_names: return True            # person-specific branch
        if key in FOOD_TYPES:                            # food-type branch
            # keep if any active member plates this type (balanced/heavy)
            return any(LEVEL_IDX.get(prefs_by_name[n].get(key,"balanced"),2)>=2 for n in active_names)
    return True

def aggregate_recipe_rows(conn, recipe_ids, servings_target=None):
    active=members(conn, active_only=True)
    names=[m["name"] for m in active]; prefs={m["name"]:m["prefs"] for m in active}
    target=servings_target or max(len(active),1)
    agg=defaultdict(lambda:{"qty":0.0,"aisle":"Other","unit":"unit","kind":"food"})
    for rid in recipe_ids:
        base=conn.execute("SELECT servings FROM recipes WHERE id=?",(rid,)).fetchone()["servings"] or 1
        scale=target/base
        for l in recipe_lines(conn,rid):
            if not _branch_applies(l["branch"],names,prefs): continue
            a=agg[l["ingredient"]]; a["qty"]+=l["quantity"]*scale
            a["aisle"]=l["aisle"]; a["unit"]=l["unit_type"]; a["kind"]=l["kind"]
    order={r["aisle"]:r["sort_pos"] for r in conn.execute("SELECT aisle,sort_pos FROM aisle_order")}
    rows=[{"ingredient":k,"aisle":v["aisle"],"quantity":round(v["qty"],1),"unit":v["unit"],"kind":v["kind"]}
          for k,v in agg.items()]
    rows.sort(key=lambda r:(order.get(r["aisle"],98),r["ingredient"])); return rows

def plan_recipe_ids(nights):
    ids=[]
    for nt in nights:
        if nt["mode"]=="together": ids.append(nt["recipe"]["id"])
        else: ids+=[r["id"] for r in nt["per_member"].values()]
    return list(dict.fromkeys(ids))  # de-dup, keep order

# ---------- Calories ----------
def calorie_split(conn, recipe_id, servings_target=None):
    active=members(conn, active_only=True)
    if not active: return {}
    names=[m["name"] for m in active]; prefs={m["name"]:m["prefs"] for m in active}
    base=conn.execute("SELECT servings FROM recipes WHERE id=?",(recipe_id,)).fetchone()["servings"] or 1
    target=servings_target or len(active); scale=target/base
    per={n:0.0 for n in names}; shared=0.0
    for l in recipe_lines(conn,recipe_id):
        if not _branch_applies(l["branch"],names,prefs): continue
        cals=l["quantity"]*l["calories_per_unit"]*scale
        b=l["branch"]
        if b=="shared": shared+=cals
        elif b.endswith("_branch") and b[:-7] in names: per[b[:-7]]+=cals
        else: shared+=cals  # type-branch shared among those who plate it
    each=shared/len(names)
    res={n:round(per[n]+each,0) for n in names}; res["_shared_each"]=round(each,0); return res

# ---------- Stores ----------
def stores(conn): return [dict(r) for r in conn.execute("SELECT id,name,sort_pos FROM stores ORDER BY sort_pos,name")]
def add_store(conn,name): conn.execute("INSERT OR IGNORE INTO stores(name) VALUES(?)",(name,)); conn.commit()

# ---------- Shopping list ----------
def add_shopping_item(conn,name,quantity=None,unit="",aisle="Other",store_id=None,kind="food",added_by=""):
    conn.execute("INSERT INTO shopping_items(name,quantity,unit,aisle,store_id,kind,added_by) VALUES(?,?,?,?,?,?,?)",
                 (name,quantity,unit,aisle,store_id,kind,added_by)); conn.commit()
def push_rows_to_list(conn,rows,store_id=None,added_by=""):
    for row in rows:
        add_shopping_item(conn,row["ingredient"],row["quantity"],row["unit"],row["aisle"],store_id,row["kind"],added_by)
def shopping_list(conn,store_id=None,added_by=None,kind=None,include_checked=True):
    q="""SELECT s.id,s.name,s.quantity,s.unit,s.aisle,s.kind,s.added_by,s.checked,st.name store,s.store_id
         FROM shopping_items s LEFT JOIN stores st ON st.id=s.store_id WHERE 1=1"""; p=[]
    if store_id is not None: q+=" AND s.store_id=?"; p.append(store_id)
    if added_by: q+=" AND s.added_by=?"; p.append(added_by)
    if kind: q+=" AND s.kind=?"; p.append(kind)
    if not include_checked: q+=" AND s.checked=0"
    order={r["aisle"]:r["sort_pos"] for r in conn.execute("SELECT aisle,sort_pos FROM aisle_order")}
    rows=[dict(r) for r in conn.execute(q,p)]; rows.sort(key=lambda r:(order.get(r["aisle"],98),r["name"])); return rows
def toggle_checked(conn,i): conn.execute("UPDATE shopping_items SET checked=1-checked WHERE id=?",(i,)); conn.commit()
def clear_checked(conn): conn.execute("DELETE FROM shopping_items WHERE checked=1"); conn.commit()
def clear_list(conn): conn.execute("DELETE FROM shopping_items"); conn.commit()
def move_item_store(conn,i,s): conn.execute("UPDATE shopping_items SET store_id=? WHERE id=?",(s,i)); conn.commit()
def list_as_text(conn,store_id=None):
    rows=shopping_list(conn,store_id=store_id)
    if not rows: return "(empty list)"
    lines=[]; cur=None
    for r in rows:
        head=f"{r['store'] or 'Any store'} - {r['aisle']}"
        if head!=cur: cur=head; lines.append(f"\n[{head}]")
        qty=f"{r['quantity']:g} {r['unit']}".strip() if r["quantity"] else ""
        lines.append(f"  {'[x]' if r['checked'] else '[ ]'} {qty+' - ' if qty else ''}{r['name']}")
    return "\n".join(lines).strip()

# ---------- Receipts + spend ----------
def add_receipt(conn,store_id,total,visit_date=None,photo_path="",added_by="",note="",items=None):
    rid=conn.execute("INSERT INTO receipts(store_id,total,visit_date,photo_path,added_by,note) VALUES(?,?,COALESCE(?,date('now')),?,?,?)",
                     (store_id,total,visit_date,photo_path,added_by,note)).lastrowid
    for it in (items or []):
        conn.execute("INSERT INTO receipt_items(receipt_id,name,qty,price) VALUES(?,?,?,?)",
                     (rid,it["name"],it.get("qty",1),it.get("price",0)))
    conn.commit(); return rid
def receipts(conn,limit=100):
    return [dict(r) for r in conn.execute("""SELECT r.id,r.total,r.visit_date,r.photo_path,r.added_by,r.note,st.name store
        FROM receipts r LEFT JOIN stores st ON st.id=r.store_id ORDER BY r.visit_date DESC,r.id DESC LIMIT ?""",(limit,))]
def spend_summary(conn):
    total=conn.execute("SELECT COALESCE(SUM(total),0) t FROM receipts").fetchone()["t"]
    by_store=[dict(r) for r in conn.execute("""SELECT st.name store,COALESCE(SUM(r.total),0) spent,COUNT(*) visits
        FROM receipts r LEFT JOIN stores st ON st.id=r.store_id GROUP BY r.store_id ORDER BY spent DESC""")]
    by_month=[dict(r) for r in conn.execute("""SELECT substr(visit_date,1,7) month,SUM(total) spent
        FROM receipts GROUP BY month ORDER BY month""")]
    return {"total":round(total,2),"by_store":by_store,"by_month":by_month}
def most_bought(conn,top=10):
    return [dict(r) for r in conn.execute("SELECT name,SUM(qty) q FROM receipt_items GROUP BY lower(name) ORDER BY q DESC LIMIT ?",(top,))]
