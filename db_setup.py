"""
db_setup.py — v3
Household meal planner with per-person dietary preferences.

New in v3:
- members carry a diet_label + per-food-type dials (none/flavor/balanced/heavy)
- recipes tagged with a food-type profile (how much of each type they feature)
- onboarding-driven (no default You/Lizzy; a fresh DB starts empty of members)
- ~40 recipes for good per-person targeting

Run:  python3 db_setup.py --reset
"""
import sqlite3, sys, os, json

DB_PATH = os.path.join(os.path.dirname(__file__), "mealplanner.db")

# The seven food types we target, and the 4-level preference scale.
FOOD_TYPES = ["red_meat","poultry","pork","seafood","veg","legumes","pasta"]
LEVELS = ["none","flavor","balanced","heavy"]   # ordered; index used for scoring

# Diet labels pre-set the dials. Values are per-type levels.
DIET_PRESETS = {
    "Omnivore":      {"red_meat":"balanced","poultry":"balanced","pork":"balanced","seafood":"balanced","veg":"balanced","legumes":"balanced","pasta":"balanced"},
    "Meat-focused":  {"red_meat":"heavy","poultry":"heavy","pork":"heavy","seafood":"balanced","veg":"flavor","legumes":"none","pasta":"balanced"},
    "Veggie-heavy":  {"red_meat":"flavor","poultry":"flavor","pork":"none","seafood":"balanced","veg":"heavy","legumes":"heavy","pasta":"balanced"},
    "Pescatarian":   {"red_meat":"none","poultry":"none","pork":"none","seafood":"heavy","veg":"heavy","legumes":"balanced","pasta":"balanced"},
    "Vegetarian":    {"red_meat":"none","poultry":"none","pork":"none","seafood":"none","veg":"heavy","legumes":"heavy","pasta":"balanced"},
}

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    diet_label TEXT DEFAULT 'Omnivore',
    prefs TEXT DEFAULT '{}',          -- JSON: {food_type: level}
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_pos INTEGER NOT NULL DEFAULT 10
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    aisle TEXT NOT NULL DEFAULT 'Pantry',
    calories_per_unit REAL NOT NULL DEFAULT 0,
    unit_type TEXT NOT NULL DEFAULT 'unit',
    kind TEXT NOT NULL DEFAULT 'food'
);

CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT,
    cuisine TEXT DEFAULT 'American',
    servings INTEGER NOT NULL DEFAULT 2,
    is_favorite INTEGER NOT NULL DEFAULT 0,
    type_profile TEXT DEFAULT '{}',   -- JSON: {food_type: 0..3 intensity}
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity REAL NOT NULL,
    branch TEXT NOT NULL DEFAULT 'shared',
    PRIMARY KEY (recipe_id, ingredient_id, branch)
);

