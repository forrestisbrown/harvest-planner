"""
core.py — v2 logic
Planner + favorites + remix/related-dish + multi-store shopping list +
receipts/spend + household items. Pure functions over the SQLite connection.
"""
import random
from collections import defaultdict
from db_setup import connect


# ---------- Members (Module A) ----------
def members(conn, active_only=False):
    q = "SELECT id,name,dietary_style,active FROM members"
    if active_only: q += " WHERE active=1"
    return [dict(r) for r in conn.execute(q + " ORDER BY id")]

def active_member_names(conn):
    return [m["name"] for m in members(conn, active_only=True)]

def add_member(conn, name, style="balanced"):
    conn.execute("INSERT OR IGNORE INTO members(name,dietary_style) VALUES(?,?)",(name,style)); conn.commit()

def set_member_active(conn, name, active):
    conn.execute("UPDATE members SET active=? WHERE name=?",(1 if active else 0,name)); conn.commit()

def remove_member(conn, name):
    conn.execute("DELETE FROM members WHERE name=?",(name,)); conn.commit()


# ---------- Recipes + favorites ----------
def recipes(conn, favorites_only=False, cuisine=None, category=None):
    q="SELECT id,name,category,cuisine,servings,is_favorite,notes FROM recipes WHERE 1=1"
    p=[]
    if favorites_only: q+=" AND is_favorite=1"
    if cuisine and cuisine!="All": q+=" AND cuisine=?"; p.append(cuisine)
    if category and category!="All": q+=" AND category=?"; p.append(category)
    return [dict(r) for r in conn.execute(q+" ORDER BY name",p)]

def cuisines(conn):
    return [r["cuisine"] for r in conn.execute("SELECT DISTINCT cuisine FROM recipes ORDER BY cuisine")]

def toggle_favorite(conn, recipe_id):
    conn.execute("UPDATE recipes SET is_favorite=1-is_favorite WHERE id=?",(recipe_id,)); conn.commit()

def recipe_lines(conn, recipe_id):
    return [dict(r) for r in conn.execute("""
        SELECT i.name ingredient,i.aisle,i.unit_type,i.calories_per_unit,i.kind,
               ri.quantity,ri.branch
        FROM recipe_ingredients ri JOIN ingredients i ON i.id=ri.ingredient_id
        WHERE ri.recipe_id=?""",(recipe_id,))]

def ingredient_set(conn, recipe_id):
    return {l["ingredient"] for l in recipe_lines(conn, recipe_id)}


# ---------- Add a custom recipe from the UI ----------
def add_recipe(conn, name, category, cuisine, servings, items):
    cur=conn.execute("INSERT INTO recipes(name,category,cuisine,servings) VALUES(?,?,?,?)",
                     (name,category,cuisine,servings))
    rid=cur.lastrowid
    for iname,qty,branch in items:
        row=conn.execute("SELECT id FROM ingredients WHERE name=?",(iname,)).fetchone()
        if not row:
            conn.execute("INSERT INTO ingredients(name) VALUES(?)",(iname,))
            row=conn.execute("SELECT id FROM ingredients WHERE name=?",(iname,)).fetchone()
        conn.execute("INSERT OR REPLACE INTO recipe_ingredients(recipe_id,ingredient_id,quantity,branch) VALUES(?,?,?,?)",
                     (rid,row["id"],float(qty),branch))
    conn.commit(); return rid


# ---------- Planner (Module C) ----------
def plan_week(conn, n=5, variety=True, favorites_only=False, seed=None):
    if seed is not None: random.seed(seed)
    pool = recipes(conn, favorites_only=favorites_only)
    if len(pool)<=n: return pool
    if not variety: return random.sample(pool,n)
    by=defaultdict(list)
    for r in pool: by[r["category"]].append(r)
    for v in by.values(): random.shuffle(v)
    picked=[]; cats=list(by); random.shuffle(cats)
    for c in cats:
        if len(picked)<n and by[c]: picked.append(by[c].pop())
    rest=[r for v in by.values() for r in v]; random.shuffle(rest)
    while len(picked)<n and rest: picked.append(rest.pop())
    return picked[:n]


