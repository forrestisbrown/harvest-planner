"""
app.py — Household Meal Planner (v2)
Warm fall theme, light/dark, favorites, remix, multi-store shared list,
receipts + spend, household items. Deploys to Streamlit Community Cloud as-is.
"""
import os, io
import streamlit as st
from db_setup import build, DB_PATH, connect
import core, theme

st.set_page_config(page_title="Harvest — Household Planner", page_icon="🍂", layout="wide")

if not os.path.exists(DB_PATH):
    build()

UP_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UP_DIR, exist_ok=True)

# ---- session defaults ----
ss = st.session_state
ss.setdefault("dark", True)
ss.setdefault("plan_ids", [])
ss.setdefault("who", None)

conn = connect()
theme.inject(ss["dark"])

# =============================== SIDEBAR ===============================
with st.sidebar:
    st.markdown("### 🍂 Harvest")
    st.caption("Household meal planning")

    # "login" = simple name picker (per your call)
    mem_names = [m["name"] for m in core.members(conn)]
    if ss["who"] not in mem_names:
        ss["who"] = mem_names[0] if mem_names else None
    ss["who"] = st.selectbox("Signed in as", mem_names,
                             index=mem_names.index(ss["who"]) if ss["who"] in mem_names else 0) if mem_names else None

    dark_new = st.toggle("Dark mode", value=ss["dark"])
    if dark_new != ss["dark"]:
        ss["dark"] = dark_new; st.rerun()

    st.divider()
    st.markdown("**Who's eating**")
    for m in core.members(conn):
        on = st.checkbox(f"{m['name']}", value=bool(m["active"]), key=f"act_{m['name']}",
                         help=m["dietary_style"])
        if on != bool(m["active"]):
            core.set_member_active(conn, m["name"], on); st.rerun()

    with st.expander("Add or remove member"):
        nm = st.text_input("Name", key="new_member")
        style = st.selectbox("Dietary style", ["balanced","meat_potatoes","veggie_heavy","pescatarian","vegetarian"])
        if st.button("Add member", use_container_width=True) and nm.strip():
            core.add_member(conn, nm.strip(), style); st.rerun()
        rm = st.selectbox("Remove", ["—"]+mem_names)
        if st.button("Remove", use_container_width=True) and rm!="—":
            core.remove_member(conn, rm); st.rerun()

    with st.expander("Stores"):
        for s in core.stores(conn): st.write("• "+s["name"])
        ns = st.text_input("Add a store", key="new_store")
        if st.button("Add store", use_container_width=True) and ns.strip():
            core.add_store(conn, ns.strip()); st.rerun()

st.markdown("# Harvest")
st.markdown('<hr class="fall-rule"/>', unsafe_allow_html=True)

tabs = st.tabs(["🗓️ Plan","📖 Recipes","🛒 Shopping List","🧾 Receipts & Spend","🧴 Household"])

