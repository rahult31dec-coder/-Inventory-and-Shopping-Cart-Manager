"""REST API backend for the Inventory and Shopping Cart Manager.

Reuses the Inventory and Cart classes from main.py.

* Every user has their own cart (login with a token).
* Anyone can browse items; only an admin can add / update / delete items.
* Passwords are stored hashed, never as plain text.

Run (development):   python app.py
Run (production):    waitress-serve --port=5000 app:app
Debug mode is OFF by default; turn it on only while developing with FLASK_DEBUG=1.
"""
import math
import os
import re
import secrets
import threading
import time
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from main import Cart, Inventory, atomic_json_dump

USERS_FILE = "users.json"
TOKEN_LIFETIME = 8 * 60 * 60  # seconds
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # reject requests bigger than 1 MB

inv = Inventory()
lock = threading.RLock()   # the dev server handles requests in threads
users = {}                 # username -> {"password_hash": ..., "role": ...}
tokens = {}                # token -> (username, expiry time)
carts = {}                 # username -> Cart


# ---------------------------------------------------------------- users
def init_users():
    """Load users from disk and make sure an admin account exists."""
    import json
    users.clear()
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE) as f:
                users.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            print("Warning: users file unreadable, starting with no users.")
    admin = os.environ.get("ADMIN_USERNAME", "admin").lower()
    if admin not in users:
        password = os.environ.get("ADMIN_PASSWORD")
        if not password:
            password = "admin123"
            print("WARNING: using the default admin password 'admin123'. "
                  "Set the ADMIN_PASSWORD environment variable to change it.")
        users[admin] = {"password_hash": generate_password_hash(password), "role": "admin"}
        atomic_json_dump(USERS_FILE, users)


init_users()


# ---------------------------------------------------------------- helpers
def err(msg, code=400):
    return jsonify({"error": msg}), code


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def as_int(value):
    if isinstance(value, bool):
        raise ValueError
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value)
    raise ValueError


def as_price(value):
    if isinstance(value, bool):
        raise ValueError
    number = float(value)
    if not math.isfinite(number):
        raise ValueError
    return number


def synchronized(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        with lock:
            return f(*args, **kwargs)
    return wrapper


def auth_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return err("Login required. Send header 'Authorization: Bearer <token>'.", 401)
            token = header[7:].strip()
            entry = tokens.get(token)
            if not entry or entry[1] < time.time() or entry[0] not in users:
                tokens.pop(token, None)
                return err("Invalid or expired token. Please log in again.", 401)
            if role and users[entry[0]]["role"] != role:
                return err("Admin access required.", 403)
            g.username = entry[0]
            return f(*args, **kwargs)
        return wrapper
    return decorator


def current_cart():
    return carts.setdefault(g.username, Cart(inv))


# ---------------------------------------------------------------- accounts
@app.post("/register")
@synchronized
def register():
    d = body()
    username = str(d.get("username", "")).strip().lower()
    password = d.get("password")
    if not USERNAME_RE.match(username):
        return err("Username must be 3-30 characters: letters, digits, _ . -")
    if not isinstance(password, str) or len(password) < 6:
        return err("Password must be at least 6 characters.")
    if username in users:
        return err("Username already taken.", 409)
    users[username] = {"password_hash": generate_password_hash(password), "role": "customer"}
    atomic_json_dump(USERS_FILE, users)
    return jsonify({"message": "Account created. Please log in."}), 201


@app.post("/login")
@synchronized
def login():
    d = body()
    username = str(d.get("username", "")).strip().lower()
    password = d.get("password")
    user = users.get(username)
    if not user or not isinstance(password, str) or \
            not check_password_hash(user["password_hash"], password):
        return err("Wrong username or password.", 401)
    now = time.time()
    for t in [t for t, (_, exp) in tokens.items() if exp < now]:
        del tokens[t]  # clean up expired tokens
    token = secrets.token_hex(24)
    tokens[token] = (username, now + TOKEN_LIFETIME)
    return jsonify({"token": token, "role": user["role"], "expires_in_seconds": TOKEN_LIFETIME})


@app.post("/logout")
@auth_required()
@synchronized
def logout():
    tokens.pop(request.headers["Authorization"][7:].strip(), None)
    return jsonify({"message": "Logged out."})


# ---------------------------------------------------------------- inventory
@app.get("/items")
@synchronized
def list_items():
    keyword = request.args.get("search")
    items = inv.search(keyword) if keyword else inv.items.values()
    return jsonify([i.to_dict() for i in items])


@app.get("/items/<item_id>")
@synchronized
def get_item(item_id):
    item = inv.items.get(item_id)
    return jsonify(item.to_dict()) if item else err("Item not found.", 404)


@app.post("/items")
@auth_required("admin")
@synchronized
def add_item():
    d = body()
    try:
        item_id, name = str(d["id"]).strip(), str(d["name"]).strip()
        price, qty = as_price(d["price"]), as_int(d["quantity"])
    except (KeyError, ValueError, TypeError):
        return err("Required JSON: id, name, price (number), quantity (whole number).")
    ok, msg = inv.add_item(item_id, name, price, qty)
    if not ok:
        return err(msg, 409 if "exists" in msg else 400)
    return jsonify(inv.items[item_id].to_dict()), 201


@app.put("/items/<item_id>")
@auth_required("admin")
@synchronized
def update_item(item_id):
    if item_id not in inv.items:
        return err("Item not found.", 404)
    d = body()
    try:
        price = as_price(d["price"]) if "price" in d else None
        qty = as_int(d["quantity"]) if "quantity" in d else None
    except (ValueError, TypeError):
        return err("price must be a number and quantity a whole number.")
    ok, msg = inv.update_item(item_id, price, qty)
    if not ok:
        return err(msg)
    return jsonify(inv.items[item_id].to_dict())


@app.delete("/items/<item_id>")
@auth_required("admin")
@synchronized
def delete_item(item_id):
    ok, msg = inv.remove_item(item_id)
    return jsonify({"message": msg}) if ok else err(msg, 404)


# ---------------------------------------------------------------- cart
@app.get("/cart")
@auth_required()
@synchronized
def view_cart():
    return jsonify(current_cart().details())


@app.post("/cart")
@auth_required()
@synchronized
def add_to_cart():
    d = body()
    try:
        item_id, qty = str(d["id"]).strip(), as_int(d["quantity"])
    except (KeyError, ValueError, TypeError):
        return err("Required JSON: id, quantity (whole number).")
    cart = current_cart()
    ok, msg = cart.add(item_id, qty)
    if not ok:
        return err(msg, 404 if "not found" in msg else 409 if "stock" in msg else 400)
    return jsonify(cart.details()), 201


@app.delete("/cart/<item_id>")
@auth_required()
@synchronized
def remove_from_cart(item_id):
    cart = current_cart()
    ok, msg = cart.remove(item_id)
    return jsonify(cart.details()) if ok else err(msg, 404)


@app.post("/checkout")
@auth_required()
@synchronized
def checkout():
    ok, msg, bill = current_cart().checkout()
    if not ok:
        return err(msg, 409 if "stock" in msg else 400)
    return jsonify({"message": msg, "bill": bill})


# ---------------------------------------------------------------- errors
@app.errorhandler(404)
def not_found(_):
    return err("Not found.", 404)


@app.errorhandler(405)
def bad_method(_):
    return err("Method not allowed.", 405)


@app.errorhandler(413)
def too_large(_):
    return err("Request too large.", 413)


@app.errorhandler(500)
def server_error(_):
    return err("Internal server error.", 500)


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "5000")),
            debug=os.environ.get("FLASK_DEBUG") == "1")
