"""Automatic API checklist for the Food Delivery project.

Use a CLEAN starter dataset before running:
    uvicorn main:app --reload
    python check_food_delivery.py

An optional base URL can be supplied, e.g.:
    python check_food_delivery.py http://127.0.0.1:8010
"""
import sys
from datetime import date

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
CUSTOMER = {"X-Role": "customer"}
RESTAURANT = {"X-Role": "restaurant"}
ADMIN = {"X-Role": "admin"}

passed = 0
failed = 0


def check(name, response, expected_status, test=None):
    """Compare status and optionally check the returned JSON body."""
    global passed, failed
    ok = response.status_code == expected_status
    reason = ""
    if ok and test is not None:
        try:
            ok = bool(test(response.json()))
            if not ok:
                reason = "reply did not match the expected value"
        except Exception as error:
            ok = False
            reason = str(error)
    if ok:
        passed = passed + 1
        print("PASS  " + name)
    else:
        failed = failed + 1
        print(
            "FAIL  " + name + " (got " + str(response.status_code)
            + ", expected " + str(expected_status) + ") "
            + reason + " " + response.text[:180]
        )


def get(path, headers=None):
    return requests.get(BASE + path, headers=headers, timeout=5)


def post(path, body=None, headers=None):
    return requests.post(BASE + path, json=body, headers=headers, timeout=5)


def patch(path, body, headers=None):
    return requests.patch(BASE + path, json=body, headers=headers, timeout=5)


def delete(path, headers=None):
    return requests.delete(BASE + path, headers=headers, timeout=5)


# Check the server and make sure tests start from the expected starter data.
try:
    start_restaurants = get("/restaurants").json()
    start_menu = get("/restaurants/1/menu").json()
    start_customers = get("/customers", ADMIN).json()
    start_orders = get("/orders", RESTAURANT).json()
except requests.exceptions.RequestException:
    print("Cannot reach " + BASE + ". Is the FastAPI server running?")
    sys.exit(1)

if (len(start_restaurants) != 3 or len(start_menu) != 3
        or len(start_customers) != 2 or len(start_orders) != 0):
    print("The data is not a clean start.")
    print("Stop the server, delete restaurants.json, menu_items.json,")
    print("customers.json and orders.json, restart the server, then retry.")
    sys.exit(1)

print("\n--- 1. Health, restaurants and menu browsing ---")
check("GET /health", get("/health"), 200, lambda data: data["status"] == "ok")
check("GET /restaurants lists 3 starter restaurants", get("/restaurants"), 200, lambda data: len(data) == 3)
check("area filter finds Indiranagar", get("/restaurants?area=Indiranagar"), 200, lambda data: len(data) == 1 and data[0]["id"] == 1)
check("open_only hides closed restaurant", get("/restaurants?open_only=true"), 200, lambda data: len(data) == 2)
check("GET /restaurants/1", get("/restaurants/1"), 200, lambda data: data["name"] == "Spice Garden")
check("unknown restaurant -> 404", get("/restaurants/99"), 404)
check("GET /restaurants/1/menu lists 3 items", get("/restaurants/1/menu"), 200, lambda data: len(data) == 3)
check("menu available_only hides item 6", get("/restaurants/2/menu?available_only=true"), 200, lambda data: [item["id"] for item in data] == [4, 5])
check("menu category filter", get("/restaurants/2/menu?category=Main"), 200, lambda data: len(data) == 1 and data[0]["id"] == 4)
check("GET /menu-items/1", get("/menu-items/1"), 200, lambda data: data["price"] == 180)
check("unknown menu item -> 404", get("/menu-items/99"), 404)

