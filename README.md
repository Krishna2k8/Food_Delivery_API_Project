# Food Delivery API

A complete classroom project for a food-delivery service. Customers place orders from restaurants, restaurants manage their menus and update order stages, and an admin manages records and views the report. The project uses **FastAPI, Pydantic and JSON files only**. It has no database, front end, real login, payment gateway, OTP, maps or internet dependency.

## 1. Run the project

Open a terminal in this folder and run:

```bash
python -m venv .venv
```

Activate the environment:

- Windows PowerShell: `.venv\Scripts\Activate.ps1`
- Windows Command Prompt: `.venv\Scripts\activate.bat`
- Linux/macOS: `source .venv/bin/activate`

Install and start:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open the interactive API page: <http://127.0.0.1:8000/docs>

The first start creates `restaurants.json`, `menu_items.json`, `customers.json` and `orders.json` next to `main.py`, using the starter data in the program. To get a clean start, stop the server with `Ctrl+C`, delete those four JSON files, and start the server again. A normal restart does **not** delete data.

## 2. Roles

Send the header `X-Role` on protected endpoints. In `/docs`, click **Try it out** and enter the value in the `x-role` box.

| Role | May do | May not do |
|---|---|---|
| Anyone (no role) | Check health; browse restaurants and menus | Create or change records; view protected customer/order data |
| `customer` | Register a customer; view a customer/order; place an order; view a customer's order list; cancel an order while it is still `placed` | Manage restaurants or menus; advance order status; list all customers/orders; view the report |
| `restaurant` | Change restaurant details/open status; add, change and delete menu items; list orders; advance order status | Create/delete restaurants or customers; place/cancel customer orders; view the report |
| `admin` | Manage restaurants and customers; manage menus; view orders; advance or cancel eligible orders; view the report | Skip the allowed order-status flow or cancel an order after it leaves `placed` |

The classroom `X-Role` header represents a role, not an authenticated person. Customer and restaurant IDs are passed in paths or request bodies. In this simplified demo, the shared `restaurant` role can manage any restaurant ID; it is not tied to a particular restaurant account. Likewise, customer IDs are not verified against a logged-in identity. This is intentionally a teaching stand-in, not production security. Real passwords, tokens and per-account ownership checks are outside the project guide's scope.

A missing or unknown role gives **401**. A recognised role that is not permitted gives **403**.

## 3. Models and links

| Model | Main fields | Connection |
|---|---|---|
| Restaurant | `id`, `name`, `area`, `cuisine`, `open` | One restaurant has many menu items and orders |
| MenuItem | `id`, `restaurant_id`, `name`, `category`, `price`, `available` | Each menu item belongs to one restaurant |
| Customer | `id`, `name`, `phone` | One customer can place many orders |
| Order | `id`, `customer_id`, `restaurant_id`, `items`, `total`, `status`, `placed_on`, `updated_on` | **Link model:** joins one customer to one restaurant; its `items` list records the ordered menu items and price snapshots |

An order item stores `menu_item_id`, `name`, `unit_price`, `quantity` and `line_total`. The item name and price are copied into the order when it is placed. Changing a menu price later does not change an older order.

Relationship sketch:

```text
Restaurant 1 --------< MenuItem
     |
     | 1
     +----------------< Order >---------------- 1 Customer
                              |
                              +-- items: menu_item_id, quantity, price snapshot
```

## 4. Business rules

| # | Rule | Status if broken | Why the system refuses it |
|---|---|---:|---|
| 1 | Every menu item in an order must belong to the selected restaurant | 409 | One order is prepared by one restaurant |
| 2 | A closed restaurant cannot accept an order | 409 | It is not accepting orders |
| 3 | An unavailable menu item cannot be ordered | 409 | The restaurant cannot prepare it |
| 4 | The order total must be at least `MIN_ORDER_VALUE` (₹100) | 409 | Enforces the project's minimum basket value |
| 5 | An item ID may appear only once in an order | 409 | Avoids duplicate lines; increase `quantity` instead |
| 6 | Status moves must follow `ALLOWED_STATUS_MOVES` | 409 | Prevents skipping stages or moving backwards |
| 7 | Cancellation is allowed only while status is `placed` | 409 | Once preparation starts, cancellation is refused |
| 8 | A restaurant with order history cannot be deleted | 409 | Keeps historical orders meaningful |
| 9 | A customer with order history cannot be deleted | 409 | Preserves the customer reference in past orders |
| 10 | A menu item that appears in an order cannot be deleted | 409 | Preserves the menu-item reference in order history |
| 11 | Duplicate restaurant name in the same area, duplicate menu-item name in one restaurant, and duplicate customer phone are refused | 409 | Avoids duplicate records |

