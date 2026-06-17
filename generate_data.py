"""
generate_data.py
----------------
Creates 4 synthetic CSVs for the FMCG beverages assistant:
  products.csv, stores.csv, sales.csv, inventory.csv

Also loads all 4 into a local SQLite file (beverages.db) for offline use.
To push to Supabase PostgreSQL (cloud), run push_to_supabase.py after this.

Design decisions:
- Promo weeks have an explicit units_sold UPLIFT so the AI has real signal to detect.
- Inventory is derived from sales so the two tables are internally consistent.
- Random seed is fixed (42) so results are reproducible every run.
"""

import csv
import random
import sqlite3
import os
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

# ─────────────────────────────────────────────
# 0. OUTPUT FOLDER
# ─────────────────────────────────────────────
# All files land in the same folder as this script.
OUT = Path(__file__).parent
DB_PATH = OUT / "beverages.db"

# ─────────────────────────────────────────────
# 1. PRODUCT MASTER  (15 beverages, 5 categories)
# ─────────────────────────────────────────────
# WHY: The agent needs a reference table to resolve names like
# "Spark Cola" to a product_id and look up the unit price.

PRODUCTS = [
    # (product_id, product_name, brand, category, sub_category, pack_size_ml, unit_price)
    ("BEV-001", "Spark Cola 500ml",          "Spark",   "Carbonated",  "Cola",            500,  1.20),
    ("BEV-002", "Spark Cola 1L",             "Spark",   "Carbonated",  "Cola",           1000,  2.10),
    ("BEV-003", "Spark Lemon Fizz 500ml",    "Spark",   "Carbonated",  "Sparkling Water", 500,  1.30),
    ("BEV-004", "ZestUp Orange Juice 1L",    "ZestUp",  "Juice",       "Fruit Juice",    1000,  2.50),
    ("BEV-005", "ZestUp Apple Juice 250ml",  "ZestUp",  "Juice",       "Fruit Juice",     250,  0.99),
    ("BEV-006", "PureFlow Still Water 500ml","PureFlow","Water",       "Still Water",     500,  0.75),
    ("BEV-007", "PureFlow Still Water 1.5L", "PureFlow","Water",       "Still Water",    1500,  1.40),
    ("BEV-008", "BlastEnergy Original 250ml","Blast",   "Energy",      "Energy Drink",    250,  1.80),
    ("BEV-009", "BlastEnergy Zero 250ml",    "Blast",   "Energy",      "Energy Drink",    250,  1.80),
    ("BEV-010", "BlastEnergy Citrus 500ml",  "Blast",   "Energy",      "Energy Drink",    500,  2.20),
    ("BEV-011", "MilkMate Full Fat 1L",      "MilkMate","Dairy",       "Flavoured Milk", 1000,  1.60),
    ("BEV-012", "MilkMate Choc 500ml",       "MilkMate","Dairy",       "Flavoured Milk",  500,  1.10),
    ("BEV-013", "ZestUp Mango Juice 1L",     "ZestUp",  "Juice",       "Fruit Juice",    1000,  2.60),
    ("BEV-014", "Spark Tonic Water 330ml",   "Spark",   "Carbonated",  "Tonic",           330,  1.00),
    ("BEV-015", "PureFlow Sparkling 750ml",  "PureFlow","Water",       "Sparkling Water", 750,  1.50),
]

PRODUCT_IDS  = [p[0] for p in PRODUCTS]
PRODUCT_DICT = {p[0]: p for p in PRODUCTS}   # quick lookup by id

# ─────────────────────────────────────────────
# 2. STORE MASTER  (30 stores, 4 regions)
# ─────────────────────────────────────────────
# WHY: Region filtering is one of the core question types.
# I spread stores evenly across North/South/East/West so comparisons are fair.

REGIONS_CITIES = {
    "North": ["Manchester", "Leeds", "Liverpool", "Sheffield"],
    "South": ["London",     "Brighton","Southampton","Oxford"],
    "East":  ["Norwich",    "Cambridge","Ipswich",   "Peterborough"],
    "West":  ["Bristol",    "Cardiff", "Plymouth",  "Exeter"],
}

FORMATS = ["Supermarket", "Hypermarket", "Convenience", "Wholesale"]

def make_stores():
    stores = []
    store_num = 1
    for region, cities in REGIONS_CITIES.items():
        for i in range(7 if region in ("North","South") else 8):
            city   = cities[i % len(cities)]
            fmt    = FORMATS[i % len(FORMATS)]
            store_id   = f"STR-{store_num:03d}"
            store_name = f"{city} {fmt} {((i // len(cities)) + 1)}"
            stores.append((store_id, store_name, region, city, fmt))
            store_num += 1
    return stores