# =============================== PLAN ===============================
with tabs[0]:
    active = core.active_member_names(conn)
    if not active:
        st.warning("Toggle at least one person on in the sidebar."); st.stop()

    c1,c2,c3,c4 = st.columns([1,1,1,1])
    n = c1.slider("Dinners", 3, 7, 5)
    variety = c2.toggle("Category variety", value=True)
    favs_only = c3.toggle("Favorites only", value=False)
    if c4.button("🎲 Generate week", use_container_width=True):
        picks = core.plan_week(conn, n=n, variety=variety, favorites_only=favs_only)
        ss["plan_ids"] = [p["id"] for p in picks]

    if not ss["plan_ids"]:
        st.info("Set your options and hit **Generate week**.")
    else:
        ids = ss["plan_ids"]
        all_r = {r["id"]: r["name"] for r in core.recipes(conn)}
        st.markdown("#### This week")
        cols = st.columns(len(ids))
        for i,rid in enumerate(list(ids)):
            with cols[i]:
                keys=list(all_r); choice=st.selectbox(f"Night {i+1}", keys,
                    index=keys.index(rid), format_func=lambda x:all_r[x], key=f"night_{i}")
                ids[i]=choice
        ss["plan_ids"]=ids

        left,right = st.columns([1,1])
        with left:
            st.markdown("#### 🛒 Grocery preview (by aisle)")
            cur=None
            for row in core.aggregate_plan(conn, ids):
                if row["aisle"]!=cur: cur=row["aisle"]; st.markdown(f"**{cur}**")
                st.markdown(f"<span class='small'>{row['quantity']:g} {row['unit']}</span> — {row['ingredient']}", unsafe_allow_html=True)
            st.write("")
            store_opts={s["name"]:s["id"] for s in core.stores(conn)}
            tgt=st.selectbox("Send to store", list(store_opts))
            if st.button("➕ Add week to shopping list", use_container_width=True):
                core.push_plan_to_list(conn, ids, store_id=store_opts[tgt], added_by=ss["who"] or "")
                st.success(f"Added {len(core.aggregate_plan(conn,ids))} items to {tgt}.")
        with right:
            st.markdown("#### 🔥 Calorie split")
            tot,per = core.week_calories(conn, ids)
            mc=st.columns(len(active))
            for col,m in zip(mc,active): col.metric(m, f"{int(tot[m])}", help="weekly kcal")
            for name,split in per:
                parts=" · ".join(f"{m} {int(v)}" for m,v in split.items() if not m.startswith("_"))
                st.markdown(f"**{name}** — <span class='small'>{parts} kcal</span>", unsafe_allow_html=True)

# =============================== RECIPES ===============================
with tabs[1]:
    st.markdown("#### Recipe library")
    f1,f2,f3 = st.columns([1,1,1])
    cz = f1.selectbox("Cuisine", ["All"]+core.cuisines(conn))
    cats = ["All"]+sorted({r["category"] for r in core.recipes(conn)})
    ct = f2.selectbox("Type", cats)
    only_fav = f3.toggle("⭐ Favorites only", key="rec_fav")
    rlist = core.recipes(conn, favorites_only=only_fav, cuisine=cz, category=ct)
    st.caption(f"{len(rlist)} recipes")

    for r in rlist:
        with st.container():
            a,b = st.columns([4,1])
            star = "⭐" if r["is_favorite"] else "☆"
            a.markdown(f"**{r['name']}** &nbsp; "
                       f"<span class='pill cuisine'>{r['cuisine']}</span>"
                       f"<span class='pill'>{r['category']}</span>"
                       f"{'<span class=\"pill fav\">favorite</span>' if r['is_favorite'] else ''}",
                       unsafe_allow_html=True)
            if b.button(f"{star} Favorite", key=f"fav_{r['id']}"):
                core.toggle_favorite(conn, r["id"]); st.rerun()
            with st.expander("Ingredients · related dishes · remix"):
                for l in core.recipe_lines(conn, r["id"]):
                    tag = "" if l["branch"]=="shared" else f" ({l['branch']} only)"
                    st.markdown(f"<span class='small'>{l['quantity']:g} {l['unit_type']}</span> {l['ingredient']}{tag}", unsafe_allow_html=True)
                st.markdown("**You might also like:**")
                for rel in core.related_dishes(conn, r["id"], k=3):
                    st.markdown(f"↳ *{rel['recipe']['name']}* — <span class='small'>{rel['reason']}</span>", unsafe_allow_html=True)
                v = core.remix_variation(conn, r["id"])
                if v:
                    st.markdown(f"🔁 <span class='small'>Variation idea:</span> {v['suggestion']}", unsafe_allow_html=True)

    with st.expander("➕ Add your own recipe"):
        rn = st.text_input("Recipe name")
        rc1,rc2,rc3 = st.columns(3)
        rcat = rc1.text_input("Type (e.g. chicken)","chicken")
        rcz = rc2.text_input("Cuisine","American")
        rserv = rc3.number_input("Servings",1,12,2)
        st.caption("Ingredients — one per line as:  name | qty | shared/You/Lizzy")
        raw = st.text_area("Ingredients","Chicken breast | 350 | shared\nBroccoli | 200 | shared")
        if st.button("Save recipe") and rn.strip():
            items=[]
            for line in raw.splitlines():
                parts=[x.strip() for x in line.split("|")]
                if len(parts)>=2:
                    nm=parts[0]; qty=float(parts[1] or 0)
                    br=parts[2] if len(parts)>2 and parts[2] else "shared"
                    items.append((nm,qty,br))
            core.add_recipe(conn, rn.strip(), rcat, rcz, int(rserv), items)
            st.success(f"Saved {rn}."); st.rerun()

