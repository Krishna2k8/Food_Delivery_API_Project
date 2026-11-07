# Design Note: Food Delivery API

## 1. Domain

The Food Delivery API represents a small food-delivery service. Customers browse restaurants and their menus, then place an order from one restaurant. Restaurant staff manage restaurant details and menu availability, and move an order through preparation and delivery stages. An admin manages restaurant and customer records and can view a summary report. The project is a classroom API only: it stores data in JSON files and does not process real payments, use maps, or provide real authentication.

## 2. Roles

| Role | May do | May not do |
|---|---|---|
| Anyone (no role) | Check API health and browse restaurants and menus | Change records or access protected records |
| Customer | Register a customer; view customer/order details; place orders; view a customer's orders; cancel an order while it is still placed | Manage restaurants/menus, advance delivery status, list all customers/orders, view report |
| Restaurant | Change restaurant details/open status; add, update and delete menu items; list orders; advance order status | Create/delete restaurants or customers; place/cancel customer orders; view report |
| Admin | Manage restaurants/customers; manage menus; list and view orders; advance or cancel eligible orders; view report | Bypass allowed status moves or cancel an order after preparation starts |

`X-Role` is a teaching stand-in for login. It verifies a role label only. IDs are passed in paths and bodies; passwords, tokens and per-account ownership checks are out of scope.

## 3. Models

| Model | Fields and types | Purpose / links |
|---|---|---|
| Restaurant | `id: int`, `name: str`, `area: str`, `cuisine: str`, `open: bool` | One restaurant has many menu items and orders |
| MenuItem | `id: int`, `restaurant_id: int`, `name: str`, `category: str`, `price: int`, `available: bool` | Belongs to one restaurant |
| Customer | `id: int`, `name: str`, `phone: str` | One customer may have many orders |
| Order | `id: int`, `customer_id: int`, `restaurant_id: int`, `items: list`, `total: int`, `status: str`, `placed_on: str`, `updated_on: str` | Link model: one customer + one restaurant; its item list stores menu-item IDs and price snapshots |

Order item fields: `menu_item_id: int`, `name: str`, `unit_price: int`, `quantity: int`, `line_total: int`. Prices are whole rupees. The price is copied into the order so that later menu-price changes do not rewrite order history.

```text
Restaurant 1 --------< MenuItem
     |
     +----------------< Order >---------------- 1 Customer
                              |
                              +-- items: menu_item_id, quantity, price snapshot
```

## 4. Endpoints

| Method and path | Who | Success | Error codes |
|---|---|---:|---|
| `GET /health` | Anyone | 200 | — |
| `GET /restaurants` | Anyone | 200 | 422 |
| `GET /restaurants/{restaurant_id}` | Anyone | 200 | 404 |
| `POST /restaurants` | Admin | 201 | 401, 403, 409, 422 |
| `PATCH /restaurants/{restaurant_id}` | Restaurant, admin | 200 | 401, 403, 404, 409, 422 |
| `DELETE /restaurants/{restaurant_id}` | Admin | 204 | 401, 403, 404, 409 |
| `GET /restaurants/{restaurant_id}/menu` | Anyone | 200 | 404, 422 |
| `POST /restaurants/{restaurant_id}/menu-items` | Restaurant, admin | 201 | 401, 403, 404, 409, 422 |
| `GET /menu-items/{menu_item_id}` | Anyone | 200 | 404 |
| `PATCH /menu-items/{menu_item_id}` | Restaurant, admin | 200 | 401, 403, 404, 409, 422 |
| `DELETE /menu-items/{menu_item_id}` | Restaurant, admin | 204 | 401, 403, 404, 409 |
| `POST /customers` | Customer, admin | 201 | 401, 403, 409, 422 |
| `GET /customers` | Admin | 200 | 401, 403 |
| `GET /customers/{customer_id}` | Customer, admin | 200 | 401, 403, 404 |
| `DELETE /customers/{customer_id}` | Admin | 204 | 401, 403, 404, 409 |
| `POST /orders` | Customer | 201 | 401, 403, 404, 409, 422 |
| `GET /orders` | Restaurant, admin | 200 | 401, 403, 422 |
| `GET /orders/{order_id}` | Customer, restaurant, admin | 200 | 401, 403, 404 |
| `GET /customers/{customer_id}/orders` | Customer, admin | 200 | 401, 403, 404 |
| `PATCH /orders/{order_id}/status` | Restaurant, admin | 200 | 401, 403, 404, 409, 422 |
| `POST /orders/{order_id}/cancel` | Customer, admin | 200 | 401, 403, 404, 409 |
| `GET /stats` | Admin | 200 | 401, 403 |

