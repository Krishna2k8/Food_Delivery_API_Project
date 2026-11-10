"""
main.py  -  Food Delivery API  (Swiggy / Zomato style group project)
================================================================
WHAT THIS PROGRAM IS
    Customers order food from restaurants, and every order moves through
    stages until it is delivered. It has:
      * four kinds of data (MODELS):  restaurants, menu items, customers, orders
      * three ROLES:                   customer, restaurant and admin
      * business RULES:                minimum order, delivery fee, order limit,
                                       status order, cancelling, rating
      * data that SURVIVES a restart:  four JSON files, no database
    Everything in it uses ideas from our classes: dictionaries, lists, loops,
    functions, API endpoints, Pydantic models, status codes and file handling.

HOW TO RUN IT
    1. Install once:      pip install "fastapi==0.115.6" "uvicorn==0.34.0"
    2. Start the server:  uvicorn main:app --reload
    3. Open:              http://127.0.0.1:8000/docs
    4. The first start creates restaurants.json, menu_items.json, customers.json
       and orders.json next to this file. To start again from scratch: stop the
       server, delete the four files, start the server.

HOW THE ROLES WORK (a simple stand-in for a real login)
    Every request may carry a HEADER named X-Role. Its value is one of
        customer     (registers, orders food, cancels, rates)
        restaurant   (manages the menu, opens/closes, moves orders forward)
        admin        (everything, plus restaurants, all lists, delivery, report)
    In /docs, every endpoint that needs a role shows an "x-role" box. Type the
    role there. Real systems use passwords and tokens; here the header keeps the
    idea simple.
        no header, or an unknown role  ->  401 (we do not know who you are)
        a known role that is not allowed -> 403 (we know you, but you may not)

THE RULES OF THIS FOOD DELIVERY SERVICE
    * All items of one order must come from the same restaurant.
    * A closed restaurant takes no orders; an unavailable item cannot be ordered.
    * The food must cost at least 100 rupees (before the delivery fee).
    * Delivery costs 40 rupees, and is free when the food costs 500 or more.
    * A customer may have at most 2 active orders at the same time.
    * The status only moves placed -> preparing -> out_for_delivery -> delivered.
      An order can be cancelled only while it is still "placed".
    * An order can be rated (1 to 5) only after delivery, and only once.
    * A restaurant with active orders cannot be deleted, and a menu item that is
      in an active order cannot be deleted.
    * The same phone cannot register twice; the same restaurant name in the
      same area cannot be added twice.

TESTING HELP
    POST /orders and GET /stats accept an optional ?today=YYYY-MM-DD. It makes
    the server PRETEND that today is that date, so that you can test dates.
"""
import json
import os
from datetime import date
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Food Delivery API",
    description="A group project: restaurants, menu items, customers, orders, "
                "three roles, rules and data saved in JSON files.",
    version="1.0",
)

# =====================================================================
# SECTION 1 - SETTINGS
# Rules that may change live in ONE place, as named constants.
# To change the minimum order you edit one line, not ten.
# =====================================================================
MIN_ORDER = 100             # the food must cost at least this much (rupees)
DELIVERY_FEE = 40           # rupees added to an order for delivery
FREE_DELIVERY_ABOVE = 500   # food worth this much or more is delivered free
MAX_ACTIVE_ORDERS = 2       # how many unfinished orders one customer may have
MAX_QUANTITY = 10           # the most of ONE item in one order
MAX_LINES = 10              # the most DIFFERENT items in one order
MIN_RATING = 1              # lowest rating a customer may give
MAX_RATING = 5              # highest rating a customer may give

# The three roles this system knows.
ALL_ROLES = ["customer", "restaurant", "admin"]

# The status of an order may only move along these arrows.
# Read it as:  current status -> the statuses it may change to.
ALLOWED_MOVES = {
    "placed": ["preparing", "cancelled"],
    "preparing": ["out_for_delivery"],
    "out_for_delivery": ["delivered"],
    "delivered": [],
    "cancelled": [],
}

# An order in one of these statuses is over. Every other order is ACTIVE.
FINISHED_STATUSES = ["delivered", "cancelled"]