STORES     = make_stores()
STORE_IDS  = [s[0] for s in STORES]
STORE_DICT = {s[0]: s for s in STORES}

# ─────────────────────────────────────────────
# 3. DATE RANGE  (16 weeks)
# ─────────────────────────────────────────────
# WHY: 16 weeks gives enough history to spot trends vs. one-off spikes.

START_DATE = date(2024, 1, 1)
WEEKS = [START_DATE + timedelta(weeks=w) for w in range(16)]

# ─────────────────────────────────────────────
# 4. PROMOTION SCHEDULE
# ─────────────────────────────────────────────
# This is the KEY design choice for the data.
# I assign specific (product, region, week) triples as "promo" — not just random.
# This means questions like "which region had the best promo ROI?" have real answers.
#
# Promo types and their discount levels:

PROMO_TYPES = {
    "Price Cut":      0.15,
    "BOGO":           0.25,
    "Display Feature":0.10,
    "Bundle":         0.20,
}

def make_promo_schedule():
    """
    Returns a dict: (product_id, region, week_date) -> (promo_type, discount_pct)
    ~20% of combinations get a promotion.
    """
    schedule = {}
    promo_type_list = list(PROMO_TYPES.keys())
    for prod_id in PRODUCT_IDS:
        for region in REGIONS_CITIES.keys():
            for week in WEEKS:
                if random.random() < 0.18:   # 18% of weeks have a promo
                    ptype    = random.choice(promo_type_list)
                    discount = PROMO_TYPES[ptype] + random.uniform(-0.03, 0.03)
                    schedule[(prod_id, region, week)] = (ptype, round(discount, 3))
    return schedule

PROMO_SCHEDULE = make_promo_schedule()

# ─────────────────────────────────────────────
# 5. SALES & PROMOTIONS TABLE
# ─────────────────────────────────────────────
# For each (week, product, store) combination:
#   - Base units drawn from a realistic range per category.
#   - In promo weeks: multiply by UPLIFT (1.4–2.2x). This is the planted signal.
#   - Revenue = units × price × (1 − discount)

CATEGORY_BASE_UNITS = {
    "Carbonated": (40, 120),
    "Juice":      (30,  90),
    "Water":      (50, 150),
    "Energy":     (20,  70),
    "Dairy":      (25,  80),
}

def make_sales_row(week, prod_id, store_id):
    _, _, region, _, _ = STORE_DICT[store_id]
    _, _, _, category, _, _, unit_price = PRODUCT_DICT[prod_id]

    lo, hi     = CATEGORY_BASE_UNITS[category]
    base_units = random.randint(lo, hi)

    promo_key  = (prod_id, region, week)
    if promo_key in PROMO_SCHEDULE:
        ptype, discount = PROMO_SCHEDULE[promo_key]
        uplift      = random.uniform(1.4, 2.2)       # THE PLANTED SIGNAL
        units_sold  = int(base_units * uplift)
        promo_flag  = True
    else:
        discount    = 0.0
        ptype       = None
        units_sold  = base_units
        promo_flag  = False

    revenue = round(units_sold * unit_price * (1 - discount), 2)

    return {
        "week_start_date": week.isoformat(),
        "product_id":      prod_id,
        "store_id":        store_id,
        "region":          region,
        "units_sold":      units_sold,
        "revenue":         revenue,
        "promotion_flag":  int(promo_flag),
        "promotion_type":  ptype if ptype else "",
        "discount_pct":    discount,
    }

# ─────────────────────────────────────────────
# 6. INVENTORY TABLE
# ─────────────────────────────────────────────
# Derived from sales so closing_stock is always consistent:
#   closing = opening + received - units_sold
# If closing goes negative we cap it at 0 and set stockout_flag = True.

def make_inventory_row(week, prod_id, store_id, units_sold):
    _, _, _, category, _, _, _ = PRODUCT_DICT[prod_id]
    lo, hi = CATEGORY_BASE_UNITS[category]

    opening_stock  = random.randint(hi, hi * 3)    # start comfortably stocked
    units_received = random.randint(lo, hi)
    closing_stock  = opening_stock + units_received - units_sold
    stockout       = 0

    if closing_stock < 0:
        closing_stock = 0
        stockout      = 1

    return {
        "week_start_date": week.isoformat(),
        "product_id":      prod_id,
        "store_id":        store_id,
        "opening_stock":   opening_stock,
        "units_received":  units_received,
        "units_sold":      units_sold,
        "closing_stock":   closing_stock,
        "stockout_flag":   stockout,
    }

# ─────────────────────────────────────────────
# 7. WRITE CSVs
# ─────────────────────────────────────────────

def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  Written: {path}  ({len(rows):,} rows)")

print("\n=== Generating CSVs ===")