print("\n--- 2. Restaurant management and roles ---")
new_restaurant = {"name": "Green Bowl", "area": "Jayanagar", "cuisine": "Healthy", "open": True}
check("POST /restaurants without role -> 401", post("/restaurants", new_restaurant), 401)
check("POST /restaurants as customer -> 403", post("/restaurants", new_restaurant, CUSTOMER), 403)
created_restaurant = post("/restaurants", new_restaurant, ADMIN)
check("POST /restaurants as admin -> 201", created_restaurant, 201, lambda data: data["id"] == 4)
check("duplicate restaurant name and area -> 409", post("/restaurants", new_restaurant, ADMIN), 409)
check("restaurant update as customer -> 403", patch("/restaurants/4", {"open": False}, CUSTOMER), 403)
check("restaurant can close restaurant 4", patch("/restaurants/4", {"open": False}, RESTAURANT), 200, lambda data: data["open"] is False)
check("restaurant can reopen restaurant 4", patch("/restaurants/4", {"open": True}, RESTAURANT), 200, lambda data: data["open"] is True)
check("invalid empty restaurant name -> 422", patch("/restaurants/4", {"name": ""}, ADMIN), 422)
check("update unknown restaurant -> 404", patch("/restaurants/99", {"open": False}, ADMIN), 404)
check("delete restaurant without role -> 401", delete("/restaurants/4"), 401)
check("delete restaurant as restaurant -> 403", delete("/restaurants/4", RESTAURANT), 403)
check("PATCH restaurant without role -> 401", patch("/restaurants/4", {"open": False}), 401)

print("\n--- 3. Menu item management ---")
new_item = {"name": "Masala Dosa", "category": "Breakfast", "price": 120, "available": True}
check("add menu item without role -> 401", post("/restaurants/4/menu-items", new_item), 401)
check("add menu item as customer -> 403", post("/restaurants/4/menu-items", new_item, CUSTOMER), 403)
created_item = post("/restaurants/4/menu-items", new_item, RESTAURANT)
check("restaurant adds menu item -> 201", created_item, 201, lambda data: data["id"] == 9 and data["restaurant_id"] == 4)
check("duplicate menu item at same restaurant -> 409", post("/restaurants/4/menu-items", new_item, RESTAURANT), 409)
check("menu item with price 0 -> 422", post("/restaurants/4/menu-items", {"name": "Bad Item", "category": "Test", "price": 0}, RESTAURANT), 422)
check("add menu item to unknown restaurant -> 404", post("/restaurants/99/menu-items", new_item, ADMIN), 404)
check("PATCH menu item as customer -> 403", patch("/menu-items/9", {"price": 130}, CUSTOMER), 403)
check("PATCH menu item without role -> 401", patch("/menu-items/9", {"price": 130}), 401)
check("restaurant updates menu item price", patch("/menu-items/9", {"price": 130}, RESTAURANT), 200, lambda data: data["price"] == 130)
check("PATCH unknown menu item -> 404", patch("/menu-items/99", {"price": 130}, RESTAURANT), 404)
check("DELETE menu item without role -> 401", delete("/menu-items/9"), 401)
check("DELETE menu item as customer -> 403", delete("/menu-items/9", CUSTOMER), 403)
check("DELETE unused menu item -> 204", delete("/menu-items/9", RESTAURANT), 204)
check("deleted menu item is not found -> 404", get("/menu-items/9"), 404)

print("\n--- 4. Customer management and roles ---")
new_customer = {"name": "Meera Nair", "phone": "9876543212"}
check("POST /customers without role -> 401", post("/customers", new_customer), 401)
check("POST /customers as restaurant -> 403", post("/customers", new_customer, RESTAURANT), 403)
created_customer = post("/customers", new_customer, CUSTOMER)
check("customer registration -> 201", created_customer, 201, lambda data: data["id"] == 3)
check("duplicate phone with different punctuation -> 409", post("/customers", {"name": "Meera N", "phone": "987-654-3212"}, ADMIN), 409)
check("invalid phone -> 422", post("/customers", {"name": "Bad Phone", "phone": "phone-number"}, CUSTOMER), 422)
check("GET /customers as customer -> 403", get("/customers", CUSTOMER), 403)
check("GET /customers without role -> 401", get("/customers"), 401)
check("GET /customers as admin", get("/customers", ADMIN), 200, lambda data: len(data) == 3)
check("GET customer 3 as customer", get("/customers/3", CUSTOMER), 200, lambda data: data["name"] == "Meera Nair")
check("GET customer as restaurant -> 403", get("/customers/1", RESTAURANT), 403)
check("GET customer without role -> 401", get("/customers/1"), 401)
check("GET unknown customer -> 404", get("/customers/99", ADMIN), 404)

