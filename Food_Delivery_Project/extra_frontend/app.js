/* Tiffin Run - the front end of the Food Delivery API.
   It has no data of its own: every list it shows and every button it has
   is one request to the FastAPI server (main.py). The role chosen at the
   top is sent as the X-Role header, exactly like typing it in /docs. */

const STAGES = ["placed", "preparing", "out_for_delivery", "delivered"];
const STAGE_NAMES = { placed: "Placed", preparing: "Preparing", out_for_delivery: "On the way",
                      delivered: "Delivered", cancelled: "Cancelled" };

const state = {
  role: "",            // "", "customer", "restaurant" or "admin"
  tab: "",             // which tab of the current role is open
  restaurants: [],     // last list from GET /restaurants
  browseId: null,      // restaurant whose menu is shown
  customer: null,      // the customer who is ordering
  cart: [],            // [{item, quantity}] - all from one restaurant
  kitchenId: null,     // restaurant chosen in the Restaurant role
  orderFilter: "",     // admin: status filter
  statsDay: "",        // admin: ?today= for the report
};

const main = document.getElementById("main");

/* ---------- small helpers ---------- */

// Build an HTML element. Text is always added as text, never as HTML.
function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, "");
    else if (value !== false && value != null) node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function rupees(amount) { return "₹" + amount; }

let toastTimer = null;
function toast(message, bad) {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.className = "show" + (bad ? " bad" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () { box.className = ""; }, bad ? 5200 : 2600);
}

// Turn the "detail" of an error reply into one readable sentence.
function explain(data) {
  if (!data || data.detail == null) return "";
  if (typeof data.detail === "string") return data.detail;
  return data.detail.map(function (problem) {
    const where = problem.loc ? problem.loc.slice(1).join(".") : "";
    return (where ? where + ": " : "") + problem.msg;
  }).join("; ");
}

function addToLog(method, path, status, why) {
  const bad = status >= 400 || status === 0;
  const item = el("li", { class: bad ? "bad" : "" },
    el("div", { class: "req" },
      el("span", { class: "path" }, method + " " + path),
      el("span", { class: "code" }, status === 0 ? "no reply" : status)),
    el("div", { class: "who" }, state.role ? "X-Role: " + state.role : "no X-Role header"),
    why ? el("div", { class: "why" }, why) : null);
  const list = document.getElementById("log-list");
  list.prepend(item);
  while (list.children.length > 40) list.lastChild.remove();
}

// Send one request to the API. Returns {ok, status, data}.
// quiet = true: do not show a toast when it fails (the log still shows it).
async function api(method, path, body, quiet) {
  const options = { method: method, headers: {} };
  if (state.role) options.headers["X-Role"] = state.role;
  if (body !== undefined && body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    addToLog(method, path, 0, "The server did not answer. Is it running?");
    toast("The server did not answer. Is it still running?", true);
    return { ok: false, status: 0, data: null };
  }
  let data = null;
  if (response.status !== 204) {
    try { data = await response.json(); } catch (error) { data = null; }
  }
  const why = response.ok ? "" : explain(data);
  addToLog(method, path, response.status, why);
  if (!response.ok && !quiet) toast(response.status + " - " + (why || response.statusText), true);
  return { ok: response.ok, status: response.status, data: data };
}

function restaurantName(id) {
  for (const restaurant of state.restaurants) {
    if (restaurant.id === id) return restaurant.name + ", " + restaurant.area;
  }
  return "Restaurant " + id + " (no longer listed)";
}

async function loadRestaurants(query) {
  const reply = await api("GET", "/restaurants" + (query || ""));
  return reply.ok ? reply.data : [];
}

function intro(title, text) {
  return el("div", { class: "intro" }, el("h2", {}, title), el("p", {}, text));
}

function tabs(names) {
  const bar = el("div", { class: "tabs" });
  for (const name of names) {
    bar.append(el("button", { class: "tab" + (state.tab === name ? " on" : ""),
      onclick: function () { state.tab = name; render(); } }, name));
  }
  return bar;
}

function field(label, input) { return el("label", { class: "field" }, label, input); }