Total: 22 endpoints. Query filters include `area`, `open_only`, `category`, `available_only`, `status` and `restaurant_id`.

## 5. Rules

| # | Rule | Status | Reason |
|---|---|---:|---|
| 1 | All items in an order must belong to the selected restaurant | 409 | One restaurant prepares one order |
| 2 | Closed restaurants cannot accept orders | 409 | Restaurant is not accepting orders |
| 3 | Unavailable menu items cannot be ordered | 409 | Item cannot be prepared |
| 4 | Order value must be at least ₹100 | 409 | Minimum basket value |
| 5 | The same menu item ID cannot appear twice in one order | 409 | Quantity belongs in one line |
| 6 | Order status can move only through the status dictionary | 409 | Prevents skipping and reversing stages |
| 7 | Only `placed` orders can be cancelled | 409 | Preparation may already have begun |
| 8 | A restaurant with order history cannot be deleted | 409 | Retains order references |
| 9 | A customer with order history cannot be deleted | 409 | Retains order references |
| 10 | A menu item used in order history cannot be deleted | 409 | Retains item references |
| 11 | Duplicate restaurant/name-area, menu-item/name-restaurant and customer phone records are refused | 409 | Avoids duplicate records |

Order status moves:

```text
placed -> preparing -> out_for_delivery -> delivered
   |
   +-> cancelled
```

## 6. First 10 test checklist rows

| # | Request | State needed | Expected |
|---:|---|---|---|
| 1 | `GET /health` | Any | 200; status is `ok` |
| 2 | `GET /restaurants` | Clean start | 200; 3 starter restaurants |
| 3 | `GET /restaurants?area=Indiranagar` | Clean start | 200; one restaurant |
| 4 | `GET /restaurants?open_only=true` | Clean start | 200; two open restaurants |
| 5 | `GET /restaurants/99` | No id 99 | 404 |
| 6 | `GET /restaurants/1/menu` | Clean start | 200; 3 menu items |
| 7 | `GET /restaurants/2/menu?available_only=true` | Clean start | 200; unavailable item is not included |
| 8 | `GET /restaurants/2/menu?category=Main` | Clean start | 200; one matching menu item |
| 9 | `GET /menu-items/99` | No id 99 | 404 |
| 10 | `POST /restaurants` with no `X-Role` | Any | 401 |

The complete 55-row checklist is in `README.md`.

## 7. Team and endpoint ownership

Fill this table with the actual group members before submission. The project guide requires 4–6 students and at least 2 endpoints per member; the exact names and roll numbers were not supplied, so they are intentionally left blank.

| Member name | Roll number | Endpoint/features owned (minimum 2 endpoints) |
|---|---|---|
| __________________ | __________________ | ______________________________ |
| __________________ | __________________ | ______________________________ |
| __________________ | __________________ | ______________________________ |
| __________________ | __________________ | ______________________________ |
| __________________ | __________________ | ______________________________ |
| __________________ | __________________ | ______________________________ |

Suggested feature split: (1) restaurants and menu; (2) customers; (3) order creation and validation; (4) order status/cancellation and report; (5–6) testing, review and README. Every member should be able to explain the full project, not only their own endpoints.