# =============================== SHOPPING LIST ===============================
with tabs[2]:
    st.markdown("#### Shared shopping list")
    store_opts = {"All stores": None} | {s["name"]: s["id"] for s in core.stores(conn)}
    g1,g2,g3 = st.columns([1,1,1])
    store_pick = g1.selectbox("Store", list(store_opts))
    kind_pick = g2.selectbox("Kind", ["all","food","household"])
    who_filter = g3.selectbox("Added by", ["everyone"]+[m["name"] for m in core.members(conn)])

    rows = core.shopping_list(conn,
        store_id=store_opts[store_pick],
        added_by=None if who_filter=="everyone" else who_filter,
        kind=None if kind_pick=="all" else kind_pick)

    if not rows:
        st.info("List is empty. Add items below, or push a week from the Plan tab.")
    else:
        cur=None
        for r in rows:
            head=f"{r['store'] or 'Any store'} · {r['aisle']}"
            if head!=cur: cur=head; st.markdown(f"**{head}**")
            cc = st.columns([6,2,2])
            qty=f"{r['quantity']:g} {r['unit']}".strip() if r["quantity"] else ""
            label=f"{qty+' — ' if qty else ''}{r['name']}"
            checked = cc[0].checkbox(label, value=bool(r["checked"]), key=f"chk_{r['id']}")
            if checked!=bool(r["checked"]): core.toggle_checked(conn,r["id"]); st.rerun()
            cc[1].markdown(f"<span class='small'>by {r['added_by'] or '—'}</span>", unsafe_allow_html=True)
            move_to = cc[2].selectbox("move", ["move…"]+[s["name"] for s in core.stores(conn)],
                                      key=f"mv_{r['id']}", label_visibility="collapsed")
            if move_to!="move…":
                sid={s["name"]:s["id"] for s in core.stores(conn)}[move_to]
                core.move_item_store(conn, r["id"], sid); st.rerun()

    st.divider()
    a1,a2,a3,a4 = st.columns(4)
    with a1:
        ni=st.text_input("Item", key="si_name")
    with a2:
        ns=st.selectbox("Store", [s["name"] for s in core.stores(conn)], key="si_store")
    with a3:
        nk=st.selectbox("Kind", ["food","household"], key="si_kind")
    with a4:
        na=st.selectbox("Aisle", ["Produce","Meat","Seafood","Dairy","Bakery","Frozen","Pantry","Spices","Canned","Household","Other"], key="si_aisle")
    if st.button("➕ Add item") and ni.strip():
        sid={s["name"]:s["id"] for s in core.stores(conn)}[ns]
        core.add_shopping_item(conn, ni.strip(), None, "", na, sid, nk, ss["who"] or "")
        st.rerun()

    b1,b2,b3 = st.columns(3)
    if b1.button("✅ Clear checked"): core.clear_checked(conn); st.rerun()
    if b2.button("🗑️ Clear all"): core.clear_list(conn); st.rerun()
    with b3.popover("📤 Share as text"):
        st.code(core.list_as_text(conn, store_id=store_opts[store_pick]), language=None)
        st.caption("Copy and paste into Messages, email, or notes.")