CREATE TABLE IF NOT EXISTS aisle_order (
    aisle TEXT PRIMARY KEY, sort_pos INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS shopping_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, quantity REAL, unit TEXT DEFAULT '',
    aisle TEXT DEFAULT 'Other',
    store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
    kind TEXT NOT NULL DEFAULT 'food', added_by TEXT DEFAULT '',
    checked INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
    total REAL NOT NULL DEFAULT 0, visit_date TEXT DEFAULT (date('now')),
    photo_path TEXT DEFAULT '', added_by TEXT DEFAULT '', note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS receipt_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    name TEXT NOT NULL, qty REAL DEFAULT 1, price REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY, value TEXT
);
"""

AISLE_ORDER = [("Produce",1),("Meat",2),("Seafood",3),("Dairy",4),("Bakery",5),
    ("Frozen",6),("Pantry",7),("Spices",8),("Canned",9),("Household",10),("Other",99)]
STORES = [("Aldi",1),("Publix",2),("Target",3),("Walmart",4)]

INGREDIENTS = [
    ("Ground beef","Meat",2.5,"g","food"),("Steak","Meat",2.7,"g","food"),
    ("Chicken thigh","Meat",2.1,"g","food"),("Chicken breast","Meat",1.65,"g","food"),
    ("Pork chop","Meat",2.3,"g","food"),("Pork sausage","Meat",3.0,"g","food"),
    ("Bacon","Meat",5.4,"g","food"),("Ground turkey","Meat",1.9,"g","food"),
    ("Salmon fillet","Seafood",2.0,"g","food"),("Shrimp","Seafood",0.99,"g","food"),
    ("Tilapia","Seafood",1.28,"g","food"),("Tuna","Seafood",1.3,"g","food"),
    ("White rice","Pantry",1.3,"g","food"),("Brown rice","Pantry",1.1,"g","food"),
    ("Russet potato","Produce",0.77,"g","food"),("Sweet potato","Produce",0.86,"g","food"),
    ("Broccoli","Produce",0.34,"g","food"),("Bell pepper","Produce",0.31,"g","food"),
    ("Yellow onion","Produce",0.40,"g","food"),("Garlic clove","Produce",4.0,"unit","food"),
    ("Carrot","Produce",0.41,"g","food"),("Zucchini","Produce",0.17,"g","food"),
    ("Spinach","Produce",0.23,"g","food"),("Mixed greens","Produce",0.20,"g","food"),
    ("Tomato","Produce",0.18,"g","food"),("Cucumber","Produce",0.15,"g","food"),
    ("Avocado","Produce",1.6,"g","food"),("Lime","Produce",30,"unit","food"),
    ("Cilantro","Produce",0.23,"g","food"),("Mushroom","Produce",0.22,"g","food"),
    ("Cabbage","Produce",0.25,"g","food"),("Kale","Produce",0.49,"g","food"),
    ("Black beans","Canned",1.3,"g","food"),("Chickpeas","Canned",1.6,"g","food"),
    ("Lentils","Pantry",1.16,"g","food"),("Kidney beans","Canned",1.27,"g","food"),
    ("Diced tomatoes","Canned",0.32,"g","food"),("Coconut milk","Canned",2.3,"ml","food"),
    ("Cheddar cheese","Dairy",4.0,"g","food"),("Mozzarella","Dairy",2.8,"g","food"),
    ("Parmesan","Dairy",4.3,"g","food"),("Butter","Dairy",7.2,"g","food"),
    ("Greek yogurt","Dairy",0.59,"g","food"),("Egg","Dairy",70,"unit","food"),
    ("Feta","Dairy",2.6,"g","food"),("Ricotta","Dairy",1.74,"g","food"),
    ("Olive oil","Pantry",8.8,"ml","food"),("Soy sauce","Pantry",0.6,"ml","food"),
    ("Pasta","Pantry",3.7,"g","food"),("Spaghetti","Pantry",3.7,"g","food"),
    ("Penne","Pantry",3.7,"g","food"),("Marinara sauce","Pantry",0.4,"ml","food"),
    ("Tortilla chips","Pantry",5.0,"g","food"),("Flour tortilla","Bakery",140,"unit","food"),
    ("Corn tortilla","Bakery",50,"unit","food"),("Naan","Bakery",260,"unit","food"),
    ("Burger bun","Bakery",150,"unit","food"),("Hoagie roll","Bakery",200,"unit","food"),
    ("Quinoa","Pantry",1.2,"g","food"),("Couscous","Pantry",3.6,"g","food"),
    ("Curry paste","Pantry",1.5,"g","food"),("Taco seasoning","Spices",3.0,"g","food"),
    ("Italian seasoning","Spices",3.0,"g","food"),("Cumin","Spices",8.0,"g","food"),
    ("Paprika","Spices",8.0,"g","food"),("Salsa","Pantry",0.3,"ml","food"),
    ("Honey","Pantry",3.0,"ml","food"),("Lemon","Produce",29,"unit","food"),
    ("Ginger","Produce",0.8,"g","food"),("Green onion","Produce",0.32,"g","food"),
    ("Basil","Produce",0.23,"g","food"),("Lettuce","Produce",0.15,"g","food"),
    ("Pesto","Pantry",4.5,"g","food"),("Pita bread","Bakery",165,"unit","food"),
    ("Paper towels","Household",0,"unit","household"),("Dish soap","Household",0,"unit","household"),
    ("Laundry detergent","Household",0,"unit","household"),("Trash bags","Household",0,"unit","household"),
    ("Toilet paper","Household",0,"unit","household"),("Sponges","Household",0,"unit","household"),
    ("Aluminum foil","Household",0,"unit","household"),("Hand soap","Household",0,"unit","household"),
]

# recipe -> (category, cuisine, servings, type_profile, [(ingredient, qty, branch)])
# type_profile intensity: 0 none, 1 light/flavor, 2 present, 3 heavy — per food type.
def _tp(**kw):
    base = {t:0 for t in FOOD_TYPES}; base.update(kw); return base

RECIPES = {
 "Beef & Potato Skillet":("beef","American",2,_tp(red_meat=3,veg=1),[("Ground beef",400,"shared"),("Russet potato",500,"shared"),("Yellow onion",100,"shared"),("Butter",30,"shared"),("Broccoli",200,"veg_branch")]),
 "Steak & Veg":("beef","American",2,_tp(red_meat=3,veg=2),[("Steak",400,"shared"),("Broccoli",250,"shared"),("Russet potato",300,"shared"),("Butter",30,"shared"),("Garlic clove",3,"shared")]),
 "Classic Beef Tacos":("beef","Mexican",2,_tp(red_meat=3,veg=1),[("Ground beef",400,"shared"),("Taco seasoning",30,"shared"),("Corn tortilla",6,"shared"),("Cheddar cheese",100,"You_branch"),("Mixed greens",120,"veg_branch"),("Tomato",120,"shared"),("Salsa",60,"shared")]),
 "Spaghetti & Meat Sauce":("pasta","Italian",2,_tp(red_meat=2,pasta=3,veg=1),[("Spaghetti",220,"shared"),("Marinara sauce",400,"shared"),("Ground beef",300,"shared"),("Garlic clove",2,"shared"),("Parmesan",40,"shared"),("Zucchini",180,"veg_branch")]),
 "Loaded Baked Potato":("potato","American",2,_tp(pork=1,veg=1),[("Russet potato",600,"shared"),("Butter",40,"shared"),("Cheddar cheese",120,"shared"),("Bacon",60,"pork_branch"),("Broccoli",200,"veg_branch"),("Greek yogurt",60,"shared")]),
 "Chicken Fried Rice":("chicken","Asian",2,_tp(poultry=3,veg=1,pasta=1),[("Chicken thigh",350,"shared"),("White rice",300,"shared"),("Soy sauce",45,"shared"),("Egg",2,"shared"),("Garlic clove",3,"shared"),("Bell pepper",150,"veg_branch"),("Green onion",30,"shared")]),
 "Teriyaki Salmon Bowl":("seafood","Asian",2,_tp(seafood=3,veg=2),[("Salmon fillet",340,"shared"),("Brown rice",280,"shared"),("Soy sauce",40,"shared"),("Honey",20,"shared"),("Broccoli",200,"shared"),("Green onion",30,"shared")]),
 "Shrimp Stir Fry":("seafood","Asian",2,_tp(seafood=3,veg=2),[("Shrimp",300,"shared"),("White rice",280,"shared"),("Soy sauce",40,"shared"),("Bell pepper",150,"shared"),("Carrot",120,"shared"),("Ginger",15,"shared"),("Garlic clove",3,"shared")]),
 "Chicken Parmesan":("chicken","Italian",2,_tp(poultry=3,pasta=2),[("Chicken breast",350,"shared"),("Marinara sauce",300,"shared"),("Mozzarella",120,"shared"),("Parmesan",40,"shared"),("Pasta",200,"shared"),("Basil",10,"shared")]),
 "Beef Burgers":("beef","American",2,_tp(red_meat=3,veg=1),[("Ground beef",400,"shared"),("Burger bun",2,"shared"),("Cheddar cheese",60,"shared"),("Lettuce",80,"shared"),("Tomato",100,"shared"),("Yellow onion",60,"shared")]),
 "Chicken Curry":("chicken","Indian",2,_tp(poultry=3,veg=1),[("Chicken thigh",350,"shared"),("Coconut milk",300,"shared"),("Curry paste",40,"shared"),("Yellow onion",120,"shared"),("Garlic clove",3,"shared"),("Ginger",15,"shared"),("Naan",2,"shared"),("Spinach",120,"veg_branch")]),
 "Chickpea Curry":("vegetarian","Indian",2,_tp(legumes=3,veg=2),[("Chickpeas",400,"shared"),("Coconut milk",300,"shared"),("Curry paste",40,"shared"),("Diced tomatoes",200,"shared"),("Yellow onion",120,"shared"),("Spinach",150,"shared"),("Naan",2,"shared")]),
 "Lentil Soup":("vegetarian","Mediterranean",2,_tp(legumes=3,veg=2),[("Lentils",300,"shared"),("Carrot",150,"shared"),("Yellow onion",120,"shared"),("Diced tomatoes",300,"shared"),("Garlic clove",3,"shared"),("Cumin",8,"shared"),("Spinach",100,"shared")]),
 "Pork Chops & Sweet Potato":("pork","American",2,_tp(pork=3,veg=1),[("Pork chop",400,"shared"),("Sweet potato",500,"shared"),("Olive oil",20,"shared"),("Paprika",8,"shared"),("Broccoli",200,"veg_branch")]),
 "Sausage & Peppers":("pork","Italian",2,_tp(pork=3,veg=2),[("Pork sausage",400,"shared"),("Bell pepper",250,"shared"),("Yellow onion",150,"shared"),("Hoagie roll",2,"shared"),("Garlic clove",2,"shared")]),
 "Turkey Chili":("beef","American",2,_tp(poultry=2,legumes=2,veg=1),[("Ground turkey",400,"shared"),("Black beans",300,"shared"),("Diced tomatoes",400,"shared"),("Yellow onion",120,"shared"),("Cumin",10,"shared"),("Bell pepper",150,"shared"),("Cheddar cheese",60,"shared")]),
 "Fajita Bowls":("chicken","Mexican",2,_tp(poultry=3,veg=2,legumes=1),[("Chicken breast",350,"shared"),("Bell pepper",200,"shared"),("Yellow onion",120,"shared"),("White rice",250,"shared"),("Black beans",200,"shared"),("Avocado",100,"veg_branch"),("Lime",1,"shared"),("Cumin",8,"shared")]),
 "Margherita Flatbread":("vegetarian","Italian",2,_tp(veg=1,pasta=1),[("Naan",2,"shared"),("Marinara sauce",150,"shared"),("Mozzarella",150,"shared"),("Tomato",120,"shared"),("Basil",15,"shared")]),
 "Greek Chicken Bowls":("chicken","Mediterranean",2,_tp(poultry=3,veg=2),[("Chicken breast",350,"shared"),("Couscous",200,"shared"),("Cucumber",150,"shared"),("Tomato",150,"shared"),("Feta",80,"shared"),("Olive oil",20,"shared"),("Lemon",1,"shared")]),
 "Salmon & Quinoa":("seafood","Mediterranean",2,_tp(seafood=3,veg=2),[("Salmon fillet",340,"shared"),("Quinoa",200,"shared"),("Spinach",120,"shared"),("Lemon",1,"shared"),("Olive oil",20,"shared"),("Garlic clove",2,"shared")]),
 "Veggie Stir Fry":("vegetarian","Asian",2,_tp(veg=3,legumes=1),[("Brown rice",280,"shared"),("Broccoli",200,"shared"),("Bell pepper",150,"shared"),("Carrot",120,"shared"),("Mushroom",150,"shared"),("Soy sauce",40,"shared"),("Ginger",15,"shared"),("Chickpeas",200,"legume_branch")]),
 "BBQ Chicken Pizza":("chicken","American",2,_tp(poultry=2,pasta=1),[("Naan",2,"shared"),("Chicken breast",250,"shared"),("Mozzarella",150,"shared"),("Bell pepper",100,"shared"),("Green onion",30,"shared")]),
 "Egg & Veggie Scramble":("vegetarian","American",2,_tp(veg=2),[("Egg",6,"shared"),("Spinach",100,"shared"),("Mushroom",120,"shared"),("Bell pepper",100,"shared"),("Cheddar cheese",60,"shared"),("Tomato",100,"shared")]),
 "Pesto Pasta":("pasta","Italian",2,_tp(pasta=3,poultry=1,veg=1),[("Penne",220,"shared"),("Pesto",80,"shared"),("Parmesan",50,"shared"),("Garlic clove",2,"shared"),("Chicken breast",250,"poultry_branch"),("Zucchini",180,"veg_branch")]),
 "Shrimp Tacos":("seafood","Mexican",2,_tp(seafood=3,veg=1),[("Shrimp",300,"shared"),("Corn tortilla",6,"shared"),("Cabbage",120,"shared"),("Avocado",100,"shared"),("Lime",1,"shared"),("Cilantro",15,"shared"),("Salsa",60,"shared")]),
 "Stuffed Bell Peppers":("beef","American",2,_tp(red_meat=2,veg=2),[("Bell pepper",4,"shared"),("Ground beef",300,"shared"),("White rice",150,"shared"),("Diced tomatoes",200,"shared"),("Cheddar cheese",80,"shared"),("Yellow onion",80,"shared")]),
 "Honey Garlic Chicken":("chicken","Asian",2,_tp(poultry=3,veg=1),[("Chicken thigh",400,"shared"),("Honey",40,"shared"),("Soy sauce",40,"shared"),("Garlic clove",4,"shared"),("White rice",280,"shared"),("Broccoli",200,"shared")]),
 "Mediterranean Chickpea Salad":("vegetarian","Mediterranean",2,_tp(legumes=3,veg=2),[("Chickpeas",300,"shared"),("Cucumber",150,"shared"),("Tomato",150,"shared"),("Feta",80,"shared"),("Olive oil",20,"shared"),("Lemon",1,"shared"),("Mixed greens",120,"shared")]),
 "Beef Stir Fry":("beef","Asian",2,_tp(red_meat=3,veg=2),[("Ground beef",350,"shared"),("Broccoli",200,"shared"),("Bell pepper",150,"shared"),("Soy sauce",40,"shared"),("Garlic clove",3,"shared"),("White rice",280,"shared"),("Ginger",15,"shared")]),
 "Caprese Chicken":("chicken","Italian",2,_tp(poultry=3,veg=1),[("Chicken breast",350,"shared"),("Mozzarella",120,"shared"),("Tomato",150,"shared"),("Basil",15,"shared"),("Olive oil",20,"shared"),("Couscous",180,"shared")]),
 "Loaded Nachos":("beef","Mexican",2,_tp(red_meat=2,legumes=1,veg=1),[("Tortilla chips",200,"shared"),("Ground beef",300,"shared"),("Cheddar cheese",150,"shared"),("Black beans",200,"shared"),("Salsa",80,"shared"),("Avocado",100,"veg_branch"),("Taco seasoning",20,"shared")]),
 "Baked Tilapia":("seafood","American",2,_tp(seafood=3,veg=1),[("Tilapia",360,"shared"),("Lemon",1,"shared"),("Olive oil",20,"shared"),("Garlic clove",2,"shared"),("Broccoli",200,"shared"),("Russet potato",300,"shared")]),
 "Tuna Pasta":("pasta","Mediterranean",2,_tp(seafood=2,pasta=3),[("Penne",220,"shared"),("Tuna",200,"shared"),("Olive oil",25,"shared"),("Garlic clove",2,"shared"),("Tomato",150,"shared"),("Parmesan",30,"shared")]),
 "Pork Fried Rice":("pork","Asian",2,_tp(pork=3,veg=1,pasta=1),[("Pork chop",300,"shared"),("White rice",300,"shared"),("Egg",2,"shared"),("Soy sauce",40,"shared"),("Carrot",100,"shared"),("Green onion",30,"shared"),("Garlic clove",3,"shared")]),
 "Black Bean Quesadillas":("vegetarian","Mexican",2,_tp(legumes=3,veg=1),[("Flour tortilla",4,"shared"),("Black beans",300,"shared"),("Cheddar cheese",150,"shared"),("Bell pepper",120,"shared"),("Salsa",60,"shared"),("Cumin",6,"shared")]),
 "Chicken Alfredo":("pasta","Italian",2,_tp(poultry=2,pasta=3),[("Penne",240,"shared"),("Chicken breast",300,"shared"),("Parmesan",80,"shared"),("Butter",40,"shared"),("Garlic clove",3,"shared"),("Broccoli",180,"veg_branch")]),
 "Kale & White Bean Stew":("vegetarian","Mediterranean",2,_tp(legumes=3,veg=3),[("Kidney beans",300,"shared"),("Kale",200,"shared"),("Diced tomatoes",300,"shared"),("Yellow onion",120,"shared"),("Garlic clove",3,"shared"),("Olive oil",20,"shared")]),
 "Turkey Meatballs":("chicken","Italian",2,_tp(poultry=3,pasta=2),[("Ground turkey",400,"shared"),("Spaghetti",200,"shared"),("Marinara sauce",300,"shared"),("Parmesan",40,"shared"),("Garlic clove",2,"shared"),("Zucchini",150,"veg_branch")]),
 "Falafel Pita":("vegetarian","Mediterranean",2,_tp(legumes=3,veg=2),[("Chickpeas",350,"shared"),("Pita bread",2,"shared"),("Cucumber",120,"shared"),("Tomato",120,"shared"),("Greek yogurt",80,"shared"),("Garlic clove",2,"shared")]),
 "Bacon Egg Hash":("pork","American",2,_tp(pork=3,veg=1),[("Bacon",120,"shared"),("Egg",4,"shared"),("Russet potato",400,"shared"),("Bell pepper",120,"shared"),("Yellow onion",80,"shared")]),
 "Salmon Poke Bowl":("seafood","Asian",2,_tp(seafood=3,veg=2,legumes=1),[("Salmon fillet",300,"shared"),("White rice",280,"shared"),("Avocado",120,"shared"),("Cucumber",120,"shared"),("Soy sauce",30,"shared"),("Green onion",30,"shared")]),
}


def connect():
    c = sqlite3.connect(DB_PATH); c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row; return c


def build(reset=False, seed_members=False):
    if reset and os.path.exists(DB_PATH): os.remove(DB_PATH)
    c = connect(); c.executescript(SCHEMA)
    c.executemany("INSERT OR REPLACE INTO aisle_order(aisle,sort_pos) VALUES(?,?)", AISLE_ORDER)
    c.executemany("INSERT OR IGNORE INTO stores(name,sort_pos) VALUES(?,?)", STORES)
    c.executemany("INSERT OR IGNORE INTO ingredients(name,aisle,calories_per_unit,unit_type,kind) VALUES(?,?,?,?,?)", INGREDIENTS)
    for rname,(cat,cz,serv,tp,items) in RECIPES.items():
        c.execute("INSERT OR IGNORE INTO recipes(name,category,cuisine,servings,type_profile) VALUES(?,?,?,?,?)",
                  (rname,cat,cz,serv,json.dumps(tp)))
        rid=c.execute("SELECT id FROM recipes WHERE name=?",(rname,)).fetchone()["id"]
        for iname,qty,branch in items:
            row=c.execute("SELECT id FROM ingredients WHERE name=?",(iname,)).fetchone()
            if not row:
                c.execute("INSERT INTO ingredients(name) VALUES(?)",(iname,))
                row=c.execute("SELECT id FROM ingredients WHERE name=?",(iname,)).fetchone()
            c.execute("INSERT OR REPLACE INTO recipe_ingredients(recipe_id,ingredient_id,quantity,branch) VALUES(?,?,?,?)",
                      (rid,row["id"],float(qty),branch))
    # settings default
    c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('onboarded','0')")
    if seed_members:
        c.execute("INSERT OR IGNORE INTO members(name,diet_label,prefs) VALUES(?,?,?)",
                  ("You","Meat-focused",json.dumps(DIET_PRESETS["Meat-focused"])))
        c.execute("INSERT OR IGNORE INTO members(name,diet_label,prefs) VALUES(?,?,?)",
                  ("Lizzy","Veggie-heavy",json.dumps(DIET_PRESETS["Veggie-heavy"])))
    c.commit()
    counts={t:c.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"] for t in ("members","recipes","ingredients","stores")}
    c.close(); return counts


if __name__=="__main__":
    counts=build(reset="--reset" in sys.argv, seed_members="--seed-members" in sys.argv)
    print(f"Database ready at {DB_PATH}")
    print("Seeded:", ", ".join(f"{k}={v}" for k,v in counts.items()))
