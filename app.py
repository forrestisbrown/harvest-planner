"""
app.py — Harvest v3
Onboarding + per-person dietary preferences + per-day individual/together
planning + single warm theme. Deploys to Streamlit Community Cloud as-is.
"""
import os
import streamlit as st
from db_setup import build, DB_PATH, connect, FOOD_TYPES, LEVELS, DIET_PRESETS
import core, theme

st.set_page_config(page_title="Harvest", page_icon="🍂", layout="wide")
if not os.path.exists(DB_PATH): build()
UP_DIR=os.path.join(os.path.dirname(__file__),"uploads"); os.makedirs(UP_DIR,exist_ok=True)

ss=st.session_state
ss.setdefault("plan_nights", [])
ss.setdefault("who", None)
ss.setdefault("editing", None)

conn=connect()
theme.inject()

TYPE_LABELS={"red_meat":"Red meat","poultry":"Poultry","pork":"Pork","seafood":"Seafood",
             "veg":"Vegetables","legumes":"Legumes/beans","pasta":"Pasta/carbs"}
LEVEL_LABELS={"none":"None","flavor":"Flavor only","balanced":"Balanced","heavy":"Heavy"}

def hero(title, sub=None):
    sub_html=f'<div class="hero-sub">{sub}</div>' if sub else ''
    st.markdown(f'<div class="center"><div class="hero-title">{title}</div>'
                f'{sub_html}<hr class="fall-rule"/></div>', unsafe_allow_html=True)

# ============================ ONBOARDING ============================
def onboarding():
    hero("Welcome to Harvest", "Let's set up your household")
    _,mid,_ = st.columns([1,2,1])
    with mid:
        st.markdown("#### Who's in your household?")
        existing=core.members(conn)
        if existing:
            st.markdown("".join(
                f'<span class="pill on">{m["name"]} · {m["diet_label"]}</span>' for m in existing),
                unsafe_allow_html=True)
        st.write("")
        with st.container():
            name=st.text_input("Name", key="onb_name", placeholder="e.g. Forrest")
            label=st.selectbox("Diet style", list(DIET_PRESETS), key="onb_label",
                               help="Sets starting preferences — you can fine-tune next.")
            st.caption("Fine-tune how much of each food type they want:")
            prefs=dict(DIET_PRESETS[label])
            cols=st.columns(2)
            for i,t in enumerate(FOOD_TYPES):
                with cols[i%2]:
                    prefs[t]=st.select_slider(TYPE_LABELS[t], options=LEVELS,
                        value=prefs[t], key=f"onb_{t}",
                        format_func=lambda x:LEVEL_LABELS[x])
            if st.button("Add this person", key="onb_add"):
                if name.strip():
                    core.add_member(conn, name.strip(), label, prefs); st.rerun()
                else: st.warning("Give them a name first.")

        if existing:
            st.write(""); st.divider()
            if st.button("Done — start planning", key="onb_done"):
                core.set_setting(conn,"onboarded","1"); st.rerun()

if not core.is_onboarded(conn):
    onboarding(); conn.close(); st.stop()

# ============================ SIDEBAR ============================
with st.sidebar:
    st.markdown("### 🍂 Harvest")
    mem_names=[m["name"] for m in core.members(conn)]
    if ss["who"] not in mem_names: ss["who"]=mem_names[0] if mem_names else None
    if mem_names:
        ss["who"]=st.selectbox("You are", mem_names, index=mem_names.index(ss["who"]))
    st.divider()
    st.markdown("**Active this week**")
    for m in core.members(conn):
        on=st.checkbox(m["name"], value=bool(m["active"]), key=f"act_{m['name']}")
        if on!=bool(m["active"]): core.set_member_active(conn,m["name"],on); st.rerun()
    st.divider()
    with st.expander("Stores"):
        for s in core.stores(conn): st.write("• "+s["name"])
        ns=st.text_input("Add a store", key="new_store")
        if st.button("Add store") and ns.strip(): core.add_store(conn,ns.strip()); st.rerun()

hero("Harvest", "Household meal planning")
tabs=st.tabs(["Plan","People","Recipes","Shopping","Receipts","Household"])

