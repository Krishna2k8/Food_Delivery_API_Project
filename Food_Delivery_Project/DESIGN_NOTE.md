# Design Note — Food Delivery API

*(Guideline Section 9. Domain taken from Section 7.2.)*

## 1 · Domain

**Food Delivery API (Swiggy / Zomato style).** Customers look at restaurants and their menus and
order food. Each order belongs to one customer and one restaurant, and moves through stages
(placed → preparing → out for delivery → delivered) until it arrives; the customer can then rate it.
Three kinds of people use it: **customers** who order, **restaurants** who manage their menu and
cook the orders, and an **admin** who runs the platform. Payments, maps, OTPs and a front end are
out of scope: money is a whole number of rupees and the demo runs in FastAPI's `/docs` page.

## 2 · Roles

The role is sent in the `X-Role` header, like the Library example. No header or an unknown role
gives 401; a known role that is not allowed gives 403.

| Role | May do | May not do |
|---|---|---|
| **Anyone** (no header) | look at restaurants and menus; `GET /health` | everything else (401) |
| **customer** | register; see a customer and their orders; place an order; cancel an order; rate an order | change menus or restaurants, list all customers or orders, change an order's status, see the report (403) |
| **restaurant** | add, change and delete menu items; open or close the restaurant; list orders; move an order to preparing and out_for_delivery | add or delete restaurants, register or list customers, place / cancel / rate orders, mark an order delivered, see the report (403) |
| **admin** | everything above, plus add and delete restaurants, list all customers, mark an order delivered, see the report | nothing is refused by role |

## 3 · Models

Saved in `restaurants.json`, `menu_items.json`, `customers.json` and `orders.json`.

| Model | Fields (type) | Validation |
|---|---|---|
| **Restaurant** | id (int), name (str), area (str), open (bool) | name 2–60 characters; area 2–40 characters; name + area unique |
| **MenuItem** | id (int), restaurant_id (int), name (str), price (int, whole rupees), is_veg (bool), available (bool) | name 2–60 characters; price 1–5000; the restaurant must exist |
| **Customer** | id (int), name (str), phone (str) | name 2–60 characters; phone exactly 10 digits; phone unique |
| **Order** — the **LINK model** | id (int), customer_id (int), restaurant_id (int), items (list of {menu_item_id (int), name (str), price (int), quantity (int)}), items_total (int), delivery_fee (int), total (int), status (str), placed_on (str, a date like "2026-11-20"), rating (int, or null until rated) | 1–10 lines; quantity 1–10 per line; customer, restaurant and every item must exist; rating 1–5 |

    Customer 1 ───────< Order >─────── 1 Restaurant
                          │
                          └── items: copies of MenuItem (name and price at the time of ordering)

    Restaurant 1 ───────< MenuItem

One customer can have many orders; one restaurant can have many orders and many menu items.
An order stores `customer_id` and `restaurant_id`, so it points to both. The name and price of each
item are **copied** into the order when it is placed, because menu prices can change later.

**Status order:** `placed → preparing → out_for_delivery → delivered`, and `placed → cancelled`.
Kept in one dictionary, `ALLOWED_MOVES`.

## 4 · Endpoints (21)

| Method and path | Who | Does | Success | Errors |
|---|---|---|---|---|
| GET /health | anyone | server alive | 200 | — |
| GET /restaurants | anyone | list; `?area=`, `?open_only=true` | 200 | — |
| GET /restaurants/{id} | anyone | one restaurant | 200 | 404 |
| POST /restaurants | admin | add a restaurant | 201 | 401 403 409 422 |
| PATCH /restaurants/{id} | restaurant, admin | change fields; open or close | 200 | 400 401 403 404 409 422 |
| DELETE /restaurants/{id} | admin | delete a restaurant and its menu | 204 | 401 403 404 409 |
| GET /restaurants/{id}/menu | anyone | menu; `?veg_only=true`, `?max_price=` | 200 | 404 |
| POST /restaurants/{id}/menu | restaurant, admin | add a menu item | 201 | 401 403 404 422 |
| PATCH /menu-items/{id} | restaurant, admin | change a menu item | 200 | 400 401 403 404 422 |
| DELETE /menu-items/{id} | restaurant, admin | delete a menu item | 204 | 401 403 404 409 |
| POST /customers | customer, admin | register | 201 | 401 403 409 422 |
| GET /customers | admin | list customers | 200 | 401 403 |
| GET /customers/{id} | customer, admin | one customer | 200 | 401 403 404 |
| GET /customers/{id}/orders | customer, admin | all orders of one customer | 200 | 401 403 404 |
| POST /orders | customer, admin | place an order; `?today=` | 201 | 400 401 403 404 409 422 |
| GET /orders | restaurant, admin | list; `?status=`, `?restaurant_id=` | 200 | 401 403 422 |
| GET /orders/{id} | any role | one order | 200 | 401 404 |
| PATCH /orders/{id}/status | restaurant, admin | move to the next status | 200 | 401 403 404 409 422 |
| POST /orders/{id}/cancel | customer, admin | cancel while placed | 200 | 401 403 404 409 |
| POST /orders/{id}/rate | customer, admin | rate a delivered order | 200 | 401 403 404 409 422 |
| GET /stats | admin | report: total orders, orders by status, orders placed today, revenue from delivered orders, average rating, most-ordered item, busiest restaurant; `?today=` | 200 | 401 403 |