# =============================== RECEIPTS ===============================
with tabs[3]:
    st.markdown("#### Log a receipt")
    r1,r2,r3 = st.columns([1,1,1])
    rstore = r1.selectbox("Store", [s["name"] for s in core.stores(conn)], key="rc_store")
    rtotal = r2.number_input("Total spent ($)", 0.0, 100000.0, 0.0, step=0.01)
    rdate = r3.date_input("Visit date")
    photo = st.file_uploader("Receipt photo", type=["png","jpg","jpeg","webp"])
    rnote = st.text_input("Note (optional)")
    st.caption("Optional — itemize for most-bought tracking:  name | qty | price")
    ritems_raw = st.text_area("Items", "", placeholder="Ground beef | 2 | 9.98")
    if st.button("💾 Save receipt"):
        path=""
        if photo is not None:
            path=os.path.join(UP_DIR, f"receipt_{rdate}_{photo.name}")
            with open(path,"wb") as f: f.write(photo.getbuffer())
        items=[]
        for line in ritems_raw.splitlines():
            parts=[x.strip() for x in line.split("|")]
            if parts and parts[0]:
                items.append({"name":parts[0],
                              "qty":float(parts[1]) if len(parts)>1 and parts[1] else 1,
                              "price":float(parts[2]) if len(parts)>2 and parts[2] else 0})
        sid={s["name"]:s["id"] for s in core.stores(conn)}[rstore]
        core.add_receipt(conn, sid, rtotal, str(rdate), path, ss["who"] or "", rnote, items)
        st.success("Receipt saved."); st.rerun()

    st.divider()
    s = core.spend_summary(conn)
    m1,m2 = st.columns([1,2])
    m1.metric("Total logged", f"${s['total']:,.2f}")
    with m2:
        if s["by_store"]:
            st.markdown("**By store**")
            for x in s["by_store"]:
                if x["store"]: st.markdown(f"{x['store']}: **${x['spent']:,.2f}** <span class='small'>({x['visits']} visits)</span>", unsafe_allow_html=True)

    mb = core.most_bought(conn, top=10)
    if mb:
        st.markdown("**Most-bought items**")
        for x in mb: st.markdown(f"• {x['name']} <span class='small'>×{x['q']:g}</span>", unsafe_allow_html=True)

    recent = core.receipts(conn, limit=12)
    if recent:
        st.markdown("**Recent visits**")
        for r in recent:
            with st.expander(f"{r['visit_date']} · {r['store'] or '—'} · ${r['total']:,.2f}"):
                if r["note"]: st.write(r["note"])
                st.caption(f"logged by {r['added_by'] or '—'}")
                if r["photo_path"] and os.path.exists(r["photo_path"]):
                    st.image(r["photo_path"], width=280)

# =============================== HOUSEHOLD ===============================
with tabs[4]:
    st.markdown("#### Household (non-food) items")
    st.caption("Paper goods, cleaning, etc. These live on the same shared list, tagged 'household'.")
    hh = core.shopping_list(conn, kind="household")
    if hh:
        for r in hh:
            cc=st.columns([6,2])
            checked=cc[0].checkbox(f"{r['name']}", value=bool(r["checked"]), key=f"hh_{r['id']}")
            if checked!=bool(r["checked"]): core.toggle_checked(conn,r["id"]); st.rerun()
            cc[1].markdown(f"<span class='small'>{r['store'] or 'Any'} · by {r['added_by'] or '—'}</span>", unsafe_allow_html=True)
    else:
        st.info("No household items yet.")
    h1,h2 = st.columns([2,1])
    hn=h1.text_input("Add household item", key="hh_name")
    hs=h2.selectbox("Store", [s["name"] for s in core.stores(conn)], key="hh_store")
    if st.button("➕ Add household item") and hn.strip():
        sid={s["name"]:s["id"] for s in core.stores(conn)}[hs]
        core.add_shopping_item(conn, hn.strip(), None, "", "Household", sid, "household", ss["who"] or "")
        st.rerun()

conn.close()
st.markdown('<hr class="fall-rule"/>', unsafe_allow_html=True)
st.caption("Harvest · runs locally or on Streamlit Community Cloud · SQLite + Python")