# Only the admin may put an order into one of these statuses.
ADMIN_ONLY_STATUSES = ["delivered", "cancelled"]

# =====================================================================
# SECTION 2 - STORAGE (file handling, as in the last class)
# One JSON file per kind of data. The same two helper functions
# (load_data and save_data) serve all four files.
# =====================================================================

# FOOD_DATA is an optional setting used only for testing; by default the
# files sit next to this program, wherever the server is started from.
DATA_FOLDER = os.environ.get("FOOD_DATA", os.path.dirname(os.path.abspath(__file__)))
RESTAURANTS_FILE = os.path.join(DATA_FOLDER, "restaurants.json")
MENU_ITEMS_FILE = os.path.join(DATA_FOLDER, "menu_items.json")
CUSTOMERS_FILE = os.path.join(DATA_FOLDER, "customers.json")
ORDERS_FILE = os.path.join(DATA_FOLDER, "orders.json")

# What the service contains on the very first start.
STARTER_RESTAURANTS = [
    {"id": 1, "name": "Dosa Corner", "area": "Koramangala", "open": True},
    {"id": 2, "name": "Biryani House", "area": "Indiranagar", "open": True},
    {"id": 3, "name": "Chaat Junction", "area": "Electronic City", "open": False},
]
# price is a whole number of rupees (never a decimal).
STARTER_MENU_ITEMS = [
    {"id": 1, "restaurant_id": 1, "name": "Masala Dosa", "price": 100, "is_veg": True, "available": True},
    {"id": 2, "restaurant_id": 1, "name": "Idli Vada", "price": 60, "is_veg": True, "available": True},
    {"id": 3, "restaurant_id": 1, "name": "Filter Coffee", "price": 33, "is_veg": True, "available": True},
    {"id": 4, "restaurant_id": 1, "name": "Ghee Podi Dosa", "price": 140, "is_veg": True, "available": True},
    {"id": 5, "restaurant_id": 2, "name": "Chicken Biryani", "price": 250, "is_veg": False, "available": True},
    {"id": 6, "restaurant_id": 2, "name": "Paneer Biryani", "price": 220, "is_veg": True, "available": True},
    {"id": 7, "restaurant_id": 2, "name": "Mutton Biryani", "price": 350, "is_veg": False, "available": True},
    {"id": 8, "restaurant_id": 2, "name": "Gulab Jamun", "price": 60, "is_veg": True, "available": False},
    {"id": 9, "restaurant_id": 3, "name": "Pani Puri", "price": 50, "is_veg": True, "available": True},
    {"id": 10, "restaurant_id": 3, "name": "Samosa Chaat", "price": 70, "is_veg": True, "available": True},
    {"id": 11, "restaurant_id": 3, "name": "Mango Lassi", "price": 80, "is_veg": True, "available": True},
]
STARTER_CUSTOMERS = [
    {"id": 1, "name": "Asha Rao", "phone": "9876543210"},
    {"id": 2, "name": "Ravi Kumar", "phone": "9123456780"},
]
# An order looks like this (the date is saved as text, "2026-11-20"):
#   {"id": 1, "customer_id": 1, "restaurant_id": 1,
#    "items": [{"menu_item_id": 1, "name": "Masala Dosa", "price": 100, "quantity": 2}],
#    "items_total": 200, "delivery_fee": 40, "total": 240,
#    "status": "placed", "placed_on": "2026-11-20", "rating": None}
# The name and price of each item are COPIED into the order when it is placed,
# so a later change of the menu price does not change an old order.
# rating is None until the customer rates the order.


def save_data(path, data):
    """Write a whole list into a JSON file (replacing what was there)."""
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def starter_copy(starter):
    """A fresh copy of the starter list (so the starter itself never changes)."""
    starting_list = []
    for item in starter:
        starting_list.append(dict(item))
    return starting_list