The main values are at the top of `main.py`: `MIN_ORDER_VALUE`, `MAX_ITEMS_PER_ORDER`, `MAX_QUANTITY_PER_ITEM` and `ALLOWED_STATUS_MOVES`. To change the minimum order to ₹150, for example, edit `MIN_ORDER_VALUE = 100` to `MIN_ORDER_VALUE = 150`.

### Order status flow

```text
placed -> preparing -> out_for_delivery -> delivered
   |
   +-> cancelled
```

Only the `placed` status can move to `cancelled`. The restaurant/admin status endpoint accepts `preparing`, `out_for_delivery` or `delivered`; it checks the dictionary before changing the order.

## 5. Endpoints

| Method and path | Who may call it | Success | Main errors |
|---|---|---:|---|
| `GET /health` | Anyone | 200 | — |
| `GET /restaurants?area=&open_only=` | Anyone | 200 | 422 for invalid parameter type |
| `GET /restaurants/{restaurant_id}` | Anyone | 200 | 404 |
| `POST /restaurants` | Admin | 201 | 401, 403, 409, 422 |
| `PATCH /restaurants/{restaurant_id}` | Restaurant, admin | 200 | 401, 403, 404, 409, 422 |
| `DELETE /restaurants/{restaurant_id}` | Admin | 204 | 401, 403, 404, 409 |
| `GET /restaurants/{restaurant_id}/menu?category=&available_only=` | Anyone | 200 | 404, 422 for invalid parameter type |
| `POST /restaurants/{restaurant_id}/menu-items` | Restaurant, admin | 201 | 401, 403, 404, 409, 422 |
| `GET /menu-items/{menu_item_id}` | Anyone | 200 | 404 |
| `PATCH /menu-items/{menu_item_id}` | Restaurant, admin | 200 | 401, 403, 404, 409, 422 |
| `DELETE /menu-items/{menu_item_id}` | Restaurant, admin | 204 | 401, 403, 404, 409 |
| `POST /customers` | Customer, admin | 201 | 401, 403, 409, 422 |
| `GET /customers` | Admin | 200 | 401, 403 |
| `GET /customers/{customer_id}` | Customer, admin | 200 | 401, 403, 404 |
| `DELETE /customers/{customer_id}` | Admin | 204 | 401, 403, 404, 409 |
| `POST /orders` | Customer | 201 | 401, 403, 404, 409, 422 |
| `GET /orders?status=&restaurant_id=` | Restaurant, admin | 200 | 401, 403, 422 |
| `GET /orders/{order_id}` | Customer, restaurant, admin | 200 | 401, 403, 404 |
| `GET /customers/{customer_id}/orders` | Customer, admin | 200 | 401, 403, 404 |
| `PATCH /orders/{order_id}/status` | Restaurant, admin | 200 | 401, 403, 404, 409, 422 |
| `POST /orders/{order_id}/cancel` | Customer, admin | 200 | 401, 403, 404, 409 |
| `GET /stats` | Admin | 200 | 401, 403 |

The API has 22 endpoints, path parameters, multiple query filters, `GET`, `POST`, `PATCH` and `DELETE`, input validation and response models.

## 6. Example requests

**Place an order** with `X-Role: customer`:

```json
{
  "customer_id": 1,
  "restaurant_id": 1,
  "items": [
    {"menu_item_id": 1, "quantity": 1},
    {"menu_item_id": 2, "quantity": 1}
  ]
}
```

This order costs ₹220 (₹180 + ₹40). A successful response has status `201` and begins with an order containing `id`, `customer_id`, `restaurant_id`, item price snapshots, `total` and `status: "placed"`.

**Advance its status** with `X-Role: restaurant` and `PATCH /orders/1/status`:

```json
{"status": "preparing"}
```

Then use `out_for_delivery` and `delivered`, in that order. Trying to jump directly from `placed` to `delivered` returns `409`.

