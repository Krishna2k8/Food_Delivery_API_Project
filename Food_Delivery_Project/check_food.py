"""
check_food.py  -  runs the whole test checklist against a RUNNING Food Delivery API
====================================================================================
You do NOT need to understand every line of this file. It does by machine what
the checklist in the README asks you to do by hand in /docs: send a request, and
compare the status code (and sometimes the reply) with what we expect.

HOW TO USE IT
    1. Stop the server, delete restaurants.json, menu_items.json, customers.json
       and orders.json (the script needs a CLEAN start), then start the server:
            uvicorn main:app
    2. In a second terminal (once):   pip install requests
    3. Run:                           python check_food.py
       To test a server on another port:  python check_food.py http://127.0.0.1:8010
    4. Every line says PASS or FAIL. To run it again, repeat from step 1.

The script expects the rule numbers that main.py starts with (MIN_ORDER = 100,
DELIVERY_FEE = 40, FREE_DELIVERY_ABOVE = 500, MAX_ACTIVE_ORDERS = 2). If you
change one of them, the checks about that rule will say FAIL. That is correct.

The restart test cannot be automated here. Do it by hand at the end:
stop the server, start it again, and call GET /restaurants and GET /orders.
"""
import sys
from datetime import date

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ADMIN = {"X-Role": "admin"}
REST = {"X-Role": "restaurant"}
CUST = {"X-Role": "customer"}

passed = 0
failed = 0


def check(name, response, expected_status, test=None):
    """Compare the status code, and (if `test` is given) the reply body."""
    global passed, failed
    ok = response.status_code == expected_status
    if ok and test is not None:
        ok = test(response.json())
    if ok:
        passed = passed + 1
        print("PASS  " + name)
    else:
        failed = failed + 1
        print("FAIL  " + name + "   (got " + str(response.status_code) +
              ", expected " + str(expected_status) + ")   " + response.text[:150])


def get(path, headers=None):
    return requests.get(BASE + path, headers=headers)


def post(path, body=None, headers=None):
    return requests.post(BASE + path, json=body, headers=headers)


def patch(path, body, headers=None):
    return requests.patch(BASE + path, json=body, headers=headers)


def delete(path, headers=None):
    return requests.delete(BASE + path, headers=headers)


def order(customer_id, restaurant_id, lines):
    """Build the body of POST /orders. lines is a list of (menu_item_id, quantity)."""
    items = []
    for menu_item_id, quantity in lines:
        items.append({"menu_item_id": menu_item_id, "quantity": quantity})
    return {"customer_id": customer_id, "restaurant_id": restaurant_id, "items": items}


today = date.today().isoformat()

# ---------------------------------------------------------------- clean start?
try:
    start_restaurants = get("/restaurants").json()
    start_customers = get("/customers", ADMIN).json()
    start_orders = get("/orders", ADMIN).json()
except requests.exceptions.ConnectionError:
    print("Cannot reach the server at " + BASE + ". Is it running?")
    sys.exit(1)
if len(start_restaurants) != 3 or len(start_customers) != 2 or len(start_orders) != 0:
    print("The data is not a clean start. Stop the server, delete restaurants.json,")
    print("menu_items.json, customers.json and orders.json, start the server again,")
    print("then re-run.")
    sys.exit(1)

print("\n--- 1. Health and browsing (no role needed) ---")
check("GET /health", get("/health"), 200, lambda d: d == {"status": "ok"})
check("GET /restaurants lists the 3 starter restaurants", get("/restaurants"), 200, lambda d: len(d) == 3)
check("GET /restaurants?open_only=true hides the closed one", get("/restaurants?open_only=true"), 200,
      lambda d: [r["id"] for r in d] == [1, 2])
check("GET /restaurants?area=koramangala filters by area", get("/restaurants?area=koramangala"), 200,
      lambda d: len(d) == 1 and d[0]["name"] == "Dosa Corner")
check("GET /restaurants/1", get("/restaurants/1"), 200, lambda d: d["open"] is True)
check("GET /restaurants/99 unknown restaurant -> 404", get("/restaurants/99"), 404)
check("GET /restaurants/1/menu has 4 items", get("/restaurants/1/menu"), 200, lambda d: len(d) == 4)
check("GET /restaurants/2/menu?veg_only=true", get("/restaurants/2/menu?veg_only=true"), 200,
      lambda d: [m["id"] for m in d] == [6, 8])
