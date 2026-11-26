# Inventory and Shopping Cart Manager

A Python mini project with two parts that share the same core logic:

1. **Console application** (`main.py`) - menu-driven inventory and shopping cart.
2. **REST API backend** (`app.py`) - Flask server with user accounts, login and a separate cart for every user.

College mini project - Budge Budge Institute of Technology (BBIT)

## Features
- Add, update, remove, view and search inventory items
- Update only the price or only the quantity (press Enter to keep the other value)
- Shopping cart with stock checks, bill and automatic stock reduction on checkout
- Data saved in `inventory.json` (safe saving, corrupted files are backed up, not lost)
- Input validation everywhere (no negative numbers, no text where numbers are needed)
- API: user registration and login, password hashing, token authentication
- API: **each user has their own cart**; only an **admin** can add, update or delete items
- 38 automated tests

## Files
| File | Purpose |
|------|---------|
| `main.py` | Console app and the `Item`, `Inventory`, `Cart` classes |
| `app.py` | Flask REST API |
| `load_sample_data.py` | Fills the inventory with demo products |
| `test_project.py` | Automated tests |
| `requirements.txt` | Python packages |

## Setup
Python 3.8 or newer is required.
```
pip install -r requirements.txt
python load_sample_data.py
```

## Run the console app
```
python main.py
```

## Run the API
Development (debug mode is **off** by default):
```
python app.py
```
Production-style server:
```
waitress-serve --port=5000 app:app
```
The server runs at http://127.0.0.1:5000

Settings (environment variables, all optional):

| Variable | Meaning | Default |
|----------|---------|---------|
| `ADMIN_USERNAME` | Admin account name | `admin` |
| `ADMIN_PASSWORD` | Admin password (**set this!**) | `admin123` (a warning is printed) |
| `PORT` / `HOST` | Where the server listens | `5000` / `127.0.0.1` |
| `FLASK_DEBUG` | `1` turns on debug mode (development only) | off |

### API endpoints
| Method | Endpoint | Who | Purpose |
|--------|----------|-----|---------|
| POST | /register | anyone | Create a customer account (`username`, `password`) |
| POST | /login | anyone | Get a token (`username`, `password`) |
| POST | /logout | logged in | Invalidate the token |
| GET | /items (optional `?search=pen`) | anyone | List / search items |
| GET | /items/<id> | anyone | Get one item |
| POST | /items | admin | Add item (`id, name, price, quantity`) |
| PUT | /items/<id> | admin | Update `price` and/or `quantity` |
| DELETE | /items/<id> | admin | Remove item |
| GET | /cart | logged in | View your own cart with total |
| POST | /cart | logged in | Add to your cart (`id, quantity`) |
| DELETE | /cart/<id> | logged in | Remove from your cart |
| POST | /checkout | logged in | Bill, reduce stock, empty cart |

Send the token with every protected request: `Authorization: Bearer <token>`

Example:
```
curl -X POST http://127.0.0.1:5000/login -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"admin123"}'
```

## Run the tests
```
python -m unittest test_project -v
```
The tests use a temporary folder, so your real data is never touched.

## Concepts used
Object-oriented programming (classes and objects), dictionaries, file handling (JSON), exception handling, input validation, REST API design, authentication (hashed passwords and tokens), role-based access, automated unit testing.

## Known limitations (future scope)
- Tokens and carts are kept in memory, so they reset when the server restarts
- Data is stored in JSON files; a real deployment would use a database
- No login rate limiting and no HTTPS (use a reverse proxy for real deployment)
