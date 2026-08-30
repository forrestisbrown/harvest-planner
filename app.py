"""app.py — Harvest v4. Onboarding, clean prefs, per-serving USDA calories on
recipe cards, quick filter, night swap, custom recipes, simple grocery list."""
import os
import streamlit as st
from db_setup import build, DB_PATH, connect, FOOD_TYPES, PREF_LEVELS, PREF_LABELS, DIET_PRESETS
import core, theme, usda, mealdb

st.set_page_config(page_title="Harvest", page_icon="🥗", layout="wide")
if not os.path.exists(DB_PATH): build()
UP=os.path.join(os.path.dirname(__file__),"uploads"); os.makedirs(UP,exist_ok=True)

ss=st.session_state
ss.setdefault("grid",[]); ss.setdefault("grid_meals",["dinner"]); ss.setdefault("who",None)
conn=connect(); theme.inject()

TYPE_LABELS={"red_meat":"Red meat","poultry":"Poultry","pork":"Pork","seafood":"Seafood",
             "veg":"Vegetables","legumes":"Legumes/beans","pasta":"Pasta/carbs"}

def hero(t,sub=None):
    s=f'<div class="hero-sub">{sub}</div>' if sub else ''
    st.markdown(f'<div class="center"><div class="hero-title">{t}</div>{s}<hr class="accent-rule"/></div>',unsafe_allow_html=True)

def pref_editor(prefix, base_prefs):
    """Render the clean Never/Sometimes/Often/Love dials. Returns dict."""
    out={}; cols=st.columns(2)
    for i,t in enumerate(FOOD_TYPES):
        with cols[i%2]:
            out[t]=st.select_slider(TYPE_LABELS[t], options=PREF_LEVELS,
                value=base_prefs.get(t,"often"), key=f"{prefix}_{t}",
                format_func=lambda x:PREF_LABELS[x])
    return out

def pref_editor_profile(prefix):
    """For a custom recipe: how much each food type FEATURES (0=none..3=heavy)."""
    lvl=["none","some","lots"]; out={t:0 for t in FOOD_TYPES}; cols=st.columns(2)
    for i,t in enumerate(FOOD_TYPES):
        with cols[i%2]:
            v=st.select_slider(TYPE_LABELS[t], options=lvl, value="none",
                key=f"{prefix}_{t}")
            out[t]={"none":0,"some":2,"lots":3}[v]
    return out

# ===================== ONBOARDING =====================
if not core.is_onboarded(conn):
    hero("Welcome to Harvest","Set up your household")
    _,mid,_=st.columns([1,2,1])
    with mid:
        existing=core.members(conn)
        if existing:
            st.markdown("".join(f'<span class="pill on">{m["name"]} · {m["diet_label"]}</span>' for m in existing),unsafe_allow_html=True)
            st.write("")
        st.markdown("#### Add a person")
        name=st.text_input("Name", placeholder="e.g. Forrest", key="onb_name")
        label=st.selectbox("Diet style", list(DIET_PRESETS), key="onb_label",
            help="Sets sensible starting preferences — fine-tune below.")
        st.caption("How often do they want each food type?")
        prefs=pref_editor("onb", dict(DIET_PRESETS[label]))
        if st.button("Add this person"):
            if name.strip(): core.add_member(conn,name.strip(),label,prefs); st.rerun()
            else: st.warning("Give them a name first.")
        if existing:
            st.divider()
            if st.button("Done — start planning"):
                core.set_setting(conn,"onboarded","1"); st.rerun()
    conn.close(); st.stop()

# ===================== SIDEBAR =====================
with st.sidebar:
    st.markdown("### 🥗 Harvest")
    mem_names=[m["name"] for m in core.members(conn)]
    if ss["who"] not in mem_names: ss["who"]=mem_names[0] if mem_names else None
    if mem_names: ss["who"]=st.selectbox("You are", mem_names, index=mem_names.index(ss["who"]))
    st.divider(); st.markdown("**Active this week**")
    for m in core.members(conn):
        on=st.checkbox(m["name"], value=bool(m["active"]), key=f"act_{m['name']}")
        if on!=bool(m["active"]): core.set_member_active(conn,m["name"],on); st.rerun()
    st.divider()
    with st.expander("Stores"):
        for s in core.stores(conn): st.write("• "+s["name"])
        nsx=st.text_input("Add a store", key="new_store")
        if st.button("Add store") and nsx.strip(): core.add_store(conn,nsx.strip()); st.rerun()

