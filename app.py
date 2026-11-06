import os
import sqlite3
from datetime import datetime
from functools import wraps

import qrcode
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from flask_socketio import SocketIO, emit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "restaurant.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")
socketio = SocketIO(app, cors_allowed_origins="*")

# Demo credentials. Change these before using the system outside your own computer.
MANAGER_USERNAME = os.environ.get("MANAGER_USERNAME", "admin")
MANAGER_PASSWORD = os.environ.get("MANAGER_PASSWORD", "admin123")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            price REAL NOT NULL CHECK(price >= 0),
            image_url TEXT DEFAULT '',
            is_available INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_no INTEGER NOT NULL,
            customer_note TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'New',
            total REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            menu_item_id INTEGER REFERENCES menu_items(id),
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL
        );
        """)
        count = conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]
        if count == 0:
            sample = [
                ("Paneer Tikka", "Starters", "Grilled paneer with spices", 220, "https://images.unsplash.com/photo-1567188040759-fb8a883dc6d8?w=600"),
                ("Veg Spring Rolls", "Starters", "Crispy rolls with vegetables", 160, "https://images.unsplash.com/photo-1544025162-d76694265947?w=600"),
                ("Margherita Pizza", "Main Course", "Classic cheese pizza", 280, "https://images.unsplash.com/photo-1579751626657-72bc17010498?w=600"),
                ("Veg Burger", "Main Course", "Vegetable patty with fresh lettuce", 150, "https://images.unsplash.com/photo-1520072959219-c595dc870360?w=600"),
                ("White Sauce Pasta", "Main Course", "Creamy white sauce pasta", 240, "https://images.unsplash.com/photo-1473093295043-cdd812d0e601?w=600"),
                ("Cold Coffee", "Beverages", "Chilled coffee", 120, "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=600"),
                ("Fresh Lime Soda", "Beverages", "Sweet or salted", 80, "https://images.unsplash.com/photo-1513558161293-ccaf765edfd4?w=600"),
            ]
            conn.executemany(
                "INSERT INTO menu_items(name,category,description,price,image_url) VALUES(?,?,?,?,?)",
                sample
            )


def manager_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("manager_logged_in"):
            return redirect(url_for("manager_login"))
        return fn(*args, **kwargs)
    return wrapper


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/menu/<int:table_no>")
def customer_menu(table_no):
    if table_no < 1 or table_no > 100:
        abort(404)
    with db() as conn:
        items = conn.execute(
            "SELECT * FROM menu_items WHERE is_available=1 ORDER BY category,name"
        ).fetchall()
    return render_template("menu.html", items=items, table_no=table_no)


@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    table_no = data.get("table_no")
    cart = data.get("items", [])
    note = str(data.get("note", ""))[:500]

    if not isinstance(table_no, int) or not 1 <= table_no <= 100:
        return jsonify(error="Invalid table number."), 400
    if not isinstance(cart, list) or not cart:
        return jsonify(error="Your cart is empty."), 400

    with db() as conn:
        item_ids = []
        quantities = {}
        for row in cart:
            try:
                item_id = int(row.get("id"))
                qty = int(row.get("quantity"))
            except (TypeError, ValueError, AttributeError):
                return jsonify(error="Invalid cart item."), 400
            if qty < 1 or qty > 50:
                return jsonify(error="Quantity must be between 1 and 50."), 400
            quantities[item_id] = quantities.get(item_id, 0) + qty
            item_ids.append(item_id)

        placeholders = ",".join("?" for _ in set(item_ids))
        menu_rows = conn.execute(
            f"SELECT * FROM menu_items WHERE id IN ({placeholders}) AND is_available=1",
            list(set(item_ids))
        ).fetchall()
        menu = {r["id"]: r for r in menu_rows}
        if len(menu) != len(set(item_ids)):
            return jsonify(error="One or more items are unavailable. Refresh the menu."), 400

        total = sum(menu[i]["price"] * qty for i, qty in quantities.items())
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            "INSERT INTO orders(table_no,customer_note,status,total,created_at) VALUES(?,?,?,?,?)",
            (table_no, note, "New", total, created_at)
        )
        order_id = cur.lastrowid
        for item_id, qty in quantities.items():
            item = menu[item_id]
            conn.execute(
                """INSERT INTO order_items(order_id,menu_item_id,item_name,quantity,unit_price)
                   VALUES(?,?,?,?,?)""",
                (order_id, item_id, item["name"], qty, item["price"])
            )

        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        order_items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()

    payload = {
        "id": order["id"], "table_no": order["table_no"], "status": order["status"],
        "total": order["total"], "created_at": order["created_at"],
        "customer_note": order["customer_note"],
        "items": [{"name": x["item_name"], "quantity": x["quantity"], "unit_price": x["unit_price"]} for x in order_items]
    }
    socketio.emit("new_order", payload)
    return jsonify(message="Order placed successfully!", order_id=order_id), 201


@app.route("/order/<int:order_id>")
def order_status(order_id):
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            abort(404)
        items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    return render_template("order_status.html", order=order, items=items)


@app.route("/manager/login", methods=["GET", "POST"])
def manager_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == MANAGER_USERNAME and password == MANAGER_PASSWORD:
            session["manager_logged_in"] = True
            return redirect(url_for("manager_dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")


@app.route("/manager/logout")
def manager_logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/manager")
@manager_required
def manager_dashboard():
    with db() as conn:
        orders = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100").fetchall()
        all_items = conn.execute("SELECT * FROM menu_items ORDER BY category,name").fetchall()
        today = datetime.now().strftime("%Y-%m-%d")
        sales = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM orders WHERE status='Completed' AND created_at LIKE ?",
            (today + "%",)
        ).fetchone()[0]
        active_count = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status NOT IN ('Completed','Cancelled')"
        ).fetchone()[0]
    return render_template("manager.html", orders=orders, menu_items=all_items,
                           sales=sales, active_count=active_count)


@app.route("/kitchen")
@manager_required
def kitchen_dashboard():
    with db() as conn:
        orders = conn.execute(
            "SELECT * FROM orders WHERE status NOT IN ('Completed','Cancelled') ORDER BY id ASC"
        ).fetchall()
        order_items = {}
        for order in orders:
            order_items[order["id"]] = conn.execute(
                "SELECT * FROM order_items WHERE order_id=?", (order["id"],)
            ).fetchall()
    return render_template("kitchen.html", orders=orders, order_items=order_items)


@app.post("/api/orders/<int:order_id>/status")
@manager_required
def update_order_status(order_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    allowed = {"Accepted", "Preparing", "Ready", "Completed", "Cancelled"}
    if status not in allowed:
        return jsonify(error="Invalid status."), 400
    with db() as conn:
        cur = conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        if cur.rowcount == 0:
            return jsonify(error="Order not found."), 404
    socketio.emit("order_updated", {"id": order_id, "status": status})
    return jsonify(message="Order status updated.")


@app.post("/manager/menu/add")
@manager_required
def add_menu_item():
    form = request.form
    try:
        name = form.get("name", "").strip()
        category = form.get("category", "").strip()
        price = float(form.get("price", "0"))
        if not name or not category or price < 0:
            raise ValueError()
        with db() as conn:
            conn.execute(
                "INSERT INTO menu_items(name,category,description,price,image_url) VALUES(?,?,?,?,?)",
                (name, category, form.get("description", "").strip(), price, form.get("image_url", "").strip())
            )
        flash("Menu item added.", "success")
    except ValueError:
        flash("Please enter a valid name, category and price.", "error")
    return redirect(url_for("manager_dashboard"))


@app.post("/manager/menu/<int:item_id>/availability")
@manager_required
def toggle_availability(item_id):
    with db() as conn:
        conn.execute("UPDATE menu_items SET is_available=1-is_available WHERE id=?", (item_id,))
    return redirect(url_for("manager_dashboard"))


@app.route("/manager/qr")
@manager_required
def qr_codes():
    # QR codes point to this app's current host. Set PUBLIC_BASE_URL when deployed.
    base_url = os.environ.get("PUBLIC_BASE_URL", request.url_root.rstrip("/"))
    codes = []
    for table_no in range(1, 11):
        target = f"{base_url}/menu/{table_no}"
        img = qrcode.make(target)
        filename = f"table_{table_no}.png"
        path = os.path.join(BASE_DIR, "static", filename)
        img.save(path)
        codes.append({"table_no": table_no, "filename": filename, "url": target})
    return render_template("qr_codes.html", codes=codes)


@app.route("/manager/orders/<int:order_id>")
@manager_required
def manager_order_detail(order_id):
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            abort(404)
        items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    return render_template("order_detail.html", order=order, items=items)


@app.route("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    init_db()
    print("\\nRestaurant system running at http://127.0.0.1:5000")
    print("Manager login: admin / admin123\\n")
    socketio.run(app,
    host='0.0.0.0',
    port=int(os.environ.get("PORT", 5000)),
    debug=False,
    allow_unsafe_werkzeug=True)
