# EXPLAIN.md — understanding main.py

Read this with `main.py` open next to it. Line numbers are for the file as delivered; if you add
lines they shift, so each one also says what text to search for (Ctrl+F).

**How to study:** the guideline says every member must be able to explain every line. Reading is
not enough. Run the server, try each endpoint in `/docs`, and for each one say out loud what every
line does. Better still, type your own endpoints again from an empty function.

---

## Part A · Walkthrough, section by section

### Before Section 1: imports and `app` (lines 52–65)

| Line | What it is |
|---|---|
| `import json` | turns Python lists/dictionaries into text for a file, and back |
| `import os` | file paths, and "does this file exist?" |
| `from datetime import date` | today's date, and the type of `?today=` |
| `from typing import Literal` | "this value must be one of these exact words" |
| `from fastapi import FastAPI, Header, HTTPException` | the app, reading a header, and stopping with an error code |
| `from pydantic import BaseModel, Field` | models that check incoming and outgoing data |
| `app = FastAPI(...)` | creates the API. `uvicorn main:app` means "in main.py, run the thing called app" |

### Section 1 · Settings (lines 67–98)

Every number a rule uses has a **name**: `MIN_ORDER`, `DELIVERY_FEE`, `FREE_DELIVERY_ABOVE`,
`MAX_ACTIVE_ORDERS`, `MAX_QUANTITY`, `MAX_LINES`, `MIN_RATING`, `MAX_RATING`. The code below never
writes `100` or `40`; it writes the name. So a rule changes by editing **one line** here.

Three more settings are lists or a dictionary:

- `ALL_ROLES` — the three role words the system knows.
- `ALLOWED_MOVES` — a dictionary. The **key** is the status an order has now; the **value** is the
  list of statuses it may change to. `"delivered": []` means "from delivered you can go nowhere".
- `FINISHED_STATUSES` — an order with one of these statuses is over. Any other order is *active*.
- `ADMIN_ONLY_STATUSES` — statuses that only the admin may set.

### Section 2 · Storage (lines 100–174)

- `DATA_FOLDER` is the folder where `main.py` sits. The four `..._FILE` names are the full paths of
  the four JSON files.
- `STARTER_...` lists are what the service contains the very first time.
- `save_data(path, data)` opens the file for **w**riting and dumps the whole list into it.
  `indent=2` makes the file readable; `ensure_ascii=False` keeps non-English letters as they are.
- `load_data(path, starter)`: if the file does **not** exist, it makes a copy of the starter list,
  saves it, and returns it. If the file exists, it reads it with `json.load`.
  `dict(item)` makes a *copy* of each dictionary so the starter list itself is never changed.
- The marked comment inside `load_data` is where try/except goes after that class. The finished
  version is in `load_data_with_try_except.py`.
- The last four lines run **once**, when the server starts: `restaurants`, `menu_items`,
  `customers` and `orders` are ordinary Python lists of dictionaries. Every endpoint works on
  these lists, and calls `save_data` after each change so the file always matches.

### Section 3 · Models (lines 177–296)

A Pydantic model is a class that lists fields and their types. FastAPI uses it to **check** data.

- **In** models (`RestaurantIn`, `MenuItemIn`, `CustomerIn`, `OrderIn`, `OrderLineIn`, `StatusIn`,
  `RatingIn`) describe what the caller must send. If the body does not fit, FastAPI answers **422**
  by itself, before our function even starts.
- **Update** models (`RestaurantUpdate`, `MenuItemUpdate`) are for PATCH. Every field is
  `... | None` with `default=None`, so the caller may send only the fields they want to change.
- **Out** models (`RestaurantOut`, `OrderOut`, ...) describe what we send back. They are used as
  `response_model=...` on the endpoints.
- `Field(...)` holds the checking rules: `min_length`, `max_length` for text; `ge` (greater or
  equal), `le` (less or equal), `gt` (greater than) for numbers; `pattern` for a regular
  expression; `default` for a value used when nothing is sent; `examples` for what `/docs` shows.
- `phone: str = Field(pattern=r"^[0-9]{10}$")` — `^` start, `[0-9]` a digit, `{10}` exactly ten of
  them, `$` end. So: exactly 10 digits and nothing else.
- `items: list[OrderLineIn] = Field(min_length=1, max_length=MAX_LINES)` — a list of 1 to 10 lines,
  and every line is checked by `OrderLineIn` (quantity 1 to `MAX_QUANTITY`).
- `status: Literal["preparing", ...]` — only these exact words are accepted; anything else is 422.
- `rating: int | None` — a whole number, or `None` (JSON shows it as `null`).

### Section 4 · Helpers (lines 298–418)

