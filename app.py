"""REST API backend for the Inventory and Shopping Cart Manager.
Reuses the Inventory logic from main.py.  Run:  python app.py
"""
from flask import Flask, jsonify, request
from main import Inventory

app = Flask(__name__)
inv = Inventory()
cart = {}  # item_id -> quantity (single shared cart, kept simple for a mini project)


def err(msg, code=400):
    return jsonify({"error": msg}), code


# ---------- Inventory ----------
@app.get("/items")
def list_items():
    q = request.args.get("search")
    items = inv.search(q) if q else inv.items.values()
    return jsonify([i.to_dict() for i in items])


@app.get("/items/<item_id>")
def get_item(item_id):
    item = inv.items.get(item_id)
    return jsonify(item.to_dict()) if item else err("Item not found", 404)


@app.post("/items")
def add_item():
    d = request.get_json(silent=True) or {}
    try:
        item_id, name = str(d["id"]), str(d["name"])
        price, qty = float(d["price"]), int(d["quantity"])
    except (KeyError, ValueError, TypeError):
        return err("Required JSON: id, name, price (number), quantity (integer)")
    if price < 0 or qty < 0:
        return err("Price and quantity cannot be negative")
    if item_id in inv.items:
        return err("Item ID already exists", 409)
    inv.add_item(item_id, name, price, qty)
    return jsonify(inv.items[item_id].to_dict()), 201


@app.put("/items/<item_id>")
def update_item(item_id):
    if item_id not in inv.items:
        return err("Item not found", 404)
    d = request.get_json(silent=True) or {}
    try:
        price = float(d["price"]) if "price" in d else None
        qty = int(d["quantity"]) if "quantity" in d else None
    except (ValueError, TypeError):
        return err("price must be a number and quantity an integer")
    inv.update_item(item_id, price, qty)
    return jsonify(inv.items[item_id].to_dict())


@app.delete("/items/<item_id>")
def delete_item(item_id):
    if item_id not in inv.items:
        return err("Item not found", 404)
    inv.remove_item(item_id)
    cart.pop(item_id, None)
    return jsonify({"message": "Item removed"})


# ---------- Cart ----------
def cart_view():
    lines = [{"id": i, "name": inv.items[i].name, "price": inv.items[i].price,
              "quantity": q, "subtotal": round(inv.items[i].price * q, 2)}
             for i, q in cart.items()]
    return {"items": lines, "total": round(sum(l["subtotal"] for l in lines), 2)}


@app.get("/cart")
def view_cart():
    return jsonify(cart_view())


@app.post("/cart")
def add_to_cart():
    d = request.get_json(silent=True) or {}
    try:
        item_id, qty = str(d["id"]), int(d["quantity"])
    except (KeyError, ValueError, TypeError):
        return err("Required JSON: id, quantity (integer)")
    item = inv.items.get(item_id)
    if not item:
        return err("Item not found", 404)
    if qty <= 0:
        return err("Quantity must be positive")
    if cart.get(item_id, 0) + qty > item.quantity:
        return err(f"Only {item.quantity} in stock", 409)
    cart[item_id] = cart.get(item_id, 0) + qty
    return jsonify(cart_view()), 201


@app.delete("/cart/<item_id>")
def remove_from_cart(item_id):
    if cart.pop(item_id, None) is None:
        return err("Item not in cart", 404)
    return jsonify(cart_view())


@app.post("/checkout")
def checkout():
    if not cart:
        return err("Cart is empty")
    bill = cart_view()
    for i, q in cart.items():
        inv.items[i].quantity -= q
    inv.save()
    cart.clear()
    return jsonify({"message": "Purchase complete", "bill": bill})


if __name__ == "__main__":
    app.run(debug=True)