function vegMark(isVeg) {
  return el("span", { class: "mark" + (isVeg ? "" : " nonveg"), title: isVeg ? "Vegetarian" : "Non-vegetarian",
                      role: "img", "aria-label": isVeg ? "Vegetarian" : "Non-vegetarian" });
}

/* ---------- order ticket (used by every role) ---------- */

function rail(order) {
  const reached = STAGES.indexOf(order.status);
  const list = el("ol", { class: "rail" });
  STAGES.forEach(function (stage, index) {
    let look = "";
    if (index <= reached) look = "done";
    if (index === reached && stage !== "delivered") look = "done now";
    list.append(el("li", { class: look }, STAGE_NAMES[stage]));
  });
  return list;
}

function ticket(order, actions) {
  const rows = [];
  for (const line of order.items) {
    rows.push(el("tr", {}, el("td", {}, line.quantity + " × " + line.name),
                           el("td", { class: "num" }, rupees(line.price * line.quantity))));
  }
  rows.push(el("tr", { class: "line" }, el("td", {}, "Food"), el("td", { class: "num" }, rupees(order.items_total))));
  rows.push(el("tr", { class: "line" }, el("td", {}, "Delivery"),
               el("td", { class: "num" }, order.delivery_fee === 0 ? "Free" : rupees(order.delivery_fee))));
  rows.push(el("tr", { class: "total" }, el("td", {}, "Total"), el("td", { class: "num" }, rupees(order.total))));

  return el("article", { class: "ticket" + (order.status === "cancelled" ? " cancelled" : "") },
    el("div", { class: "ticket-head" },
      el("h3", {}, "Order " + order.id),
      order.status === "cancelled" ? el("span", { class: "stamp" }, "Cancelled") : el("span", { class: "muted" }, order.placed_on)),
    el("p", { class: "where" }, restaurantName(order.restaurant_id) + " → customer " + order.customer_id),
    el("table", {}, rows),
    order.status === "cancelled" ? null : rail(order),
    order.rating != null ? el("div", { class: "rated", "aria-label": "Rated " + order.rating + " out of 5" },
                               "★".repeat(order.rating) + "☆".repeat(5 - order.rating)) : null,
    actions && actions.length ? el("div", { class: "actions" }, actions) : null);
}

function ticketList(orders, actionsFor, emptyText) {
  if (orders.length === 0) return el("p", { class: "empty" }, emptyText);
  const box = el("div", { class: "tickets" });
  for (const order of orders.slice().reverse()) box.append(ticket(order, actionsFor(order)));
  return box;
}

async function moveOrder(order, status, done) {
  const reply = await api("PATCH", "/orders/" + order.id + "/status", { status: status });
  if (reply.ok) toast("Order " + order.id + " is now " + STAGE_NAMES[status].toLowerCase());
  done();
}

/* ---------- browsing restaurants and menus (guest and customer) ---------- */

