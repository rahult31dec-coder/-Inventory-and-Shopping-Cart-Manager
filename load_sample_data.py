"""Fills inventory.json with sample products so you can demo the project.
Run once:  python load_sample_data.py   (safe to run again; existing IDs are skipped)
"""
from main import Inventory

SAMPLE = [
    ("P101", "Notebook", 50.0, 100),
    ("P102", "Ball Pen", 10.0, 250),
    ("P103", "Pencil Box", 120.0, 40),
    ("P104", "School Bag", 650.0, 15),
    ("P105", "Calculator", 450.0, 25),
    ("P106", "Water Bottle", 199.0, 30),
]

if __name__ == "__main__":
    inv = Inventory()
    added = 0
    for item in SAMPLE:
        ok, _ = inv.add_item(*item)
        added += ok
    print(f"Sample data ready: {added} new item(s) added, {len(inv.items)} total.")