# Products
write_csv(OUT / "products.csv",
    ["product_id","product_name","brand","category","sub_category","pack_size_ml","unit_price"],
    [dict(zip(["product_id","product_name","brand","category","sub_category","pack_size_ml","unit_price"], p))
     for p in PRODUCTS])

# Stores
write_csv(OUT / "stores.csv",
    ["store_id","store_name","region","city","store_format"],
    [dict(zip(["store_id","store_name","region","city","store_format"], s)) for s in STORES])

# Sales + Inventory (one pass so units_sold is shared)
sales_rows     = []
inventory_rows = []

for week in WEEKS:
    for prod_id in PRODUCT_IDS:
        for store_id in STORE_IDS:
            sr = make_sales_row(week, prod_id, store_id)
            sales_rows.append(sr)
            ir = make_inventory_row(week, prod_id, store_id, sr["units_sold"])
            inventory_rows.append(ir)

write_csv(OUT / "sales.csv",
    ["week_start_date","product_id","store_id","region","units_sold",
     "revenue","promotion_flag","promotion_type","discount_pct"],
    sales_rows)

write_csv(OUT / "inventory.csv",
    ["week_start_date","product_id","store_id","opening_stock",
     "units_received","units_sold","closing_stock","stockout_flag"],
    inventory_rows)

# ─────────────────────────────────────────────
# 8. LOAD INTO SQLITE
# ─────────────────────────────────────────────
# WHY SQLite here: zero-install local backup. Production data lives in Supabase PostgreSQL.
# We create the tables with proper types and then bulk-insert from the CSVs.

print("\n=== Loading into SQLite: beverages.db ===")

if DB_PATH.exists():
    DB_PATH.unlink()   # fresh build every run

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

cur.executescript("""
CREATE TABLE products (
    product_id   TEXT PRIMARY KEY,
    product_name TEXT,
    brand        TEXT,
    category     TEXT,
    sub_category TEXT,
    pack_size_ml INTEGER,
    unit_price   REAL
);

CREATE TABLE stores (
    store_id     TEXT PRIMARY KEY,
    store_name   TEXT,
    region       TEXT,
    city         TEXT,
    store_format TEXT
);

CREATE TABLE sales (
    week_start_date TEXT,
    product_id      TEXT,
    store_id        TEXT,
    region          TEXT,
    units_sold      INTEGER,
    revenue         REAL,
    promotion_flag  INTEGER,
    promotion_type  TEXT,
    discount_pct    REAL,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (store_id)   REFERENCES stores(store_id)
);

CREATE TABLE inventory (
    week_start_date TEXT,
    product_id      TEXT,
    store_id        TEXT,
    opening_stock   INTEGER,
    units_received  INTEGER,
    units_sold      INTEGER,
    closing_stock   INTEGER,
    stockout_flag   INTEGER,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (store_id)   REFERENCES stores(store_id)
);
""")

def load_csv_to_table(csv_path, table_name):
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)
        if not rows:
            return
        cols        = rows[0].keys()
        placeholders = ",".join("?" for _ in cols)
        sql          = f"INSERT INTO {table_name} ({','.join(cols)}) VALUES ({placeholders})"
        cur.executemany(sql, [list(r.values()) for r in rows])
        print(f"  Loaded {len(rows):,} rows -> {table_name}")

load_csv_to_table(OUT / "products.csv",  "products")
load_csv_to_table(OUT / "stores.csv",    "stores")
load_csv_to_table(OUT / "sales.csv",     "sales")
load_csv_to_table(OUT / "inventory.csv", "inventory")

conn.commit()
conn.close()

# ─────────────────────────────────────────────
# 9. QUICK SANITY CHECK
# ─────────────────────────────────────────────
# Run 3 hand-verifiable queries so you can confirm the data makes sense
# before trusting the AI's answers.

print("\n=== Sanity checks ===")

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

checks = [
    ("Total sales rows",
     "SELECT COUNT(*) FROM sales"),
    ("Avg units_sold: promo vs non-promo (should be ~1.6-2x higher)",
     "SELECT promotion_flag, ROUND(AVG(units_sold),1) avg_units FROM sales GROUP BY promotion_flag"),
    ("Revenue by region (top 4)",
     "SELECT region, ROUND(SUM(revenue),0) total_rev FROM sales GROUP BY region ORDER BY total_rev DESC"),
    ("Stockout rate by category",
     """SELECT p.category, ROUND(100.0*SUM(i.stockout_flag)/COUNT(*),1) pct_stockout
        FROM inventory i JOIN products p ON i.product_id=p.product_id
        GROUP BY p.category ORDER BY pct_stockout DESC"""),
]

for label, sql in checks:
    print(f"\n  {label}:")
    for row in cur.execute(sql):
        print(f"    {row}")

conn.close()
print("\n=== Done. Files created in:", OUT, "===")