| Helper | What it does |
|---|---|
| `check_role(x_role, allowed)` | role not one of the three → **401**. Role known but not in `allowed` → **403**. Otherwise nothing happens and the endpoint continues |
| `find_restaurant`, `find_menu_item`, `find_customer`, `find_order` | loop through the list; return the dictionary with that id; if the loop ends without finding it, **404** |
| `next_id(items)` | finds the highest id in a list and returns it + 1 |
| `is_active(order)` | `True` if the status is not delivered and not cancelled |
| `active_orders_of_customer`, `active_orders_of_restaurant` | count active orders with a loop and `count = count + 1` |
| `menu_item_in_active_order(menu_item_id)` | a loop inside a loop: every active order, every line in it |
| `restaurant_name_taken(name, area, skip_id)` | is there *another* restaurant with this name and area? `.lower()` makes the comparison ignore capital letters. `skip_id` lets a restaurant keep its own name when it is being changed |
| `calculate_delivery_fee(items_total)` | the **only** place the fee is decided: 0 if the food costs `FREE_DELIVERY_ABOVE` or more, else `DELIVERY_FEE` |
| `check_move(order, new_status)` | looks up the order's current status in `ALLOWED_MOVES`; if `new_status` is not in that list → **409** |
| `pick_today(today)` | the real date, unless `?today=` was sent |

`raise HTTPException(...)` **stops the function immediately** and sends the error. That is why the
checks can simply be written one after another: if a check fails, nothing below it runs.

### Section 5 · Endpoints (lines 421–824)

Every endpoint has two parts: the `@app...` line (method, path, success status code, response
model) and the function below it.

Where the function's inputs come from:

- a name that also appears in the path in `{...}` (like `restaurant_id`) → the **path**
- `body: SomeModelIn` → the JSON **body**
- `x_role: str | None = Header(default=None)` → the **X-Role header** (FastAPI turns `x_role` into `X-Role`)
- anything else with a default (like `open_only: bool = False`, `today: date | None = None`) → a **query parameter** after `?`

Every endpoint that changes data does the same steps in the same order:

1. `check_role(...)` — 401 / 403
2. `find_...(...)` — 404
3. the rules — 409 (or 400 for a request that makes no sense)
4. change the list or dictionary
5. `save_data(...)`
6. `return ...`

Nothing is changed before all the checks have passed. That is why a refused request never leaves
half-finished data behind.

**The endpoint to know best: `place_order` (POST /orders, line 622).**

1. `check_role` — customer or admin.
2. Exists? The customer, the restaurant, and every menu item. The found menu items go into the
   list `chosen`, in the same order as the lines the customer sent.
3. Rules, first failure stops:
   same item listed twice (400) → restaurant closed (409) → an item from another restaurant (409)
   → an item not available (409).
4. Build `order_lines`: for each line, **copy** the id, name and price from the menu item and add
   the quantity; add `price * quantity` to `items_total`. `position` counts 0, 1, 2... so that
   `chosen[position]` is the menu item of the current line.
5. Two more rules that need the total: below `MIN_ORDER` (409) → too many active orders (409).
6. Fee from `calculate_delivery_fee`, build the order dictionary with status `"placed"`,
   `append`, `save_data`, return it (201).

**Other points worth knowing**

- `update_restaurant` / `update_menu_item`: `body.model_dump(exclude_none=True)` turns the body
  into a dictionary with only the fields that were actually sent. The `for key, value in
  changes.items()` loop copies each one into the stored dictionary.
- `delete_restaurant`: also removes that restaurant's menu items. It builds `kept_items` (the items
  of the other restaurants), then `menu_items.clear()` and `menu_items.extend(kept_items)` so the
  **same list** is refilled (making a new list would leave the other functions looking at the old one).
- `change_order_status`: a second role check — if the new status is in `ADMIN_ONLY_STATUSES` and
  the role is not admin → 403. Then `check_move`.
- `cancel_order`: just `check_move(order, "cancelled")`. Rule 8 ("only while placed") is not
  written as an `if`; it comes from `ALLOWED_MOVES`, where only `"placed"` lists `"cancelled"`.
- DELETE endpoints return nothing: status 204 means "done, no body".
- `stats`: one loop over all orders fills several counters. `times_ordered.get(item_id, 0) + ...`
  means "the count so far, or 0 if this is the first time". After the loop, `sorted(...)` walks the
  ids from small to large and keeps the one with the highest count, so on a tie the smaller id wins.

---

## Part B · 10 likely TA questions

**1. What is the difference between 401 and 403, and where is it decided?**
401 = we do not know who you are (no `X-Role`, or a word that is not a role). 403 = we know your
role, but it may not do this. Both are in `check_role` (line 305): the first `if` gives 401, the
second gives 403.

**2. Why do you copy the name and price into the order instead of storing only the item id?**
Menu prices change. If the order only stored the id, an old order's total would no longer match
its items after a price change, and a deleted item would leave a hole. The copy happens in
`place_order` where `order_lines.append({...})` is built. Checklist rows 8–9 prove it.