# ---------- Remix / related dish ----------
def related_dishes(conn, recipe_id, k=4):
    base=conn.execute("SELECT name,category,cuisine FROM recipes WHERE id=?",(recipe_id,)).fetchone()
    base_ings=ingredient_set(conn,recipe_id)
    out=[]
    for r in recipes(conn):
        if r["id"]==recipe_id: continue
        ings=ingredient_set(conn,r["id"])
        shared=base_ings & ings
        score=len(shared)*2; reasons=[]
        if shared: reasons.append(f"{len(shared)} shared ingredients")
        if r["cuisine"]==base["cuisine"]: score+=2; reasons.append(f"same cuisine ({r['cuisine']})")
        if r["category"]==base["category"]: score+=2; reasons.append(f"same type ({r['category']})")
        if score>0:
            out.append({"recipe":r,"shared":sorted(shared),"score":score,"reason":", ".join(reasons)})
    out.sort(key=lambda x:-x["score"])
    return out[:k]

def remix_variation(conn, recipe_id):
    lines=recipe_lines(conn,recipe_id)
    proteins={"Ground beef","Chicken thigh","Chicken breast","Pork chop","Ground turkey",
              "Salmon fillet","Shrimp","Chickpeas","Black beans"}
    base=conn.execute("SELECT name FROM recipes WHERE id=?",(recipe_id,)).fetchone()["name"]
    present=[l for l in lines if l["ingredient"] in proteins]
    if not present: return None
    swap_from=present[0]["ingredient"]
    alts=[p for p in proteins if p!=swap_from]; swap_to=random.choice(alts)
    return {"base":base,"swap_from":swap_from,"swap_to":swap_to,
            "suggestion":f"Try {base} with {swap_to} instead of {swap_from}."}


# ---------- Grocery aggregation (Module D) ----------
def _applies(branch, active): return branch=="shared" or branch in active

def aggregate_plan(conn, recipe_ids, servings_target=None):
    active=active_member_names(conn)
    target=servings_target or max(len(active),1)
    agg=defaultdict(lambda:{"qty":0.0,"aisle":"Other","unit":"unit","kind":"food"})
    for rid in recipe_ids:
        base=conn.execute("SELECT servings FROM recipes WHERE id=?",(rid,)).fetchone()["servings"] or 1
        scale=target/base
        for l in recipe_lines(conn,rid):
            if not _applies(l["branch"],active): continue
            a=agg[l["ingredient"]]
            a["qty"]+=l["quantity"]*scale; a["aisle"]=l["aisle"]
            a["unit"]=l["unit_type"]; a["kind"]=l["kind"]
    order={r["aisle"]:r["sort_pos"] for r in conn.execute("SELECT aisle,sort_pos FROM aisle_order")}
    rows=[{"ingredient":k,"aisle":v["aisle"],"quantity":round(v["qty"],1),
           "unit":v["unit"],"kind":v["kind"]} for k,v in agg.items()]
    rows.sort(key=lambda r:(order.get(r["aisle"],98),r["ingredient"]))
    return rows


# ---------- Calories (Module E) ----------
def calorie_split(conn, recipe_id, servings_target=None):
    active=active_member_names(conn)
    if not active: return {}
    base=conn.execute("SELECT servings FROM recipes WHERE id=?",(recipe_id,)).fetchone()["servings"] or 1
    target=servings_target or len(active); scale=target/base
    per={m:0.0 for m in active}; shared=0.0
    for l in recipe_lines(conn,recipe_id):
        cals=l["quantity"]*l["calories_per_unit"]*scale
        if l["branch"]=="shared": shared+=cals
        elif l["branch"] in per: per[l["branch"]]+=cals
    each=shared/len(active)
    res={m:round(per[m]+each,0) for m in active}; res["_shared_each"]=round(each,0)
    return res

def week_calories(conn, recipe_ids):
    active=active_member_names(conn); tot={m:0.0 for m in active}; per=[]
    for rid in recipe_ids:
        nm=conn.execute("SELECT name FROM recipes WHERE id=?",(rid,)).fetchone()["name"]
        s=calorie_split(conn,rid); per.append((nm,s))
        for m in active: tot[m]+=s.get(m,0)
    return {m:round(tot[m],0) for m in active}, per


# ---------- Stores ----------
def stores(conn):
    return [dict(r) for r in conn.execute("SELECT id,name,sort_pos FROM stores ORDER BY sort_pos,name")]
def add_store(conn,name):
    conn.execute("INSERT OR IGNORE INTO stores(name) VALUES(?)",(name,)); conn.commit()


# ---------- Shopping list ----------
def add_shopping_item(conn, name, quantity=None, unit="", aisle="Other",
                      store_id=None, kind="food", added_by=""):
    conn.execute("""INSERT INTO shopping_items(name,quantity,unit,aisle,store_id,kind,added_by)
                    VALUES(?,?,?,?,?,?,?)""",(name,quantity,unit,aisle,store_id,kind,added_by))
    conn.commit()

