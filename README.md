# Inventory and Shopping Cart Manager

A console-based Python mini project (Budge Budge Institute of Technology).

## Features
- Add, update, remove, view and search inventory items
- Shopping cart: add/remove items, view cart, checkout with bill
- Stock is reduced automatically after purchase
- Data saved in `inventory.json` (persists between runs)
- Input validation and stock checks

## Run
```
python main.py
```
Requires Python 3.8+. No external libraries needed.

## Concepts used
Classes and objects, dictionaries, file handling (JSON), exception handling, functions, menu-driven programming.

## Backend (REST API)
`app.py` is a Flask backend that reuses the same inventory logic.

```
pip install -r requirements.txt
python app.py
```
Server runs at http://127.0.0.1:5000

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /items (optional `?search=pen`) | List / search items |
| GET | /items/<id> | Get one item |
| POST | /items | Add item (`id, name, price, quantity`) |
| PUT | /items/<id> | Update price and/or quantity |
| DELETE | /items/<id> | Remove item |
| GET | /cart | View cart with total |
| POST | /cart | Add to cart (`id, quantity`) |
| DELETE | /cart/<id> | Remove from cart |
| POST | /checkout | Generate bill, reduce stock, empty cart |