async function browse(canOrder) {
  const areaBox = el("input", { type: "text", placeholder: "for example Indiranagar", value: browse.area || "" });
  const openBox = el("input", { type: "checkbox" });
  openBox.checked = !!browse.openOnly;
  const listBox = el("div", { class: "rest-list" });
  const menuBox = el("div", {});

  async function showList() {
    browse.area = areaBox.value.trim();
    browse.openOnly = openBox.checked;
    const parts = [];
    if (browse.area) parts.push("area=" + encodeURIComponent(browse.area));
    if (browse.openOnly) parts.push("open_only=true");
    const found = await loadRestaurants(parts.length ? "?" + parts.join("&") : "");
    if (!parts.length) state.restaurants = found;
    listBox.replaceChildren();
    if (found.length === 0) listBox.append(el("p", { class: "empty" }, "No restaurant matches. Clear the filters to see them all."));
    for (const restaurant of found) {
      listBox.append(el("button", {
        class: "rest" + (restaurant.open ? "" : " shut") + (state.browseId === restaurant.id ? " on" : ""),
        onclick: function () { state.browseId = restaurant.id; showList(); showMenu(); } },
        el("span", {}, el("strong", {}, restaurant.name), restaurant.area),
        el("span", { class: "pill " + (restaurant.open ? "open" : "shut") }, restaurant.open ? "Open" : "Closed")));
    }
  }

  const vegBox = el("input", { type: "checkbox" });
  const priceBox = el("input", { type: "number", min: "1", class: "small", placeholder: "any" });

  async function showMenu() {
    menuBox.replaceChildren();
    if (state.browseId == null) {
      menuBox.append(el("p", { class: "empty" }, "Pick a restaurant to see its menu."));
      return;
    }
    const parts = [];
    if (vegBox.checked) parts.push("veg_only=true");
    if (priceBox.value) parts.push("max_price=" + encodeURIComponent(priceBox.value));
    const reply = await api("GET", "/restaurants/" + state.browseId + "/menu" + (parts.length ? "?" + parts.join("&") : ""), null, true);
    if (!reply.ok) { state.browseId = null; showMenu(); return; }
    const list = el("ul", { class: "menu" });
    for (const item of reply.data) {
      list.append(el("li", { class: item.available ? "" : "gone" },
        vegMark(item.is_veg),
        el("span", { class: "name" }, item.name, item.available ? null : el("span", { class: "pill off", style: "margin-left:8px" }, "Not available")),
        el("span", { class: "price" }, rupees(item.price)),
        canOrder ? el("button", { class: "btn tiny quiet", onclick: function () { addToCart(item); } }, "Add") : null));
    }
    menuBox.append(el("h3", {}, "Menu of " + restaurantName(state.browseId)),
      el("div", { class: "row", style: "margin:10px 0 4px" },
        el("label", { class: "check" }, vegBox, "Vegetarian only"),
        field("Costs at most (₹)", priceBox)),
      reply.data.length ? list : el("p", { class: "empty" }, "Nothing on the menu matches."));
  }
  vegBox.addEventListener("change", showMenu);
  priceBox.addEventListener("change", showMenu);
  areaBox.addEventListener("change", showList);
  openBox.addEventListener("change", showList);

  const left = el("div", {},
    el("section", { class: "panel" }, el("h3", {}, "Restaurants"),
      el("div", { class: "row", style: "margin-bottom:12px" },
        field("Area", areaBox), el("label", { class: "check" }, openBox, "Open now only")),
      listBox),
    el("section", { class: "panel" }, menuBox));
  await showList();
  await showMenu();
  return left;
}

/* ---------- guest ---------- */

async function guestView() {
  main.replaceChildren(
    intro("Look around", "Without a role you can only read restaurants and menus. Choose Customer at the top to order."),
    await browse(false));
}

/* ---------- customer ---------- */

function addToCart(item) {
  if (state.cart.length && state.cart[0].item.restaurant_id !== item.restaurant_id) {
    state.cart = [];
    toast("The basket was emptied: one order comes from one restaurant.");
  }
  for (const line of state.cart) {
    if (line.item.id === item.id) { line.quantity = line.quantity + 1; drawCart(); return; }
  }
  state.cart.push({ item: item, quantity: 1 });
  drawCart();
}

function drawCart() {
  const box = document.getElementById("cart");
  if (!box) return;
  box.replaceChildren(el("h3", {}, "Your basket"));
  if (state.cart.length === 0) {
    box.append(el("p", { class: "empty" }, "Empty. Add something from a menu."));
    return;
  }
  let sum = 0;
  const list = el("ul", {});
  for (const line of state.cart) {
    sum = sum + line.item.price * line.quantity;
    list.append(el("li", {}, el("span", {}, line.item.name),
      el("span", { class: "qty" },
        el("button", { "aria-label": "One less " + line.item.name, onclick: function () {
          line.quantity = line.quantity - 1;
          if (line.quantity === 0) state.cart.splice(state.cart.indexOf(line), 1);
          drawCart(); } }, "−"),
        line.quantity,
        el("button", { "aria-label": "One more " + line.item.name, onclick: function () { line.quantity = line.quantity + 1; drawCart(); } }, "+")),
      el("span", {}, rupees(line.item.price * line.quantity))));
  }
  box.append(el("p", { class: "muted", style: "margin:0 0 6px" }, "From " + restaurantName(state.cart[0].item.restaurant_id)),
    list,
    el("div", { class: "sum" }, el("span", {}, "Food"), el("span", {}, rupees(sum))),
    el("p", { class: "muted", style: "margin:0 0 10px;font-size:13px" }, "The server adds the delivery fee and checks the rules."),
    el("button", { class: "btn gold", style: "width:100%", onclick: placeOrder }, "Place order"));
}

