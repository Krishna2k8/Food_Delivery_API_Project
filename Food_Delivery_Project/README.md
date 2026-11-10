# Food Delivery API

A small Python API project in the style of Swiggy or Zomato: restaurants, menu items, customers and
orders, three roles (customer, restaurant, admin), rules (minimum order, delivery fee, order limit,
status order, cancelling, rating) and data saved in JSON files. No database. FastAPI's `/docs`
page is the main demo interface; an optional web page is in `extra_frontend/`.

## Run

Mac / Linux:

    pip install -r requirements.txt
    uvicorn main:app --reload

Windows (Command Prompt, inside the `Food_Delivery_Project` folder):

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python -m uvicorn main:app --reload

Then open http://127.0.0.1:8000/docs

(If `python` is not found on Windows, use `py` instead. In PowerShell the activate command is
`.venv\Scripts\Activate.ps1`; if PowerShell refuses to run it, use Command Prompt.)

The first start creates `restaurants.json`, `menu_items.json`, `customers.json` and `orders.json`
next to `main.py`.

**Clean start:** stop the server (Ctrl+C), delete those four files, start the server.

    Windows:      del restaurants.json menu_items.json customers.json orders.json
    Mac / Linux:  rm restaurants.json menu_items.json customers.json orders.json

## Starter data

| Restaurant | Area | Open | Menu (id: name ₹price) |
|---|---|---|---|
| 1 Dosa Corner | Koramangala | yes | 1: Masala Dosa ₹100 · 2: Idli Vada ₹60 · 3: Filter Coffee ₹33 · 4: Ghee Podi Dosa ₹140 |
| 2 Biryani House | Indiranagar | yes | 5: Chicken Biryani ₹250 · 6: Paneer Biryani ₹220 · 7: Mutton Biryani ₹350 · 8: Gulab Jamun ₹60 (**not available**) |
| 3 Chaat Junction | Electronic City | **closed** | 9: Pani Puri ₹50 · 10: Samosa Chaat ₹70 · 11: Mango Lassi ₹80 |

Customers: 1 Asha Rao (9876543210), 2 Ravi Kumar (9123456780). No orders.

## Roles

Send a header `X-Role` with the value `customer`, `restaurant` or `admin` (in /docs, type it into
the `x-role` box). No header or an unknown role gives **401**; a known role that is not allowed
gives **403**.

| Role | May do |
|---|---|
| Anyone (no header) | `GET /health`, `GET /restaurants`, `GET /restaurants/{id}`, `GET /restaurants/{id}/menu` |
| customer | register; see a customer and their orders; see one order; place, cancel and rate an order |
| restaurant | add, change and delete menu items; open or close the restaurant; list orders; see one order; move an order to `preparing` and `out_for_delivery` |
| admin | everything above, plus: add and delete restaurants; list all customers; mark an order `delivered` (or `cancelled`); the `/stats` report |

Like the Library example, the header says only *which kind* of user is calling, not *which* customer
or restaurant. So any `customer` can look at any customer id. A real system would use a login.

## Rules

The numbers are named constants at the top of `main.py` (Section 1).

| # | Rule | Status when broken |
|---|---|---|
| 1 | All items of an order must belong to the same restaurant | 409 |
| 2 | A closed restaurant cannot take orders | 409 |
| 3 | An unavailable menu item cannot be ordered | 409 |
| 4 | The food must cost at least `MIN_ORDER` = ₹100 (before the delivery fee) | 409 |
| 5 | Delivery costs `DELIVERY_FEE` = ₹40; it is free when the food costs `FREE_DELIVERY_ABOVE` = ₹500 or more | — (a calculation) |
| 6 | A customer may have at most `MAX_ACTIVE_ORDERS` = 2 active orders (not delivered, not cancelled) | 409 |
| 7 | The status moves only along `ALLOWED_MOVES`: placed → preparing or cancelled; preparing → out_for_delivery; out_for_delivery → delivered | 409 |
| 8 | An order can be cancelled only while it is `placed` | 409 |
| 9 | An order can be rated (1–5) only after it is delivered, and only once | 409 |
| 10 | A restaurant with active orders cannot be deleted; a menu item in an active order cannot be deleted | 409 |
| 11 | The same phone cannot register twice; the same restaurant name in the same area cannot be added twice | 409 |