hero("Harvest","Household meal planning")
tabs=st.tabs(["Plan","People","Recipes","Lookup","Shopping","Receipts","Household"])

def macro_badges(rid):
    m=core.recipe_macros(conn, rid)
    if m.get("kcal") is None: return '<span class="pill">cal: —</span>'
    return (f'<span class="pill">~{m["kcal"]} cal</span>'
            f'<span class="pill">P {m["protein"]}g</span>'
            f'<span class="pill">C {m["carbs"]}g</span>'
            f'<span class="pill">F {m["fat"]}g</span>')

# ===================== PLAN =====================
with tabs[0]:
    active=core.members(conn,active_only=True)
    if not active:
        st.info("Turn someone on in the sidebar to plan.")
    else:
        st.markdown("#### Plan your meals")
        c1,c2=st.columns([1,2])
        days=c1.slider("How many days?",1,7,3)
        # meal selection as pills (segmented buttons), not a dropdown
        st.write("Which meals?")
        pc=st.columns(3)
        for idx,mlabel in enumerate(["breakfast","lunch","dinner"]):
            on = mlabel in ss["grid_meals"]
            if pc[idx].button(("● " if on else "○ ")+mlabel.capitalize(),
                              key=f"mealpill_{mlabel}", use_container_width=True):
                if on and len(ss["grid_meals"])>1: ss["grid_meals"].remove(mlabel)
                elif not on: ss["grid_meals"].append(mlabel)
                st.rerun()
        # keep canonical order
        ss["grid_meals"]=[m for m in ["breakfast","lunch","dinner"] if m in ss["grid_meals"]]

        c3,c4,c5,c6=st.columns([1.4,1,1,1.1])
        cz=c3.selectbox("Mood / cuisine",["Any"]+core.cuisines(conn),
            help="Steer the whole plan toward a cuisine.")
        quick=c4.toggle("Quick only",key="plan_quick")
        favs=c5.toggle("Favorites",key="plan_favs")
        discover=c6.toggle("Discover new",value=True,key="plan_discover",
            help="Mix in fresh meals from TheMealDB")
        if st.button("🎲 Generate meals"):
            with st.spinner("Building your plan…"):
                ss["grid"]=core.plan_grid_blended(conn, days=days, meals=ss["grid_meals"],
                    cuisine=None if cz=="Any" else cz, quick_only=quick,
                    favorites_only=favs, discover=discover)

        grid=ss["grid"]
        if not grid:
            st.info("Pick your days and meals, then generate.")
        else:
            WEEKDAYS=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            all_by_meal={m:{r["id"]:r["name"] for r in core.recipes(conn,meal=m)} for m in ["breakfast","lunch","dinner"]}
            for di,day in enumerate(grid):
                st.markdown(f'<div class="daylabel">{WEEKDAYS[di%7]}</div>',unsafe_allow_html=True)
                cols=st.columns(len(day))
                for ci,(meal,r) in enumerate(day.items()):
                    with cols[ci]:
                        if not r:
                            st.markdown(f'<div class="mcard"><span class="mmeta">{meal}: none</span></div>',unsafe_allow_html=True)
                            continue
                        m=core.recipe_macros(conn,r["id"])
                        cal = f"{m['kcal']} cal" if m.get("kcal") else "cal —"
                        st.markdown(
                            f'<div class="mcard">'
                            f'<span class="pill veg">{meal}</span>'
                            f'<span class="pill cuisine">{r["cuisine"]}</span>'
                            f'<div class="mname">{r["name"]}</div>'
                            f'<span class="mmeta">{r["minutes"]} min · {cal}</span>'
                            f'</div>', unsafe_allow_html=True)
                        with st.expander("View recipe"):
                            if m.get("kcal"):
                                mm=st.columns(4)
                                mm[0].metric("Cal",f"{m['kcal']}")
                                mm[1].metric("Protein",f"{m['protein']}g")
                                mm[2].metric("Carbs",f"{m['carbs']}g")
                                mm[3].metric("Fat",f"{m['fat']}g")
                            st.markdown("**Ingredients**")
                            for l in core.recipe_lines(conn,r["id"]):
                                amt=f"{l['amount']} " if l["amount"] else ""
                                st.markdown(f"• {amt}{l['ingredient']}")
                            if r["steps"]:
                                st.markdown("**Steps**"); st.write(r["steps"])
                        bc=st.columns(2)
                        if bc[0].button("🎲 Reroll", key=f"rr_{di}_{meal}"):
                            used={x["id"] for d2 in grid for mm2,x in d2.items() if mm2==meal and x}
                            newr=None
                            if discover: newr=core.discover_meal(conn, meal, cuisine=None if cz=="Any" else cz)
                            if not newr:
                                newr=core.pick_one(conn, meal, exclude=used,
                                    cuisine=None if cz=="Any" else cz, quick_only=quick, favorites_only=favs)
                            if newr: ss["grid"][di][meal]=newr; st.rerun()
                        pick=bc[1].selectbox("swap",["swap…"]+list(all_by_meal[meal].values()),
                            key=f"sw_{di}_{meal}", label_visibility="collapsed")
                        if pick!="swap…":
                            rid=[k for k,v in all_by_meal[meal].items() if v==pick][0]
                            ss["grid"][di][meal]=core.recipe_by_id(conn,rid); st.rerun()

            ids=core.grid_recipe_ids(grid)
            st.markdown("#### 🛒 Grocery preview")
            st.caption("Combined across every planned meal — no duplicates.")
            cur=None
            for row in core.grocery_items(conn,ids):
                if row["aisle"]!=cur: cur=row["aisle"]; st.markdown(f"**{cur}**")
                st.markdown(f"• {row['ingredient']}")
            store_opts={s["name"]:s["id"] for s in core.stores(conn)}
            tgt=st.selectbox("Add to store", list(store_opts))
            if st.button("➕ Add all to shopping list"):
                core.push_items_to_list(conn, core.grocery_items(conn,ids), store_id=store_opts[tgt], added_by=ss["who"] or "")
                st.success("Added to your shopping list.")