async function placeOrder() {
  const items = [];
  for (const line of state.cart) items.push({ menu_item_id: line.item.id, quantity: line.quantity });
  const reply = await api("POST", "/orders", { customer_id: state.customer.id,
    restaurant_id: state.cart[0].item.restaurant_id, items: items });
  if (reply.ok) {
    state.cart = [];
    state.tab = "My orders";
    toast("Order " + reply.data.id + " placed. Total " + rupees(reply.data.total));
    render();
  }
}

function customerGate() {
  const idBox = el("input", { type: "number", min: "1", class: "small", value: "1" });
  const nameBox = el("input", { type: "text", placeholder: "Meera Nair" });
  const phoneBox = el("input", { type: "text", placeholder: "10 digits", maxlength: "10", inputmode: "numeric" });
  async function signIn() {
    const reply = await api("GET", "/customers/" + encodeURIComponent(idBox.value || "0"));
    if (reply.ok) { state.customer = reply.data; render(); }
  }
  async function register() {
    const reply = await api("POST", "/customers", { name: nameBox.value.trim(), phone: phoneBox.value.trim() });
    if (reply.ok) { state.customer = reply.data; toast("Registered. Your customer number is " + reply.data.id); render(); }
  }
  return el("div", {},
    intro("Who is ordering?", "The starter data has customer 1 (Asha Rao) and customer 2 (Ravi Kumar)."),
    el("section", { class: "panel" }, el("h3", {}, "I already have a customer number"),
      el("div", { class: "row" }, field("Customer number", idBox), el("button", { class: "btn", onclick: signIn }, "Continue"))),
    el("section", { class: "panel" }, el("h3", {}, "I am new"),
      el("div", { class: "row" }, field("Name", nameBox), field("Phone", phoneBox),
        el("button", { class: "btn", onclick: register }, "Register"))));
}

async function customerView() {
  if (!state.customer) { main.replaceChildren(customerGate()); return; }
  if (state.tab !== "Order food" && state.tab !== "My orders") state.tab = "Order food";
  const head = el("div", { class: "intro" },
    el("h2", {}, "Hello, " + state.customer.name),
    el("p", {}, "Customer " + state.customer.id + ", phone " + state.customer.phone + ". ",
      el("button", { class: "link", onclick: function () { state.customer = null; state.cart = []; render(); } }, "Switch customer")));
  if (state.tab === "Order food") {
    const left = await browse(true);
    main.replaceChildren(head, tabs(["Order food", "My orders"]),
      el("div", { class: "split" }, left, el("section", { class: "panel cart", id: "cart" })));
    drawCart();
    return;
  }
  if (state.restaurants.length === 0) state.restaurants = await loadRestaurants("");
  const reply = await api("GET", "/customers/" + state.customer.id + "/orders");
  const orders = reply.ok ? reply.data : [];
  main.replaceChildren(head, tabs(["Order food", "My orders"]),
    ticketList(orders, function (order) {
      const actions = [];
      if (order.status === "placed") {
        actions.push(el("button", { class: "btn danger tiny", onclick: async function () {
          const answer = await api("POST", "/orders/" + order.id + "/cancel");
          if (answer.ok) toast("Order " + order.id + " cancelled");
          render(); } }, "Cancel order"));
      }
      if (order.status === "delivered" && order.rating == null) {
        const stars = el("span", { class: "stars" });
        for (let value = 1; value <= 5; value++) {
          stars.append(el("button", { "aria-label": "Rate " + value + " out of 5", onclick: async function () {
            const answer = await api("POST", "/orders/" + order.id + "/rate", { rating: value });
            if (answer.ok) toast("Rated order " + order.id + " " + value + " out of 5");
            render(); } }, "★"));
        }
        actions.push(el("span", { class: "muted" }, "Rate it:"), stars);
      }
      return actions;
    }, "No orders yet. Open Order food to place one."));
}

