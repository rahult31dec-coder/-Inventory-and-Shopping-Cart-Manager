"""Inventory and Shopping Cart Manager
A console-based Python mini project.

Features: manage inventory (add / update / remove / search), shopping cart
(add / remove / view), checkout with a bill, automatic stock update and JSON
file persistence.  The Inventory and Cart classes are also used by the REST
API in app.py.
"""
import json
import math
import os
import tempfile

DATA_FILE = "inventory.json"


def atomic_json_dump(path, data):
    """Write JSON safely: write to a temp file first, then replace the old one,
    so a crash while saving can never leave a half-written data file."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def valid_price(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def valid_quantity(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


class Item:
    def __init__(self, item_id, name, price, quantity):
        self.item_id = item_id
        self.name = name
        self.price = price
        self.quantity = quantity

    def to_dict(self):
        return {"id": self.item_id, "name": self.name,
                "price": self.price, "quantity": self.quantity}


class Inventory:
    """Stores all items. Every change method returns (ok, message)."""

    def __init__(self, filename=DATA_FILE):
        self.filename = filename
        self.items = {}
        self.load()

    def load(self):
        if not os.path.exists(self.filename):
            return
        try:
            with open(self.filename) as f:
                records = json.load(f)
            if not isinstance(records, list):
                raise ValueError("data file must contain a list")
        except (json.JSONDecodeError, ValueError, OSError):
            backup = self.filename + ".bak"
            try:
                os.replace(self.filename, backup)
                print(f"Warning: data file was corrupted; saved a copy as {backup}.")
            except OSError:
                print("Warning: data file was corrupted and could not be read.")
            return
        for d in records:
            try:
                item = Item(str(d["id"]), str(d["name"]), d["price"], d["quantity"])
                if not (valid_price(item.price) and valid_quantity(item.quantity)):
                    raise ValueError
                self.items[item.item_id] = item
            except (KeyError, TypeError, ValueError):
                print(f"Warning: skipped an invalid record in {self.filename}.")

    def save(self):
        atomic_json_dump(self.filename, [i.to_dict() for i in self.items.values()])

    def add_item(self, item_id, name, price, quantity):
        item_id = str(item_id).strip()
        name = str(name).strip()
        if not item_id or not name:
            return False, "Item ID and name cannot be empty."
        if not valid_price(price):
            return False, "Price must be a number that is 0 or more."
        if not valid_quantity(quantity):
            return False, "Quantity must be a whole number that is 0 or more."
        if item_id in self.items:
            return False, "Item ID already exists."
        self.items[item_id] = Item(item_id, name, round(float(price), 2), quantity)
        self.save()
        return True, f"'{name}' added."

    def update_item(self, item_id, price=None, quantity=None):
        """Change price and/or quantity. Pass None to keep the current value."""
        item = self.items.get(item_id)
        if not item:
            return False, "Item not found."
        if price is None and quantity is None:
            return False, "Nothing to update."
        if price is not None and not valid_price(price):
            return False, "Price must be a number that is 0 or more."
        if quantity is not None and not valid_quantity(quantity):
            return False, "Quantity must be a whole number that is 0 or more."
        if price is not None:
            item.price = round(float(price), 2)
        if quantity is not None:
            item.quantity = quantity
        self.save()
        return True, "Item updated."

    def remove_item(self, item_id):
        if item_id not in self.items:
            return False, "Item not found."
        del self.items[item_id]
        self.save()
        return True, "Item removed."

    def search(self, keyword):
        keyword = keyword.strip().lower()
        return [i for i in self.items.values()
                if keyword in i.name.lower() or keyword in i.item_id.lower()]

    def display(self, items=None):
        items = list(self.items.values()) if items is None else items
        if not items:
            print("No items to show.")
            return
        print(f"\n{'ID':<8}{'Name':<20}{'Price':>10}{'Stock':>8}")
        print("-" * 46)
        for i in items:
            print(f"{i.item_id:<8}{i.name:<20}{i.price:>10.2f}{i.quantity:>8}")


class Cart:
    """A shopping cart. Every change method returns (ok, message)."""

    def __init__(self, inventory):
        self.inventory = inventory
        self.lines = {}  # item_id -> quantity

    def _prune(self):
        """Drop cart lines whose item was deleted from the inventory."""
        for item_id in [i for i in self.lines if i not in self.inventory.items]:
            del self.lines[item_id]

    def add(self, item_id, qty):
        item = self.inventory.items.get(item_id)
        if not item:
            return False, "Item not found."
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            return False, "Quantity must be a positive whole number."
        if self.lines.get(item_id, 0) + qty > item.quantity:
            return False, f"Only {item.quantity} in stock."
        self.lines[item_id] = self.lines.get(item_id, 0) + qty
        return True, f"Added {qty} x {item.name} to cart."

    def remove(self, item_id):
        if self.lines.pop(item_id, None) is None:
            return False, "Item not in cart."
        return True, "Removed from cart."

    def details(self):
        self._prune()
        rows = []
        for item_id, qty in self.lines.items():
            it = self.inventory.items[item_id]
            rows.append({"id": item_id, "name": it.name, "price": it.price,
                         "quantity": qty, "subtotal": round(it.price * qty, 2)})
        return {"items": rows, "total": round(sum(r["subtotal"] for r in rows), 2)}

    def view(self):
        d = self.details()
        if not d["items"]:
            print("Cart is empty.")
            return
        print(f"\n{'Item':<20}{'Qty':>5}{'Price':>10}{'Subtotal':>12}")
        print("-" * 47)
        for r in d["items"]:
            print(f"{r['name']:<20}{r['quantity']:>5}{r['price']:>10.2f}{r['subtotal']:>12.2f}")
        print("-" * 47)
        print(f"{'TOTAL':<35}{d['total']:>12.2f}")

    def checkout(self):
        """Returns (ok, message, bill). Reduces stock only if everything is available."""
        self._prune()
        if not self.lines:
            return False, "Cart is empty.", None
        for item_id, qty in self.lines.items():
            item = self.inventory.items[item_id]
            if qty > item.quantity:
                return (False, f"Only {item.quantity} of '{item.name}' left in stock. "
                               "Please update your cart.", None)
        bill = self.details()
        for item_id, qty in self.lines.items():
            self.inventory.items[item_id].quantity -= qty
        self.inventory.save()
        self.lines.clear()
        return True, "Purchase complete. Stock updated.", bill


def read_number(prompt, cast=int, allow_blank=False):
    """Keep asking until a valid, non-negative number is typed.
    With allow_blank=True, pressing Enter returns None (keep current value)."""
    while True:
        raw = input(prompt).strip()
        if raw == "" and allow_blank:
            return None
        try:
            value = cast(raw)
        except ValueError:
            print("Invalid input, try again.")
            continue
        if not math.isfinite(value) or value < 0:
            print("Please enter a number that is 0 or more.")
            continue
        return value


def say(result):
    print(result[1])


def inventory_menu(inv):
    while True:
        print("\n--- Inventory Menu ---\n1. View all\n2. Add item\n3. Update item"
              "\n4. Remove item\n5. Search\n6. Back")
        c = input("Choice: ").strip()
        if c == "1":
            inv.display()
        elif c == "2":
            item_id = input("ID: ").strip()
            name = input("Name: ").strip()
            price = read_number("Price: ", float)
            qty = read_number("Quantity: ")
            say(inv.add_item(item_id, name, price, qty))
        elif c == "3":
            item_id = input("ID: ").strip()
            if item_id not in inv.items:
                print("Item not found.")
                continue
            price = read_number("New price (press Enter to keep current): ", float, True)
            qty = read_number("New quantity (press Enter to keep current): ", int, True)
            say(inv.update_item(item_id, price, qty))
        elif c == "4":
            say(inv.remove_item(input("ID: ").strip()))
        elif c == "5":
            inv.display(inv.search(input("Keyword: ")))
        elif c == "6":
            return
        else:
            print("Invalid choice.")


def cart_menu(inv, cart):
    while True:
        print("\n--- Shopping Cart Menu ---\n1. Browse items\n2. Add to cart"
              "\n3. Remove from cart\n4. View cart\n5. Checkout\n6. Back")
        c = input("Choice: ").strip()
        if c == "1":
            inv.display()
        elif c == "2":
            item_id = input("Item ID: ").strip()
            say(cart.add(item_id, read_number("Quantity: ")))
        elif c == "3":
            say(cart.remove(input("Item ID: ").strip()))
        elif c == "4":
            cart.view()
        elif c == "5":
            cart.view()
            if not cart.lines:
                continue
            if input("Confirm purchase? (y/n): ").strip().lower() != "y":
                print("Checkout cancelled.")
                continue
            ok, msg, _ = cart.checkout()
            print(msg if ok else f"Checkout failed: {msg}")
        elif c == "6":
            return
        else:
            print("Invalid choice.")


def main():
    inv = Inventory()
    cart = Cart(inv)
    try:
        while True:
            print("\n===== Inventory & Shopping Cart Manager =====\n1. Manage Inventory"
                  "\n2. Shopping Cart\n3. Exit")
            c = input("Choice: ").strip()
            if c == "1":
                inventory_menu(inv)
            elif c == "2":
                cart_menu(inv, cart)
            elif c == "3":
                break
            else:
                print("Invalid choice.")
    except (EOFError, KeyboardInterrupt):
        print()
    except OSError as e:
        print(f"File error: {e}")
    print("Goodbye!")


if __name__ == "__main__":
    main()