print("\n--- 5. Order validation and business rules ---")
valid_order_1 = {
    "customer_id": 1,
    "restaurant_id": 1,
    "items": [
        {"menu_item_id": 1, "quantity": 1},
        {"menu_item_id": 2, "quantity": 1},
    ],
}
check("POST /orders without role -> 401", post("/orders", valid_order_1), 401)
check("POST /orders as restaurant -> 403", post("/orders", valid_order_1, RESTAURANT), 403)
check("order for unknown customer -> 404", post("/orders", {**valid_order_1, "customer_id": 99}, CUSTOMER), 404)
check("order for unknown restaurant -> 404", post("/orders", {**valid_order_1, "restaurant_id": 99}, CUSTOMER), 404)
check("closed restaurant refuses order -> 409", post("/orders", {"customer_id": 1, "restaurant_id": 3, "items": [{"menu_item_id": 7, "quantity": 1}]}, CUSTOMER), 409)
check("unavailable menu item refuses order -> 409", post("/orders", {"customer_id": 1, "restaurant_id": 2, "items": [{"menu_item_id": 6, "quantity": 1}]}, CUSTOMER), 409)
check("items from different restaurants -> 409", post("/orders", {"customer_id": 1, "restaurant_id": 1, "items": [{"menu_item_id": 1, "quantity": 1}, {"menu_item_id": 4, "quantity": 1}]}, CUSTOMER), 409)
check("same menu item repeated -> 409", post("/orders", {"customer_id": 1, "restaurant_id": 1, "items": [{"menu_item_id": 1, "quantity": 1}, {"menu_item_id": 1, "quantity": 2}]}, CUSTOMER), 409)
check("below minimum order value -> 409", post("/orders", {"customer_id": 1, "restaurant_id": 1, "items": [{"menu_item_id": 2, "quantity": 1}]}, CUSTOMER), 409)
check("unknown menu item in order -> 404", post("/orders", {"customer_id": 1, "restaurant_id": 1, "items": [{"menu_item_id": 99, "quantity": 1}]}, CUSTOMER), 404)
check("empty order items -> 422", post("/orders", {"customer_id": 1, "restaurant_id": 1, "items": []}, CUSTOMER), 422)
check("zero quantity -> 422", post("/orders", {"customer_id": 1, "restaurant_id": 1, "items": [{"menu_item_id": 1, "quantity": 0}]}, CUSTOMER), 422)

order_1 = post("/orders", valid_order_1, CUSTOMER)
check("valid order -> 201 and total ₹220", order_1, 201, lambda data: data["id"] == 1 and data["total"] == 220 and data["status"] == "placed")
check("GET /orders as customer -> 403", get("/orders", CUSTOMER), 403)
check("GET /orders without role -> 401", get("/orders"), 401)
check("GET /orders as restaurant", get("/orders", RESTAURANT), 200, lambda data: len(data) == 1)
check("GET /orders filtered by restaurant id", get("/orders?restaurant_id=1", ADMIN), 200, lambda data: len(data) == 1)
check("invalid order status filter -> 422", get("/orders?status=bogus", ADMIN), 422)
check("GET order 1 as customer", get("/orders/1", CUSTOMER), 200, lambda data: data["items"][0]["unit_price"] == 180)
check("GET order without role -> 401", get("/orders/1"), 401)
check("GET unknown order -> 404", get("/orders/99", CUSTOMER), 404)
check("GET customer 1 orders", get("/customers/1/orders", CUSTOMER), 200, lambda data: len(data) == 1)
check("GET customer orders without role -> 401", get("/customers/1/orders"), 401)
check("customer order list for unknown customer -> 404", get("/customers/99/orders", ADMIN), 404)
check("customer order list as restaurant -> 403", get("/customers/1/orders", RESTAURANT), 403)