check("GET /restaurants/1/menu?max_price=60", get("/restaurants/1/menu?max_price=60"), 200,
      lambda d: [m["id"] for m in d] == [2, 3])
check("GET /restaurants/99/menu -> 404", get("/restaurants/99/menu"), 404)

print("\n--- 2. Roles on adding a restaurant ---")
udupi = {"name": "Udupi Sagar", "area": "Jayanagar"}
check("POST /restaurants without a role -> 401", post("/restaurants", udupi), 401)
check("POST /restaurants with an unknown role -> 401", post("/restaurants", udupi, {"X-Role": "chef"}), 401)
check("POST /restaurants as customer -> 403", post("/restaurants", udupi, CUST), 403)
check("POST /restaurants as restaurant -> 403", post("/restaurants", udupi, REST), 403)
check("POST /restaurants as admin -> 201", post("/restaurants", udupi, ADMIN), 201,
      lambda d: d["id"] == 4 and d["open"] is True)
check("same name, same area (other case) -> 409",
      post("/restaurants", {"name": "udupi sagar", "area": "JAYANAGAR"}, ADMIN), 409)
check("same name, another area -> 201",
      post("/restaurants", {"name": "Udupi Sagar", "area": "Whitefield"}, ADMIN), 201, lambda d: d["id"] == 5)

print("\n--- 3. Validation on restaurants (422) ---")
check("name missing", post("/restaurants", {"area": "Jayanagar"}, ADMIN), 422)
check("area too short", post("/restaurants", {"name": "Tiny", "area": "J"}, ADMIN), 422)
check("open is not true/false", patch("/restaurants/4", {"open": "maybe"}, REST), 422)

print("\n--- 4. Changing a restaurant (open / close) ---")
check("PATCH close restaurant 4 as restaurant", patch("/restaurants/4", {"open": False}, REST), 200,
      lambda d: d["open"] is False and d["name"] == "Udupi Sagar")
check("PATCH open it again as admin", patch("/restaurants/4", {"open": True}, ADMIN), 200,
      lambda d: d["open"] is True)
check("PATCH as customer -> 403", patch("/restaurants/4", {"open": False}, CUST), 403)
check("PATCH without a role -> 401", patch("/restaurants/4", {"open": False}), 401)
check("PATCH unknown restaurant -> 404", patch("/restaurants/99", {"open": False}, REST), 404)
check("PATCH with nothing to change -> 400", patch("/restaurants/4", {}, REST), 400)
check("PATCH restaurant 5 into the same name and area as 4 -> 409",
      patch("/restaurants/5", {"area": "Jayanagar"}, ADMIN), 409)

print("\n--- 5. Menu items ---")
rava = {"name": "Rava Idli", "price": 70, "is_veg": True}
check("POST menu item without a role -> 401", post("/restaurants/4/menu", rava), 401)
check("POST menu item as customer -> 403", post("/restaurants/4/menu", rava, CUST), 403)
check("POST menu item as restaurant -> 201", post("/restaurants/4/menu", rava, REST), 201,
      lambda d: d["id"] == 12 and d["restaurant_id"] == 4 and d["available"] is True)
check("POST menu item price 0 -> 422",
      post("/restaurants/4/menu", {"name": "Free Vada", "price": 0, "is_veg": True}, REST), 422)
check("POST menu item without is_veg -> 422",
      post("/restaurants/4/menu", {"name": "Mystery", "price": 50}, REST), 422)
check("POST menu item to unknown restaurant -> 404", post("/restaurants/99/menu", rava, REST), 404)
check("PATCH menu item price", patch("/menu-items/12", {"price": 75}, REST), 200,
      lambda d: d["price"] == 75 and d["name"] == "Rava Idli")
check("PATCH menu item as customer -> 403", patch("/menu-items/12", {"price": 80}, CUST), 403)
check("PATCH unknown menu item -> 404", patch("/menu-items/99", {"price": 80}, REST), 404)
check("PATCH menu item with nothing to change -> 400", patch("/menu-items/12", {}, REST), 400)
check("PATCH menu item price -5 -> 422", patch("/menu-items/12", {"price": -5}, REST), 422)

print("\n--- 6. Customers ---")
meera = {"name": "Meera Nair", "phone": "9000000001"}
check("POST /customers as customer -> 201", post("/customers", meera, CUST), 201, lambda d: d["id"] == 3)
check("POST /customers same phone -> 409",
      post("/customers", {"name": "Someone Else", "phone": "9000000001"}, CUST), 409)