# ===================== PEOPLE =====================
with tabs[1]:
    st.markdown("#### Household preferences")
    st.caption("Set how often each person wants each food type. This targets the menu.")
    for m in core.members(conn):
        st.markdown(f'<div class="card"><b style="font-size:1.15rem">{m["name"]}</b> '
            f'<span class="pill on">{m["diet_label"]}</span>'
            +"".join(f'<span class="pill">{TYPE_LABELS[t]}: {PREF_LABELS[m["prefs"].get(t,"often")]}</span>' for t in FOOD_TYPES)
            +'</div>',unsafe_allow_html=True)
        with st.expander(f"Edit {m['name']}"):
            lbl=st.selectbox("Diet style",list(DIET_PRESETS),
                index=list(DIET_PRESETS).index(m["diet_label"]) if m["diet_label"] in DIET_PRESETS else 0,
                key=f"lbl_{m['id']}")
            if st.button(f"Reset to {lbl} defaults", key=f"rs_{m['id']}"):
                core.update_member_prefs(conn,m["name"],lbl,dict(DIET_PRESETS[lbl])); st.rerun()
            new=pref_editor(f"pf_{m['id']}", m["prefs"])
            b1,b2=st.columns(2)
            if b1.button("Save",key=f"sv_{m['id']}"):
                core.update_member_prefs(conn,m["name"],lbl,new); st.success("Saved."); st.rerun()
            if b2.button("Remove person",key=f"rm_{m['id']}"):
                core.remove_member(conn,m["name"]); st.rerun()
    st.divider()
    with st.expander("➕ Add a new person"):
        nm=st.text_input("Name",key="add_nm")
        lbl2=st.selectbox("Diet style",list(DIET_PRESETS),key="add_lbl")
        pf=pref_editor("addp", dict(DIET_PRESETS[lbl2]))
        if st.button("Add person") and nm.strip():
            core.add_member(conn,nm.strip(),lbl2,pf); st.rerun()

