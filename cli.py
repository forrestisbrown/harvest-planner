"""
cli.py — quick terminal access (optional; the web app is the main interface)

  python3 cli.py plan [--n 5] [--seed 42] [--favorites]
  python3 cli.py recipes [--favorites]
  python3 cli.py members
"""
import sys, os
from db_setup import build, DB_PATH
import core

if not os.path.exists(DB_PATH): build()

def _flag(args,name): return name in args
def _val(args,name,default=None,cast=str):
    return cast(args[args.index(name)+1]) if name in args else default

def cmd_plan(args):
    from db_setup import connect; c=connect()
    picks=core.plan_week(c, n=_val(args,"--n",5,int), seed=_val(args,"--seed",None,int),
                         favorites_only=_flag(args,"--favorites"))
    ids=[p["id"] for p in picks]
    print("\nActive:", ", ".join(core.active_member_names(c)))
    print(f"\n=== Week ({len(picks)}) ===")
    for i,p in enumerate(picks,1): print(f"  {i}. {p['name']}  [{p['cuisine']}/{p['category']}]")
    print("\n=== Grocery (by aisle) ==="); cur=None
    for row in core.aggregate_plan(c, ids):
        if row["aisle"]!=cur: cur=row["aisle"]; print(f"\n  -- {cur} --")
        print(f"     {row['quantity']:>7g} {row['unit']:<4} {row['ingredient']}")
    print("\n=== Calories ===")
    tot,per=core.week_calories(c, ids)
    for name,split in per:
        print(f"  {name}: "+", ".join(f"{m} {int(v)}" for m,v in split.items() if not m.startswith("_")))
    print("\n  Weekly: "+", ".join(f"{m} {int(v)}" for m,v in tot.items())); c.close()

def cmd_recipes(args):
    from db_setup import connect; c=connect()
    for r in core.recipes(c, favorites_only=_flag(args,"--favorites")):
        star="⭐" if r["is_favorite"] else "  "
        print(f"  {star} {r['name']:<30} [{r['cuisine']}/{r['category']}]")
    c.close()

def cmd_members(args):
    from db_setup import connect; c=connect()
    for m in core.members(c):
        print(f"  [{'ON ' if m['active'] else 'off'}] {m['name']:<10} ({m['dietary_style']})")
    c.close()

CMDS={"plan":cmd_plan,"recipes":cmd_recipes,"members":cmd_members}
if __name__=="__main__":
    if len(sys.argv)<2 or sys.argv[1] not in CMDS: print(__doc__); sys.exit(0)
    CMDS[sys.argv[1]](sys.argv[2:])