Validation (422, done by FastAPI): quantity 1–10 per item, 1–10 lines per order, phone exactly
10 digits, price ₹1–5000, rating 1–5, status one of the fixed words.
Makes no sense (400): the same item on two lines of one order; a PATCH with nothing to change.

Deleting a restaurant also deletes its menu. Old orders stay readable because the item names and
prices were copied into them.

## Endpoints (21)

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
| GET /stats | admin | report; `?today=` | 200 | 401 403 |

`GET /stats` gives: `total_orders`, `orders_by_status`, `orders_placed_today`, `total_revenue`
(the `total` of delivered orders), `average_rating`, `most_ordered_item_id` and
`most_ordered_item_name` (by quantity), `busiest_restaurant_id` (by number of orders). Cancelled
orders are not counted for the last three. On a tie the smaller id wins.

`?today=YYYY-MM-DD` on `POST /orders` and `GET /stats` pretends today is that date.

## Testing

1. Clean start (see above).
2. Follow the two tables below in `/docs`, in order.
3. Or run the automatic checks (needs a clean start): `python check_food.py`
   (142 checks; optional argument: server URL, e.g. `python check_food.py http://127.0.0.1:8010`)
4. Restart test by hand (row 17).

### Test checklist, part 1: the happy path

Start from a **clean start** and do the rows in order.

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
| 11 | `PATCH /orders/1/status` (restaurant)<br>`{"status":"preparing"}` | order 1 is placed | 200 | status is preparing |
| 12 | `PATCH /orders/1/status` (restaurant)<br>`{"status":"out_for_delivery"}` | order 1 is preparing | 200 | status is out_for_delivery |
| 13 | `PATCH /orders/1/status` (admin)<br>`{"status":"delivered"}` | order 1 is out_for_delivery | 200 | status is delivered |
| 14 | `POST /orders/1/rate` (customer)<br>`{"rating":5}` | order 1 is delivered | 200 | rating is 5 |
| 15 | `GET /customers/1/orders` (customer) | — | 200 | one order (order 1) |
| 16 | `GET /stats` (admin) | rows 1–14 done | 200 | total_orders 1; delivered 1; total_revenue 140; average_rating 5.0; most_ordered_item_name Masala Dosa; busiest_restaurant_id 1 |
| 17 | **Restart test.** Stop the server (Ctrl+C) and start it again. Do **not** delete the files. Then `GET /restaurants` (no role) and `GET /orders` (admin) | rows 1–16 done | 200 | the same data as before the restart: 4 restaurants, order 1 delivered with rating 5 |

### Test checklist, part 2: break it on purpose

Continue straight after part 1 (do **not** make a clean start in between). The "state needed"
column says what must already be true. Both sides of every limit are here: ₹99 refused (row 27)
and ₹100 allowed (row 7); ₹499 pays the fee (row 34) and ₹500 is free (row 35); the 2nd active
order allowed (row 35) and the 3rd refused (row 36).