def push_plan_to_list(conn, recipe_ids, store_id=None, added_by=""):
    for row in aggregate_plan(conn, recipe_ids):
        add_shopping_item(conn,row["ingredient"],row["quantity"],row["unit"],
                          row["aisle"],store_id,row["kind"],added_by)

def shopping_list(conn, store_id=None, added_by=None, kind=None, include_checked=True):
    q="""SELECT s.id,s.name,s.quantity,s.unit,s.aisle,s.kind,s.added_by,s.checked,
                st.name store, s.store_id
         FROM shopping_items s LEFT JOIN stores st ON st.id=s.store_id WHERE 1=1"""
    p=[]
    if store_id is not None: q+=" AND s.store_id=?"; p.append(store_id)
    if added_by: q+=" AND s.added_by=?"; p.append(added_by)
    if kind: q+=" AND s.kind=?"; p.append(kind)
    if not include_checked: q+=" AND s.checked=0"
    order={r["aisle"]:r["sort_pos"] for r in conn.execute("SELECT aisle,sort_pos FROM aisle_order")}
    rows=[dict(r) for r in conn.execute(q,p)]
    rows.sort(key=lambda r:(order.get(r["aisle"],98),r["name"]))
    return rows

def toggle_checked(conn,item_id):
    conn.execute("UPDATE shopping_items SET checked=1-checked WHERE id=?",(item_id,)); conn.commit()
def clear_checked(conn):
    conn.execute("DELETE FROM shopping_items WHERE checked=1"); conn.commit()
def clear_list(conn):
    conn.execute("DELETE FROM shopping_items"); conn.commit()
def move_item_store(conn,item_id,store_id):
    conn.execute("UPDATE shopping_items SET store_id=? WHERE id=?",(store_id,item_id)); conn.commit()

def list_as_text(conn, store_id=None):
    rows=shopping_list(conn,store_id=store_id)
    if not rows: return "(empty list)"
    lines=[]; cur=None
    for r in rows:
        head=f"{r['store'] or 'Any store'} - {r['aisle']}"
        if head!=cur: cur=head; lines.append(f"\n[{head}]")
        qty=f"{r['quantity']:g} {r['unit']}".strip() if r["quantity"] else ""
        box="[x]" if r["checked"] else "[ ]"
        lines.append(f"  {box} {qty+' - ' if qty else ''}{r['name']}")
    return "\n".join(lines).strip()


# ---------- Receipts + spend ----------
def add_receipt(conn, store_id, total, visit_date=None, photo_path="", added_by="", note="", items=None):
    cur=conn.execute("""INSERT INTO receipts(store_id,total,visit_date,photo_path,added_by,note)
                        VALUES(?,?,COALESCE(?,date('now')),?,?,?)""",
                     (store_id,total,visit_date,photo_path,added_by,note))
    rid=cur.lastrowid
    for it in (items or []):
        conn.execute("INSERT INTO receipt_items(receipt_id,name,qty,price) VALUES(?,?,?,?)",
                     (rid,it["name"],it.get("qty",1),it.get("price",0)))
    conn.commit(); return rid

def receipts(conn, limit=100):
    return [dict(r) for r in conn.execute("""
        SELECT r.id,r.total,r.visit_date,r.photo_path,r.added_by,r.note,st.name store
        FROM receipts r LEFT JOIN stores st ON st.id=r.store_id
        ORDER BY r.visit_date DESC, r.id DESC LIMIT ?""",(limit,))]

def spend_summary(conn):
    total=conn.execute("SELECT COALESCE(SUM(total),0) t FROM receipts").fetchone()["t"]
    by_store=[dict(r) for r in conn.execute("""
        SELECT st.name store, COALESCE(SUM(r.total),0) spent, COUNT(*) visits
        FROM receipts r LEFT JOIN stores st ON st.id=r.store_id
        GROUP BY r.store_id ORDER BY spent DESC""")]
    by_month=[dict(r) for r in conn.execute("""
        SELECT substr(visit_date,1,7) month, SUM(total) spent
        FROM receipts GROUP BY month ORDER BY month""")]
    return {"total":round(total,2),"by_store":by_store,"by_month":by_month}

def most_bought(conn, top=10):
    rows=conn.execute("SELECT name, SUM(qty) q FROM receipt_items GROUP BY lower(name) ORDER BY q DESC LIMIT ?",(top,)).fetchall()
    return [dict(r) for r in rows]