# ============================ PLAN ============================
with tabs[0]:
    active=core.members(conn, active_only=True)
    if not active:
        st.info("Turn someone on in the sidebar to plan.")
    else:
        c1,c2,c3=st.columns([1.2,1,1])
        with c1:
            mode=st.radio("Meal style", ["Together","Individual"], horizontal=True,
                help="Together = one meal with per-person tweaks. Individual = each person their own dish.")
        n=c2.slider("Nights",3,7,5)
        favs=c3.toggle("Favorites only")
        if st.button("🎲 Generate the week"):
            ss["plan_nights"]=core.plan_week(conn, n=n,
                mode="together" if mode=="Together" else "individual",
                favorites_only=favs)

        nights=ss["plan_nights"]
        if not nights:
            st.info("Pick your options and generate a week.")
        else:
            st.markdown("#### This week")
            for i,nt in enumerate(nights,1):
                if nt["mode"]=="together":
                    st.markdown(f'<div class="card"><b>Night {i}</b> &nbsp;'
                        f'<span class="pill cuisine">{nt["recipe"]["cuisine"]}</span>'
                        f'<span class="pill">{nt["recipe"]["category"]}</span><br>'
                        f'<span style="font-size:1.15rem">{nt["recipe"]["name"]}</span></div>',
                        unsafe_allow_html=True)
                else:
                    who_dishes="".join(
                        f'<div style="margin-top:6px"><span class="pill on">{w}</span> {r["name"]}</div>'
                        for w,r in nt["per_member"].items())
                    st.markdown(f'<div class="card"><b>Night {i}</b> '
                        f'<span class="pill veg">individual</span>{who_dishes}</div>',
                        unsafe_allow_html=True)

            ids=core.plan_recipe_ids(nights)
            left,right=st.columns(2)
            with left:
                st.markdown("#### 🛒 Grocery preview")
                cur=None
                for row in core.aggregate_recipe_rows(conn, ids):
                    if row["aisle"]!=cur: cur=row["aisle"]; st.markdown(f"**{cur}**")
                    st.markdown(f"<span class='small'>{row['quantity']:g} {row['unit']}</span> — {row['ingredient']}", unsafe_allow_html=True)
                store_opts={s["name"]:s["id"] for s in core.stores(conn)}
                tgt=st.selectbox("Add to store", list(store_opts))
                if st.button("➕ Add week to shopping list"):
                    core.push_rows_to_list(conn, core.aggregate_recipe_rows(conn,ids),
                                           store_id=store_opts[tgt], added_by=ss["who"] or "")
                    st.success("Added to your shopping list.")
            with right:
                st.markdown("#### 🔥 Calories per person")
                names=[m["name"] for m in active]
                totals={nm:0 for nm in names}
                for rid in ids:
                    sp=core.calorie_split(conn,rid)
                    for nm in names: totals[nm]+=sp.get(nm,0)
                mc=st.columns(len(names))
                for col,nm in zip(mc,names): col.metric(nm, f"{int(totals[nm])}", help="weekly kcal (approx)")

# ============================ PEOPLE ============================
with tabs[1]:
    st.markdown("#### Household preferences")
    st.caption("Edit anyone's diet style and per-food-type appetite. Changes retarget the menu.")
    for m in core.members(conn):
        with st.container():
            st.markdown(f'<div class="card"><b style="font-size:1.15rem">{m["name"]}</b> '
                        f'<span class="pill on">{m["diet_label"]}</span>'
                        + "".join(f'<span class="pill">{TYPE_LABELS[t]}: {LEVEL_LABELS[m["prefs"].get(t,"balanced")]}</span>'
                                  for t in FOOD_TYPES) + '</div>', unsafe_allow_html=True)
            with st.expander(f"Edit {m['name']}"):
                lbl=st.selectbox("Diet style", list(DIET_PRESETS),
                    index=list(DIET_PRESETS).index(m["diet_label"]) if m["diet_label"] in DIET_PRESETS else 0,
                    key=f"lbl_{m['id']}")
                if st.button(f"Reset dials to {lbl} defaults", key=f"reset_{m['id']}"):
                    core.update_member_prefs(conn, m["name"], lbl, dict(DIET_PRESETS[lbl])); st.rerun()
                new={} ; cc=st.columns(2)
                for i,t in enumerate(FOOD_TYPES):
                    with cc[i%2]:
                        new[t]=st.select_slider(TYPE_LABELS[t], options=LEVELS,
                            value=m["prefs"].get(t,"balanced"), key=f"pf_{m['id']}_{t}",
                            format_func=lambda x:LEVEL_LABELS[x])
                b1,b2=st.columns(2)
                if b1.button("Save", key=f"save_{m['id']}"):
                    core.update_member_prefs(conn, m["name"], lbl, new); st.success("Saved."); st.rerun()
                if b2.button("Remove person", key=f"rm_{m['id']}"):
                    core.remove_member(conn, m["name"]); st.rerun()
    st.divider()
    with st.expander("➕ Add a new person"):
        nm=st.text_input("Name", key="add_name")
        lbl=st.selectbox("Diet style", list(DIET_PRESETS), key="add_lbl")
        if st.button("Add person", key="add_person") and nm.strip():
            core.add_member(conn, nm.strip(), lbl); st.rerun()

