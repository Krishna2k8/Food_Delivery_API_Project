"""
main.py - Food Delivery API (a complete small project)
======================================================
WHAT THIS PROGRAM IS
    A worked example of a food-delivery service API. It has:
      * four kinds of data (MODELS): restaurants, menu items, customers, orders
      * three ROLES: customer, restaurant and admin
      * business RULES: restaurant opening, menu availability, order minimum,
        one-restaurant-per-order and a fixed order-status flow
      * data that SURVIVES a restart: four JSON files, no database
    Everything uses the ideas from the project guide: dictionaries, lists,
    loops, functions, API endpoints, Pydantic models, status codes and files.

HOW TO RUN IT
    1. Install once:      pip install -r requirements.txt
    2. Start the server:  uvicorn main:app --reload
    3. Open:              http://127.0.0.1:8000/docs
    4. The first start creates restaurants.json, menu_items.json,
       customers.json and orders.json next to this file. To start again from
       scratch: stop the server, delete those four files, and start it again.

HOW THE ROLES WORK (a simple stand-in for a real login)
    Send a header named X-Role. Its value is customer, restaurant or admin.
    The header simulates a role only; it is NOT a real login and does not prove
    a person's identity. IDs are supplied in request paths or bodies, just as
    the Library sample uses a member_id. Real passwords, tokens and payments
    are outside this classroom project.

THE MAIN RULES
    * Every item in one order must belong to the selected restaurant.
    * A closed restaurant cannot accept an order.
    * An unavailable menu item cannot be ordered.
    * The total order value must be at least Rs 100.
    * Order statuses move only along the allowed path.
    * A customer may cancel only while the order is still placed.
    * A restaurant/customer with order history cannot be deleted; a menu item
      that appears in an order cannot be deleted. This preserves order history.

TESTING HELP
    Order endpoints accept an optional ?today=YYYY-MM-DD. It lets you set the
    date stored on an order or status change while testing. No waiting is needed.
"""
import json
import os
from datetime import date
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(
    title="Food Delivery API",
    description=(
        "A classroom food-delivery service API with restaurants, menu items, "
        "customers, orders, three roles, business rules and JSON-file storage."
    ),
    version="1.0",
)

# =====================================================================
# SECTION 1 - SETTINGS
# Rules and values that may change live are kept in ONE place.
# =====================================================================
MIN_ORDER_VALUE = 100       # minimum order total, in whole rupees
MAX_ITEMS_PER_ORDER = 20   # maximum different menu-item lines in one order
MAX_QUANTITY_PER_ITEM = 20 # maximum quantity in one line

# The value on the right lists every status that may follow the key status.
ALLOWED_STATUS_MOVES = {
    "placed": ["preparing", "cancelled"],
    "preparing": ["out_for_delivery"],
    "out_for_delivery": ["delivered"],
    "delivered": [],
    "cancelled": [],
}

# =====================================================================
# SECTION 2 - STORAGE
# One JSON file per model. load_data creates starter data on the first run.
# =====================================================================
DATA_FOLDER = os.environ.get(
    "FOOD_DELIVERY_DATA", os.path.dirname(os.path.abspath(__file__))
)
os.makedirs(DATA_FOLDER, exist_ok=True)

RESTAURANTS_FILE = os.path.join(DATA_FOLDER, "restaurants.json")
MENU_ITEMS_FILE = os.path.join(DATA_FOLDER, "menu_items.json")
CUSTOMERS_FILE = os.path.join(DATA_FOLDER, "customers.json")
ORDERS_FILE = os.path.join(DATA_FOLDER, "orders.json")

STARTER_RESTAURANTS = [
    {"id": 1, "name": "Spice Garden", "area": "Indiranagar", "cuisine": "North Indian", "open": True},
    {"id": 2, "name": "Wok This Way", "area": "Koramangala", "cuisine": "Chinese", "open": True},
    {"id": 3, "name": "Pizza Corner", "area": "Whitefield", "cuisine": "Italian", "open": False},
]