# ===================== RECIPES =====================
with tabs[2]:
    st.markdown("#### Find a recipe")
    sc1,sc2=st.columns([3,1])
    sq=sc1.text_input("Search", placeholder="Search your library and thousands more…", label_visibility="collapsed")
    go=sc2.button("Search", use_container_width=True)
    if go and sq.strip():
        with st.spinner("Searching…"):
            results=core.blended_search(conn, sq.strip())
        if not results:
            st.info("No matches found.")
        else:
            st.caption(f"{len(results)} results")
            for res in results[:20]:
                rc=st.columns([1,4,1])
                if res.get("thumb"): rc[0].image(res["thumb"], width=60)
                src_pill = '<span class="pill veg">saved</span>' if res["source"]=="library" else '<span class="pill cuisine">new</span>'
                rc[1].markdown(f'{res["name"]} {src_pill}'
                    + (f'<span class="pill">{res["cuisine"]}</span>' if res.get("cuisine") else ''),
                    unsafe_allow_html=True)
                if res["source"]=="library":
                    if rc[2].button("View", key=f"sv_{res['id']}"):
                        st.session_state["view_recipe"]=res["id"]; st.rerun()
                else:
                    if rc[2].button("Add", key=f"sm_{res['meal_id']}"):
                        saved=core.save_mealdb_by_id(conn, res["meal_id"])
                        if saved: st.success(f"Added {saved['name']} to your library.")
                        else: st.warning("Couldn't add that one.")
                        st.rerun()
        st.divider()

    st.markdown("#### Recipe library")
    f1,f2,f3,f4=st.columns(4)
    cz=f1.selectbox("Cuisine",["All"]+core.cuisines(conn))
    ct=f2.selectbox("Type",["All"]+core.categories(conn))
    qk=f3.toggle("Quick only",key="rec_quick")
    fav=f4.toggle("⭐ Favorites",key="rec_favs")
    rlist=core.recipes(conn,favorites_only=fav,cuisine=cz,category=ct,quick_only=qk)
    st.caption(f"{len(rlist)} recipes")
    for r in rlist:
        a,b=st.columns([5,1])
        tags=f'<span class="pill cuisine">{r["cuisine"]}</span><span class="pill">{r["minutes"]} min</span>'
        if r["is_quick"]: tags+='<span class="pill veg">quick</span>'
        if r["is_custom"]: tags+='<span class="pill">custom</span>'
        a.markdown(f'**{r["name"]}** {tags}',unsafe_allow_html=True)
        if b.button("★" if r["is_favorite"] else "☆", key=f"fav_{r['id']}"):
            core.toggle_favorite(conn,r["id"]); st.rerun()
        with st.expander("Recipe details"):
            m=core.recipe_macros(conn,r["id"])
            if m.get("kcal") is not None:
                mm=st.columns(4)
                mm[0].metric("Calories",f"~{m['kcal']}")
                mm[1].metric("Protein",f"{m['protein']}g")
                mm[2].metric("Carbs",f"{m['carbs']}g")
                mm[3].metric("Fat",f"{m['fat']}g")
                st.caption("Per serving · USDA estimate")
            else:
                st.markdown("<span class='small'>Nutrition unavailable (add a USDA key to enable)</span>",unsafe_allow_html=True)
            st.markdown(f"**Serves {r['servings']} · {r['minutes']} min · {r['meal']}**")
            st.markdown("**Ingredients**")
            for l in core.recipe_lines(conn,r["id"]):
                tag="" if l["branch"]=="shared" else f" — *{l['branch'].replace('_branch','')}*"
                amt=f"{l['amount']} " if l["amount"] else ""
                st.markdown(f"• {amt}{l['ingredient']}{tag}")
            if r["steps"]:
                st.markdown("**Steps**"); st.write(r["steps"])
            if r["is_custom"] and st.button("Delete this recipe", key=f"del_{r['id']}"):
                core.delete_recipe(conn,r["id"]); st.rerun()

    st.divider()
    with st.expander("➕ Add your own recipe"):
        rn=st.text_input("Name",key="cr_n")
        d1,d2,d3,d4=st.columns(4)
        rcat=d1.text_input("Type","chicken",key="cr_cat")
        rcz=d2.text_input("Cuisine","American",key="cr_cz")
        rmin=d3.number_input("Minutes",5,180,25,key="cr_min")
        rmeal=d4.selectbox("Meal",["dinner","lunch","breakfast"],key="cr_meal")
        rserv=st.number_input("Servings",1,12,2,key="cr_sv")
        st.caption("Food-type profile (helps targeting) — how much each type features:")
        tp=pref_editor_profile("crp")
        st.caption("Ingredients — one per line:  name | amount | shared/You/veg")
        raw=st.text_area("Ingredients","Chicken breast | 1 lb | shared\nBroccoli | 1 head | shared",key="cr_ings")
        steps=st.text_area("Steps","",key="cr_steps",placeholder="Short method, a few sentences.")
        if st.button("Save recipe") and rn.strip():
            items=[]
            for line in raw.splitlines():
                p=[x.strip() for x in line.split("|")]
                if p and p[0]:
                    items.append((p[0], p[1] if len(p)>1 else "", (p[2]+"_branch") if len(p)>2 and p[2] and p[2]!="shared" else "shared"))
            core.add_recipe(conn,rn.strip(),rcat,rcz,int(rserv),int(rmin),tp,steps,items,meal=rmeal)
            st.success(f"Saved {rn}. Open its card to auto-calc calories."); st.rerun()