| # | Request (method, path, role, body) | State needed | Expected status | Expected reply or effect |
|---|---|---|---|---|
| 18 | `POST /restaurants` (no role)<br>`{"name":"New Place","area":"Hebbal"}` | any | 401 | no X-Role header |
| 19 | `POST /restaurants` (customer)<br>`{"name":"New Place","area":"Hebbal"}` | any | 403 | a customer may not add restaurants |
| 20 | `POST /restaurants` (admin)<br>`{"name":"udupi sagar","area":"JAYANAGAR"}` | restaurant 4 exists | 409 | same name in the same area (letter case does not matter) |
| 21 | `POST /restaurants` (admin)<br>`{"area":"Hebbal"}` | any | 422 | name is missing |
| 22 | `GET /restaurants/99` (no role) | no restaurant 99 | 404 | Restaurant not found |
| 23 | `PATCH /restaurants/4` (restaurant)<br>`{}` | any | 400 | nothing to change |
| 24 | `POST /customers` (customer)<br>`{"name":"Someone Else","phone":"9000000001"}` | customer 3 exists | 409 | phone already registered |
| 25 | `POST /customers` (customer)<br>`{"name":"Short Phone","phone":"12345"}` | any | 422 | phone must be exactly 10 digits |
| 26 | `GET /customers` (customer) | any | 403 | only the admin lists all customers |
| 27 | `POST /orders` (customer)<br>`{"customer_id":1,"restaurant_id":1,"items":[{"menu_item_id":3,"quantity":3}]}` | any | 409 | **₹99 is refused** (3 × Filter Coffee at 33): below MIN_ORDER |
| 28 | `POST /orders` (customer)<br>`{"customer_id":1,"restaurant_id":1,"items":[{"menu_item_id":1,"quantity":1},{"menu_item_id":5,"quantity":1}]}` | any | 409 | Chicken Biryani belongs to restaurant 2 (rule 1) |
| 29 | `POST /orders` (customer)<br>`{"customer_id":1,"restaurant_id":3,"items":[{"menu_item_id":9,"quantity":3}]}` | restaurant 3 is closed | 409 | closed restaurant (rule 2) |
| 30 | `POST /orders` (customer)<br>`{"customer_id":1,"restaurant_id":2,"items":[{"menu_item_id":5,"quantity":1},{"menu_item_id":8,"quantity":1}]}` | item 8 is unavailable | 409 | Gulab Jamun is not available (rule 3) |
| 31 | `POST /orders` (customer)<br>`{"customer_id":1,"restaurant_id":1,"items":[{"menu_item_id":1,"quantity":11}]}` | any | 422 | quantity must be 1 to 10 |
| 32 | `POST /orders` (customer)<br>`{"customer_id":1,"restaurant_id":1,"items":[{"menu_item_id":1,"quantity":1},{"menu_item_id":1,"quantity":2}]}` | any | 400 | the same item is listed twice |
| 33 | `POST /orders` (customer)<br>`{"customer_id":1,"restaurant_id":1,"items":[{"menu_item_id":99,"quantity":1}]}` | no menu item 99 | 404 | Menu item 99 not found |
| 34 | `POST /orders` (customer)<br>`{"customer_id":2,"restaurant_id":1,"items":[{"menu_item_id":1,"quantity":4},{"menu_item_id":3,"quantity":3}]}` | customer 2 has no orders | 201 | **₹499 pays the fee.** id 2; items_total 499; delivery_fee 40; total 539 |
| 35 | `POST /orders` (customer)<br>`{"customer_id":2,"restaurant_id":1,"items":[{"menu_item_id":1,"quantity":5}]}` | customer 2 has 1 active order | 201 | **₹500 is delivered free, and the 2nd active order is allowed.** id 3; delivery_fee 0; total 500 |
| 36 | `POST /orders` (customer)<br>`{"customer_id":2,"restaurant_id":1,"items":[{"menu_item_id":1,"quantity":1}]}` | customer 2 has 2 active orders | 409 | **the 3rd active order is refused** (MAX_ACTIVE_ORDERS) |
| 37 | `PATCH /orders/2/status` (restaurant)<br>`{"status":"out_for_delivery"}` | order 2 is placed | 409 | placed cannot jump to out_for_delivery (rule 7) |
| 38 | `PATCH /orders/2/status` (restaurant)<br>`{"status":"delivered"}` | any | 403 | only the admin marks an order delivered |
| 39 | `PATCH /orders/2/status` (admin)<br>`{"status":"eaten"}` | any | 422 | not one of the allowed status words |
| 40 | `POST /orders/3/rate` (customer)<br>`{"rating":4}` | order 3 is placed | 409 | only a delivered order can be rated (rule 9) |
| 41 | `POST /orders/1/rate` (customer)<br>`{"rating":3}` | order 1 already rated | 409 | an order is rated only once (rule 9) |
| 42 | `POST /orders/1/rate` (customer)<br>`{"rating":6}` | any | 422 | rating must be 1 to 5 |
| 43 | `DELETE /restaurants/1` (admin) | orders 2 and 3 are active | 409 | restaurant has active orders (rule 10) |
| 44 | `DELETE /menu-items/1` (restaurant) | orders 2 and 3 are active | 409 | item is in an active order (rule 10) |
| 45 | `POST /orders/2/cancel` (customer) | order 2 is placed | 200 | status is cancelled |
| 46 | `POST /orders/2/cancel` (customer) | order 2 is cancelled | 409 | cannot cancel twice |
| 47 | `PATCH /orders/3/status` (restaurant)<br>`{"status":"preparing"}` | order 3 is placed | 200 | status is preparing |
| 48 | `POST /orders/3/cancel` (customer) | order 3 is preparing | 409 | too late to cancel: only while placed (rule 8) |
| 49 | `POST /orders?today=2026-12-25` (customer)<br>`{"customer_id":2,"restaurant_id":2,"items":[{"menu_item_id":5,"quantity":1}]}` | customer 2 has 1 active order | 201 | id 4; placed_on is 2026-12-25; total 290 |
| 50 | `GET /stats?today=2026-12-25` (admin) | row 49 done | 200 | orders_placed_today is 1; total_orders is 4 |
| 51 | `GET /orders?status=cancelled` (admin) | order 2 is cancelled | 200 | one order (order 2) |
| 52 | `GET /orders?restaurant_id=2` (restaurant) | order 4 exists | 200 | one order (order 4) |
| 53 | `GET /orders?status=bogus` (admin) | any | 422 | status must be one of the five status words |
| 54 | `GET /orders` (customer) | any | 403 | a customer may not list all orders |
| 55 | `GET /stats` (customer) | any | 403 | only the admin sees the report |
| 56 | `DELETE /menu-items/12` (restaurant) | item 12 was never ordered | 204 | no body; the item is gone from GET /restaurants/4/menu |
| 57 | `DELETE /restaurants/4` (admin) | restaurant 4 has no orders | 204 | no body |
| 58 | `GET /restaurants/4` (no role) | row 57 done | 404 | the restaurant is gone |