STARTER_MENU_ITEMS = [
    {"id": 1, "restaurant_id": 1, "name": "Paneer Butter Masala", "category": "Main Course", "price": 180, "available": True},
    {"id": 2, "restaurant_id": 1, "name": "Butter Naan", "category": "Bread", "price": 40, "available": True},
    {"id": 3, "restaurant_id": 1, "name": "Veg Biryani", "category": "Main Course", "price": 150, "available": True},
    {"id": 4, "restaurant_id": 2, "name": "Veg Hakka Noodles", "category": "Main Course", "price": 160, "available": True},
    {"id": 5, "restaurant_id": 2, "name": "Spring Rolls", "category": "Starter", "price": 90, "available": True},
    {"id": 6, "restaurant_id": 2, "name": "Chilli Paneer", "category": "Starter", "price": 140, "available": False},
    {"id": 7, "restaurant_id": 3, "name": "Margherita Pizza", "category": "Pizza", "price": 220, "available": True},
    {"id": 8, "restaurant_id": 3, "name": "Garlic Bread", "category": "Side", "price": 90, "available": True},
]

STARTER_CUSTOMERS = [
    {"id": 1, "name": "Asha Rao", "phone": "9876543210"},
    {"id": 2, "name": "Rohan Mehta", "phone": "9876543211"},
]

# An order stores a PRICE SNAPSHOT. If a menu price changes later, an old
# order keeps the unit_price and line_total that were true when it was placed.
STARTER_ORDERS = []


def save_data(path, data):
    """Write a whole list to a JSON file, replacing its previous contents."""
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def load_data(path, starter):
    """Load a JSON list; create starter data if missing or recover if damaged.

    A damaged file is moved to a .corrupt copy when possible. The server then
    starts with starter data instead of crashing during import.
    """
    if not os.path.exists(path):
        starting_list = []
        for item in starter:
            starting_list.append(dict(item))
        save_data(path, starting_list)
        return starting_list

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise ValueError("The data file must contain a JSON list of objects")
        return data
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print("Warning: could not read " + path + ": " + str(error))
        try:
            if os.path.exists(path):
                os.replace(path, path + ".corrupt")
        except OSError:
            pass
        starting_list = []
        for item in starter:
            starting_list.append(dict(item))
        save_data(path, starting_list)
        return starting_list


# Load all four lists ONCE when the server starts. Every later change is saved.
restaurants = load_data(RESTAURANTS_FILE, STARTER_RESTAURANTS)
menu_items = load_data(MENU_ITEMS_FILE, STARTER_MENU_ITEMS)
customers = load_data(CUSTOMERS_FILE, STARTER_CUSTOMERS)
orders = load_data(ORDERS_FILE, STARTER_ORDERS)

# =====================================================================
# SECTION 3 - MODELS (Pydantic)
# In models describe what callers SEND. Out models describe what we RETURN.
# Every input field has Field(...) validation or an explicit default.
# =====================================================================
class RestaurantIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=80, examples=["Green Bowl"])
    area: str = Field(..., min_length=2, max_length=60, examples=["Jayanagar"])
    cuisine: str = Field(..., min_length=2, max_length=40, examples=["Healthy"])
    open: bool = Field(default=True, examples=[True])


class RestaurantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    area: str | None = Field(default=None, min_length=2, max_length=60)
    cuisine: str | None = Field(default=None, min_length=2, max_length=40)
    open: bool | None = Field(default=None)


class RestaurantOut(BaseModel):
    id: int
    name: str
    area: str
    cuisine: str
    open: bool


class MenuItemIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=80, examples=["Masala Dosa"])
    category: str = Field(..., min_length=2, max_length=40, examples=["Breakfast"])
    price: int = Field(..., ge=1, le=20000, examples=[120])
    available: bool = Field(default=True, examples=[True])


class MenuItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    category: str | None = Field(default=None, min_length=2, max_length=40)
    price: int | None = Field(default=None, ge=1, le=20000)
    available: bool | None = Field(default=None)


class MenuItemOut(BaseModel):
    id: int
    restaurant_id: int
    name: str
    category: str
    price: int
    available: bool


class CustomerIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=60, examples=["Meera Nair"])
    phone: str = Field(
        ..., min_length=7, max_length=20,
        pattern=r"^[0-9+\-\s]{7,20}$", examples=["9876543212"]
    )


class CustomerOut(BaseModel):
    id: int
    name: str
    phone: str