## 5 · Rules

| # | Rule | Real-world reason | Status |
|---|---|---|---|
| 1 | All items of an order must belong to the same restaurant | one kitchen cooks one order, one rider collects it | 409 |
| 2 | A closed restaurant cannot take orders | nobody is there to cook | 409 |
| 3 | An unavailable menu item cannot be ordered | the kitchen has run out | 409 |
| 4 | The food must cost at least MIN_ORDER = ₹100 (before the fee) | a tiny order is not worth a delivery trip | 409 |
| 5 | Delivery fee DELIVERY_FEE = ₹40; free when the food costs FREE_DELIVERY_ABOVE = ₹500 or more (one helper function) | big orders are rewarded | — |
| 6 | A customer may have at most MAX_ACTIVE_ORDERS = 2 active orders | stops fake or accidental repeat orders | 409 |
| 7 | Status moves only follow ALLOWED_MOVES (no skipping, no going back) | food cannot be delivered before it is cooked | 409 |
| 8 | An order can be cancelled only while it is placed | once cooking starts the food is wasted | 409 |
| 9 | An order can be rated (1–5) only after delivery, and only once | you cannot judge food you have not received | 409 |
| 10 | A restaurant with active orders cannot be deleted; a menu item in an active order cannot be deleted | customers are waiting for that food | 409 |
| 11 | The same phone cannot register twice; the same restaurant name in the same area cannot be added twice | no duplicate accounts or listings | 409 |

Validation (422): quantity 1–10, 1–10 lines per order, phone 10 digits, price 1–5000, rating 1–5.

## 6 · Test checklist (first 10 rows)

From a clean start, in order. The full checklist (58 rows) is in `README.md`.

| # | Request (method, path, role, body) | State needed | Expected status | Expected reply or effect |
|---|---|---|---|---|
| 1 | `GET /restaurants` (no role) | clean start | 200 | 3 restaurants |
| 2 | `GET /restaurants?open_only=true` (no role) | clean start | 200 | 2 restaurants (Chaat Junction is closed) |
| 3 | `GET /restaurants/1/menu?veg_only=true&max_price=60` (no role) | clean start | 200 | 2 items: Idli Vada and Filter Coffee |
| 4 | `POST /restaurants` (admin)<br>`{"name":"Udupi Sagar","area":"Jayanagar"}` | — | 201 | id is 4; open is true |
| 5 | `POST /restaurants/4/menu` (restaurant)<br>`{"name":"Rava Idli","price":70,"is_veg":true}` | row 4 done | 201 | id is 12; restaurant_id is 4; available is true |
| 6 | `POST /customers` (customer)<br>`{"name":"Meera Nair","phone":"9000000001"}` | — | 201 | id is 3 |
| 7 | `POST /orders` (customer)<br>`{"customer_id":1,"restaurant_id":1,"items":[{"menu_item_id":1,"quantity":1}]}` | — | 201 | **₹100 is allowed.** id 1; items_total 100; delivery_fee 40; total 140; status placed; rating null |
| 8 | `PATCH /menu-items/1` (restaurant)<br>`{"price":110}` | order 1 exists | 200 | menu price is now 110 |
| 9 | `GET /orders/1` (customer) | row 8 done | 200 | the order still shows price 100 and total 140 (the price was copied) |
| 10 | `PATCH /menu-items/1` (restaurant)<br>`{"price":100}` | — | 200 | price is back to 100 (needed for the later rows) |

## 7 · Team

| # | Name | Roll number | Team job | Builds (endpoints) |
|---|---|---|---|---|
| 1 | ____________ | ____________ | Team lead (plan, checklist, README) | **Restaurants:** GET /restaurants · GET /restaurants/{id} · POST /restaurants · PATCH /restaurants/{id} |
| 2 | ____________ | ____________ | Integrator (the only one who edits the real main.py) | **Menu:** GET /restaurants/{id}/menu · POST /restaurants/{id}/menu · PATCH /menu-items/{id} · DELETE /menu-items/{id} |
| 3 | ____________ | ____________ | Reviewer for member 4 | **Customers:** POST /customers · GET /customers · GET /customers/{id} · GET /customers/{id}/orders |
| 4 | ____________ | ____________ | Reviewer for member 5 | **Placing orders:** POST /orders (rules 1–6) · GET /orders · GET /orders/{id} |
| 5 | ____________ | ____________ | Reviewer for member 6 | **Life of an order:** PATCH /orders/{id}/status (rule 7) · POST /orders/{id}/cancel (rule 8) · POST /orders/{id}/rate (rule 9) |
| 6 | ____________ | ____________ | Tester (runs check_food.py after every merge) | **Admin and report:** DELETE /restaurants/{id} (rule 10) · GET /stats · GET /health, plus the try/except in load_data |

Built **together** on one screen first (guideline steps 5–8): the five sections, storage
(`save_data`, `load_data`), the models, and the helpers `check_role`, `find_...` and `next_id`.

If the team has **5** members, delete row 6 and give its three endpoints to members 4 and 5
(DELETE /restaurants/{id} to member 4; GET /stats and GET /health to member 5). If the team has
**4**, also share member 5's three endpoints among members 1–3. (With fewer people, some members
then have more than 4 endpoints; 21 endpoints cannot be shared any other way.)
