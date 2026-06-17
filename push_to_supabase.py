"""
push_to_supabase.py
-------------------
Reads the 4 CSVs and pushes them into Supabase PostgreSQL.
Run once to seed the cloud database.
"""

import os
import csv
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).parent / ".env")

DB_URL = os.getenv("SUPABASE_DB_URL")
OUT    = Path(__file__).parent

engine = create_engine(DB_URL)

# ── Create tables ────────────────────────────────────────────────────
CREATE_SQL = """
DROP TABLE IF EXISTS inventory CASCADE;
DROP TABLE IF EXISTS sales     CASCADE;
DROP TABLE IF EXISTS stores    CASCADE;
DROP TABLE IF EXISTS products  CASCADE;

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
    product_id      TEXT REFERENCES products(product_id),
    store_id        TEXT REFERENCES stores(store_id),
    region          TEXT,
    units_sold      INTEGER,
    revenue         REAL,
    promotion_flag  INTEGER,
    promotion_type  TEXT,
    discount_pct    REAL
);

CREATE TABLE inventory (
    week_start_date TEXT,
    product_id      TEXT REFERENCES products(product_id),
    store_id        TEXT REFERENCES stores(store_id),
    opening_stock   INTEGER,
    units_received  INTEGER,
    units_sold      INTEGER,
    closing_stock   INTEGER,
    stockout_flag   INTEGER
);
"""

def load_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def insert_rows(conn, table, rows, batch=500):
    if not rows:
        return
    cols         = list(rows[0].keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    sql          = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    for i in range(0, len(rows), batch):
        conn.execute(text(sql), rows[i:i+batch])
    print(f"  Inserted {len(rows):,} rows -> {table}")

print("=== Creating tables on Supabase ===")
with engine.begin() as conn:
    conn.execute(text(CREATE_SQL))

print("\n=== Pushing data ===")
with engine.begin() as conn:
    insert_rows(conn, "products",  load_csv(OUT / "products.csv"))
    insert_rows(conn, "stores",    load_csv(OUT / "stores.csv"))
    insert_rows(conn, "sales",     load_csv(OUT / "sales.csv"))
    insert_rows(conn, "inventory", load_csv(OUT / "inventory.csv"))

print("\n=== Verifying row counts ===")
with engine.connect() as conn:
    for table in ["products", "stores", "sales", "inventory"]:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        print(f"  {table}: {count:,} rows")

print("\nDone. Supabase is ready.")