check("POST /customers phone with 9 digits -> 422",
      post("/customers", {"name": "Short Phone", "phone": "900000000"}, CUST), 422)
check("POST /customers phone with letters -> 422",
      post("/customers", {"name": "Letter Phone", "phone": "90000abcde"}, CUST), 422)
check("POST /customers without a role -> 401", post("/customers", meera), 401)
check("POST /customers as restaurant -> 403", post("/customers", meera, REST), 403)
check("GET /customers as admin", get("/customers", ADMIN), 200, lambda d: len(d) == 3)
check("GET /customers as customer -> 403", get("/customers", CUST), 403)
check("GET /customers/1 as customer", get("/customers/1", CUST), 200, lambda d: d["name"] == "Asha Rao")
check("GET /customers/1 without a role -> 401", get("/customers/1"), 401)
check("GET /customers/99 -> 404", get("/customers/99", CUST), 404)

print("\n--- 7. Placing orders: happy path and the rules ---")
check("order without a role -> 401", post("/orders", order(1, 1, [(1, 1)])), 401)
check("order as restaurant -> 403", post("/orders", order(1, 1, [(1, 1)]), REST), 403)
check("food worth 99 (3 coffees) -> 409 (minimum order)", post("/orders", order(1, 1, [(3, 3)]), CUST), 409)
check("food worth exactly 100 -> 201", post("/orders", order(1, 1, [(1, 1)]), CUST), 201,
      lambda d: d["id"] == 1 and d["items_total"] == 100 and d["delivery_fee"] == 40
      and d["total"] == 140 and d["status"] == "placed" and d["placed_on"] == today
      and d["rating"] is None
      and d["items"] == [{"menu_item_id": 1, "name": "Masala Dosa", "price": 100, "quantity": 1}])
check("food worth 499: delivery fee 40 (customer 1's 2nd active order)",
      post("/orders", order(1, 1, [(1, 4), (3, 3)]), CUST), 201,
      lambda d: d["id"] == 2 and d["items_total"] == 499 and d["delivery_fee"] == 40 and d["total"] == 539)
check("customer 1's 3rd active order -> 409 (limit)", post("/orders", order(1, 1, [(1, 1)]), CUST), 409)
check("food worth exactly 500: delivery is free", post("/orders", order(2, 1, [(1, 5)]), CUST), 201,
      lambda d: d["id"] == 3 and d["items_total"] == 500 and d["delivery_fee"] == 0 and d["total"] == 500)
check("item from another restaurant -> 409", post("/orders", order(2, 1, [(1, 1), (5, 1)]), CUST), 409)
check("closed restaurant -> 409", post("/orders", order(2, 3, [(9, 3)]), CUST), 409)
check("unavailable item -> 409", post("/orders", order(2, 2, [(5, 1), (8, 1)]), CUST), 409)
check("unknown customer -> 404", post("/orders", order(99, 1, [(1, 1)]), CUST), 404)
check("unknown restaurant -> 404", post("/orders", order(2, 99, [(1, 1)]), CUST), 404)
check("unknown menu item -> 404", post("/orders", order(2, 1, [(99, 1)]), CUST), 404)
check("quantity 0 -> 422", post("/orders", order(2, 1, [(1, 0)]), CUST), 422)
check("quantity 11 -> 422", post("/orders", order(2, 1, [(1, 11)]), CUST), 422)
check("no items at all -> 422",
      post("/orders", order(2, 1, []), CUST), 422)
check("11 lines -> 422", post("/orders", order(2, 1, [(1, 1)] * 11), CUST), 422)
check("the same item on two lines -> 400", post("/orders", order(2, 1, [(1, 1), (1, 2)]), CUST), 400)
check("order with ?today=2026-12-25 (customer 2's 2nd active order)",
      post("/orders?today=2026-12-25", order(2, 2, [(5, 1)]), CUST), 201,
      lambda d: d["id"] == 4 and d["placed_on"] == "2026-12-25" and d["total"] == 290)
check("?today=not-a-date -> 422", post("/orders?today=tomorrow", order(3, 1, [(1, 1)]), CUST), 422)
check("customer 2's 3rd active order -> 409 (limit)", post("/orders", order(2, 1, [(1, 1)]), CUST), 409)

print("\n--- 8. The price is copied into the order ---")
check("menu price of item 1 changes to 110", patch("/menu-items/1", {"price": 110}, REST), 200,
      lambda d: d["price"] == 110)