class OrderItemIn(BaseModel):
    menu_item_id: int = Field(..., gt=0, examples=[1])
    quantity: int = Field(..., ge=1, le=MAX_QUANTITY_PER_ITEM, examples=[2])


class OrderIn(BaseModel):
    customer_id: int = Field(..., gt=0, examples=[1])
    restaurant_id: int = Field(..., gt=0, examples=[1])
    items: list[OrderItemIn] = Field(
        ..., min_length=1, max_length=MAX_ITEMS_PER_ORDER,
        examples=[[{"menu_item_id": 1, "quantity": 1}, {"menu_item_id": 2, "quantity": 1}]],
    )


class OrderItemOut(BaseModel):
    menu_item_id: int
    name: str
    unit_price: int
    quantity: int
    line_total: int


class OrderOut(BaseModel):
    id: int
    customer_id: int
    restaurant_id: int
    items: list[OrderItemOut]
    total: int
    status: Literal["placed", "preparing", "out_for_delivery", "delivered", "cancelled"]
    placed_on: str
    updated_on: str


class OrderStatusIn(BaseModel):
    status: Literal["preparing", "out_for_delivery", "delivered"] = Field(
        ..., examples=["preparing"]
    )


class HealthOut(BaseModel):
    status: str


class StatsOut(BaseModel):
    restaurants: int
    menu_items: int
    customers: int
    total_orders: int
    placed_orders: int
    preparing_orders: int
    out_for_delivery_orders: int
    delivered_orders: int
    cancelled_orders: int
    delivered_revenue: int

# =====================================================================
# SECTION 4 - HELPER FUNCTIONS
# Shared lookups and rule calculations live here, not repeated in endpoints.
# =====================================================================
def check_role(x_role, allowed):
    """Return 401 for an unknown role and 403 for a known but forbidden role."""
    if x_role not in ("customer", "restaurant", "admin"):
        raise HTTPException(
            status_code=401,
            detail="Send X-Role with the value customer, restaurant or admin",
        )
    if x_role not in allowed:
        raise HTTPException(
            status_code=403,
            detail="The role '" + x_role + "' is not allowed to do this",
        )


def find_restaurant(restaurant_id):
    for restaurant in restaurants:
        if restaurant["id"] == restaurant_id:
            return restaurant
    raise HTTPException(status_code=404, detail="Restaurant not found")


def find_menu_item(menu_item_id):
    for item in menu_items:
        if item["id"] == menu_item_id:
            return item
    raise HTTPException(status_code=404, detail="Menu item not found")


def find_customer(customer_id):
    for customer in customers:
        if customer["id"] == customer_id:
            return customer
    raise HTTPException(status_code=404, detail="Customer not found")


def find_order(order_id):
    for order in orders:
        if order["id"] == order_id:
            return order
    raise HTTPException(status_code=404, detail="Order not found")


def next_id(items):
    """Return highest id + 1, or 1 when the list is empty."""
    return max([item["id"] for item in items], default=0) + 1


def pick_today(today):
    """Use the optional test date, or the real date when it was not supplied."""
    if today is None:
        return date.today()
    return today


def order_has_restaurant_history(restaurant_id):
    for order in orders:
        if order["restaurant_id"] == restaurant_id:
            return True
    return False


def order_has_customer_history(customer_id):
    for order in orders:
        if order["customer_id"] == customer_id:
            return True
    return False


def menu_item_has_order_history(menu_item_id):
    for order in orders:
        for ordered_item in order["items"]:
            if ordered_item["menu_item_id"] == menu_item_id:
                return True
    return False


def order_view(order):
    """Return an order dictionary; its item prices are already snapshots."""
    return order


def count_orders_with_status(status):
    count = 0
    for order in orders:
        if order["status"] == status:
            count = count + 1
    return count

# =====================================================================
# SECTION 5 - ENDPOINTS
# Data-changing endpoints check role, existence and rules before changing,
# then save the relevant JSON file and return the response.
# =====================================================================

# ---------- health and restaurant browsing (public) ----------
@app.get("/health", response_model=HealthOut, tags=["system"], summary="Check whether the API is running")
def health():
    return {"status": "ok"}