**3. How do you stop an order going from placed straight to delivered?**
`ALLOWED_MOVES` (line 86) lists, for every status, what may come next. `check_move` (line 407)
raises 409 if the new status is not in that list. `"placed"` only allows `"preparing"` and
`"cancelled"`.

**4. What happens, step by step, when a customer orders food worth ₹99?**
Role OK → customer, restaurant and items exist → no duplicate, restaurant open, items belong and
are available → `items_total` is 99 → `if items_total < MIN_ORDER` is true → 409. Nothing was
appended and nothing was saved.

**5. Why `>=` in the active-order check and `<` in the minimum-order check?**
`active_orders_of_customer(...) >= MAX_ACTIVE_ORDERS` runs *before* the new order is added: with 2
already active, a third must be refused, and 2 >= 2 is true. `items_total < MIN_ORDER` refuses 99
but allows exactly 100. Both boundaries are in the checklist (rows 7, 27, 35, 36).

**6. What is the difference between an In model and an Out model?**
In = what the caller sends; it has `Field(...)` rules and never has an `id` (the server chooses
the id). Out = what we reply; used in `response_model`, so `/docs` shows the shape and FastAPI
sends only those fields.

**7. Where does 422 come from? You never write `status_code=422`.**
From FastAPI and Pydantic. When the body, a path number or a query value does not fit the model or
type (`quantity` 11, phone with 9 digits, `?status=bogus`), FastAPI replies 422 before our function runs.

**8. What happens to the data when the server restarts? What if I delete orders.json?**
Every change calls `save_data`, so the files always hold the latest lists. At start, `load_data`
reads them back. If a file is missing, `load_data` creates it again from the starter data (orders
start empty).

**9. How do you decide whether a restaurant can be deleted?**
`delete_restaurant` calls `active_orders_of_restaurant`, which counts that restaurant's orders for
which `is_active` is true (status not in `FINISHED_STATUSES`). More than 0 → 409. Finished orders
do not block it.

**10. Why is the delivery fee in its own function?**
So there is one place to change it. `place_order` only calls `calculate_delivery_fee(items_total)`.
A request like "add a ₹10 surcharge" or "free delivery above ₹300" is an edit in one small function
or one constant.

**Honest limits to mention if asked:** `X-Role` is not real security, and it says only the *kind*
of user, so any customer can look at any customer's orders and any restaurant can change any menu
(the Library example has the same simplification). Ids are "highest + 1", so the id of a deleted
last item can be reused.

---

## Part C · 5 likely live changes

After any change, save the file (with `--reload` the server restarts itself) and try it in `/docs`.
`check_food.py` expects the original numbers, so the checks for the rule you changed will FAIL.
That is expected; change the number back afterwards.

**1. "Change the minimum order to ₹150."** Line 72:

    MIN_ORDER = 100     →     MIN_ORDER = 150

Show it: 1 × Masala Dosa (₹100) is now refused with 409; 2 × Masala Dosa is accepted.

**2. "Make delivery ₹50, free above ₹300."** Lines 73 and 74:

    DELIVERY_FEE = 40            →     DELIVERY_FEE = 50
    FREE_DELIVERY_ABOVE = 500    →     FREE_DELIVERY_ABOVE = 300

Show it: 1 × Masala Dosa → delivery_fee 50; 3 × Masala Dosa (₹300) → delivery_fee 0.

**3. "Let a customer have 3 active orders."** Line 75:

    MAX_ACTIVE_ORDERS = 2     →     MAX_ACTIVE_ORDERS = 3

Show it: the same customer's 3rd order is accepted and the 4th is refused.

**4. "Allow cancelling while the food is being prepared."** Line 88, inside `ALLOWED_MOVES`:

    "preparing": ["out_for_delivery"],     →     "preparing": ["out_for_delivery", "cancelled"],

Show it: place an order, move it to preparing, then `POST /orders/{id}/cancel` → 200.
No other line changes, because `cancel_order` uses `check_move`.

**5. "Let the restaurant mark an order delivered."** Line 98:

    ADMIN_ONLY_STATUSES = ["delivered", "cancelled"]     →     ADMIN_ONLY_STATUSES = ["cancelled"]

Show it: with role `restaurant`, move an out_for_delivery order to delivered → 200 (it was 403).

**Three more that are also one line**

- "Ratings out of 10": line 79, `MAX_RATING = 10`.
- "At most 5 of one item": line 76, `MAX_QUANTITY = 5` (quantity 6 then gives 422).
- "Add a ₹10 packing charge to every order": in `calculate_delivery_fee` (line 400) change the last
  line `return DELIVERY_FEE` to `return DELIVERY_FEE + 10` — or, if they mean *every* order, add 10
  to both `return` lines.