check("order 1 still shows the old price 100", get("/orders/1", CUST), 200,
      lambda d: d["items"][0]["price"] == 100 and d["total"] == 140)
check("put the price back to 100", patch("/menu-items/1", {"price": 100}, REST), 200)

print("\n--- 9. Looking at orders ---")
check("GET /orders/1 as customer", get("/orders/1", CUST), 200, lambda d: d["customer_id"] == 1)
check("GET /orders/1 without a role -> 401", get("/orders/1"), 401)
check("GET /orders/99 -> 404", get("/orders/99", CUST), 404)
check("GET /customers/1/orders", get("/customers/1/orders", CUST), 200, lambda d: len(d) == 2)
check("GET /customers/99/orders -> 404", get("/customers/99/orders", CUST), 404)
check("GET /orders as admin", get("/orders", ADMIN), 200, lambda d: len(d) == 4)
check("GET /orders as restaurant", get("/orders", REST), 200, lambda d: len(d) == 4)
check("GET /orders as customer -> 403", get("/orders", CUST), 403)
check("GET /orders?status=placed", get("/orders?status=placed", ADMIN), 200, lambda d: len(d) == 4)
check("GET /orders?restaurant_id=2", get("/orders?restaurant_id=2", REST), 200,
      lambda d: [o["id"] for o in d] == [4])
check("GET /orders?status=bogus -> 422", get("/orders?status=bogus", ADMIN), 422)

print("\n--- 10. Deleting is protected ---")
check("delete restaurant 1 with active orders -> 409", delete("/restaurants/1", ADMIN), 409)
check("delete menu item 1 that is in an active order -> 409", delete("/menu-items/1", REST), 409)
check("delete a restaurant as restaurant -> 403", delete("/restaurants/5", REST), 403)
check("delete a menu item as customer -> 403", delete("/menu-items/12", CUST), 403)
check("delete a restaurant without a role -> 401", delete("/restaurants/5"), 401)

print("\n--- 11. Status moves (ALLOWED_MOVES) ---")
check("status change without a role -> 401", patch("/orders/1/status", {"status": "preparing"}), 401)
check("status change as customer -> 403", patch("/orders/1/status", {"status": "preparing"}, CUST), 403)
check("restaurant marks delivered -> 403 (admin only)",
      patch("/orders/1/status", {"status": "delivered"}, REST), 403)
check("restaurant cancels through PATCH -> 403 (admin only)",
      patch("/orders/1/status", {"status": "cancelled"}, REST), 403)
check("placed -> out_for_delivery skips a step -> 409",
      patch("/orders/1/status", {"status": "out_for_delivery"}, REST), 409)
check("placed -> delivered skips steps -> 409", patch("/orders/1/status", {"status": "delivered"}, ADMIN), 409)
check("placed -> preparing", patch("/orders/1/status", {"status": "preparing"}, REST), 200,
      lambda d: d["status"] == "preparing")
check("preparing -> preparing again -> 409", patch("/orders/1/status", {"status": "preparing"}, REST), 409)
check("customer cancels while preparing -> 409", post("/orders/1/cancel", None, CUST), 409)
check("admin cancels while preparing -> 409", patch("/orders/1/status", {"status": "cancelled"}, ADMIN), 409)
check("preparing -> out_for_delivery", patch("/orders/1/status", {"status": "out_for_delivery"}, REST), 200,
      lambda d: d["status"] == "out_for_delivery")
check("out_for_delivery -> delivered as admin", patch("/orders/1/status", {"status": "delivered"}, ADMIN), 200,
      lambda d: d["status"] == "delivered")
check("delivered -> preparing goes backwards -> 409", patch("/orders/1/status", {"status": "preparing"}, REST), 409)
check("status 'eaten' -> 422", patch("/orders/1/status", {"status": "eaten"}, ADMIN), 422)
check("status of unknown order -> 404", patch("/orders/99/status", {"status": "preparing"}, REST), 404)
check("customer 1 has only 1 active order now, so can order again",
      post("/orders", order(1, 1, [(2, 2)]), CUST), 201, lambda d: d["id"] == 5 and d["items_total"] == 120)

print("\n--- 12. Cancelling ---")
check("cancel without a role -> 401", post("/orders/2/cancel"), 401)
check("cancel as restaurant -> 403", post("/orders/2/cancel", None, REST), 403)
check("customer cancels order 2 while placed", post("/orders/2/cancel", None, CUST), 200,
      lambda d: d["status"] == "cancelled")