@app.get("/restaurants", response_model=list[RestaurantOut], tags=["restaurants"], summary="List restaurants")
def list_restaurants(area: str | None = None, open_only: bool = False):
    result = []
    for restaurant in restaurants:
        if area is not None and area.lower() not in restaurant["area"].lower():
            continue
        if open_only and not restaurant["open"]:
            continue
        result.append(restaurant)
    return result


@app.get("/restaurants/{restaurant_id}", response_model=RestaurantOut, tags=["restaurants"], summary="Get one restaurant")
def get_restaurant(restaurant_id: int):
    return find_restaurant(restaurant_id)


@app.post("/restaurants", status_code=201, response_model=RestaurantOut, tags=["restaurants"], summary="Add a restaurant (admin)")
def add_restaurant(body: RestaurantIn, x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    for restaurant in restaurants:
        if (restaurant["name"].lower() == body.name.lower()
                and restaurant["area"].lower() == body.area.lower()):
            raise HTTPException(status_code=409, detail="This restaurant already exists in this area")
    restaurant = {
        "id": next_id(restaurants), "name": body.name, "area": body.area,
        "cuisine": body.cuisine, "open": body.open,
    }
    restaurants.append(restaurant)
    save_data(RESTAURANTS_FILE, restaurants)
    return restaurant


@app.patch("/restaurants/{restaurant_id}", response_model=RestaurantOut, tags=["restaurants"], summary="Change restaurant details or opening status")
def update_restaurant(restaurant_id: int, body: RestaurantUpdate, x_role: str | None = Header(default=None)):
    check_role(x_role, ["restaurant", "admin"])
    restaurant = find_restaurant(restaurant_id)
    changes = body.model_dump(exclude_none=True)
    new_name = changes.get("name", restaurant["name"])
    new_area = changes.get("area", restaurant["area"])
    for other in restaurants:
        if other["id"] != restaurant_id and other["name"].lower() == new_name.lower() and other["area"].lower() == new_area.lower():
            raise HTTPException(status_code=409, detail="This restaurant already exists in this area")
    for key, value in changes.items():
        restaurant[key] = value
    save_data(RESTAURANTS_FILE, restaurants)
    return restaurant


@app.delete("/restaurants/{restaurant_id}", status_code=204, tags=["restaurants"], summary="Delete a restaurant (admin)")
def delete_restaurant(restaurant_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    restaurant = find_restaurant(restaurant_id)
    if order_has_restaurant_history(restaurant_id):
        raise HTTPException(status_code=409, detail="A restaurant with order history cannot be deleted")
    restaurants.remove(restaurant)
    # Menu items belong to a restaurant, so remove them with it.
    remaining_items = []
    for item in menu_items:
        if item["restaurant_id"] != restaurant_id:
            remaining_items.append(item)
    menu_items[:] = remaining_items
    save_data(RESTAURANTS_FILE, restaurants)
    save_data(MENU_ITEMS_FILE, menu_items)


# ---------- menu items ----------
@app.get("/restaurants/{restaurant_id}/menu", response_model=list[MenuItemOut], tags=["menu"], summary="List a restaurant's menu")
def list_menu(restaurant_id: int, category: str | None = None, available_only: bool = False):
    find_restaurant(restaurant_id)
    result = []
    for item in menu_items:
        if item["restaurant_id"] != restaurant_id:
            continue
        if category is not None and category.lower() not in item["category"].lower():
            continue
        if available_only and not item["available"]:
            continue
        result.append(item)
    return result


@app.post("/restaurants/{restaurant_id}/menu-items", status_code=201, response_model=MenuItemOut, tags=["menu"], summary="Add a menu item (restaurant or admin)")
def add_menu_item(restaurant_id: int, body: MenuItemIn, x_role: str | None = Header(default=None)):
    check_role(x_role, ["restaurant", "admin"])
    find_restaurant(restaurant_id)
    for item in menu_items:
        if item["restaurant_id"] == restaurant_id and item["name"].lower() == body.name.lower():
            raise HTTPException(status_code=409, detail="This menu item already exists at the restaurant")
    item = {
        "id": next_id(menu_items), "restaurant_id": restaurant_id,
        "name": body.name, "category": body.category,
        "price": body.price, "available": body.available,
    }
    menu_items.append(item)
    save_data(MENU_ITEMS_FILE, menu_items)
    return item


@app.get("/menu-items/{menu_item_id}", response_model=MenuItemOut, tags=["menu"], summary="Get one menu item")
def get_menu_item(menu_item_id: int):
    return find_menu_item(menu_item_id)


@app.patch("/menu-items/{menu_item_id}", response_model=MenuItemOut, tags=["menu"], summary="Change a menu item (restaurant or admin)")
def update_menu_item(menu_item_id: int, body: MenuItemUpdate, x_role: str | None = Header(default=None)):
    check_role(x_role, ["restaurant", "admin"])
    item = find_menu_item(menu_item_id)
    changes = body.model_dump(exclude_none=True)
    new_name = changes.get("name", item["name"])
    for other in menu_items:
        if other["id"] != menu_item_id and other["restaurant_id"] == item["restaurant_id"] and other["name"].lower() == new_name.lower():
            raise HTTPException(status_code=409, detail="This menu item already exists at the restaurant")
    for key, value in changes.items():
        item[key] = value
    save_data(MENU_ITEMS_FILE, menu_items)
    return item


@app.delete("/menu-items/{menu_item_id}", status_code=204, tags=["menu"], summary="Delete a menu item (restaurant or admin)")
def delete_menu_item(menu_item_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["restaurant", "admin"])
    item = find_menu_item(menu_item_id)
    if menu_item_has_order_history(menu_item_id):
        raise HTTPException(status_code=409, detail="A menu item in order history cannot be deleted")
    menu_items.remove(item)
    save_data(MENU_ITEMS_FILE, menu_items)


# ---------- customers ----------
@app.post("/customers", status_code=201, response_model=CustomerOut, tags=["customers"], summary="Register a customer")
def add_customer(body: CustomerIn, x_role: str | None = Header(default=None)):
    check_role(x_role, ["customer", "admin"])
    phone = "".join(character for character in body.phone if character.isdigit())
    for customer in customers:
        if customer["phone"] == phone:
            raise HTTPException(status_code=409, detail="This phone number is already registered")
    customer = {"id": next_id(customers), "name": body.name, "phone": phone}
    customers.append(customer)
    save_data(CUSTOMERS_FILE, customers)
    return customer


@app.get("/customers", response_model=list[CustomerOut], tags=["customers"], summary="List customers (admin)")
def list_customers(x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    return customers


@app.get("/customers/{customer_id}", response_model=CustomerOut, tags=["customers"], summary="Get one customer")
def get_customer(customer_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["customer", "admin"])
    return find_customer(customer_id)


@app.delete("/customers/{customer_id}", status_code=204, tags=["customers"], summary="Delete a customer (admin)")
def delete_customer(customer_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    customer = find_customer(customer_id)
    if order_has_customer_history(customer_id):
        raise HTTPException(status_code=409, detail="A customer with order history cannot be deleted")
    customers.remove(customer)
    save_data(CUSTOMERS_FILE, customers)


# ---------- orders ----------
@app.post("/orders", status_code=201, response_model=OrderOut, tags=["orders"], summary="Place an order (customer)")
def place_order(body: OrderIn, x_role: str | None = Header(default=None), today: date | None = None):
    check_role(x_role, ["customer"])
    restaurant = find_restaurant(body.restaurant_id)
    find_customer(body.customer_id)

    if not restaurant["open"]:
        raise HTTPException(status_code=409, detail="The restaurant is closed")

    # Repeating an item id in the same request is rejected rather than counted twice.
    seen_item_ids = []
    for requested_item in body.items:
        if requested_item.menu_item_id in seen_item_ids:
            raise HTTPException(status_code=409, detail="An item may appear only once in an order")
        seen_item_ids.append(requested_item.menu_item_id)

    order_items = []
    total = 0
    for requested_item in body.items:
        item = find_menu_item(requested_item.menu_item_id)
        if item["restaurant_id"] != body.restaurant_id:
            raise HTTPException(status_code=409, detail="All items in an order must belong to the selected restaurant")
        if not item["available"]:
            raise HTTPException(status_code=409, detail="Menu item '" + item["name"] + "' is not available")
        line_total = item["price"] * requested_item.quantity
        total = total + line_total
        order_items.append({
            "menu_item_id": item["id"],
            "name": item["name"],
            "unit_price": item["price"],
            "quantity": requested_item.quantity,
            "line_total": line_total,
        })

    if total < MIN_ORDER_VALUE:
        raise HTTPException(
            status_code=409,
            detail="Minimum order value is Rs " + str(MIN_ORDER_VALUE),
        )

    placed_date = pick_today(today).isoformat()
    order = {
        "id": next_id(orders),
        "customer_id": body.customer_id,
        "restaurant_id": body.restaurant_id,
        "items": order_items,
        "total": total,
        "status": "placed",
        "placed_on": placed_date,
        "updated_on": placed_date,
    }
    orders.append(order)
    save_data(ORDERS_FILE, orders)
    return order_view(order)


@app.get("/orders", response_model=list[OrderOut], tags=["orders"], summary="List orders (restaurant or admin)")
def list_orders(
    status: Literal["placed", "preparing", "out_for_delivery", "delivered", "cancelled"] | None = None,
    restaurant_id: int | None = Query(default=None, gt=0),
    x_role: str | None = Header(default=None),
):
    check_role(x_role, ["restaurant", "admin"])
    result = []
    for order in orders:
        if status is not None and order["status"] != status:
            continue
        if restaurant_id is not None and order["restaurant_id"] != restaurant_id:
            continue
        result.append(order_view(order))
    return result


@app.get("/orders/{order_id}", response_model=OrderOut, tags=["orders"], summary="Get one order")
def get_order(order_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["customer", "restaurant", "admin"])
    return order_view(find_order(order_id))


@app.get("/customers/{customer_id}/orders", response_model=list[OrderOut], tags=["orders"], summary="List a customer's orders")
def customer_orders(customer_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["customer", "admin"])
    find_customer(customer_id)
    result = []
    for order in orders:
        if order["customer_id"] == customer_id:
            result.append(order_view(order))
    return result


@app.patch("/orders/{order_id}/status", response_model=OrderOut, tags=["orders"], summary="Advance an order (restaurant or admin)")
def update_order_status(
    order_id: int,
    body: OrderStatusIn,
    x_role: str | None = Header(default=None),
    today: date | None = None,
):
    check_role(x_role, ["restaurant", "admin"])
    order = find_order(order_id)
    allowed_moves = ALLOWED_STATUS_MOVES[order["status"]]
    if body.status not in allowed_moves:
        raise HTTPException(
            status_code=409,
            detail="Order cannot move from '" + order["status"] + "' to '" + body.status + "'",
        )
    order["status"] = body.status
    order["updated_on"] = pick_today(today).isoformat()
    save_data(ORDERS_FILE, orders)
    return order_view(order)


@app.post("/orders/{order_id}/cancel", response_model=OrderOut, tags=["orders"], summary="Cancel an order while it is still placed")
def cancel_order(
    order_id: int,
    x_role: str | None = Header(default=None),
    today: date | None = None,
):
    check_role(x_role, ["customer", "admin"])
    order = find_order(order_id)
    if "cancelled" not in ALLOWED_STATUS_MOVES[order["status"]]:
        raise HTTPException(status_code=409, detail="Only an order with status 'placed' can be cancelled")
    order["status"] = "cancelled"
    order["updated_on"] = pick_today(today).isoformat()
    save_data(ORDERS_FILE, orders)
    return order_view(order)


# ---------- report ----------
@app.get("/stats", response_model=StatsOut, tags=["system"], summary="Food-delivery report (admin)")
def stats(x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    delivered_revenue = 0
    for order in orders:
        if order["status"] == "delivered":
            delivered_revenue = delivered_revenue + order["total"]
    return {
        "restaurants": len(restaurants),
        "menu_items": len(menu_items),
        "customers": len(customers),
        "total_orders": len(orders),
        "placed_orders": count_orders_with_status("placed"),
        "preparing_orders": count_orders_with_status("preparing"),
        "out_for_delivery_orders": count_orders_with_status("out_for_delivery"),
        "delivered_orders": count_orders_with_status("delivered"),
        "cancelled_orders": count_orders_with_status("cancelled"),
        "delivered_revenue": delivered_revenue,
    }
