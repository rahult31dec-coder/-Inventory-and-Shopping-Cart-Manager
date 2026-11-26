"""Automated tests.   Run:  python -m unittest test_project -v
Everything runs in a temporary folder, so your real data files are never touched."""
import builtins
import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

_tmp = tempfile.TemporaryDirectory()
os.chdir(_tmp.name)
os.environ["ADMIN_PASSWORD"] = "adminpass"

import app as api  # noqa: E402
import main  # noqa: E402
from main import Cart, Inventory  # noqa: E402


def quiet(func, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return func(*args, **kwargs)


def run_console(lines, inv):
    """Run main.main() with typed input; returns everything it printed."""
    out = io.StringIO()
    typed = iter(lines)

    def fake_input(prompt=""):
        try:
            return next(typed)
        except StopIteration:
            raise EOFError  # like a closed keyboard / ended input

    with contextlib.redirect_stdout(out), \
            mock.patch.object(main, "Inventory", return_value=inv), \
            mock.patch.object(builtins, "input", fake_input):
        main.main()
    return out.getvalue()


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(_tmp.name, "t_inv.json")
        for p in (self.path, self.path + ".bak"):
            if os.path.exists(p):
                os.remove(p)
        self.inv = Inventory(self.path)
        self.inv.add_item("A1", "Pen", 10.0, 5)

    def test_duplicate_rejected(self):
        ok, _ = self.inv.add_item("A1", "Other", 1.0, 1)
        self.assertFalse(ok)
        self.assertEqual(self.inv.items["A1"].name, "Pen")

    def test_invalid_values_rejected(self):
        self.assertFalse(self.inv.add_item("B", "x", -1, 1)[0])
        self.assertFalse(self.inv.add_item("B", "x", float("nan"), 1)[0])
        self.assertFalse(self.inv.add_item("B", "x", 1, -5)[0])
        self.assertFalse(self.inv.add_item("B", "x", 1, 2.5)[0])
        self.assertFalse(self.inv.add_item("  ", "x", 1, 1)[0])
        self.assertFalse(self.inv.add_item("B", "  ", 1, 1)[0])

    def test_update_only_price_keeps_quantity(self):
        self.assertTrue(self.inv.update_item("A1", price=12.0)[0])
        self.assertEqual(self.inv.items["A1"].price, 12.0)
        self.assertEqual(self.inv.items["A1"].quantity, 5)

    def test_update_only_quantity_keeps_price(self):
        self.assertTrue(self.inv.update_item("A1", quantity=9)[0])
        self.assertEqual(self.inv.items["A1"].price, 10.0)
        self.assertEqual(self.inv.items["A1"].quantity, 9)

    def test_update_nothing_or_bad_values(self):
        self.assertFalse(self.inv.update_item("A1")[0])
        self.assertFalse(self.inv.update_item("A1", price=-3)[0])
        self.assertFalse(self.inv.update_item("NOPE", price=3)[0])

    def test_remove(self):
        self.assertTrue(self.inv.remove_item("A1")[0])
        self.assertFalse(self.inv.remove_item("A1")[0])

    def test_search(self):
        self.assertEqual(len(self.inv.search("PEN")), 1)
        self.assertEqual(len(self.inv.search("a1")), 1)
        self.assertEqual(len(self.inv.search("zzz")), 0)

    def test_persistence(self):
        self.assertEqual(Inventory(self.path).items["A1"].quantity, 5)

    def test_corrupted_file_is_backed_up(self):
        with open(self.path, "w") as f:
            f.write("{not json")
        inv = quiet(Inventory, self.path)
        self.assertEqual(inv.items, {})
        self.assertTrue(os.path.exists(self.path + ".bak"))

    def test_invalid_records_skipped(self):
        with open(self.path, "w") as f:
            f.write('[{"id":"X","name":"ok","price":1,"quantity":1},'
                    '{"id":"Y","name":"bad","price":-1,"quantity":1}, 5]')
        inv = quiet(Inventory, self.path)
        self.assertEqual(list(inv.items), ["X"])


class CartTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(_tmp.name, "c_inv.json")
        if os.path.exists(self.path):
            os.remove(self.path)
        self.inv = Inventory(self.path)
        self.inv.add_item("A1", "Pen", 10.0, 5)
        self.cart = Cart(self.inv)

    def test_stock_limit_and_total(self):
        self.assertTrue(self.cart.add("A1", 3)[0])
        self.assertFalse(self.cart.add("A1", 3)[0])
        self.assertEqual(self.cart.details()["total"], 30.0)

    def test_bad_quantities(self):
        for q in (0, -1, 2.5, True, "3"):
            self.assertFalse(self.cart.add("A1", q)[0], q)

    def test_item_deleted_while_in_cart_does_not_crash(self):
        self.cart.add("A1", 2)
        self.inv.remove_item("A1")
        self.assertEqual(self.cart.details(), {"items": [], "total": 0})
        self.assertFalse(self.cart.checkout()[0])

    def test_stock_changed_before_checkout(self):
        self.cart.add("A1", 4)
        self.inv.update_item("A1", quantity=2)
        ok, msg, _ = self.cart.checkout()
        self.assertFalse(ok)
        self.assertEqual(self.inv.items["A1"].quantity, 2)  # untouched

    def test_checkout_reduces_stock_and_empties_cart(self):
        self.cart.add("A1", 3)
        ok, _, bill = self.cart.checkout()
        self.assertTrue(ok)
        self.assertEqual(bill["total"], 30.0)
        self.assertEqual(self.inv.items["A1"].quantity, 2)
        self.assertEqual(self.cart.lines, {})
        self.assertEqual(Inventory(self.path).items["A1"].quantity, 2)  # saved

    def test_empty_checkout(self):
        self.assertFalse(self.cart.checkout()[0])


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(_tmp.name, "console_inv.json")
        if os.path.exists(self.path):
            os.remove(self.path)
        self.inv = Inventory(self.path)
        self.inv.add_item("A1", "Pen", 10.0, 5)

    def test_update_price_only_with_enter_for_quantity(self):
        run_console(["1", "3", "A1", "25", "", "6", "3"], self.inv)
        self.assertEqual(self.inv.items["A1"].price, 25.0)
        self.assertEqual(self.inv.items["A1"].quantity, 5)

    def test_update_quantity_only_with_enter_for_price(self):
        run_console(["1", "3", "A1", "", "40", "6", "3"], self.inv)
        self.assertEqual(self.inv.items["A1"].price, 10.0)
        self.assertEqual(self.inv.items["A1"].quantity, 40)

    def test_negative_and_text_input_rejected_then_accepted(self):
        out = run_console(["1", "2", "B2", "Cap", "-5", "abc", "7", "-1", "3", "6", "3"], self.inv)
        self.assertIn("Please enter a number", out)
        self.assertIn("Invalid input", out)
        self.assertEqual(self.inv.items["B2"].price, 7.0)
        self.assertEqual(self.inv.items["B2"].quantity, 3)

    def test_full_purchase_flow(self):
        out = run_console(["2", "2", "A1", "2", "5", "y", "6", "3"], self.inv)
        self.assertIn("Purchase complete", out)
        self.assertEqual(self.inv.items["A1"].quantity, 3)

    def test_input_ends_without_crash(self):
        out = run_console(["1"], self.inv)  # input runs out -> EOFError
        self.assertIn("Goodbye", out)


class ApiTests(unittest.TestCase):
    def setUp(self):
        api.inv.items.clear()
        api.tokens.clear()
        api.carts.clear()
        if os.path.exists(api.USERS_FILE):
            os.remove(api.USERS_FILE)
        quiet(api.init_users)
        self.c = api.app.test_client()
        self.admin = self.login("admin", "adminpass")
        self.c.post("/items", json={"id": "P1", "name": "Pen", "price": 10, "quantity": 50},
                    headers=self.admin)

    def login(self, user, password):
        r = self.c.post("/login", json={"username": user, "password": password})
        self.assertEqual(r.status_code, 200, r.get_json())
        return {"Authorization": "Bearer " + r.get_json()["token"]}

    def customer(self, name="alice"):
        self.c.post("/register", json={"username": name, "password": "secret1"})
        return self.login(name, "secret1")

    # --- safety settings
    def test_debug_is_off_by_default(self):
        self.assertFalse(api.app.debug)

    # --- accounts
    def test_register_rules(self):
        r = self.c.post("/register", json={"username": "bob", "password": "secret1"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.c.post("/register", json={"username": "BOB", "password": "secret1"}).status_code, 409)
        self.assertEqual(self.c.post("/register", json={"username": "x", "password": "secret1"}).status_code, 400)
        self.assertEqual(self.c.post("/register", json={"username": "carl", "password": "123"}).status_code, 400)
        self.assertEqual(self.c.post("/register", json={"username": "carl", "password": 123456}).status_code, 400)

    def test_login_wrong_password(self):
        self.c.post("/register", json={"username": "dave", "password": "secret1"})
        self.assertEqual(self.c.post("/login", json={"username": "dave", "password": "nope"}).status_code, 401)
        self.assertEqual(self.c.post("/login", json={"username": "ghost", "password": "x"}).status_code, 401)
        self.assertEqual(self.c.post("/login", data="garbage").status_code, 401)

    def test_passwords_are_hashed(self):
        self.customer("erin")
        self.assertNotIn("secret1", open(api.USERS_FILE).read())

    def test_logout_invalidates_token(self):
        h = self.customer()
        self.assertEqual(self.c.get("/cart", headers=h).status_code, 200)
        self.c.post("/logout", headers=h)
        self.assertEqual(self.c.get("/cart", headers=h).status_code, 401)

    def test_expired_token_rejected(self):
        h = self.customer()
        token = h["Authorization"][7:]
        api.tokens[token] = (api.tokens[token][0], 0)
        self.assertEqual(self.c.get("/cart", headers=h).status_code, 401)

    # --- permissions
    def test_cart_requires_login(self):
        self.assertEqual(self.c.get("/cart").status_code, 401)
        self.assertEqual(self.c.post("/checkout").status_code, 401)
        self.assertEqual(self.c.get("/cart", headers={"Authorization": "Bearer fake"}).status_code, 401)

    def test_customer_cannot_change_inventory(self):
        h = self.customer()
        self.assertEqual(self.c.post("/items", json={"id": "Z", "name": "z", "price": 1, "quantity": 1}, headers=h).status_code, 403)
        self.assertEqual(self.c.put("/items/P1", json={"price": 1}, headers=h).status_code, 403)
        self.assertEqual(self.c.delete("/items/P1", headers=h).status_code, 403)
        self.assertEqual(self.c.post("/items", json={"id": "Z", "name": "z", "price": 1, "quantity": 1}).status_code, 401)

    def test_anyone_can_browse(self):
        self.assertEqual(len(self.c.get("/items").get_json()), 1)
        self.assertEqual(len(self.c.get("/items?search=pe").get_json()), 1)
        self.assertEqual(self.c.get("/items/P1").status_code, 200)
        self.assertEqual(self.c.get("/items/NOPE").status_code, 404)

    # --- separate carts
    def test_each_user_has_own_cart(self):
        a, b = self.customer("alice"), self.customer("bobby")
        self.c.post("/cart", json={"id": "P1", "quantity": 3}, headers=a)
        self.assertEqual(self.c.get("/cart", headers=a).get_json()["total"], 30.0)
        self.assertEqual(self.c.get("/cart", headers=b).get_json(), {"items": [], "total": 0})

    def test_checkout_by_two_users_cannot_oversell(self):
        self.c.put("/items/P1", json={"quantity": 5}, headers=self.admin)
        a, b = self.customer("alice"), self.customer("bobby")
        self.assertEqual(self.c.post("/cart", json={"id": "P1", "quantity": 4}, headers=a).status_code, 201)
        self.assertEqual(self.c.post("/cart", json={"id": "P1", "quantity": 4}, headers=b).status_code, 201)
        self.assertEqual(self.c.post("/checkout", headers=a).status_code, 200)
        self.assertEqual(self.c.post("/checkout", headers=b).status_code, 409)
        self.assertEqual(self.c.get("/items/P1").get_json()["quantity"], 1)

    def test_deleted_item_vanishes_from_carts(self):
        a = self.customer()
        self.c.post("/cart", json={"id": "P1", "quantity": 2}, headers=a)
        self.c.delete("/items/P1", headers=self.admin)
        self.assertEqual(self.c.get("/cart", headers=a).status_code, 200)
        self.assertEqual(self.c.post("/checkout", headers=a).status_code, 400)

    # --- validation
    def test_bad_item_data(self):
        for bad in ({"id": "P2", "name": "x", "price": "abc", "quantity": 1},
                    {"id": "P2", "name": "x", "price": -1, "quantity": 1},
                    {"id": "P2", "name": "x", "price": 1, "quantity": 2.5},
                    {"id": "P2", "name": "x", "price": 1, "quantity": True},
                    {"id": "P2", "name": "x", "price": "nan", "quantity": 1},
                    {"id": "P2", "name": "x", "price": 1e999, "quantity": 1},
                    {"id": "  ", "name": "x", "price": 1, "quantity": 1},
                    {"name": "x"}):
            r = self.c.post("/items", json=bad, headers=self.admin)
            self.assertEqual(r.status_code, 400, bad)
        r = self.c.post("/items", json={"id": "P1", "name": "x", "price": 1, "quantity": 1}, headers=self.admin)
        self.assertEqual(r.status_code, 409)

    def test_update_rules(self):
        self.assertEqual(self.c.put("/items/P1", json={}, headers=self.admin).status_code, 400)
        self.assertEqual(self.c.put("/items/P1", json={"price": -5}, headers=self.admin).status_code, 400)
        self.assertEqual(self.c.put("/items/P1", json={"quantity": "x"}, headers=self.admin).status_code, 400)
        self.assertEqual(self.c.put("/items/NOPE", json={"price": 5}, headers=self.admin).status_code, 404)
        r = self.c.put("/items/P1", json={"price": 12}, headers=self.admin).get_json()
        self.assertEqual((r["price"], r["quantity"]), (12.0, 50))

    def test_bad_cart_requests(self):
        a = self.customer()
        self.assertEqual(self.c.post("/cart", json={"id": "P1", "quantity": 0}, headers=a).status_code, 400)
        self.assertEqual(self.c.post("/cart", json={"id": "P1", "quantity": -2}, headers=a).status_code, 400)
        self.assertEqual(self.c.post("/cart", json={"id": "P1", "quantity": "x"}, headers=a).status_code, 400)
        self.assertEqual(self.c.post("/cart", json={"id": "NOPE", "quantity": 1}, headers=a).status_code, 404)
        self.assertEqual(self.c.post("/cart", json={"id": "P1", "quantity": 99}, headers=a).status_code, 409)
        self.assertEqual(self.c.delete("/cart/P1", headers=a).status_code, 404)
        self.assertEqual(self.c.post("/checkout", headers=a).status_code, 400)
        self.assertEqual(self.c.post("/cart", data="[1,2]", content_type="application/json", headers=a).status_code, 400)

    def test_full_shopping_flow(self):
        a = self.customer()
        self.c.post("/cart", json={"id": "P1", "quantity": 3}, headers=a)
        r = self.c.post("/checkout", headers=a)
        self.assertEqual(r.get_json()["bill"]["total"], 30.0)
        self.assertEqual(self.c.get("/items/P1").get_json()["quantity"], 47)
        self.assertEqual(self.c.get("/cart", headers=a).get_json()["items"], [])

    def test_json_error_pages(self):
        self.assertEqual(self.c.get("/nothing").get_json(), {"error": "Not found."})
        self.assertEqual(self.c.patch("/items").status_code, 405)


if __name__ == "__main__":
    unittest.main()
