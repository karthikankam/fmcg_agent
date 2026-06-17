import sqlite3

conn = sqlite3.connect(r"F:\newproject\fmcg_assistant\beverages.db")
cur  = conn.cursor()

print("=== TABLES IN DATABASE ===")
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(" -", row[0])

print()
print("=== PRODUCTS (all 15) ===")
print(f"  {'ID':<10} {'Name':<35} {'Brand':<10} {'Category':<12} {'Sub-cat':<18} {'ml':>5} {'Price':>6}")
print("  " + "-"*100)
for r in cur.execute("SELECT * FROM products ORDER BY category, product_id"):
    print(f"  {r[0]:<10} {r[1]:<35} {r[2]:<10} {r[3]:<12} {r[4]:<18} {r[5]:>5} {r[6]:>6.2f}")

print()
print("=== STORES (all 30) ===")
print(f"  {'ID':<10} {'Name':<35} {'Region':<8} {'City':<15} {'Format':<15}")
print("  " + "-"*85)
for r in cur.execute("SELECT * FROM stores ORDER BY region, store_id"):
    print(f"  {r[0]:<10} {r[1]:<35} {r[2]:<8} {r[3]:<15} {r[4]:<15}")

print()
print("=== SALES: sample 8 rows (mix of promo + non-promo) ===")
print(f"  {'Week':<12} {'Product':<10} {'Store':<9} {'Region':<7} {'Units':>6} {'Revenue':>9} {'Promo':>6} {'Type':<17} {'Disc':>5}")
print("  " + "-"*95)
for r in cur.execute("""
    SELECT * FROM sales
    WHERE promotion_flag=1 LIMIT 4
"""):
    print(f"  {r[0]:<12} {r[1]:<10} {r[2]:<9} {r[3]:<7} {r[4]:>6} {r[5]:>9.2f} {'YES':>6} {str(r[7]):<17} {r[8]:>5.2f}")
for r in cur.execute("""
    SELECT * FROM sales
    WHERE promotion_flag=0 LIMIT 4
"""):
    print(f"  {r[0]:<12} {r[1]:<10} {r[2]:<9} {r[3]:<7} {r[4]:>6} {r[5]:>9.2f} {'no':>6} {'-':<17} {r[8]:>5.2f}")

print()
print("=== INVENTORY: sample 5 rows ===")
print(f"  {'Week':<12} {'Product':<10} {'Store':<9} {'Opening':>8} {'Received':>9} {'Sold':>6} {'Closing':>8} {'Stockout':>9}")
print("  " + "-"*80)
for r in cur.execute("SELECT * FROM inventory LIMIT 5"):
    print(f"  {r[0]:<12} {r[1]:<10} {r[2]:<9} {r[3]:>8} {r[4]:>9} {r[5]:>6} {r[6]:>8} {r[7]:>9}")

print()
print("=== KEY STATS ===")
stats = [
    ("Total sales rows",   "SELECT COUNT(*) FROM sales"),
    ("Total inventory rows","SELECT COUNT(*) FROM inventory"),
    ("Weeks covered",      "SELECT MIN(week_start_date), MAX(week_start_date) FROM sales"),
    ("Promo rows",         "SELECT COUNT(*) FROM sales WHERE promotion_flag=1"),
    ("Non-promo rows",     "SELECT COUNT(*) FROM sales WHERE promotion_flag=0"),
    ("Promo types used",   "SELECT promotion_type, COUNT(*) FROM sales WHERE promotion_flag=1 GROUP BY promotion_type"),
    ("Products per category","SELECT category, COUNT(*) FROM products GROUP BY category"),
    ("Stores per region",  "SELECT region, COUNT(*) FROM stores GROUP BY region"),
    ("Stockout events",    "SELECT COUNT(*) FROM inventory WHERE stockout_flag=1"),
]
for label, sql in stats:
    print(f"\n  {label}:")
    for row in cur.execute(sql):
        print(f"    {row}")

conn.close()