### After the exception-handling class

Replace `load_data` with the version in `load_data_with_try_except.py`, then add this row:

| # | Request | State needed | Expected | Expected reply or effect |
|---|---|---|---|---|
| 59 | Stop the server. Open `orders.json`, type rubbish into it, save. Start the server. `GET /orders` (admin) | server stopped | the server starts; 200 | a warning is printed; the bad file is kept as `orders.json.damaged`; the list is `[]` |

## Optional front end (`extra_frontend/`)

A web page for the same API, for demos. `main.py` does not import it or know about it: the folder
has its own small starter file that imports `app` from `main.py` and adds the pages at `/app`.

Run this **instead of** the usual uvicorn command, from the `Food_Delivery_Project` folder:

    python -m uvicorn extra_frontend.run_with_frontend:app --reload

Then open http://127.0.0.1:8000/app/ (and http://127.0.0.1:8000/docs still works).

- Choose Guest, Customer, Restaurant or Admin at the top. That choice is sent as the `X-Role` header.
- The dark panel on the right lists every request the page made and the status code the API gave
  back, with the error message for 4xx replies. It is the link between the page and `main.py`.
- It needs no internet and no extra packages.
- To remove it, delete the `extra_frontend` folder. Nothing else changes, and
  `uvicorn main:app --reload` and `check_food.py` work exactly as before.

## Files

- `main.py` - the whole API, five sections: settings, storage, models, helpers, endpoints
- `check_food.py` - automatic test checklist
- `load_data_with_try_except.py` - the second version of `load_data`, to paste in later (not used by `main.py`)
- `DESIGN_NOTE.md` - the design note (guideline Section 9)
- `EXPLAIN.md` - a walkthrough of `main.py`, TA questions and live changes
- `extra_frontend/` - optional web page (`index.html`, `style.css`, `app.js`, `run_with_frontend.py`)
- `requirements.txt`, `.gitignore`