check("cancel order 2 again -> 409", post("/orders/2/cancel", None, CUST), 409)
check("cancel unknown order -> 404", post("/orders/99/cancel", None, CUST), 404)
check("cancel a delivered order -> 409", post("/orders/1/cancel", None, CUST), 409)
check("cancelled -> preparing -> 409", patch("/orders/2/status", {"status": "preparing"}, REST), 409)
check("admin cancels order 5 through PATCH", patch("/orders/5/status", {"status": "cancelled"}, ADMIN), 200,
      lambda d: d["status"] == "cancelled")

print("\n--- 13. Rating ---")
check("rate without a role -> 401", post("/orders/1/rate", {"rating": 5}), 401)
check("rate as restaurant -> 403", post("/orders/1/rate", {"rating": 5}, REST), 403)
check("rate order 3 before delivery -> 409", post("/orders/3/rate", {"rating": 4}, CUST), 409)
check("rate a cancelled order -> 409", post("/orders/2/rate", {"rating": 4}, CUST), 409)
check("rating 0 -> 422", post("/orders/1/rate", {"rating": 0}, CUST), 422)
check("rating 6 -> 422", post("/orders/1/rate", {"rating": 6}, CUST), 422)
check("rate delivered order 1 with 5", post("/orders/1/rate", {"rating": 5}, CUST), 200,
      lambda d: d["rating"] == 5)
check("rate order 1 a second time -> 409", post("/orders/1/rate", {"rating": 1}, CUST), 409)
check("rate unknown order -> 404", post("/orders/99/rate", {"rating": 3}, CUST), 404)
check("order 3 -> preparing", patch("/orders/3/status", {"status": "preparing"}, REST), 200)
check("order 3 -> out_for_delivery", patch("/orders/3/status", {"status": "out_for_delivery"}, REST), 200)
check("order 3 -> delivered", patch("/orders/3/status", {"status": "delivered"}, ADMIN), 200)
check("rate order 3 with 4", post("/orders/3/rate", {"rating": 4}, CUST), 200, lambda d: d["rating"] == 4)

print("\n--- 14. The report ---")
check("GET /stats without a role -> 401", get("/stats"), 401)
check("GET /stats as customer -> 403", get("/stats", CUST), 403)
check("GET /stats as restaurant -> 403", get("/stats", REST), 403)
check("GET /stats as admin", get("/stats", ADMIN), 200,
      lambda d: d == {"total_orders": 5,
                      "orders_by_status": {"placed": 1, "preparing": 0, "out_for_delivery": 0,
                                           "delivered": 2, "cancelled": 2},
                      "orders_placed_today": 4, "total_revenue": 640, "average_rating": 4.5,
                      "most_ordered_item_id": 1, "most_ordered_item_name": "Masala Dosa",
                      "busiest_restaurant_id": 1})
check("GET /stats?today=2026-12-25 counts that day's order", get("/stats?today=2026-12-25", ADMIN), 200,
      lambda d: d["orders_placed_today"] == 1 and d["total_orders"] == 5)

print("\n--- 15. Deleting when allowed ---")
check("delete menu item 5 (in active order 4) -> 409", delete("/menu-items/5", REST), 409)
check("delete restaurant 2 (active order 4) -> 409", delete("/restaurants/2", ADMIN), 409)
check("delete menu item 12 (never ordered)", delete("/menu-items/12", REST), 204)
check("restaurant 4's menu is empty now", get("/restaurants/4/menu"), 200, lambda d: d == [])
check("delete unknown menu item -> 404", delete("/menu-items/99", REST), 404)
check("delete restaurant 5 (no orders)", delete("/restaurants/5", ADMIN), 204)
check("restaurant 5 is gone", get("/restaurants/5"), 404)
check("delete unknown restaurant -> 404", delete("/restaurants/99", ADMIN), 404)
check("delete restaurant 1 (its orders are all finished)", delete("/restaurants/1", ADMIN), 204)
check("its menu went with it", get("/restaurants/1/menu"), 404)
check("old order 1 can still be read (name and price were copied)", get("/orders/1", ADMIN), 200,
      lambda d: d["items"][0]["name"] == "Masala Dosa" and d["restaurant_id"] == 1)

print("\nPassed: " + str(passed) + "   Failed: " + str(failed))
print("Now do the restart test by hand: stop the server, start it, call GET /restaurants and GET /orders.")
sys.exit(1 if failed > 0 else 0)