def load_data(path, starter):
    """Read a list from a JSON file. If the file does not exist yet, or it is
    damaged, start again from `starter`. A bad file never crashes the server."""
    if not os.path.exists(path):
        starting_list = starter_copy(starter)
        save_data(path, starting_list)
        return starting_list
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if type(data) is not list:
            raise ValueError("the file does not contain a list")
        return data
    except (ValueError, OSError) as error:
        # ValueError: the text in the file is not good JSON (or not a list).
        # OSError:    the file could not be opened or read at all.
        print("WARNING: could not read " + path + " (" + str(error) + ")")
        print("         The bad file is kept as " + path + ".damaged")
        print("         Starting again from the starter data.")
        os.replace(path, path + ".damaged")
        starting_list = starter_copy(starter)
        save_data(path, starting_list)
        return starting_list


# Load everything ONCE when the server starts. From now on these four lists
# are the working copy; every change is also saved to its file.
restaurants = load_data(RESTAURANTS_FILE, STARTER_RESTAURANTS)
menu_items = load_data(MENU_ITEMS_FILE, STARTER_MENU_ITEMS)
customers = load_data(CUSTOMERS_FILE, STARTER_CUSTOMERS)
orders = load_data(ORDERS_FILE, [])


# =====================================================================
# SECTION 3 - MODELS (Pydantic)
# "In" models describe what a caller SENDS. "Out" models describe what we
# send BACK. FastAPI checks both automatically.
# =====================================================================
class RestaurantIn(BaseModel):
    """What the admin sends to add a restaurant."""
    name: str = Field(min_length=2, max_length=60, examples=["Udupi Sagar"])
    area: str = Field(min_length=2, max_length=40, examples=["Jayanagar"])
    open: bool = Field(default=True, examples=[True])


class RestaurantUpdate(BaseModel):
    """What may be sent to change SOME fields of a restaurant (PATCH)."""
    name: str | None = Field(default=None, min_length=2, max_length=60)
    area: str | None = Field(default=None, min_length=2, max_length=40)
    open: bool | None = Field(default=None)


class RestaurantOut(BaseModel):
    id: int
    name: str
    area: str
    open: bool


class MenuItemIn(BaseModel):
    """What a restaurant sends to add an item to its menu."""
    name: str = Field(min_length=2, max_length=60, examples=["Rava Idli"])
    price: int = Field(ge=1, le=5000, examples=[70])        # whole rupees
    is_veg: bool = Field(examples=[True])
    available: bool = Field(default=True, examples=[True])


class MenuItemUpdate(BaseModel):
    """What may be sent to change SOME fields of a menu item (PATCH)."""
    name: str | None = Field(default=None, min_length=2, max_length=60)
    price: int | None = Field(default=None, ge=1, le=5000)
    is_veg: bool | None = Field(default=None)
    available: bool | None = Field(default=None)


class MenuItemOut(BaseModel):
    id: int
    restaurant_id: int
    name: str
    price: int
    is_veg: bool
    available: bool


class CustomerIn(BaseModel):
    """What a customer sends to register."""
    name: str = Field(min_length=2, max_length=60, examples=["Meera Nair"])
    # pattern= is a REGULAR EXPRESSION: here "exactly 10 digits, nothing else".
    phone: str = Field(pattern=r"^[0-9]{10}$", examples=["9000000001"])


class CustomerOut(BaseModel):
    id: int
    name: str
    phone: str


class OrderLineIn(BaseModel):
    """One line of an order as the customer sends it: which item, how many."""
    menu_item_id: int = Field(gt=0, examples=[1])
    quantity: int = Field(ge=1, le=MAX_QUANTITY, examples=[2])


class OrderIn(BaseModel):
    """What a customer sends to place an order."""
    customer_id: int = Field(gt=0, examples=[1])
    restaurant_id: int = Field(gt=0, examples=[1])
    items: list[OrderLineIn] = Field(min_length=1, max_length=MAX_LINES)


class OrderLineOut(BaseModel):
    """One line of a saved order. name and price were copied from the menu."""
    menu_item_id: int
    name: str
    price: int
    quantity: int


class OrderOut(BaseModel):
    id: int
    customer_id: int
    restaurant_id: int
    items: list[OrderLineOut]
    items_total: int
    delivery_fee: int
    total: int
    status: str
    placed_on: str
    rating: int | None


class StatusIn(BaseModel):
    """What is sent to move an order to its next status."""
    status: Literal["preparing", "out_for_delivery", "delivered", "cancelled"] = Field(
        examples=["preparing"])