# ============================ RECIPES ============================
with tabs[2]:
    st.markdown("#### Recipe library")
    f1,f2,f3=st.columns(3)
    cz=f1.selectbox("Cuisine", ["All"]+core.cuisines(conn))
    cats=["All"]+sorted({r["category"] for r in core.recipes(conn)})
    ct=f2.selectbox("Type", cats)
    fav=f3.toggle("⭐ Favorites only", key="rec_fav")
    rlist=core.recipes(conn, favorites_only=fav, cuisine=cz, category=ct)
    st.caption(f"{len(rlist)} recipes")
    for r in rlist:
        a,b=st.columns([5,1])
        prof=" ".join(f'<span class="pill">{TYPE_LABELS[t]}</span>'
                      for t,v in r["type_profile"].items() if v>=2)
        a.markdown(f'**{r["name"]}** <span class="pill cuisine">{r["cuisine"]}</span>'
                   f'{"<span class=\"pill fav\">favorite</span>" if r["is_favorite"] else ""}<br>{prof}',
                   unsafe_allow_html=True)
        if b.button("⭐" if not r["is_favorite"] else "★", key=f"fav_{r['id']}"):
            core.toggle_favorite(conn,r["id"]); st.rerun()

# ============================ SHOPPING ============================
with tabs[3]:
    st.markdown("#### Shared shopping list")
    store_opts={"All stores":None}|{s["name"]:s["id"] for s in core.stores(conn)}
    g1,g2,g3=st.columns(3)
    sp=g1.selectbox("Store", list(store_opts))
    kp=g2.selectbox("Kind", ["all","food","household"])
    wp=g3.selectbox("Added by", ["everyone"]+[m["name"] for m in core.members(conn)])
    rows=core.shopping_list(conn, store_id=store_opts[sp],
        added_by=None if wp=="everyone" else wp, kind=None if kp=="all" else kp)
    if not rows:
        st.info("Nothing here yet. Push a week from Plan, or add items below.")
    else:
        cur=None
        for r in rows:
            head=f"{r['store'] or 'Any store'} · {r['aisle']}"
            if head!=cur: cur=head; st.markdown(f"**{head}**")
            cc=st.columns([6,2,2])
            qty=f"{r['quantity']:g} {r['unit']}".strip() if r["quantity"] else ""
            ch=cc[0].checkbox(f"{qty+' — ' if qty else ''}{r['name']}", value=bool(r["checked"]), key=f"ck_{r['id']}")
            if ch!=bool(r["checked"]): core.toggle_checked(conn,r["id"]); st.rerun()
            cc[1].markdown(f"<span class='small'>by {r['added_by'] or '—'}</span>", unsafe_allow_html=True)
            mv=cc[2].selectbox("move",["move…"]+[s["name"] for s in core.stores(conn)],
                key=f"mv_{r['id']}", label_visibility="collapsed")
            if mv!="move…":
                core.move_item_store(conn,r["id"],{s["name"]:s["id"] for s in core.stores(conn)}[mv]); st.rerun()
    st.divider()
    a1,a2,a3,a4=st.columns(4)
    ni=a1.text_input("Item", key="si_n")
    nsx=a2.selectbox("Store",[s["name"] for s in core.stores(conn)], key="si_s")
    nk=a3.selectbox("Kind",["food","household"], key="si_k")
    na=a4.selectbox("Aisle",["Produce","Meat","Seafood","Dairy","Bakery","Frozen","Pantry","Spices","Canned","Household","Other"], key="si_a")
    if st.button("➕ Add item") and ni.strip():
        core.add_shopping_item(conn,ni.strip(),None,"",na,
            {s["name"]:s["id"] for s in core.stores(conn)}[nsx],nk,ss["who"] or ""); st.rerun()
    b1,b2,b3=st.columns(3)
    if b1.button("✅ Clear checked"): core.clear_checked(conn); st.rerun()
    if b2.button("🗑️ Clear all"): core.clear_list(conn); st.rerun()
    with b3.popover("📤 Share as text"):
        st.code(core.list_as_text(conn, store_id=store_opts[sp]), language=None)

