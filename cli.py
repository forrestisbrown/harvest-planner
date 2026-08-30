"""cli.py — quick terminal access (the web app is the main interface).
  python3 cli.py plan [--n 5] [--individual] [--seed 42]
  python3 cli.py people
"""
import sys, os
from db_setup import build, DB_PATH
import core
if not os.path.exists(DB_PATH): build()
def _val(a,n,d,cast=str): return cast(a[a.index(n)+1]) if n in a else d
def cmd_plan(a):
    from db_setup import connect; c=connect()
    if not core.members(c,active_only=True): print("No active members. Open the web app to set up."); return
    mode="individual" if "--individual" in a else "together"
    nights=core.plan_week(c,n=_val(a,"--n",5,int),mode=mode,seed=_val(a,"--seed",None,int))
    print(f"\n=== Week ({mode}) ===")
    for i,nt in enumerate(nights,1):
        if nt["mode"]=="together": print(f"  Night {i}: {nt['recipe']['name']}")
        else: print(f"  Night {i}: "+" | ".join(f"{w}: {r['name']}" for w,r in nt["per_member"].items()))
    ids=core.plan_recipe_ids(nights)
    print("\n=== Grocery ==="); cur=None
    for row in core.aggregate_recipe_rows(c,ids):
        if row["aisle"]!=cur: cur=row["aisle"]; print(f"\n  -- {cur} --")
        print(f"     {row['quantity']:>7g} {row['unit']:<4} {row['ingredient']}")
    c.close()
def cmd_people(a):
    from db_setup import connect,FOOD_TYPES; c=connect()
    for m in core.members(c):
        print(f"  {m['name']} [{m['diet_label']}]  "+", ".join(f"{t}:{m['prefs'].get(t)}" for t in FOOD_TYPES))
    c.close()
CMDS={"plan":cmd_plan,"people":cmd_people}
if __name__=="__main__":
    if len(sys.argv)<2 or sys.argv[1] not in CMDS: print(__doc__); sys.exit(0)
    CMDS[sys.argv[1]](sys.argv[2:])