/* ---------- restaurant ---------- */

async function restaurantView() {
  state.restaurants = await loadRestaurants("");
  if (state.tab !== "Orders to cook" && state.tab !== "Menu") state.tab = "Orders to cook";
  let mine = null;
  for (const restaurant of state.restaurants) if (restaurant.id === state.kitchenId) mine = restaurant;
  if (!mine && state.restaurants.length) { mine = state.restaurants[0]; state.kitchenId = mine.id; }
  if (!mine) {
    main.replaceChildren(intro("No restaurants", "The admin has to add a restaurant first."));
    return;
  }
  const picker = el("select", { onchange: function () { state.kitchenId = Number(picker.value); render(); } });
  for (const restaurant of state.restaurants) {
    const option = el("option", { value: restaurant.id }, restaurant.name + ", " + restaurant.area);
    option.selected = restaurant.id === mine.id;
    picker.append(option);
  }
  const head = el("section", { class: "panel" },
    el("div", { class: "row", style: "justify-content:space-between" },
      field("Kitchen", picker),
      el("div", { class: "row", style: "align-items:center" },
        el("span", { class: "pill " + (mine.open ? "open" : "shut") }, mine.open ? "Open, taking orders" : "Closed"),
        el("button", { class: "btn " + (mine.open ? "danger" : ""), onclick: async function () {
          const reply = await api("PATCH", "/restaurants/" + mine.id, { open: !mine.open });
          if (reply.ok) toast(mine.name + (reply.data.open ? " is open" : " is closed"));
          render(); } }, mine.open ? "Close the restaurant" : "Open the restaurant"))));
  const top = [intro("Kitchen counter", "Move orders forward as you cook them, and keep the menu up to date."), head,
               tabs(["Orders to cook", "Menu"])];

  if (state.tab === "Orders to cook") {
    const reply = await api("GET", "/orders?restaurant_id=" + mine.id);
    const orders = reply.ok ? reply.data : [];
    main.replaceChildren(...top, ticketList(orders, function (order) {
      if (order.status === "placed") return [el("button", { class: "btn tiny", onclick: function () { moveOrder(order, "preparing", render); } }, "Start preparing")];
      if (order.status === "preparing") return [el("button", { class: "btn tiny", onclick: function () { moveOrder(order, "out_for_delivery", render); } }, "Send out for delivery")];
      if (order.status === "out_for_delivery") return [el("span", { class: "muted" }, "The admin marks it delivered.")];
      return [];
    }, "No orders for this kitchen yet."));
    return;
  }

  const reply = await api("GET", "/restaurants/" + mine.id + "/menu");
  const items = reply.ok ? reply.data : [];
  const body = el("tbody", {});
  for (const item of items) {
    const priceBox = el("input", { type: "number", min: "1", class: "small", value: item.price, "aria-label": "Price of " + item.name });
    body.append(el("tr", {},
      el("td", {}, vegMark(item.is_veg)),
      el("td", {}, item.name),
      el("td", {}, el("div", { class: "row" }, priceBox, el("button", { class: "btn tiny quiet", onclick: async function () {
        const answer = await api("PATCH", "/menu-items/" + item.id, { price: Number(priceBox.value) });
        if (answer.ok) toast(item.name + " now costs " + rupees(answer.data.price));
        render(); } }, "Save price"))),
      el("td", {}, el("button", { class: "btn tiny quiet", onclick: async function () {
        const answer = await api("PATCH", "/menu-items/" + item.id, { available: !item.available });
        if (answer.ok) toast(item.name + (answer.data.available ? " is available" : " is not available"));
        render(); } }, item.available ? "Mark not available" : "Mark available"),
        item.available ? null : el("span", { class: "pill off", style: "margin-left:8px" }, "Not available")),
      el("td", {}, el("button", { class: "btn tiny danger", onclick: async function () {
        const answer = await api("DELETE", "/menu-items/" + item.id);
        if (answer.ok) toast(item.name + " deleted");
        render(); } }, "Delete"))));
  }
  const nameBox = el("input", { type: "text", placeholder: "Rava Idli" });
  const newPrice = el("input", { type: "number", min: "1", class: "small", placeholder: "70" });
  const vegBox = el("input", { type: "checkbox" });
  vegBox.checked = true;
  main.replaceChildren(...top,
    el("section", { class: "panel" }, el("h3", {}, "Menu"),
      items.length ? el("div", { class: "scroll" }, el("table", { class: "grid" },
        el("thead", {}, el("tr", {}, el("th", {}, ""), el("th", {}, "Item"), el("th", {}, "Price (₹)"), el("th", {}, "On the menu today"), el("th", {}, ""))),
        body)) : el("p", { class: "empty" }, "The menu is empty. Add the first item below.")),
    el("section", { class: "panel" }, el("h3", {}, "Add an item"),
      el("div", { class: "row" }, field("Name", nameBox), field("Price (₹)", newPrice),
        el("label", { class: "check" }, vegBox, "Vegetarian"),
        el("button", { class: "btn", onclick: async function () {
          const answer = await api("POST", "/restaurants/" + mine.id + "/menu",
            { name: nameBox.value.trim(), price: Number(newPrice.value), is_veg: vegBox.checked });
          if (answer.ok) { toast(answer.data.name + " added to the menu"); render(); } } }, "Add item"))));
}

