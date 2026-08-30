"""
db_setup.py — v4
Strips fake gram precision: recipes now store human amounts ("1 lb"), short
steps, a total-time bucket (quick flag), and per-serving calories are computed
live from USDA (cached in the recipes table once known).

Preference model redesigned: one clean scale per food type —
Never / Sometimes / Often / Love it (no nonsensical 'pork flavor-only').

Run:  python3 db_setup.py --reset
"""
import sqlite3, sys, os, json

DB_PATH = os.path.join(os.path.dirname(__file__), "mealplanner.db")

FOOD_TYPES = ["red_meat","poultry","pork","seafood","veg","legumes","pasta"]
# clean 4-level appetite scale, sensible for every type
PREF_LEVELS = ["never","sometimes","often","love"]
PREF_LABELS = {"never":"Never","sometimes":"Sometimes","often":"Often","love":"Love it"}

DIET_PRESETS = {
 "Omnivore":     {"red_meat":"often","poultry":"often","pork":"sometimes","seafood":"sometimes","veg":"often","legumes":"sometimes","pasta":"often"},
 "Meat-focused": {"red_meat":"love","poultry":"love","pork":"often","seafood":"sometimes","veg":"sometimes","legumes":"never","pasta":"often"},
 "Veggie-heavy": {"red_meat":"sometimes","poultry":"sometimes","pork":"never","seafood":"often","veg":"love","legumes":"love","pasta":"often"},
 "Pescatarian":  {"red_meat":"never","poultry":"never","pork":"never","seafood":"love","veg":"love","legumes":"often","pasta":"often"},
 "Vegetarian":   {"red_meat":"never","poultry":"never","pork":"never","seafood":"never","veg":"love","legumes":"love","pasta":"often"},
}

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
    diet_label TEXT DEFAULT 'Omnivore', prefs TEXT DEFAULT '{}', active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, sort_pos INTEGER NOT NULL DEFAULT 10);
CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
    aisle TEXT NOT NULL DEFAULT 'Pantry', kind TEXT NOT NULL DEFAULT 'food');
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
    category TEXT, cuisine TEXT DEFAULT 'American', servings INTEGER NOT NULL DEFAULT 2,
    minutes INTEGER DEFAULT 30, meal TEXT DEFAULT 'dinner', is_quick INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0,
    is_custom INTEGER DEFAULT 0, type_profile TEXT DEFAULT '{}',
    steps TEXT DEFAULT '', cal_per_serving INTEGER, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    amount TEXT DEFAULT '', branch TEXT NOT NULL DEFAULT 'shared',
    PRIMARY KEY (recipe_id, ingredient_id, branch));
