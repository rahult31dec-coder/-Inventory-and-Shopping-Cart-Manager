"""Inventory and Shopping Cart Manager
A console-based Python mini project.
Features: manage inventory (add/update/remove/search), shopping cart
(add/remove/view), checkout with bill, stock auto-update, JSON persistence.
"""
import json
import os

DATA_FILE = "inventory.json"


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
    def __init__(self, filename=DATA_FILE):
        self.filename = filename
        self.items = {}
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename) as f:
                    for d in json.load(f):
                        self.items[d["id"]] = Item(d["id"], d["name"], d["price"], d["quantity"])
            except (json.JSONDecodeError, KeyError):
                print("Warning: data file corrupted, starting empty.")

    def save(self):
        with open(self.filename, "w") as f:
            json.dump([i.to_dict() for i in self.items.values()], f, indent=2)

    def add_item(self, item_id, name, price, quantity):
        if item_id in self.items:
            print("Item ID already exists.")
            return
        self.items[item_id] = Item(item_id, name, price, quantity)
        self.save()
        print(f"'{name}' added.")

    def update_item(self, item_id, price=None, quantity=None):
        item = self.items.get(item_id)
        if not item:
            print("Item not found.")
            return
        if price is not None:
            item.price = price
        if quantity is not None:
            item.quantity = quantity
        self.save()
        print("Item updated.")

    def remove_item(self, item_id):
        if self.items.pop(item_id, None):
            self.save()
            print("Item removed.")
        else:
            print("Item not found.")

    def search(self, keyword):
        return [i for i in self.items.values() if keyword.lower() in i.name.lower()]

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
    def __init__(self, inventory):
        self.inventory = inventory
        self.lines = {}  # item_id -> quantity

    def add(self, item_id, qty):
        item = self.inventory.items.get(item_id)
        if not item:
            print("Item not found.")
        elif qty <= 0:
            print("Quantity must be positive.")
        elif self.lines.get(item_id, 0) + qty > item.quantity:
            print(f"Only {item.quantity} in stock.")
        else:
            self.lines[item_id] = self.lines.get(item_id, 0) + qty
            print(f"Added {qty} x {item.name} to cart.")

    def remove(self, item_id):
        if self.lines.pop(item_id, None):
            print("Removed from cart.")
        else:
            print("Item not in cart.")

    def total(self):
        return sum(self.inventory.items[i].price * q for i, q in self.lines.items())

    def view(self):
        if not self.lines:
            print("Cart is empty.")
            return
        print(f"\n{'Item':<20}{'Qty':>5}{'Price':>10}{'Subtotal':>12}")
        print("-" * 47)
        for i, q in self.lines.items():
            it = self.inventory.items[i]
            print(f"{it.name:<20}{q:>5}{it.price:>10.2f}{it.price * q:>12.2f}")
        print("-" * 47)
        print(f"{'TOTAL':<35}{self.total():>12.2f}")

    def checkout(self):
        if not self.lines:
            print("Cart is empty.")
            return
        self.view()
        if input("Confirm purchase? (y/n): ").strip().lower() != "y":
            print("Checkout cancelled.")
            return
        for i, q in self.lines.items():
            self.inventory.items[i].quantity -= q
        self.inventory.save()
        print("Thank you! Purchase complete. Stock updated.")
        self.lines.clear()


def read_number(prompt, cast=int):
    while True:
        try:
            return cast(input(prompt))
        except ValueError:
            print("Invalid input, try again.")


def inventory_menu(inv):
    while True:
        print("\n--- Inventory Menu ---\n1. View all\n2. Add item\n3. Update item"
              "\n4. Remove item\n5. Search\n6. Back")
        c = input("Choice: ").strip()
        if c == "1":
            inv.display()
        elif c == "2":
            inv.add_item(input("ID: ").strip(), input("Name: ").strip(),
                         read_number("Price: ", float), read_number("Quantity: "))
        elif c == "3":
            inv.update_item(input("ID: ").strip(),
                            read_number("New price: ", float), read_number("New quantity: "))
        elif c == "4":
            inv.remove_item(input("ID: ").strip())
        elif c == "5":
            inv.display(inv.search(input("Keyword: ").strip()))
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
            cart.add(input("Item ID: ").strip(), read_number("Quantity: "))
        elif c == "3":
            cart.remove(input("Item ID: ").strip())
        elif c == "4":
            cart.view()
        elif c == "5":
            cart.checkout()
        elif c == "6":
            return
        else:
            print("Invalid choice.")


def main():
    inv = Inventory()
    cart = Cart(inv)
    while True:
        print("\n===== Inventory & Shopping Cart Manager =====\n1. Manage Inventory"
              "\n2. Shopping Cart\n3. Exit")
        c = input("Choice: ").strip()
        if c == "1":
            inventory_menu(inv)
        elif c == "2":
            cart_menu(inv, cart)
        elif c == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