class RatingIn(BaseModel):
    """What a customer sends to rate a delivered order."""
    rating: int = Field(ge=MIN_RATING, le=MAX_RATING, examples=[5])


class StatsOut(BaseModel):
    """The report. Every number in it is CALCULATED from the orders."""
    total_orders: int
    orders_by_status: dict[str, int]
    orders_placed_today: int
    total_revenue: int
    average_rating: float | None
    most_ordered_item_id: int | None
    most_ordered_item_name: str | None
    busiest_restaurant_id: int | None


# =====================================================================
# SECTION 4 - HELPER FUNCTIONS
# Small functions that the endpoints share. Writing each idea ONCE keeps
# the endpoints short and the rules consistent.
# =====================================================================

# Stop the request unless the X-Role header is one of the `allowed` roles.
def check_role(x_role, allowed):
    if x_role not in ALL_ROLES:
        raise HTTPException(status_code=401,
                            detail="Send the header X-Role with the value customer, restaurant or admin")
    if x_role not in allowed:
        raise HTTPException(status_code=403,
                            detail="The role '" + x_role + "' is not allowed to do this")


# Return the restaurant with this id, or stop with 404.
def find_restaurant(restaurant_id):
    for restaurant in restaurants:
        if restaurant["id"] == restaurant_id:
            return restaurant
    raise HTTPException(status_code=404, detail="Restaurant not found")


# Return the menu item with this id, or stop with 404.
def find_menu_item(menu_item_id):
    for menu_item in menu_items:
        if menu_item["id"] == menu_item_id:
            return menu_item
    raise HTTPException(status_code=404, detail="Menu item " + str(menu_item_id) + " not found")


# Return the customer with this id, or stop with 404.
def find_customer(customer_id):
    for customer in customers:
        if customer["id"] == customer_id:
            return customer
    raise HTTPException(status_code=404, detail="Customer not found")


# Return the order with this id, or stop with 404.
def find_order(order_id):
    for order in orders:
        if order["id"] == order_id:
            return order
    raise HTTPException(status_code=404, detail="Order not found")


# The next free id for a list of dictionaries: highest id + 1.
def next_id(items):
    highest = 0
    for item in items:
        if item["id"] > highest:
            highest = item["id"]
    return highest + 1


# True while an order is still on its way (not delivered and not cancelled).
def is_active(order):
    return order["status"] not in FINISHED_STATUSES


# How many active orders this customer has right now.
def active_orders_of_customer(customer_id):
    count = 0
    for order in orders:
        if order["customer_id"] == customer_id and is_active(order):
            count = count + 1
    return count


# How many active orders this restaurant has right now.
def active_orders_of_restaurant(restaurant_id):
    count = 0
    for order in orders:
        if order["restaurant_id"] == restaurant_id and is_active(order):
            count = count + 1
    return count


# True if this menu item is inside any active order.
def menu_item_in_active_order(menu_item_id):
    for order in orders:
        if is_active(order):
            for line in order["items"]:
                if line["menu_item_id"] == menu_item_id:
                    return True
    return False


# True if ANOTHER restaurant (not skip_id) already has this name in this area.
def restaurant_name_taken(name, area, skip_id):
    for restaurant in restaurants:
        if restaurant["id"] == skip_id:
            continue
        if restaurant["name"].lower() == name.lower() and restaurant["area"].lower() == area.lower():
            return True
    return False


# The delivery fee for an order whose food costs items_total rupees.
# This is the ONLY place where the fee is decided.
def calculate_delivery_fee(items_total):
    if items_total >= FREE_DELIVERY_ABOVE:
        return 0
    return DELIVERY_FEE


# Stop with 409 unless the order may move from its status to new_status.
def check_move(order, new_status):
    if new_status not in ALLOWED_MOVES[order["status"]]:
        raise HTTPException(status_code=409,
                            detail="An order that is '" + order["status"] +
                                   "' cannot become '" + new_status + "'")


# Today's date, unless the caller asked us to pretend it is another day.
def pick_today(today):
    if today is None:
        return date.today()
    return today


# =====================================================================
# SECTION 5 - ENDPOINTS
# Every endpoint that changes data does these steps in this order:
# (1) check the role, (2) check that things exist (404), (3) check the
# rules (409), (4) change the data, (5) SAVE the file, (6) reply.
# =====================================================================