CREATE TABLE IF NOT EXISTS aisle_order (aisle TEXT PRIMARY KEY, sort_pos INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS shopping_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
    aisle TEXT DEFAULT 'Other', store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
    kind TEXT NOT NULL DEFAULT 'food', added_by TEXT DEFAULT '',
    checked INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
    total REAL NOT NULL DEFAULT 0, visit_date TEXT DEFAULT (date('now')),
    photo_path TEXT DEFAULT '', added_by TEXT DEFAULT '', note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS receipt_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_id INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    name TEXT NOT NULL, qty REAL DEFAULT 1, price REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""

AISLE_ORDER=[("Produce",1),("Meat",2),("Seafood",3),("Dairy",4),("Bakery",5),
    ("Frozen",6),("Pantry",7),("Spices",8),("Canned",9),("Household",10),("Other",99)]
STORES=[("Aldi",1),("Publix",2),("Target",3),("Walmart",4)]

# name, aisle, kind   (no calorie columns — USDA provides that live)
INGREDIENTS=[
 ("Ground beef","Meat","food"),("Steak","Meat","food"),("Chicken thigh","Meat","food"),
 ("Chicken breast","Meat","food"),("Pork chop","Meat","food"),("Pork sausage","Meat","food"),
 ("Bacon","Meat","food"),("Ground turkey","Meat","food"),("Salmon fillet","Seafood","food"),
 ("Shrimp","Seafood","food"),("Tilapia","Seafood","food"),("Canned tuna","Canned","food"),
 ("White rice","Pantry","food"),("Brown rice","Pantry","food"),("Potatoes","Produce","food"),
 ("Sweet potato","Produce","food"),("Broccoli","Produce","food"),("Bell pepper","Produce","food"),
 ("Onion","Produce","food"),("Garlic","Produce","food"),("Carrot","Produce","food"),
 ("Zucchini","Produce","food"),("Spinach","Produce","food"),("Mixed greens","Produce","food"),
 ("Tomato","Produce","food"),("Cucumber","Produce","food"),("Avocado","Produce","food"),
 ("Lime","Produce","food"),("Cilantro","Produce","food"),("Mushroom","Produce","food"),
 ("Cabbage","Produce","food"),("Kale","Produce","food"),("Black beans","Canned","food"),
 ("Chickpeas","Canned","food"),("Lentils","Pantry","food"),("Kidney beans","Canned","food"),
 ("Diced tomatoes","Canned","food"),("Coconut milk","Canned","food"),("Cheddar cheese","Dairy","food"),
 ("Mozzarella","Dairy","food"),("Parmesan","Dairy","food"),("Butter","Dairy","food"),
 ("Greek yogurt","Dairy","food"),("Eggs","Dairy","food"),("Feta","Dairy","food"),
 ("Olive oil","Pantry","food"),("Soy sauce","Pantry","food"),("Pasta","Pantry","food"),
 ("Spaghetti","Pantry","food"),("Penne","Pantry","food"),("Marinara sauce","Pantry","food"),
 ("Tortilla chips","Pantry","food"),("Flour tortillas","Bakery","food"),("Corn tortillas","Bakery","food"),
 ("Naan","Bakery","food"),("Burger buns","Bakery","food"),("Hoagie rolls","Bakery","food"),
 ("Quinoa","Pantry","food"),("Couscous","Pantry","food"),("Curry paste","Pantry","food"),
 ("Taco seasoning","Spices","food"),("Cumin","Spices","food"),("Paprika","Spices","food"),
 ("Salsa","Pantry","food"),("Honey","Pantry","food"),("Lemon","Produce","food"),
 ("Ginger","Produce","food"),("Green onion","Produce","food"),("Basil","Produce","food"),
 ("Pesto","Pantry","food"),("Pita bread","Bakery","food"),
 ("Paper towels","Household","household"),("Dish soap","Household","household"),
 ("Laundry detergent","Household","household"),("Trash bags","Household","household"),
 ("Toilet paper","Household","household"),("Sponges","Household","household"),
 ("Aluminum foil","Household","household"),("Hand soap","Household","household"),
]

def _tp(**kw):
    b={t:0 for t in FOOD_TYPES}; b.update(kw); return b

# recipe -> dict(category,cuisine,servings,minutes,type_profile,steps,ingredients=[(name,amount,branch)])
def R(category,cuisine,servings,minutes,tp,steps,ings,meal="dinner"):
    return {"category":category,"cuisine":cuisine,"servings":servings,"minutes":minutes,
            "type_profile":tp,"steps":steps,"ings":ings,"meal":meal}

RECIPES = {
 "Beef & Potato Skillet": R("beef","American",2,25,_tp(red_meat=3,veg=1),
   "Brown the beef with diced onion. Add cubed potato and a splash of water, cover and cook until tender. Season and serve.",
   [("Ground beef","1 lb","shared"),("Potatoes","2 medium","shared"),("Onion","1","shared"),("Butter","2 tbsp","shared"),("Broccoli","1 head","veg_branch")]),
 "Classic Beef Tacos": R("beef","Mexican",2,20,_tp(red_meat=3,veg=1),
   "Brown beef, stir in taco seasoning with a little water. Warm tortillas. Fill and top with cheese, greens, tomato, salsa.",
   [("Ground beef","1 lb","shared"),("Taco seasoning","1 packet","shared"),("Corn tortillas","6","shared"),("Cheddar cheese","1 cup","You_branch"),("Mixed greens","2 cups","veg_branch"),("Tomato","1","shared"),("Salsa","1/2 cup","shared")]),
 "Spaghetti & Meat Sauce": R("pasta","Italian",2,30,_tp(red_meat=2,pasta=3,veg=1),
   "Boil spaghetti. Brown beef with garlic, add marinara and simmer. Toss and top with parmesan.",
   [("Spaghetti","8 oz","shared"),("Marinara sauce","2 cups","shared"),("Ground beef","3/4 lb","shared"),("Garlic","2 cloves","shared"),("Parmesan","1/4 cup","You_branch"),("Zucchini","1","veg_branch")]),
 "Loaded Baked Potato": R("potato","American",2,45,_tp(pork=1,veg=1),
   "Bake potatoes until soft. Split, add butter and cheese. Top with bacon or steamed broccoli as desired.",
   [("Potatoes","2 large","shared"),("Butter","3 tbsp","shared"),("Cheddar cheese","1 cup","shared"),("Bacon","4 strips","pork_branch"),("Broccoli","1 head","veg_branch"),("Greek yogurt","1/4 cup","shared")]),
 "Chicken Fried Rice": R("chicken","Asian",2,20,_tp(poultry=3,veg=1,pasta=1),
   "Cook rice ahead. Scramble egg, set aside. Stir-fry chicken and garlic, add rice, soy sauce, egg and green onion.",
   [("Chicken thigh","3/4 lb","shared"),("White rice","2 cups cooked","shared"),("Soy sauce","3 tbsp","shared"),("Eggs","2","shared"),("Garlic","3 cloves","shared"),("Bell pepper","1","veg_branch"),("Green onion","2","shared")]),
 "Teriyaki Salmon Bowl": R("seafood","Asian",2,25,_tp(seafood=3,veg=2),
   "Roast salmon glazed with soy and honey. Serve over rice with steamed broccoli.",
   [("Salmon fillet","2 fillets","shared"),("Brown rice","1.5 cups cooked","shared"),("Soy sauce","3 tbsp","shared"),("Honey","1 tbsp","shared"),("Broccoli","1 head","shared"),("Green onion","2","shared")]),
 "Shrimp Stir Fry": R("seafood","Asian",2,20,_tp(seafood=3,veg=2),
   "Stir-fry shrimp with garlic and ginger. Add peppers and carrot, then soy sauce. Serve over rice.",
   [("Shrimp","3/4 lb","shared"),("White rice","1.5 cups cooked","shared"),("Soy sauce","3 tbsp","shared"),("Bell pepper","1","shared"),("Carrot","2","shared"),("Ginger","1 tbsp","shared"),("Garlic","3 cloves","shared")]),
 "Chicken Parmesan": R("chicken","Italian",2,35,_tp(poultry=3,pasta=2),
   "Bread and pan-fry chicken. Top with marinara and mozzarella, bake until melted. Serve with pasta.",
   [("Chicken breast","2","shared"),("Marinara sauce","1.5 cups","shared"),("Mozzarella","1 cup","shared"),("Parmesan","1/4 cup","shared"),("Pasta","6 oz","shared"),("Basil","a few leaves","shared")]),
 "Beef Burgers": R("beef","American",2,20,_tp(red_meat=3,veg=1),
   "Form and grill patties. Toast buns. Assemble with cheese and toppings.",
   [("Ground beef","1 lb","shared"),("Burger buns","2","shared"),("Cheddar cheese","2 slices","You_branch"),("Mixed greens","1 cup","shared"),("Tomato","1","shared"),("Onion","1/2","shared")]),
 "Chicken Curry": R("chicken","Indian",2,35,_tp(poultry=3,veg=1),
   "Saute onion, garlic, ginger. Add curry paste and coconut milk, simmer chicken until cooked. Serve with naan.",
   [("Chicken thigh","3/4 lb","shared"),("Coconut milk","1 can","shared"),("Curry paste","2 tbsp","shared"),("Onion","1","shared"),("Garlic","3 cloves","shared"),("Ginger","1 tbsp","shared"),("Naan","2","shared"),("Spinach","2 cups","veg_branch")]),
 "Chickpea Curry": R("vegetarian","Indian",2,25,_tp(legumes=3,veg=2),
   "Saute onion, add curry paste, coconut milk, tomatoes and chickpeas. Simmer, wilt in spinach. Serve with naan.",
   [("Chickpeas","2 cans","shared"),("Coconut milk","1 can","shared"),("Curry paste","2 tbsp","shared"),("Diced tomatoes","1 can","shared"),("Onion","1","shared"),("Spinach","2 cups","shared"),("Naan","2","shared")]),
 "Lentil Soup": R("vegetarian","Mediterranean",2,35,_tp(legumes=3,veg=2),
   "Saute onion, carrot, garlic. Add lentils, tomatoes, cumin and water. Simmer until tender, stir in spinach.",
   [("Lentils","1 cup","shared"),("Carrot","2","shared"),("Onion","1","shared"),("Diced tomatoes","1 can","shared"),("Garlic","3 cloves","shared"),("Cumin","1 tsp","shared"),("Spinach","1 cup","shared")]),
 "Pork Chops & Sweet Potato": R("pork","American",2,30,_tp(pork=3,veg=1),
   "Sear seasoned pork chops. Roast sweet potato wedges. Add a green side as desired.",
   [("Pork chop","2","shared"),("Sweet potato","2","shared"),("Olive oil","2 tbsp","shared"),("Paprika","1 tsp","shared"),("Broccoli","1 head","veg_branch")]),
 "Sausage & Peppers": R("pork","Italian",2,25,_tp(pork=3,veg=2),
   "Brown sausage. Saute peppers and onion with garlic. Combine; serve on rolls.",
   [("Pork sausage","1 lb","shared"),("Bell pepper","2","shared"),("Onion","1","shared"),("Hoagie rolls","2","shared"),("Garlic","2 cloves","shared")]),
 "Turkey Chili": R("beef","American",2,40,_tp(poultry=2,legumes=2,veg=1),
   "Brown turkey with onion. Add beans, tomatoes, pepper and cumin. Simmer 25 min.",
   [("Ground turkey","1 lb","shared"),("Black beans","1 can","shared"),("Diced tomatoes","1 can","shared"),("Onion","1","shared"),("Cumin","1 tbsp","shared"),("Bell pepper","1","shared"),("Cheddar cheese","1/2 cup","You_branch")]),
 "Fajita Bowls": R("chicken","Mexican",2,25,_tp(poultry=3,veg=2,legumes=1),
   "Saute sliced chicken with peppers and onion and cumin. Serve over rice with beans, avocado, lime.",
   [("Chicken breast","3/4 lb","shared"),("Bell pepper","2","shared"),("Onion","1","shared"),("White rice","1.5 cups cooked","shared"),("Black beans","1 can","shared"),("Avocado","1","veg_branch"),("Lime","1","shared"),("Cumin","1 tsp","shared")]),
 "Margherita Flatbread": R("vegetarian","Italian",2,15,_tp(veg=1,pasta=1),
   "Spread sauce on naan, add mozzarella and tomato. Bake until bubbly, top with basil.",
   [("Naan","2","shared"),("Marinara sauce","1/2 cup","shared"),("Mozzarella","1 cup","shared"),("Tomato","1","shared"),("Basil","a few leaves","shared")]),
 "Greek Chicken Bowls": R("chicken","Mediterranean",2,25,_tp(poultry=3,veg=2),
   "Cook seasoned chicken. Fluff couscous. Bowl with cucumber, tomato, feta, olive oil, lemon.",
   [("Chicken breast","3/4 lb","shared"),("Couscous","1 cup","shared"),("Cucumber","1","shared"),("Tomato","1","shared"),("Feta","1/2 cup","shared"),("Olive oil","2 tbsp","shared"),("Lemon","1","shared")]),
 "Salmon & Quinoa": R("seafood","Mediterranean",2,25,_tp(seafood=3,veg=2),
   "Roast salmon. Cook quinoa. Wilt spinach with garlic. Plate with lemon and olive oil.",
   [("Salmon fillet","2 fillets","shared"),("Quinoa","1 cup","shared"),("Spinach","2 cups","shared"),("Lemon","1","shared"),("Olive oil","2 tbsp","shared"),("Garlic","2 cloves","shared")]),
 "Veggie Stir Fry": R("vegetarian","Asian",2,20,_tp(veg=3,legumes=1),
   "Stir-fry mixed veg with ginger and garlic, add soy sauce. Serve over rice; add chickpeas for protein.",
   [("Brown rice","1.5 cups cooked","shared"),("Broccoli","1 head","shared"),("Bell pepper","1","shared"),("Carrot","2","shared"),("Mushroom","1 cup","shared"),("Soy sauce","3 tbsp","shared"),("Ginger","1 tbsp","shared"),("Chickpeas","1 can","legume_branch")]),
 "BBQ Chicken Pizza": R("chicken","American",2,20,_tp(poultry=2,pasta=1),
   "Top naan with sauce, chicken, mozzarella, peppers. Bake until melted; add green onion.",
   [("Naan","2","shared"),("Chicken breast","1/2 lb","shared"),("Mozzarella","1 cup","shared"),("Bell pepper","1","shared"),("Green onion","2","shared")]),
 "Egg & Veggie Scramble": R("vegetarian","American",2,15,_tp(veg=2),
   "Scramble eggs with spinach, mushroom, pepper and tomato. Finish with cheese.",
   [("Eggs","6","shared"),("Spinach","1 cup","shared"),("Mushroom","1 cup","shared"),("Bell pepper","1","shared"),("Cheddar cheese","1/2 cup","You_branch"),("Tomato","1","shared")]),
 "Pesto Pasta": R("pasta","Italian",2,20,_tp(pasta=3,poultry=1,veg=1),
   "Boil penne. Toss with pesto and parmesan. Add cooked chicken or roasted zucchini as desired.",
   [("Penne","8 oz","shared"),("Pesto","1/3 cup","shared"),("Parmesan","1/4 cup","shared"),("Garlic","2 cloves","shared"),("Chicken breast","1/2 lb","You_branch"),("Zucchini","1","veg_branch")]),
 "Shrimp Tacos": R("seafood","Mexican",2,20,_tp(seafood=3,veg=1),
   "Saute shrimp. Warm tortillas. Fill with cabbage, avocado, cilantro, lime, salsa.",
   [("Shrimp","3/4 lb","shared"),("Corn tortillas","6","shared"),("Cabbage","2 cups","shared"),("Avocado","1","shared"),("Lime","1","shared"),("Cilantro","handful","shared"),("Salsa","1/2 cup","shared")]),
 "Stuffed Bell Peppers": R("beef","American",2,45,_tp(red_meat=2,veg=2),
   "Brown beef with onion, mix with rice and tomatoes. Stuff peppers, top with cheese, bake 30 min.",
   [("Bell pepper","4","shared"),("Ground beef","3/4 lb","shared"),("White rice","1 cup cooked","shared"),("Diced tomatoes","1 can","shared"),("Cheddar cheese","3/4 cup","shared"),("Onion","1","shared")]),
 "Honey Garlic Chicken": R("chicken","Asian",2,25,_tp(poultry=3,veg=1),
   "Sear chicken thighs. Add honey, soy, garlic; simmer to glaze. Serve with rice and broccoli.",
   [("Chicken thigh","1 lb","shared"),("Honey","3 tbsp","shared"),("Soy sauce","3 tbsp","shared"),("Garlic","4 cloves","shared"),("White rice","1.5 cups cooked","shared"),("Broccoli","1 head","shared")]),
 "Mediterranean Chickpea Salad": R("vegetarian","Mediterranean",2,15,_tp(legumes=3,veg=2),
   "Toss chickpeas with cucumber, tomato, feta, greens, olive oil and lemon. No cooking.",
   [("Chickpeas","1 can","shared"),("Cucumber","1","shared"),("Tomato","1","shared"),("Feta","1/2 cup","shared"),("Olive oil","2 tbsp","shared"),("Lemon","1","shared"),("Mixed greens","2 cups","shared")]),
 "Beef Stir Fry": R("beef","Asian",2,20,_tp(red_meat=3,veg=2),
   "Stir-fry beef with garlic and ginger. Add broccoli and peppers, then soy sauce. Serve over rice.",
   [("Ground beef","3/4 lb","shared"),("Broccoli","1 head","shared"),("Bell pepper","1","shared"),("Soy sauce","3 tbsp","shared"),("Garlic","3 cloves","shared"),("White rice","1.5 cups cooked","shared"),("Ginger","1 tbsp","shared")]),
 "Caprese Chicken": R("chicken","Italian",2,25,_tp(poultry=3,veg=1),
   "Cook chicken, top with mozzarella and tomato, melt. Finish with basil and olive oil; serve with couscous.",
   [("Chicken breast","3/4 lb","shared"),("Mozzarella","1 cup","shared"),("Tomato","1","shared"),("Basil","a few leaves","shared"),("Olive oil","1 tbsp","shared"),("Couscous","3/4 cup","shared")]),
 "Loaded Nachos": R("beef","Mexican",2,20,_tp(red_meat=2,legumes=1,veg=1),
   "Brown beef with seasoning. Layer chips, beef, cheese, beans. Bake to melt; top with salsa and avocado.",
   [("Tortilla chips","1 bag","shared"),("Ground beef","3/4 lb","shared"),("Cheddar cheese","1.5 cups","shared"),("Black beans","1 can","shared"),("Salsa","3/4 cup","shared"),("Avocado","1","veg_branch"),("Taco seasoning","1 packet","shared")]),
 "Baked Tilapia": R("seafood","American",2,25,_tp(seafood=3,veg=1),
   "Bake tilapia with lemon, garlic, olive oil. Roast potatoes and steam broccoli.",
   [("Tilapia","2 fillets","shared"),("Lemon","1","shared"),("Olive oil","2 tbsp","shared"),("Garlic","2 cloves","shared"),("Broccoli","1 head","shared"),("Potatoes","2 medium","shared")]),
 "Tuna Pasta": R("pasta","Mediterranean",2,20,_tp(seafood=2,pasta=3),
   "Boil penne. Toss with tuna, olive oil, garlic, tomato and parmesan.",
   [("Penne","8 oz","shared"),("Canned tuna","2 cans","shared"),("Olive oil","2 tbsp","shared"),("Garlic","2 cloves","shared"),("Tomato","1","shared"),("Parmesan","2 tbsp","shared")]),
 "Black Bean Quesadillas": R("vegetarian","Mexican",2,15,_tp(legumes=3,veg=1),
   "Mash beans with cumin. Fill tortillas with beans, cheese, peppers. Griddle until crisp; serve with salsa.",
   [("Flour tortillas","4","shared"),("Black beans","1 can","shared"),("Cheddar cheese","1.5 cups","shared"),("Bell pepper","1","shared"),("Salsa","1/2 cup","shared"),("Cumin","1 tsp","shared")]),
 "Chicken Alfredo": R("pasta","Italian",2,30,_tp(poultry=2,pasta=3),
   "Boil penne. Cook chicken. Make a quick parmesan-butter sauce, toss all; add broccoli as desired.",
   [("Penne","8 oz","shared"),("Chicken breast","3/4 lb","shared"),("Parmesan","3/4 cup","shared"),("Butter","3 tbsp","shared"),("Garlic","3 cloves","shared"),("Broccoli","1 head","veg_branch")]),
 "Kale & White Bean Stew": R("vegetarian","Mediterranean",2,30,_tp(legumes=3,veg=3),
   "Saute onion and garlic. Add beans, tomatoes and water, simmer. Stir in kale until wilted.",
   [("Kidney beans","2 cans","shared"),("Kale","4 cups","shared"),("Diced tomatoes","1 can","shared"),("Onion","1","shared"),("Garlic","3 cloves","shared"),("Olive oil","2 tbsp","shared")]),
 "Turkey Meatballs": R("chicken","Italian",2,35,_tp(poultry=3,pasta=2),
   "Form and bake turkey meatballs. Simmer in marinara. Serve over spaghetti with parmesan.",
   [("Ground turkey","1 lb","shared"),("Spaghetti","6 oz","shared"),("Marinara sauce","1.5 cups","shared"),("Parmesan","1/4 cup","shared"),("Garlic","2 cloves","shared"),("Zucchini","1","veg_branch")]),
 "Falafel Pita": R("vegetarian","Mediterranean",2,25,_tp(legumes=3,veg=2),
   "Blend and pan-fry chickpea patties. Stuff pita with falafel, cucumber, tomato, yogurt.",
   [("Chickpeas","1.5 cans","shared"),("Pita bread","2","shared"),("Cucumber","1","shared"),("Tomato","1","shared"),("Greek yogurt","1/3 cup","shared"),("Garlic","2 cloves","shared")]),
 "Bacon Egg Hash": R("pork","American",2,20,_tp(pork=3,veg=1),
   "Crisp bacon. Cook diced potato in the fat with pepper and onion. Fry eggs on top.",
   [("Bacon","6 strips","shared"),("Eggs","4","shared"),("Potatoes","2 medium","shared"),("Bell pepper","1","shared"),("Onion","1/2","shared")]),
 "Salmon Poke Bowl": R("seafood","Asian",2,15,_tp(seafood=3,veg=2,legumes=1),
   "Cube cooked salmon. Bowl over rice with avocado, cucumber, soy sauce and green onion. No cooking beyond the fish.",
   [("Salmon fillet","2 fillets","shared"),("White rice","1.5 cups cooked","shared"),("Avocado","1","shared"),("Cucumber","1","shared"),("Soy sauce","3 tbsp","shared"),("Green onion","2","shared")]),

 # ---------- BREAKFASTS ----------
 "Classic Oatmeal": R("breakfast","American",1,10,_tp(),
   "Simmer oats in milk or water. Top with banana, blueberries, a drizzle of honey.",
   [("Oats","1/2 cup","shared"),("Milk","1 cup","shared"),("Banana","1","shared"),("Blueberries","1/4 cup","shared"),("Honey","1 tsp","shared")], meal="breakfast"),
 "Scrambled Eggs & Toast": R("breakfast","American",1,10,_tp(),
   "Scramble eggs in butter. Toast bread. Serve with a side of fruit.",
   [("Eggs","3","shared"),("Butter","1 tbsp","shared"),("Bread","2 slices","shared")], meal="breakfast"),
 "Greek Yogurt Bowl": R("breakfast","Mediterranean",1,5,_tp(),
   "Layer yogurt with granola, strawberries and honey. No cooking.",
   [("Greek yogurt","1 cup","shared"),("Granola","1/3 cup","shared"),("Strawberries","1/2 cup","shared"),("Honey","1 tsp","shared")], meal="breakfast"),
 "Peanut Butter Banana Toast": R("breakfast","American",1,5,_tp(),
   "Toast bread, spread peanut butter, top with banana slices.",
   [("Bread","2 slices","shared"),("Peanut butter","2 tbsp","shared"),("Banana","1","shared")], meal="breakfast"),
 "Sausage Egg Bagel": R("breakfast","American",1,15,_tp(pork=2),
   "Cook sausage and egg. Stack on a toasted bagel with cheese.",
   [("Bagel","1","shared"),("Sausage links","2","shared"),("Eggs","1","shared"),("Cheddar cheese","1 slice","shared")], meal="breakfast"),
 "Pancakes": R("breakfast","American",2,20,_tp(pasta=1),
   "Mix and griddle pancakes. Serve with syrup and fruit.",
   [("Pancake mix","1 cup","shared"),("Milk","3/4 cup","shared"),("Eggs","1","shared"),("Maple syrup","2 tbsp","shared"),("Blueberries","1/2 cup","shared")], meal="breakfast"),
 "Veggie Omelette": R("breakfast","American",1,15,_tp(veg=2),
   "Whisk eggs, pour into pan, fill with peppers, spinach, mushroom and cheese. Fold.",
   [("Eggs","3","shared"),("Bell pepper","1/2","shared"),("Spinach","1/2 cup","shared"),("Mushroom","1/4 cup","shared"),("Cheddar cheese","1/4 cup","shared")], meal="breakfast"),
 "Breakfast Burrito": R("breakfast","Mexican",1,15,_tp(veg=1),
   "Scramble eggs with pepper and onion. Wrap in a tortilla with cheese and salsa.",
   [("Eggs","2","shared"),("Flour tortillas","1","shared"),("Bell pepper","1/2","shared"),("Onion","1/4","shared"),("Cheddar cheese","1/4 cup","shared"),("Salsa","2 tbsp","shared")], meal="breakfast"),
 "Avocado Toast": R("breakfast","American",1,10,_tp(veg=1),
   "Toast bread, mash avocado on top, add egg and a squeeze of lemon.",
   [("Bread","2 slices","shared"),("Avocado","1","shared"),("Eggs","1","shared"),("Lemon","1/4","shared")], meal="breakfast"),
 "Yogurt & Cereal": R("breakfast","American",1,5,_tp(),
   "Bowl cereal with milk; side of yogurt and fruit. Fastest breakfast there is.",
   [("Honey nut cereal","1 cup","shared"),("Milk","1 cup","shared"),("Banana","1","shared")], meal="breakfast"),
 "Cottage Cheese & Fruit": R("breakfast","American",1,5,_tp(),
   "Scoop cottage cheese, top with berries and a drizzle of honey.",
   [("Cottage cheese","1 cup","shared"),("Blueberries","1/2 cup","shared"),("Honey","1 tsp","shared")], meal="breakfast"),
 "Ham & Cheese English Muffin": R("breakfast","American",1,10,_tp(pork=2),
   "Toast an english muffin, layer ham, egg and cheese.",
   [("English muffin","1","shared"),("Ham","2 slices","shared"),("Eggs","1","shared"),("Cheddar cheese","1 slice","shared")], meal="breakfast"),

 # ---------- LUNCHES ----------
 "Turkey Sandwich": R("lunch","American",1,10,_tp(poultry=2),
   "Layer turkey, provolone, greens and tomato on bread with mustard.",
   [("Bread","2 slices","shared"),("Deli turkey","4 slices","shared"),("Provolone","1 slice","shared"),("Mixed greens","1/2 cup","shared"),("Tomato","2 slices","shared"),("Mustard","1 tsp","shared")], meal="lunch"),
 "Chicken Caesar Salad": R("lunch","American",1,15,_tp(poultry=3,veg=2),
   "Toss romaine with caesar dressing, grilled chicken, parmesan and croutons.",
   [("Chicken breast","1/2 lb","shared"),("Mixed greens","2 cups","shared"),("Caesar dressing","2 tbsp","shared"),("Parmesan","2 tbsp","shared"),("Croutons","1/4 cup","shared")], meal="lunch"),
 "Hummus Veggie Wrap": R("lunch","Mediterranean",1,10,_tp(legumes=2,veg=3),
   "Spread hummus on a tortilla, fill with cucumber, pepper, greens. Roll and slice.",
   [("Flour tortillas","1","shared"),("Hummus","1/4 cup","shared"),("Cucumber","1/2","shared"),("Bell pepper","1/2","shared"),("Mixed greens","1 cup","shared")], meal="lunch"),
 "Italian Sub": R("lunch","Italian",1,10,_tp(pork=2),
   "Layer salami, ham, provolone, greens and tomato on a hoagie roll.",
   [("Hoagie rolls","1","shared"),("Salami","4 slices","shared"),("Ham","3 slices","shared"),("Provolone","2 slices","shared"),("Mixed greens","1/2 cup","shared"),("Tomato","2 slices","shared")], meal="lunch"),
 "Leftover Rice Bowl": R("lunch","Asian",1,10,_tp(veg=2),
   "Reheat rice, top with a fried egg, veg and soy sauce. Uses up leftovers.",
   [("White rice","1 cup cooked","shared"),("Eggs","1","shared"),("Broccoli","1/2 cup","shared"),("Soy sauce","1 tbsp","shared"),("Green onion","1","shared")], meal="lunch"),
 "Caprese Sandwich": R("lunch","Italian",1,10,_tp(veg=1),
   "Layer mozzarella, tomato and basil on bread with olive oil.",
   [("Bread","2 slices","shared"),("Mozzarella","3 slices","shared"),("Tomato","3 slices","shared"),("Basil","a few leaves","shared"),("Olive oil","1 tsp","shared")], meal="lunch"),
 "Tuna Salad": R("lunch","American",1,10,_tp(seafood=3),
   "Mix tuna with mayo, serve on greens or bread.",
   [("Canned tuna","1 can","shared"),("Mayonnaise","2 tbsp","shared"),("Mixed greens","1 cup","shared"),("Bread","2 slices","shared")], meal="lunch"),
 "Quesadilla": R("lunch","Mexican",1,10,_tp(veg=1),
   "Fill a tortilla with cheese and pepper, griddle until crisp. Serve with salsa.",
   [("Flour tortillas","2","shared"),("Cheddar cheese","3/4 cup","shared"),("Bell pepper","1/2","shared"),("Salsa","2 tbsp","shared")], meal="lunch"),
 "Chickpea Salad Bowl": R("lunch","Mediterranean",1,10,_tp(legumes=3,veg=2),
   "Toss chickpeas with cucumber, tomato, feta and lemon. No cooking.",
   [("Chickpeas","1 can","shared"),("Cucumber","1/2","shared"),("Tomato","1","shared"),("Feta","1/4 cup","shared"),("Lemon","1/2","shared"),("Olive oil","1 tbsp","shared")], meal="lunch"),
 "Grilled Cheese & Soup": R("lunch","American",1,15,_tp(veg=1),
   "Griddle a cheese sandwich in butter. Serve with a bowl of tomato soup.",
   [("Bread","2 slices","shared"),("Cheddar cheese","2 slices","shared"),("Butter","1 tbsp","shared"),("Diced tomatoes","1 cup","shared")], meal="lunch"),
 "BLT": R("lunch","American",1,15,_tp(pork=2,veg=1),
   "Crisp bacon, stack with lettuce and tomato on toast with mayo.",
   [("Bread","2 slices","shared"),("Bacon","3 strips","shared"),("Mixed greens","1/2 cup","shared"),("Tomato","2 slices","shared"),("Mayonnaise","1 tbsp","shared")], meal="lunch"),
 "Chicken Salad Croissant": R("lunch","American",1,10,_tp(poultry=3),
   "Mix diced chicken with mayo, serve on a croissant with greens.",
   [("Chicken breast","1/2 lb","shared"),("Mayonnaise","2 tbsp","shared"),("Croissant","1","shared"),("Mixed greens","1/2 cup","shared")], meal="lunch"),
}


def connect():
    c=sqlite3.connect(DB_PATH); c.execute("PRAGMA foreign_keys=ON"); c.row_factory=sqlite3.Row; return c

def build(reset=False, seed_members=False):
    if reset and os.path.exists(DB_PATH): os.remove(DB_PATH)
    c=connect(); c.executescript(SCHEMA)
    c.executemany("INSERT OR REPLACE INTO aisle_order(aisle,sort_pos) VALUES(?,?)",AISLE_ORDER)
    c.executemany("INSERT OR IGNORE INTO stores(name,sort_pos) VALUES(?,?)",STORES)
    c.executemany("INSERT OR IGNORE INTO ingredients(name,aisle,kind) VALUES(?,?,?)",INGREDIENTS)
    for nm,r in RECIPES.items():
        quick=1 if r["minutes"]<=20 else 0
        c.execute("""INSERT OR IGNORE INTO recipes(name,category,cuisine,servings,minutes,meal,is_quick,type_profile,steps)
                     VALUES(?,?,?,?,?,?,?,?,?)""",
                  (nm,r["category"],r["cuisine"],r["servings"],r["minutes"],r.get("meal","dinner"),quick,json.dumps(r["type_profile"]),r["steps"]))
        rid=c.execute("SELECT id FROM recipes WHERE name=?",(nm,)).fetchone()["id"]
        for iname,amount,branch in r["ings"]:
            row=c.execute("SELECT id FROM ingredients WHERE name=?",(iname,)).fetchone()
            if not row:
                c.execute("INSERT INTO ingredients(name) VALUES(?)",(iname,))
                row=c.execute("SELECT id FROM ingredients WHERE name=?",(iname,)).fetchone()
            c.execute("INSERT OR REPLACE INTO recipe_ingredients(recipe_id,ingredient_id,amount,branch) VALUES(?,?,?,?)",
                      (rid,row["id"],amount,branch))
    c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('onboarded','0')")
    if seed_members:
        c.execute("INSERT OR IGNORE INTO members(name,diet_label,prefs) VALUES(?,?,?)",("You","Meat-focused",json.dumps(DIET_PRESETS["Meat-focused"])))
        c.execute("INSERT OR IGNORE INTO members(name,diet_label,prefs) VALUES(?,?,?)",("Lizzy","Veggie-heavy",json.dumps(DIET_PRESETS["Veggie-heavy"])))
    c.commit()
    counts={t:c.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"] for t in ("members","recipes","ingredients","stores")}
    c.close(); return counts

if __name__=="__main__":
    counts=build(reset="--reset" in sys.argv, seed_members="--seed-members" in sys.argv)
    print(f"Database ready at {DB_PATH}")
    print("Seeded:", ", ".join(f"{k}={v}" for k,v in counts.items()))