# ============================ RECEIPTS ============================
with tabs[4]:
    st.markdown("#### Log a receipt")
    r1,r2,r3=st.columns(3)
    rs=r1.selectbox("Store",[s["name"] for s in core.stores(conn)], key="rc_s")
    rt=r2.number_input("Total ($)",0.0,100000.0,0.0,step=0.01)
    rd=r3.date_input("Date")
    ph=st.file_uploader("Receipt photo",type=["png","jpg","jpeg","webp"])
    rnote=st.text_input("Note (optional)")
    st.caption("Optional itemize (name | qty | price):")
    ri=st.text_area("Items","",placeholder="Ground beef | 2 | 9.98", label_visibility="collapsed")
    if st.button("💾 Save receipt"):
        path=""
        if ph is not None:
            path=os.path.join(UP_DIR,f"receipt_{rd}_{ph.name}")
            with open(path,"wb") as f: f.write(ph.getbuffer())
        items=[]
        for line in ri.splitlines():
            pr=[x.strip() for x in line.split("|")]
            if pr and pr[0]: items.append({"name":pr[0],
                "qty":float(pr[1]) if len(pr)>1 and pr[1] else 1,
                "price":float(pr[2]) if len(pr)>2 and pr[2] else 0})
        core.add_receipt(conn,{s["name"]:s["id"] for s in core.stores(conn)}[rs],
            rt,str(rd),path,ss["who"] or "",rnote,items)
        st.success("Saved."); st.rerun()
    st.divider()
    s=core.spend_summary(conn)
    st.metric("Total logged", f"${s['total']:,.2f}")
    if s["by_store"]:
        st.markdown("**By store**")
        for x in s["by_store"]:
            if x["store"]: st.markdown(f"{x['store']}: **${x['spent']:,.2f}** <span class='small'>({x['visits']} visits)</span>", unsafe_allow_html=True)
    mb=core.most_bought(conn)
    if mb:
        st.markdown("**Most-bought**")
        for x in mb: st.markdown(f"• {x['name']} <span class='small'>×{x['q']:g}</span>", unsafe_allow_html=True)
    for r in core.receipts(conn, limit=10):
        with st.expander(f"{r['visit_date']} · {r['store'] or '—'} · ${r['total']:,.2f}"):
            if r["note"]: st.write(r["note"])
            if r["photo_path"] and os.path.exists(r["photo_path"]): st.image(r["photo_path"], width=260)

# ============================ HOUSEHOLD ============================
with tabs[5]:
    st.markdown("#### Household (non-food) items")
    hh=core.shopping_list(conn, kind="household")
    if hh:
        for r in hh:
            cc=st.columns([6,2])
            ch=cc[0].checkbox(r["name"], value=bool(r["checked"]), key=f"hh_{r['id']}")
            if ch!=bool(r["checked"]): core.toggle_checked(conn,r["id"]); st.rerun()
            cc[1].markdown(f"<span class='small'>{r['store'] or 'Any'} · {r['added_by'] or '—'}</span>", unsafe_allow_html=True)
    else:
        st.info("No household items yet.")
    h1,h2=st.columns([2,1])
    hn=h1.text_input("Add household item", key="hh_n")
    hsx=h2.selectbox("Store",[s["name"] for s in core.stores(conn)], key="hh_s")
    if st.button("➕ Add household item") and hn.strip():
        core.add_shopping_item(conn,hn.strip(),None,"","Household",
            {s["name"]:s["id"] for s in core.stores(conn)}[hsx],"household",ss["who"] or ""); st.rerun()

conn.close()