# ---------- health (no role needed) ----------
# Tells the caller that the server is running.
@app.get("/health", tags=["system"], summary="Is the server alive?")
def health():
    return {"status": "ok"}


# ---------- restaurants ----------
# Lists the restaurants. Anyone may look. ?area= keeps one area,
# ?open_only=true hides the closed ones.
@app.get("/restaurants", response_model=list[RestaurantOut], tags=["restaurants"],
         summary="List restaurants")
def list_restaurants(area: str | None = None, open_only: bool = False):
    result = []
    for restaurant in restaurants:
        if area is not None and area.lower() not in restaurant["area"].lower():
            continue
        if open_only and not restaurant["open"]:
            continue
        result.append(restaurant)
    return result


# Shows one restaurant. Anyone may look.
@app.get("/restaurants/{restaurant_id}", response_model=RestaurantOut, tags=["restaurants"],
         summary="Get one restaurant")
def get_restaurant(restaurant_id: int):
    return find_restaurant(restaurant_id)


# Adds a new restaurant. Only the admin may do this.
@app.post("/restaurants", status_code=201, response_model=RestaurantOut, tags=["restaurants"],
          summary="Add a restaurant (admin)")
def add_restaurant(body: RestaurantIn, x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    if restaurant_name_taken(body.name, body.area, 0):
        raise HTTPException(status_code=409, detail="This restaurant already exists in this area")
    restaurant = {"id": next_id(restaurants), "name": body.name, "area": body.area,
                  "open": body.open}
    restaurants.append(restaurant)
    save_data(RESTAURANTS_FILE, restaurants)
    return restaurant


# Changes some fields of a restaurant. This is how it is opened or closed:
# send {"open": false}.
@app.patch("/restaurants/{restaurant_id}", response_model=RestaurantOut, tags=["restaurants"],
           summary="Change a restaurant, for example open or close it (restaurant, admin)")
def update_restaurant(restaurant_id: int, body: RestaurantUpdate,
                      x_role: str | None = Header(default=None)):
    check_role(x_role, ["restaurant", "admin"])
    restaurant = find_restaurant(restaurant_id)
    changes = body.model_dump(exclude_none=True)       # only the fields that were sent
    if len(changes) == 0:
        raise HTTPException(status_code=400, detail="Send at least one field to change")
    new_name = changes.get("name", restaurant["name"])
    new_area = changes.get("area", restaurant["area"])
    if restaurant_name_taken(new_name, new_area, restaurant_id):
        raise HTTPException(status_code=409, detail="Another restaurant has this name in this area")
    for key, value in changes.items():
        restaurant[key] = value
    save_data(RESTAURANTS_FILE, restaurants)
    return restaurant


# Deletes a restaurant and its menu. Only the admin may do this, and only
# when the restaurant has no active orders.
@app.delete("/restaurants/{restaurant_id}", status_code=204, tags=["restaurants"],
            summary="Delete a restaurant (admin)")
def delete_restaurant(restaurant_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    restaurant = find_restaurant(restaurant_id)
    if active_orders_of_restaurant(restaurant_id) > 0:
        raise HTTPException(status_code=409, detail="This restaurant still has active orders")
    restaurants.remove(restaurant)
    # Its menu goes with it: keep only the items of the OTHER restaurants.
    kept_items = []
    for menu_item in menu_items:
        if menu_item["restaurant_id"] != restaurant_id:
            kept_items.append(menu_item)
    menu_items.clear()
    menu_items.extend(kept_items)
    save_data(RESTAURANTS_FILE, restaurants)
    save_data(MENU_ITEMS_FILE, menu_items)


# ---------- menu ----------
# Lists the menu of one restaurant. Anyone may look. ?veg_only=true keeps
# the vegetarian items, ?max_price=100 keeps items that cost 100 or less.
@app.get("/restaurants/{restaurant_id}/menu", response_model=list[MenuItemOut], tags=["menu"],
         summary="The menu of one restaurant")
def list_menu(restaurant_id: int, veg_only: bool = False, max_price: int | None = None):
    find_restaurant(restaurant_id)                      # 404 if there is no such restaurant
    result = []
    for menu_item in menu_items:
        if menu_item["restaurant_id"] != restaurant_id:
            continue
        if veg_only and not menu_item["is_veg"]:
            continue
        if max_price is not None and menu_item["price"] > max_price:
            continue
        result.append(menu_item)
    return result


# Adds an item to the menu of one restaurant.
@app.post("/restaurants/{restaurant_id}/menu", status_code=201, response_model=MenuItemOut,
          tags=["menu"], summary="Add a menu item (restaurant, admin)")
def add_menu_item(restaurant_id: int, body: MenuItemIn,
                  x_role: str | None = Header(default=None)):
    check_role(x_role, ["restaurant", "admin"])
    find_restaurant(restaurant_id)                      # 404 if there is no such restaurant
    menu_item = {"id": next_id(menu_items), "restaurant_id": restaurant_id, "name": body.name,
                 "price": body.price, "is_veg": body.is_veg, "available": body.available}
    menu_items.append(menu_item)
    save_data(MENU_ITEMS_FILE, menu_items)
    return menu_item


# Changes some fields of a menu item, for example its price, or
# {"available": false} when the kitchen has run out.
@app.patch("/menu-items/{menu_item_id}", response_model=MenuItemOut, tags=["menu"],
           summary="Change a menu item (restaurant, admin)")
def update_menu_item(menu_item_id: int, body: MenuItemUpdate,
                     x_role: str | None = Header(default=None)):
    check_role(x_role, ["restaurant", "admin"])
    menu_item = find_menu_item(menu_item_id)
    changes = body.model_dump(exclude_none=True)       # only the fields that were sent
    if len(changes) == 0:
        raise HTTPException(status_code=400, detail="Send at least one field to change")
    for key, value in changes.items():
        menu_item[key] = value
    save_data(MENU_ITEMS_FILE, menu_items)
    return menu_item


# Removes an item from the menu, but not while an active order contains it.
@app.delete("/menu-items/{menu_item_id}", status_code=204, tags=["menu"],
            summary="Delete a menu item (restaurant, admin)")
def delete_menu_item(menu_item_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["restaurant", "admin"])
    menu_item = find_menu_item(menu_item_id)
    if menu_item_in_active_order(menu_item_id):
        raise HTTPException(status_code=409, detail="This item is in an active order")
    menu_items.remove(menu_item)
    save_data(MENU_ITEMS_FILE, menu_items)


# ---------- customers ----------
# Registers a new customer. The phone number must not be used already.
@app.post("/customers", status_code=201, response_model=CustomerOut, tags=["customers"],
          summary="Register a customer (customer, admin)")
def add_customer(body: CustomerIn, x_role: str | None = Header(default=None)):
    check_role(x_role, ["customer", "admin"])
    for customer in customers:
        if customer["phone"] == body.phone:
            raise HTTPException(status_code=409, detail="This phone number is already registered")
    customer = {"id": next_id(customers), "name": body.name, "phone": body.phone}
    customers.append(customer)
    save_data(CUSTOMERS_FILE, customers)
    return customer


# Lists every customer. Only the admin may see the whole list.
@app.get("/customers", response_model=list[CustomerOut], tags=["customers"],
         summary="List customers (admin)")
def list_customers(x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    return customers


# Shows the details of one customer.
@app.get("/customers/{customer_id}", response_model=CustomerOut, tags=["customers"],
         summary="Get one customer (customer, admin)")
def get_customer(customer_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["customer", "admin"])
    return find_customer(customer_id)


# Lists all the orders of one customer, old and new.
@app.get("/customers/{customer_id}/orders", response_model=list[OrderOut], tags=["customers"],
         summary="All orders of one customer (customer, admin)")
def customer_orders(customer_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["customer", "admin"])
    find_customer(customer_id)                          # 404 if there is no such customer
    result = []
    for order in orders:
        if order["customer_id"] == customer_id:
            result.append(order)
    return result


# ---------- orders ----------
# Places an order. This is the endpoint with the most rules.
@app.post("/orders", status_code=201, response_model=OrderOut, tags=["orders"],
          summary="Place an order (customer, admin)")
def place_order(body: OrderIn, x_role: str | None = Header(default=None),
                today: date | None = None):
    check_role(x_role, ["customer", "admin"])
    find_customer(body.customer_id)                     # 404 if unknown
    restaurant = find_restaurant(body.restaurant_id)    # 404 if unknown
    chosen = []                                         # the menu items, in the order sent
    for line in body.items:
        chosen.append(find_menu_item(line.menu_item_id))    # 404 if unknown

    # The rules, checked in this order; the FIRST one that fails stops the request.
    seen_ids = []
    for menu_item in chosen:
        if menu_item["id"] in seen_ids:
            raise HTTPException(status_code=400,
                                detail="List each item once and use quantity for more")
        seen_ids.append(menu_item["id"])
    if not restaurant["open"]:
        raise HTTPException(status_code=409, detail="This restaurant is closed")
    for menu_item in chosen:
        if menu_item["restaurant_id"] != body.restaurant_id:
            raise HTTPException(status_code=409,
                                detail="All items must belong to the same restaurant; '" +
                                       menu_item["name"] + "' does not")
        if not menu_item["available"]:
            raise HTTPException(status_code=409,
                                detail="'" + menu_item["name"] + "' is not available right now")

    # Build the lines of the order, COPYING the name and the price, and add up.
    order_lines = []
    items_total = 0
    position = 0
    for line in body.items:
        menu_item = chosen[position]
        order_lines.append({"menu_item_id": menu_item["id"], "name": menu_item["name"],
                            "price": menu_item["price"], "quantity": line.quantity})
        items_total = items_total + menu_item["price"] * line.quantity
        position = position + 1

    if items_total < MIN_ORDER:
        raise HTTPException(status_code=409,
                            detail="The minimum order is " + str(MIN_ORDER) +
                                   " rupees; this one is " + str(items_total))
    if active_orders_of_customer(body.customer_id) >= MAX_ACTIVE_ORDERS:
        raise HTTPException(status_code=409,
                            detail="Limit reached: a customer may have " +
                                   str(MAX_ACTIVE_ORDERS) + " active orders")

    delivery_fee = calculate_delivery_fee(items_total)
    order = {"id": next_id(orders), "customer_id": body.customer_id,
             "restaurant_id": body.restaurant_id, "items": order_lines,
             "items_total": items_total, "delivery_fee": delivery_fee,
             "total": items_total + delivery_fee, "status": "placed",
             "placed_on": pick_today(today).isoformat(), "rating": None}
    orders.append(order)
    save_data(ORDERS_FILE, orders)
    return order


# Lists orders. `Literal[...]` limits ?status= to a fixed list: anything else
# gives 422 for free, and /docs shows a drop-down. ?restaurant_id= keeps the
# orders of one restaurant (this is how a kitchen sees what to cook).
@app.get("/orders", response_model=list[OrderOut], tags=["orders"],
         summary="List orders, optionally filtered (restaurant, admin)")
def list_orders(status: Literal["placed", "preparing", "out_for_delivery",
                                "delivered", "cancelled"] | None = None,
                restaurant_id: int | None = None,
                x_role: str | None = Header(default=None)):
    check_role(x_role, ["restaurant", "admin"])
    result = []
    for order in orders:
        if status is not None and order["status"] != status:
            continue
        if restaurant_id is not None and order["restaurant_id"] != restaurant_id:
            continue
        result.append(order)
    return result


# Shows one order.
@app.get("/orders/{order_id}", response_model=OrderOut, tags=["orders"],
         summary="Get one order (any role)")
def get_order(order_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["customer", "restaurant", "admin"])
    return find_order(order_id)


# Moves an order to its next status. A restaurant may set "preparing" and
# "out_for_delivery"; only the admin may set "delivered" or "cancelled".
@app.patch("/orders/{order_id}/status", response_model=OrderOut, tags=["orders"],
           summary="Move an order to its next status (restaurant, admin)")
def change_order_status(order_id: int, body: StatusIn,
                        x_role: str | None = Header(default=None)):
    check_role(x_role, ["restaurant", "admin"])
    if body.status in ADMIN_ONLY_STATUSES and x_role != "admin":
        raise HTTPException(status_code=403,
                            detail="Only the admin may mark an order " + body.status)
    order = find_order(order_id)
    check_move(order, body.status)                      # 409 if this move is not allowed
    order["status"] = body.status
    save_data(ORDERS_FILE, orders)
    return order


# Cancels an order. ALLOWED_MOVES only lets "placed" become "cancelled", so
# once the kitchen has started (preparing) it is too late.
@app.post("/orders/{order_id}/cancel", response_model=OrderOut, tags=["orders"],
          summary="Cancel an order that is still placed (customer, admin)")
def cancel_order(order_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["customer", "admin"])
    order = find_order(order_id)
    check_move(order, "cancelled")                      # 409 unless the status is "placed"
    order["status"] = "cancelled"
    save_data(ORDERS_FILE, orders)
    return order


# Rates an order from 1 to 5: only after it was delivered, and only once.
@app.post("/orders/{order_id}/rate", response_model=OrderOut, tags=["orders"],
          summary="Rate a delivered order (customer, admin)")
def rate_order(order_id: int, body: RatingIn, x_role: str | None = Header(default=None)):
    check_role(x_role, ["customer", "admin"])
    order = find_order(order_id)
    if order["status"] != "delivered":
        raise HTTPException(status_code=409, detail="Only a delivered order can be rated")
    if order["rating"] is not None:
        raise HTTPException(status_code=409, detail="This order was already rated")
    order["rating"] = body.rating
    save_data(ORDERS_FILE, orders)
    return order


# ---------- report ----------
# Calculates a summary from the orders. Nothing here is stored: every number
# is counted fresh each time. Cancelled orders are left out of the
# "most ordered item" and the "busiest restaurant".
@app.get("/stats", response_model=StatsOut, tags=["system"], summary="Report (admin)")
def stats(today: date | None = None, x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    now = pick_today(today).isoformat()

    by_status = {}                                       # status -> how many orders
    for status in ALLOWED_MOVES:
        by_status[status] = 0
    placed_today = 0
    total_revenue = 0
    rating_sum = 0
    rating_count = 0
    times_ordered = {}                                   # menu_item_id -> how many were ordered
    item_names = {}                                      # menu_item_id -> its name
    orders_per_restaurant = {}                           # restaurant_id -> how many orders
    for order in orders:
        by_status[order["status"]] = by_status[order["status"]] + 1
        if order["placed_on"] == now:
            placed_today = placed_today + 1
        if order["status"] == "delivered":
            total_revenue = total_revenue + order["total"]
        if order["rating"] is not None:
            rating_sum = rating_sum + order["rating"]
            rating_count = rating_count + 1
        if order["status"] == "cancelled":
            continue
        restaurant_id = order["restaurant_id"]
        orders_per_restaurant[restaurant_id] = orders_per_restaurant.get(restaurant_id, 0) + 1
        for line in order["items"]:
            item_id = line["menu_item_id"]
            times_ordered[item_id] = times_ordered.get(item_id, 0) + line["quantity"]
            item_names[item_id] = line["name"]

    average_rating = None
    if rating_count > 0:
        average_rating = round(rating_sum / rating_count, 2)

    # Most ordered item: highest count; on a tie the smaller id wins.
    most_ordered = None
    best_count = 0
    for item_id in sorted(times_ordered):
        if times_ordered[item_id] > best_count:
            best_count = times_ordered[item_id]
            most_ordered = item_id
    most_ordered_name = None
    if most_ordered is not None:
        most_ordered_name = item_names[most_ordered]

    # Busiest restaurant: most orders; on a tie the smaller id wins.
    busiest = None
    best_count = 0
    for restaurant_id in sorted(orders_per_restaurant):
        if orders_per_restaurant[restaurant_id] > best_count:
            best_count = orders_per_restaurant[restaurant_id]
            busiest = restaurant_id

    return {
        "total_orders": len(orders),
        "orders_by_status": by_status,
        "orders_placed_today": placed_today,
        "total_revenue": total_revenue,
        "average_rating": average_rating,
        "most_ordered_item_id": most_ordered,
        "most_ordered_item_name": most_ordered_name,
        "busiest_restaurant_id": busiest,
    }