print("\n--- 6. Order status flow, cancellation and snapshots ---")
# Changing a menu price must not change an order that has already been placed.
check("change menu price after order", patch("/menu-items/1", {"price": 200}, RESTAURANT), 200, lambda data: data["price"] == 200)
check("old order keeps its price snapshot", get("/orders/1", CUSTOMER), 200, lambda data: data["items"][0]["unit_price"] == 180 and data["total"] == 220)
check("advance order as customer -> 403", patch("/orders/1/status", {"status": "preparing"}, CUSTOMER), 403)
check("advance order without role -> 401", patch("/orders/1/status", {"status": "preparing"}), 401)
check("cancel order as restaurant -> 403", post("/orders/1/cancel", headers=RESTAURANT), 403)
check("cancel order without role -> 401", post("/orders/1/cancel"), 401)
check("cancel placed order -> cancelled", post("/orders/1/cancel", headers=CUSTOMER), 200, lambda data: data["status"] == "cancelled")
check("cancel same order twice -> 409", post("/orders/1/cancel", headers=CUSTOMER), 409)
check("advance cancelled order -> 409", patch("/orders/1/status", {"status": "preparing"}, RESTAURANT), 409)

valid_order_2 = {
    "customer_id": 2,
    "restaurant_id": 1,
    "items": [{"menu_item_id": 3, "quantity": 1}],
}
order_2 = post("/orders", valid_order_2, CUSTOMER)
check("place second order -> 201", order_2, 201, lambda data: data["id"] == 2 and data["total"] == 150)
check("cannot skip placed straight to delivered -> 409", patch("/orders/2/status", {"status": "delivered"}, RESTAURANT), 409)
check("placed -> preparing is allowed", patch("/orders/2/status", {"status": "preparing"}, RESTAURANT), 200, lambda data: data["status"] == "preparing")
check("cannot cancel after preparation starts -> 409", post("/orders/2/cancel", headers=CUSTOMER), 409)
check("cannot move preparing back to preparing -> 409", patch("/orders/2/status", {"status": "preparing"}, RESTAURANT), 409)
check("preparing -> out_for_delivery is allowed", patch("/orders/2/status", {"status": "out_for_delivery"}, RESTAURANT), 200, lambda data: data["status"] == "out_for_delivery")
check("out_for_delivery -> delivered is allowed", patch("/orders/2/status", {"status": "delivered"}, RESTAURANT), 200, lambda data: data["status"] == "delivered")
check("delivered order cannot move backwards -> 409", patch("/orders/2/status", {"status": "preparing"}, RESTAURANT), 409)
check("list delivered orders", get("/orders?status=delivered", RESTAURANT), 200, lambda data: len(data) == 1)

print("\n--- 7. Protected deletion and report ---")
check("delete menu item in order history -> 409", delete("/menu-items/1", RESTAURANT), 409)
check("delete customer with order history -> 409", delete("/customers/1", ADMIN), 409)
check("delete customer without role -> 401", delete("/customers/3"), 401)
check("delete customer as customer -> 403", delete("/customers/3", CUSTOMER), 403)
check("delete restaurant with order history -> 409", delete("/restaurants/1", ADMIN), 409)
check("delete unknown menu item -> 404", delete("/menu-items/99", RESTAURANT), 404)
check("delete unknown customer -> 404", delete("/customers/99", ADMIN), 404)
check("delete unknown restaurant -> 404", delete("/restaurants/99", ADMIN), 404)
check("GET /stats as customer -> 403", get("/stats", CUSTOMER), 403)
check("GET /stats without role -> 401", get("/stats"), 401)
check(
    "GET /stats as admin",
    get("/stats", ADMIN),
    200,
    lambda data: data["total_orders"] == 2
    and data["cancelled_orders"] == 1
    and data["delivered_orders"] == 1
    and data["delivered_revenue"] == 150,
)
check("delete customer 3 with no orders -> 204", delete("/customers/3", ADMIN), 204)
check("customer 3 is gone", get("/customers/3", ADMIN), 404)
check("delete restaurant 4 with no orders -> 204", delete("/restaurants/4", ADMIN), 204)
check("restaurant 4 is gone", get("/restaurants/4"), 404)
check("delete unused menu item 8 -> 204", delete("/menu-items/8", RESTAURANT), 204)
check("menu item 8 is gone", get("/menu-items/8"), 404)

print("\nPassed: " + str(passed) + "   Failed: " + str(failed))
print("Now do the restart test by hand: restart the server without deleting JSON files,")
print("then check GET /restaurants, GET /customers (admin) and GET /orders (restaurant).")
sys.exit(1 if failed > 0 else 0)