# ===================== LOOKUP =====================
with tabs[3]:
    st.markdown("#### Food nutrition lookup")
    st.caption("Type any food to see USDA nutrition. Adjust the amount to scale it.")
    lc1,lc2=st.columns([2,1])
    food=lc1.text_input("Food", placeholder="e.g. cheddar cheese, banana, chicken breast")
    grams=lc2.number_input("Grams",1,2000,100,step=10)
    if st.button("Look up") and food.strip():
        res=usda.lookup(food.strip(), grams)
        if not res:
            st.warning("No match found (or USDA key not set). Try a simpler name.")
        else:
            st.markdown(f"**{res['desc']}** — per {res['grams']}g")
            m1,m2,m3,m4=st.columns(4)
            m1.metric("Calories",f"{res['kcal']}")
            m2.metric("Protein",f"{res['protein']} g")
            m3.metric("Carbs",f"{res['carbs']} g")
            m4.metric("Fat",f"{res['fat']} g")
            st.caption("Source: USDA FoodData Central. Values are per the amount shown.")

# ===================== SHOPPING =====================
with tabs[4]:
    st.markdown("#### Shared shopping list")
    store_opts={"All stores":None}|{s["name"]:s["id"] for s in core.stores(conn)}
    g1,g2,g3=st.columns(3)
    spk=g1.selectbox("Store",list(store_opts))
    kp=g2.selectbox("Kind",["all","food","household"])
    wp=g3.selectbox("Added by",["everyone"]+[m["name"] for m in core.members(conn)])
    rows=core.shopping_list(conn,store_id=store_opts[spk],
        added_by=None if wp=="everyone" else wp, kind=None if kp=="all" else kp)
    if not rows:
        st.info("Nothing yet. Push a week from Plan, or add below.")
    else:
        cur=None
        for r in rows:
            head=f"{r['store'] or 'Any store'} · {r['aisle']}"
            if head!=cur: cur=head; st.markdown(f"**{head}**")
            cc=st.columns([6,2,2])
            ch=cc[0].checkbox(r["name"], value=bool(r["checked"]), key=f"ck_{r['id']}")
            if ch!=bool(r["checked"]): core.toggle_checked(conn,r["id"]); st.rerun()
            cc[1].markdown(f"<span class='small'>by {r['added_by'] or '—'}</span>",unsafe_allow_html=True)
            mv=cc[2].selectbox("move",["move…"]+[s["name"] for s in core.stores(conn)],key=f"mv_{r['id']}",label_visibility="collapsed")
            if mv!="move…": core.move_item_store(conn,r["id"],{s["name"]:s["id"] for s in core.stores(conn)}[mv]); st.rerun()
    st.divider()
    a1,a2,a3=st.columns(3)
    ni=a1.text_input("Item",key="si_n")
    nsx=a2.selectbox("Store",[s["name"] for s in core.stores(conn)],key="si_s")
    nk=a3.selectbox("Kind",["food","household"],key="si_k")
    if st.button("➕ Add item") and ni.strip():
        core.add_shopping_item(conn,ni.strip(),"Other",{s["name"]:s["id"] for s in core.stores(conn)}[nsx],nk,ss["who"] or ""); st.rerun()
    b1,b2,b3=st.columns(3)
    if b1.button("✅ Clear checked"): core.clear_checked(conn); st.rerun()
    if b2.button("🗑️ Clear all"): core.clear_list(conn); st.rerun()
    with b3.popover("📤 Share as text"):
        st.code(core.list_as_text(conn,store_id=store_opts[spk]),language=None)