**Filter menus and orders**:

```text
GET /restaurants?area=Indiranagar&open_only=true
GET /restaurants/1/menu?category=Main&available_only=true
GET /orders?status=placed&restaurant_id=1   (X-Role: restaurant)
```

## 7. Test checklist

Begin with a clean start: stop the server, delete the four JSON files, restart the server, and open `/docs`. The table below has more than the required 30 rows and includes role checks across the protected endpoints. The automatic script runs the same kinds of checks against a clean starter dataset.

| # | Request (method, path, role/body) | State needed | Expected status and reply/effect |
|---:|---|---|---|
| 1 | `GET /health` (no role) | Any | 200; `{"status":"ok"}` |
| 2 | `GET /restaurants` (no role) | Clean start | 200; 3 starter restaurants |
| 3 | `GET /restaurants?area=Indiranagar` | Clean start | 200; only restaurant 1 |
| 4 | `GET /restaurants?open_only=true` | Clean start | 200; only the 2 open restaurants |
| 5 | `GET /restaurants/99` | No restaurant 99 | 404 |
| 6 | `GET /restaurants/1/menu` | Clean start | 200; 3 menu items |
| 7 | `GET /restaurants/2/menu?available_only=true` | Clean start | 200; unavailable item 6 is hidden |
| 8 | `GET /restaurants/2/menu?category=Main` | Clean start | 200; only Veg Hakka Noodles |
| 9 | `GET /menu-items/99` | No item 99 | 404 |
| 10 | `POST /restaurants` without `X-Role` | Any | 401 |
| 11 | `POST /restaurants` as customer | Any | 403 |
| 12 | `POST /restaurants` as admin, valid body | Clean start | 201; new restaurant id 4 |
| 13 | `POST /restaurants` with duplicate name and area | Restaurant exists | 409 |
| 14 | `PATCH /restaurants/4` as restaurant, `{"open":false}` | Restaurant 4 exists | 200; restaurant 4 is closed |
| 15 | `PATCH /restaurants/99` as admin | No restaurant 99 | 404 |
| 16 | `DELETE /restaurants/4` as restaurant | Restaurant 4 exists | 403 |
| 17 | `POST /customers` without role | Any | 401 |
| 18 | `POST /customers` as restaurant | Any | 403 |
| 19 | `POST /customers` as customer, valid body | Clean start | 201; new customer id 3 |
| 20 | `POST /customers` with duplicate phone | Customer exists | 409 |
| 21 | `POST /customers` with invalid phone text | Any | 422 |
| 22 | `GET /customers` as customer | Any | 403 |
| 23 | `GET /customers` as admin | Customer 3 exists | 200; 3 customers |
| 24 | `GET /customers/99` as admin | No customer 99 | 404 |
| 25 | `POST /restaurants/4/menu-items` as restaurant, valid body | Restaurant 4 exists | 201; new menu item id 9 |
| 26 | `POST /restaurants/99/menu-items` as admin | No restaurant 99 | 404 |
| 27 | `POST /restaurants/4/menu-items` with price 0 | Restaurant 4 exists | 422 |
| 28 | `PATCH /menu-items/9` as customer | Item 9 exists | 403 |
| 29 | `PATCH /menu-items/9` as restaurant, change price | Item 9 exists | 200; price changed |
| 30 | `DELETE /menu-items/9` as restaurant | Item 9 has no order history | 204; item removed |
| 31 | `POST /orders` without role | Any | 401 |
| 32 | `POST /orders` as restaurant | Any | 403 |
| 33 | `POST /orders` for unknown customer 99 | No customer 99 | 404 |
| 34 | `POST /orders` for closed restaurant 3 | Restaurant 3 is closed | 409 |
| 35 | `POST /orders` with unavailable item 6 | Item 6 is unavailable | 409 |
| 36 | `POST /orders` with items from restaurants 1 and 2 | Clean start | 409; same-restaurant rule |
| 37 | `POST /orders` with item 2 only (₹40) | Restaurant 1 open | 409; below ₹100 minimum |
| 38 | `POST /orders` with item 1 and item 2 | Customer 1, restaurant 1 open | 201; total ₹220; status `placed` |
| 39 | `GET /orders` as customer | At least one order | 403 |
| 40 | `GET /orders?status=bogus` as admin | Any | 422; status must be from the fixed list |
| 41 | `GET /orders/1` as customer | Order 1 exists | 200; order details |
| 42 | `GET /customers/1/orders` as customer | Order 1 exists | 200; order 1 appears |
| 43 | `POST /orders/1/cancel` as customer | Order 1 is `placed` | 200; status becomes `cancelled` |
| 44 | `POST /orders/1/cancel` again | Order 1 is `cancelled` | 409; only placed orders can be cancelled |
| 45 | Place order 2, then `PATCH /orders/2/status` to `delivered` immediately | Order 2 is `placed` | 409; cannot skip stages |
| 46 | `PATCH /orders/2/status` to `preparing` | Order 2 is `placed` | 200; status becomes `preparing` |
| 47 | `POST /orders/2/cancel` as customer | Order 2 is `preparing` | 409; cancellation is too late |
| 48 | Advance order 2 to `out_for_delivery`, then `delivered` | Order 2 is `preparing`, then `out_for_delivery` | 200 for each allowed move |
| 49 | `DELETE /menu-items/1` as restaurant | Item 1 appears in order history | 409 |
| 50 | `DELETE /customers/1` as admin | Customer 1 has order history | 409 |
| 51 | `DELETE /restaurants/1` as admin | Restaurant 1 has order history | 409 |
| 52 | `GET /stats` as customer | Any | 403 |
| 53 | `GET /stats` as admin | At least 2 orders: one cancelled, one delivered | 200; counts and delivered revenue match the orders |
| 54 | Stop and restart the server; call `GET /restaurants`, `GET /customers` as admin and `GET /orders` as restaurant | Data was changed before restart | 200; changes remain saved |
| 55 | Replace a JSON file with damaged text and restart | The chosen data file is invalid JSON | Server starts; damaged file is preserved as `.corrupt`, starter data is recreated |
| 56 | `PATCH /restaurants/4` with no role | Restaurant 4 exists | 401 |
| 57 | `GET /customers` with no role | Any | 401 |
| 58 | `GET /customers/1` as restaurant | Customer 1 exists | 403 |
| 59 | `PATCH /menu-items/9` with no role | Item 9 exists | 401 |
| 60 | `DELETE /menu-items/9` with no role | Item 9 has no order history | 401 |
| 61 | `DELETE /menu-items/9` as customer | Item 9 has no order history | 403 |
| 62 | `GET /orders` with no role | Any | 401 |
| 63 | `GET /orders/1` with no role | Order 1 exists | 401 |
| 64 | `GET /customers/1/orders` with no role | Customer 1 exists | 401 |
| 65 | `PATCH /orders/1/status` with no role | Order 1 is placed | 401 |
| 66 | `PATCH /orders/1/status` as customer | Order 1 is placed | 403 |
| 67 | `POST /orders/1/cancel` as restaurant | Order 1 is placed | 403 |
| 68 | `POST /orders/1/cancel` with no role | Order 1 is placed | 401 |
| 69 | `DELETE /customers/3` with no role | Customer 3 has no orders | 401 |
| 70 | `DELETE /customers/3` as customer | Customer 3 has no orders | 403 |
| 71 | `GET /stats` with no role | Any | 401 |

For the status boundary, test both an allowed move and a refused move. In particular, `placed -> preparing` must work, while `placed -> delivered` must fail. For cancellation, `placed -> cancelled` must work while `preparing -> cancelled` must fail.

## 8. Automatic checks

The optional test script uses `requests` and expects a clean starter dataset:

```bash
pip install requests
python check_food_delivery.py
```

To test another port, pass the server URL:

```bash
python check_food_delivery.py http://127.0.0.1:8010
```

It runs 109 API checks in the supplied version and prints `PASS` or `FAIL` for each one. The JSON restart test is still done by hand as row 54. The damaged-file recovery can be checked as row 55.

## 9. Files

- `main.py` - complete API, using the five sections shown in the Library sample
- `check_food_delivery.py` - automatic API test checklist
- `DESIGN_NOTE.docx` - editable, formatted two-page design note for the first submission
- `DESIGN_NOTE.md` - Markdown source of the design note
- `requirements.txt` - pinned FastAPI and Uvicorn versions plus `requests`
- `.gitignore` - ignores virtual environments and generated JSON data