/* ---------- admin ---------- */

async function adminView() {
  const names = ["Report", "Orders", "Restaurants", "Customers"];
  if (names.indexOf(state.tab) === -1) state.tab = "Report";
  state.restaurants = await loadRestaurants("");
  const top = [intro("Control room", "The admin sees everything, adds and removes restaurants, and marks orders delivered."), tabs(names)];

  if (state.tab === "Report") {
    const reply = await api("GET", "/stats" + (state.statsDay ? "?today=" + state.statsDay : ""));
    if (!reply.ok) { main.replaceChildren(...top); return; }
    const report = reply.data;
    const dayBox = el("input", { type: "date", value: state.statsDay, onchange: function () { state.statsDay = dayBox.value; render(); } });
    function figure(value, label) { return el("div", { class: "figure" }, el("b", {}, value), el("span", {}, label)); }
    let most = 1;
    for (const status in report.orders_by_status) most = Math.max(most, report.orders_by_status[status]);
    const bars = el("div", { class: "bars" });
    for (const status in report.orders_by_status) {
      const count = report.orders_by_status[status];
      bars.append(el("div", { class: "bar" }, el("span", {}, STAGE_NAMES[status] || status),
        el("i", { style: "width:" + Math.round(count / most * 100) + "%" + (count === 0 ? ";background:#cfd6d1" : "") }),
        el("span", {}, count)));
    }
    main.replaceChildren(...top,
      el("section", { class: "panel" },
        el("div", { class: "report" },
          figure(report.total_orders, "orders in total"),
          figure(rupees(report.total_revenue), "revenue from delivered orders"),
          figure(report.average_rating == null ? "–" : report.average_rating + " / 5", "average rating"),
          figure(report.orders_placed_today, state.statsDay ? "orders placed on " + state.statsDay : "orders placed today")),
        el("div", { class: "row", style: "margin-bottom:16px" }, field("Pretend today is (optional)", dayBox)),
        el("h3", {}, "Orders by status"), bars),
      el("section", { class: "panel" }, el("h3", {}, "Favourites"),
        el("p", { style: "margin:0" }, "Most ordered item: ",
          el("strong", {}, report.most_ordered_item_name == null ? "none yet" : report.most_ordered_item_name + " (item " + report.most_ordered_item_id + ")")),
        el("p", { style: "margin:4px 0 0" }, "Busiest restaurant: ",
          el("strong", {}, report.busiest_restaurant_id == null ? "none yet" : restaurantName(report.busiest_restaurant_id)))));
    return;
  }

  if (state.tab === "Orders") {
    const filter = el("select", { onchange: function () { state.orderFilter = filter.value; render(); } },
      el("option", { value: "" }, "All orders"));
    for (const status of STAGES.concat(["cancelled"])) {
      const option = el("option", { value: status }, STAGE_NAMES[status]);
      option.selected = state.orderFilter === status;
      filter.append(option);
    }
    const reply = await api("GET", "/orders" + (state.orderFilter ? "?status=" + state.orderFilter : ""));
    const orders = reply.ok ? reply.data : [];
    main.replaceChildren(...top,
      el("div", { class: "row", style: "margin-bottom:22px" }, field("Show", filter)),
      ticketList(orders, function (order) {
        const actions = [];
        if (order.status === "placed") {
          actions.push(el("button", { class: "btn tiny", onclick: function () { moveOrder(order, "preparing", render); } }, "Start preparing"));
          actions.push(el("button", { class: "btn tiny danger", onclick: function () { moveOrder(order, "cancelled", render); } }, "Cancel order"));
        }
        if (order.status === "preparing") actions.push(el("button", { class: "btn tiny", onclick: function () { moveOrder(order, "out_for_delivery", render); } }, "Send out for delivery"));
        if (order.status === "out_for_delivery") actions.push(el("button", { class: "btn tiny gold", onclick: function () { moveOrder(order, "delivered", render); } }, "Mark delivered"));
        return actions;
      }, "No orders here."));
    return;
  }

  if (state.tab === "Restaurants") {
    const body = el("tbody", {});
    for (const restaurant of state.restaurants) {
      body.append(el("tr", {}, el("td", {}, restaurant.id), el("td", {}, restaurant.name), el("td", {}, restaurant.area),
        el("td", {}, el("span", { class: "pill " + (restaurant.open ? "open" : "shut") }, restaurant.open ? "Open" : "Closed")),
        el("td", {}, el("button", { class: "btn tiny danger", onclick: async function () {
          const answer = await api("DELETE", "/restaurants/" + restaurant.id);
          if (answer.ok) toast(restaurant.name + " deleted, with its menu");
          render(); } }, "Delete"))));
    }
    const nameBox = el("input", { type: "text", placeholder: "Udupi Sagar" });
    const areaBox = el("input", { type: "text", placeholder: "Jayanagar" });
    main.replaceChildren(...top,
      el("section", { class: "panel" }, el("h3", {}, "Restaurants"),
        el("div", { class: "scroll" }, el("table", { class: "grid" },
          el("thead", {}, el("tr", {}, el("th", {}, "No."), el("th", {}, "Name"), el("th", {}, "Area"), el("th", {}, "Now"), el("th", {}, ""))), body))),
      el("section", { class: "panel" }, el("h3", {}, "Add a restaurant"),
        el("div", { class: "row" }, field("Name", nameBox), field("Area", areaBox),
          el("button", { class: "btn", onclick: async function () {
            const answer = await api("POST", "/restaurants", { name: nameBox.value.trim(), area: areaBox.value.trim() });
            if (answer.ok) { toast(answer.data.name + " added"); render(); } } }, "Add restaurant"))));
    return;
  }

  const reply = await api("GET", "/customers");
  const body = el("tbody", {});
  for (const customer of (reply.ok ? reply.data : [])) {
    body.append(el("tr", {}, el("td", {}, customer.id), el("td", {}, customer.name), el("td", {}, customer.phone)));
  }
  main.replaceChildren(...top, el("section", { class: "panel" }, el("h3", {}, "Customers"),
    el("div", { class: "scroll" }, el("table", { class: "grid" },
      el("thead", {}, el("tr", {}, el("th", {}, "No."), el("th", {}, "Name"), el("th", {}, "Phone"))), body))));
}

/* ---------- start ---------- */

async function render() {
  for (const button of document.querySelectorAll(".role")) {
    button.classList.toggle("on", button.dataset.role === state.role);
  }
  if (state.role === "customer") await customerView();
  else if (state.role === "restaurant") await restaurantView();
  else if (state.role === "admin") await adminView();
  else await guestView();
}

for (const button of document.querySelectorAll(".role")) {
  button.addEventListener("click", function () {
    state.role = button.dataset.role;
    state.tab = "";
    render();
  });
}
document.getElementById("clear-log").addEventListener("click", function () {
  document.getElementById("log-list").replaceChildren();
});
render();