# ===================== RECEIPTS =====================
with tabs[5]:
    st.markdown("#### Log a receipt")
    r1,r2,r3=st.columns(3)
    rs=r1.selectbox("Store",[s["name"] for s in core.stores(conn)],key="rc_s")
    rt=r2.number_input("Total ($)",0.0,100000.0,0.0,step=0.01)
    rd=r3.date_input("Date")
    ph=st.file_uploader("Receipt photo",type=["png","jpg","jpeg","webp"])
    rnote=st.text_input("Note (optional)")
    st.caption("Optional itemize (name | qty | price):")
    ri=st.text_area("Items","",label_visibility="collapsed",placeholder="Ground beef | 1 | 5.99")
    if st.button("💾 Save receipt"):
        path=""
        if ph is not None:
            path=os.path.join(UP,f"receipt_{rd}_{ph.name}")
            with open(path,"wb") as f: f.write(ph.getbuffer())
        items=[]
        for line in ri.splitlines():
            p=[x.strip() for x in line.split("|")]
            if p and p[0]: items.append({"name":p[0],"qty":float(p[1]) if len(p)>1 and p[1] else 1,"price":float(p[2]) if len(p)>2 and p[2] else 0})
        core.add_receipt(conn,{s["name"]:s["id"] for s in core.stores(conn)}[rs],rt,str(rd),path,ss["who"] or "",rnote,items)
        st.success("Saved."); st.rerun()
    st.divider()
    s=core.spend_summary(conn)
    st.metric("Total logged",f"${s['total']:,.2f}")
    if s["by_store"]:
        st.markdown("**By store**")
        for x in s["by_store"]:
            if x["store"]: st.markdown(f"{x['store']}: **${x['spent']:,.2f}** <span class='small'>({x['visits']} visits)</span>",unsafe_allow_html=True)
    mb=core.most_bought(conn)
    if mb:
        st.markdown("**Most-bought**")
        for x in mb: st.markdown(f"• {x['name']} <span class='small'>×{x['q']:g}</span>",unsafe_allow_html=True)
    for r in core.receipts(conn,limit=10):
        with st.expander(f"{r['visit_date']} · {r['store'] or '—'} · ${r['total']:,.2f}"):
            if r["note"]: st.write(r["note"])
            if r["photo_path"] and os.path.exists(r["photo_path"]): st.image(r["photo_path"],width=260)

# ===================== HOUSEHOLD =====================
with tabs[6]:
    st.markdown("#### Household (non-food) items")
    hh=core.shopping_list(conn,kind="household")
    if hh:
        for r in hh:
            cc=st.columns([6,2])
            ch=cc[0].checkbox(r["name"],value=bool(r["checked"]),key=f"hh_{r['id']}")
            if ch!=bool(r["checked"]): core.toggle_checked(conn,r["id"]); st.rerun()
            cc[1].markdown(f"<span class='small'>{r['store'] or 'Any'} · {r['added_by'] or '—'}</span>",unsafe_allow_html=True)
    else: st.info("No household items yet.")
    h1,h2=st.columns([2,1])
    hn=h1.text_input("Add household item",key="hh_n")
    hsx=h2.selectbox("Store",[s["name"] for s in core.stores(conn)],key="hh_s")
    if st.button("➕ Add household item") and hn.strip():
        core.add_shopping_item(conn,hn.strip(),"Household",{s["name"]:s["id"] for s in core.stores(conn)}[hsx],"household",ss["who"] or ""); st.rerun()

conn.close()
