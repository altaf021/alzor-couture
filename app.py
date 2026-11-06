from flask import Flask, render_template, request, session, jsonify, redirect, url_for, Response
import json
import logging
import os
import random
import sqlite3
import string
from contextlib import contextmanager
from datetime import datetime

from dotenv import load_dotenv
import razorpay

try:
    import psycopg
    from psycopg.types.json import Jsonb
except ImportError:
    psycopg = None
    Jsonb = None

load_dotenv()


# =========================================================
# BASIC CONFIGURATION
# =========================================================

AVAILABLE_SIZES = ["S", "M", "L", "XL", "XXL"]
SITE_URL = os.getenv("SITE_URL", "https://alzorcouture.in").strip().rstrip("/")

app = Flask(__name__)

# Production must always use a strong secret configured in the environment.
_configured_secret = os.getenv("FLASK_SECRET_KEY", "").strip()
if not _configured_secret:
    if os.getenv("DATABASE_URL", "").strip() and not os.getenv("FLASK_DEBUG", "").strip().lower() == "true":
        raise RuntimeError(
            "FLASK_SECRET_KEY must be configured in the production environment."
        )
    _configured_secret = "alzor-couture-dev-secret-key-change-in-production"
app.secret_key = _configured_secret

# Security and caching headers
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.endpoint == "order_confirmation":
        response.headers["Cache-Control"] = "no-store, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Vary"] = "Cookie"
    return response

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
RAZORPAY_IS_LIVE = RAZORPAY_KEY_ID.startswith("rzp_live_")
RAZORPAY_IS_TEST = RAZORPAY_KEY_ID.startswith("rzp_test_")


def get_razorpay_client():
    """Return a configured Razorpay client, or None when keys are missing."""
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return None
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


# =========================================================
# CO-ORD SET PRODUCTS
# =========================================================

PRODUCTS = [

    {
        "name": "Denim Éclat Set",
        "slug": "denim-eclat-set",
        "category": "CO-ORD SET",
        "price": 6999,
        "original_price": 8399,
        "images": [
            "denim-1.JPG",
            "denim-2.JPG",
            "denim-3.JPG",
            "denim-4.JPG",
            "denim-5.JPG"
        ],
        "description":
            "A refined denim two-piece where relaxed structure meets couture detail, creating an effortless silhouette with a distinctly polished, contemporary character.",
        "details": [
            "Premium denim fabric",
            "Relaxed yet structured silhouette",
            "Two-piece co-ord set",
            "Designed for elevated everyday dressing"
        ],
        "care":
            "Dry clean recommended."
    },

    {
        "name": "Scarlet MUSE Set (Black)",
        "slug": "scarlet-muse-set-black",
        "category": "CO-ORD SET",
        "price": 7499,
        "original_price": 8999,
        "images": [
            "SMB.png",
            "SMB-1.png",
            "SMB-2.png",
            "SMB-3.png",
            "SMB-4.png"
        ],
        "description":
            "A study in modern evening elegance, this black co-ord balances a confident silhouette with quiet drama for an instantly composed statement.",
        "details": [
            "Premium fabric",
            "Contemporary silhouette",
            "Two-piece set",
            "Elegant statement design"
        ],
        "care":
            "Dry clean recommended."
    },

    {
        "name": "Monochrome Fleur Set",
        "slug": "monochrome-fleur-set",
        "category": "CO-ORD SET",
        "price": 4999,
        "original_price": 5999,
        "images": [
            "MFS.jpg",
            "MFS-2.jpg",
            "MFS-3.jpg",
            "MFS-4.jpg",
            "MFS-5.jpg"
        ],
        "description":
            "An understated monochrome composition softened by floral-inspired detailing, crafted in cotton for a graceful balance of ease, texture and contemporary femininity.",
        "details": [
            "Cotton fabric",
            "Floral-inspired detailing",
            "Two-piece co-ord set",
            "Comfortable and versatile silhouette"
        ],
        "care":
            "Gentle wash or dry clean recommended."
    },

    {
        "name": "Scarlet Cipher Set",
        "slug": "scarlet-cipher-set",
        "category": "CO-ORD SET",
        "price": 5999,
        "original_price": 7199,
        "images": [
            "SCS.png",
            "SCS-2.png",
            "SCS-3.png",
            "SCS-4.png",
            "SCS-5.png",
            "SCS-6.png"
        ],
        "description":
            "A vivid scarlet statement paired with sharp black tailoring, this two-piece brings striking contrast and a sleek, assured presence to the wardrobe.",
        "details": [
            "Scarlet red top",
            "Black wide-leg trousers",
            "Two-piece co-ord set",
            "Contemporary tailored silhouette"
        ],
        "care":
            "Dry clean recommended."
    },

    {
        "name": "Alzor Golden Veil Set",
        "slug": "alzor-golden-veil-set",
        "category": "CO-ORD SET",
        "price": 5999,
        "original_price": 7199,
        "images": [
            "AGVS.png",
            "AGVS-2.png",
            "AGVS-3.png",
            "AGVS-4.png",
            "AGVS-5.png"
        ],
        "description":
            "Softly luminous and fluid in character, the Golden Veil Set drapes with understated richness, bringing a graceful golden mood to occasion dressing.",
        "details": [
            "Banana crepe fabric",
            "Soft flowing silhouette",
            "Two-piece co-ord set",
            "Elegant occasion-ready design"
        ],
        "care":
            "Dry clean recommended."
    },

    {
        "name": "Alzor Eclipse Ensemble",
        "slug": "alzor-eclipse-ensemble",
        "category": "CO-ORD SET",
        "price": 7499,
        "original_price": 8999,
        "images": [
            "AEE-1.png",
            "AEE-2.png",
            "AEE-3.png",
            "AEE-4.png",
            "AEE-5.png"
        ],
        "description":
            "A dramatic black-and-white ensemble defined by clean tailoring, floral shoulder accents and statement sleeves for a poised, architectural take on contemporary dressing.",
        "details": [
            "Black and white co-ord set",
            "Contemporary tailored silhouette",
            "Floral shoulder detailing",
            "Button-front design",
            "Statement sleeve detailing"
        ],
        "care":
            "Dry clean recommended."
    },

    {
        "name": "Pastel Edge Set",
        "slug": "pastel-edge-set",
        "category": "CO-ORD SET",
        "price": 6499,
        "original_price": 7799,
        "images": [
            "white.jpg",
            "white-2.jpeg",
            "white-3.jpeg",
            "white-4.jpeg"
        ],
        "description":
            "A softly hued two-piece with a delicate contemporary spirit, balancing clean lines and an airy palette for polished ease from day to evening.",
        "details": [
            "Two-piece co-ord set",
            "Soft pastel aesthetic",
            "Contemporary silhouette",
            "Elegant everyday statement"
        ],
        "care":
            "Gentle wash or dry clean recommended."
    },

    {
        "name": "Shadow Blossom Ensemble",
        "slug": "shadow-blossom-ensemble",
        "category": "CO-ORD SET",
        "price": 7999,
        "original_price": 9599,
        "images": [
            "SBE.png",
            "SBE-2.png",
            "SBE-3.png",
            "SBE-4.png",
            "SBE-5.png"
        ],
        "description":
            "A dark floral vision layered with a sheer, expressive overlay, combining a refined silhouette with quiet drama for an unmistakably sophisticated finish.",
        "details": [
            "Black co-ord set",
            "Floral sheer overlay",
            "Contemporary silhouette",
            "Elegant statement design"
        ],
        "care":
            "Dry clean recommended."
    }
]


# =========================================================
# DRESSES
# =========================================================

DRESSES = [

    {
        "name": "Teal Fairy Dress",
        "slug": "teal-fairy-dress",
        "category": "DRESS",
        "price": 5999,
        "original_price": 7199,
        "images": [
            "gd1.jpeg",
            "gd2.jpeg",
            "gd3.jpeg",
            "gd4.jpeg",
            "gd5.jpeg"
        ],
        "description":
            "A graceful teal silhouette framed by delicate floral neckline detailing, a button-front finish and a soft flare, completed with a defining waist belt.",
        "details": [
            "Teal dress",
            "Floral neckline detailing",
            "Button-front design",
            "Matching waist belt",
            "Soft flared silhouette"
        ],
        "care":
            "Gentle wash or dry clean recommended."
    }
]


# =========================================================
# INSTAGRAM
# =========================================================

INSTAGRAM_POSTS = [

    {
        "image": "insta-1.jpeg",
        "url": "https://www.instagram.com/p/DYjBcjSD0VV/"
    },

    {
        "image": "insta-2.jpeg",
        "url": "https://www.instagram.com/p/DYJfSCRD4_x/"
    },

    {
        "image": "insta-3.jpeg",
        "url": "https://www.instagram.com/p/DXivl08D7lP/"
    },

    {
        "image": "insta-4.jpeg",
        "url": "https://www.instagram.com/p/DW-m9WID2QF/"
    },

    {
        "image": "insta-5.jpeg",
        "url": "https://www.instagram.com/p/DYTl-rxDwm0/"
    }
]


# =========================================================
# DUAL DATABASE ORDER STORAGE (PostgreSQL / SQLite fallback)
# =========================================================

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL and psycopg is not None)
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.db")


def get_database_url():
    """Return a normalized PostgreSQL URL."""
    if not DATABASE_URL:
        return ""
    if DATABASE_URL.startswith("postgres://"):
        return "postgresql://" + DATABASE_URL[len("postgres://"):]
    return DATABASE_URL


def ensure_database_schema(conn, is_postgres=True):
    """Create the storage tables if this is the first app run."""
    if is_postgres:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_orders (
                order_number TEXT PRIMARY KEY,
                razorpay_payment_id TEXT UNIQUE NOT NULL,
                order_data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_pending_payments (
                razorpay_order_id TEXT PRIMARY KEY,
                payment_data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_orders (
                order_number TEXT PRIMARY KEY,
                razorpay_payment_id TEXT UNIQUE NOT NULL,
                order_data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_pending_payments (
                razorpay_order_id TEXT PRIMARY KEY,
                payment_data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


@contextmanager
def get_db_cursor():
    """Context manager yielding (cursor, is_postgres). Handles commits/rollbacks."""
    if USE_POSTGRES:
        with psycopg.connect(get_database_url(), connect_timeout=8, autocommit=False) as conn:
            ensure_database_schema(conn, is_postgres=True)
            with conn.cursor() as cur:
                yield cur, True
            conn.commit()
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        try:
            ensure_database_schema(conn, is_postgres=False)
            cur = conn.cursor()
            yield cur, False
            conn.commit()
        finally:
            conn.close()


def save_pending_payment(razorpay_order_id, pending):
    with get_db_cursor() as (cur, is_pg):
        if is_pg:
            cur.execute(
                """INSERT INTO alzor_pending_payments (razorpay_order_id, payment_data)
                   VALUES (%s, %s)
                   ON CONFLICT (razorpay_order_id) DO UPDATE SET payment_data = EXCLUDED.payment_data""",
                (razorpay_order_id, Jsonb(pending)),
            )
        else:
            cur.execute(
                """INSERT OR REPLACE INTO alzor_pending_payments (razorpay_order_id, payment_data)
                   VALUES (?, ?)""",
                (razorpay_order_id, json.dumps(pending, ensure_ascii=False)),
            )


def load_pending_payment(razorpay_order_id):
    if not razorpay_order_id:
        return None
    with get_db_cursor() as (cur, is_pg):
        param_char = "%s" if is_pg else "?"
        cur.execute(
            f"SELECT payment_data FROM alzor_pending_payments WHERE razorpay_order_id = {param_char}",
            (razorpay_order_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        data = row[0]
        if isinstance(data, str):
            try:
                return json.loads(data)
            except Exception:
                return None
        return data


def delete_pending_payment(razorpay_order_id):
    with get_db_cursor() as (cur, is_pg):
        param_char = "%s" if is_pg else "?"
        cur.execute(
            f"DELETE FROM alzor_pending_payments WHERE razorpay_order_id = {param_char}",
            (razorpay_order_id,),
        )


def find_order_by_payment_id(payment_id):
    with get_db_cursor() as (cur, is_pg):
        param_char = "%s" if is_pg else "?"
        cur.execute(
            f"SELECT order_data FROM alzor_orders WHERE razorpay_payment_id = {param_char}",
            (payment_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        data = row[0]
        if isinstance(data, str):
            try:
                return json.loads(data)
            except Exception:
                return None
        return data


def save_order(order):
    """Save a confirmed order once; payment ID uniqueness prevents duplicates."""
    with get_db_cursor() as (cur, is_pg):
        if is_pg:
            cur.execute(
                """INSERT INTO alzor_orders (order_number, razorpay_payment_id, order_data)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (razorpay_payment_id) DO NOTHING""",
                (order["order_number"], order["razorpay_payment_id"], Jsonb(order)),
            )
            cur.execute(
                "SELECT order_data FROM alzor_orders WHERE razorpay_payment_id = %s",
                (order["razorpay_payment_id"],),
            )
            row = cur.fetchone()
            return row[0] if row else order
        else:
            cur.execute(
                """INSERT OR IGNORE INTO alzor_orders (order_number, razorpay_payment_id, order_data)
                   VALUES (?, ?, ?)""",
                (order["order_number"], order["razorpay_payment_id"], json.dumps(order, ensure_ascii=False)),
            )
            cur.execute(
                "SELECT order_data FROM alzor_orders WHERE razorpay_payment_id = ?",
                (order["razorpay_payment_id"],),
            )
            row = cur.fetchone()
            if row and isinstance(row[0], str):
                try:
                    return json.loads(row[0])
                except Exception:
                    return order
            return row[0] if row else order


def find_order_by_number(order_number):
    with get_db_cursor() as (cur, is_pg):
        param_char = "%s" if is_pg else "?"
        cur.execute(
            f"SELECT order_data FROM alzor_orders WHERE order_number = {param_char}",
            (order_number,),
        )
        row = cur.fetchone()
        if not row:
            return None
        data = row[0]
        if isinstance(data, str):
            try:
                return json.loads(data)
            except Exception:
                return None
        return data


# =========================================================
# ALL PRODUCTS
# =========================================================

def get_all_products():
    return PRODUCTS + DRESSES


# =========================================================
# FIND PRODUCT
# =========================================================

def find_product(slug):
    return next(
        (
            product
            for product in get_all_products()
            if product["slug"] == slug
        ),
        None
    )


# =========================================================
# CART HELPERS
# =========================================================

def get_cart_count():
    cart = session.get("cart", [])
    total_quantity = 0

    for item in cart:
        try:
            total_quantity += int(item.get("quantity", 1))
        except (TypeError, ValueError):
            total_quantity += 1

    return total_quantity


def get_cart_subtotal():
    cart = session.get("cart", [])
    subtotal = 0

    for item in cart:
        product = find_product(item.get("slug"))

        if product is None:
            continue

        try:
            quantity = int(item.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1

        if quantity < 1:
            quantity = 1

        subtotal += product["price"] * quantity

    return subtotal


# =========================================================
# GLOBAL VALUES
# =========================================================

@app.context_processor
def inject_global_values():
    return {
        "available_sizes": AVAILABLE_SIZES,
        "cart_count": get_cart_count(),
        "site_url": SITE_URL,
        "domain": "alzorcouture.in",
        "contact_email": "contact@alzorcouture.in",
        "brand_name": "Alzor Couture",
        "razorpay_is_live": RAZORPAY_IS_LIVE,
        "razorpay_is_test": RAZORPAY_IS_TEST
    }


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template(
        "index.html",
        products=PRODUCTS,
        instagram_posts=INSTAGRAM_POSTS
    )


# =========================================================
# NEW ARRIVALS
# =========================================================

@app.route("/new-arrivals")
def new_arrivals():
    return render_template(
        "newarrival.html",
        products=PRODUCTS + DRESSES
    )


# =========================================================
# DRESSES
# =========================================================

@app.route("/dresses")
def dresses():
    return render_template(
        "dresses.html",
        dresses=DRESSES
    )


# =========================================================
# CO-ORD SETS
# =========================================================

@app.route("/co-ord-sets")
def co_ord_sets():
    co_ord_products = [
        product
        for product in PRODUCTS
        if product["category"] == "CO-ORD SET"
    ]

    return render_template(
        "coordsets.html",
        products=co_ord_products
    )


# =========================================================
# SEARCH
# =========================================================

@app.route("/search")
def search_page():
    query = request.args.get("q", "").strip()

    return render_template(
        "search.html",
        query=query
    )


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify({
            "query": "",
            "results": []
        })

    query_lower = query.casefold()
    query_words = [
        word
        for word in query_lower.split()
        if word
    ]

    results = []

    for product in get_all_products():

        searchable_parts = [
            product.get("name", ""),
            product.get("category", ""),
            product.get("description", ""),
            product.get("care", ""),
            " ".join(product.get("details", []))
        ]

        searchable_text = " ".join(
            searchable_parts
        ).casefold()

        name_lower = product.get(
            "name",
            ""
        ).casefold()

        score = 0

        if query_lower in name_lower:
            score += 100

        if name_lower.startswith(query_lower):
            score += 40

        if query_lower in product.get(
            "category",
            ""
        ).casefold():
            score += 25

        if query_lower in searchable_text:
            score += 10

        score += sum(
            5
            for word in query_words
            if word in searchable_text
        )

        if score > 0:
            results.append({
                "name": product.get("name"),
                "slug": product.get("slug"),
                "category": product.get("category"),
                "image": url_for(
                    "static",
                    filename="images/" + product["images"][0]
                ),
                "price": product.get("price"),
                "original_price": product.get(
                    "original_price"
                ),
                "score": score
            })

    results.sort(
        key=lambda item: (
            -item["score"],
            item["name"].casefold()
        )
    )

    for item in results:
        item.pop("score", None)

    return jsonify({
        "query": query,
        "results": results[:24]
    })


# =========================================================
# RECOMMENDATIONS
# =========================================================

def get_recommended_products(
    current_product,
    limit=4
):
    all_products = get_all_products()

    current_slug = current_product.get("slug")
    current_category = current_product.get("category")

    same_category = [
        item
        for item in all_products
        if item.get("slug") != current_slug
        and item.get("category") == current_category
    ]

    other_category = [
        item
        for item in all_products
        if item.get("slug") != current_slug
        and item.get("category") != current_category
    ]

    return (
        same_category + other_category
    )[:limit]


# =========================================================
# WISHLIST
# =========================================================

@app.route("/wishlist")
def wishlist():
    return render_template(
        "wishlist.html",
        products=get_all_products()
    )


# =========================================================
# PRODUCT
# =========================================================

@app.route("/product/<slug>")
def product(slug):
    selected_product = find_product(slug)

    if selected_product is None:
        return "Product not found", 404

    return render_template(
        "product.html",
        product=selected_product,
        recommended_products=get_recommended_products(
            selected_product
        )
    )


# =========================================================
# CART
# =========================================================

@app.route("/cart")
def cart():
    stored_cart = session.get("cart", [])

    cart_items = []
    subtotal = 0

    for item in stored_cart:

        product = find_product(
            item.get("slug")
        )

        if product is None:
            continue

        try:
            quantity = int(
                item.get("quantity", 1)
            )
        except (TypeError, ValueError):
            quantity = 1

        if quantity < 1:
            quantity = 1

        price = product.get("price")

        item_total = price * quantity

        subtotal += item_total

        cart_items.append({
            "slug": product["slug"],
            "name": product["name"],
            "category": product["category"],
            "price": product["price"],
            "original_price": product.get(
                "original_price"
            ),
            "image": product["images"][0],
            "size": item.get("size", "S"),
            "quantity": quantity,
            "total": item_total
        })

    return render_template(
        "cart.html",
        cart_items=cart_items,
        subtotal=subtotal
    )


# =========================================================
# ADD TO CART
# =========================================================

@app.route("/add-to-cart", methods=["POST"])
def add_to_cart():

    if request.is_json:

        data = request.get_json(
            silent=True
        ) or {}

        slug = data.get("slug")
        size = data.get("size")

    else:

        slug = request.form.get("slug")
        size = request.form.get("size")

    product = find_product(slug)

    if product is None:

        if request.is_json:
            return jsonify({
                "success": False,
                "message": "Product not found."
            }), 404

        return "Product not found", 404

    if size not in AVAILABLE_SIZES:

        message = (
            "Please select a valid size: "
            + ", ".join(AVAILABLE_SIZES)
        )

        if request.is_json:
            return jsonify({
                "success": False,
                "message": message
            }), 400

        return message, 400

    cart = session.get("cart", [])

    existing_item = None

    for item in cart:

        if (
            item.get("slug") == slug
            and item.get("size") == size
        ):
            existing_item = item
            break

    if existing_item:

        try:
            current_quantity = int(
                existing_item.get(
                    "quantity",
                    1
                )
            )

        except (TypeError, ValueError):
            current_quantity = 1

        existing_item["quantity"] = min(
            current_quantity + 1,
            20
        )

    else:

        cart.append({
            "slug": slug,
            "size": size,
            "quantity": 1
        })

    session["cart"] = cart
    session.modified = True

    if request.is_json:
        cart_subtotal = 0
        for ci in cart:
            p = find_product(ci.get("slug"))
            if p and p.get("price") is not None:
                try:
                    q = int(ci.get("quantity", 1))
                except (TypeError, ValueError):
                    q = 1
                cart_subtotal += p["price"] * q

        product_image = product["images"][0] if product.get("images") else ""

        return jsonify({
            "success": True,
            "message": f"{product['name']} (Size: {size}) added to your cart successfully.",
            "product_name": product.get("name"),
            "size": size,
            "price": product.get("price"),
            "image": product_image,
            "cart_count": get_cart_count(),
            "subtotal": cart_subtotal
        })

    return redirect(
        url_for("cart")
    )


# =========================================================
# UPDATE CART
# =========================================================

@app.route("/update-cart", methods=["POST"])
def update_cart():

    data = request.get_json(
        silent=True
    ) or {}

    slug = data.get("slug")
    size = data.get("size")

    try:
        quantity = int(
            data.get("quantity", 1)
        )
    except (TypeError, ValueError):
        quantity = 1

    quantity = max(
        1,
        min(quantity, 20)
    )

    cart = session.get("cart", [])

    item_found = False

    for item in cart:

        if (
            item.get("slug") == slug
            and item.get("size") == size
        ):

            item["quantity"] = quantity
            item_found = True
            break

    if not item_found:

        return jsonify({
            "success": False,
            "message": "Cart item not found."
        }), 404

    session["cart"] = cart
    session.modified = True

    product = find_product(slug)

    item_total = (
        product["price"] * quantity
        if product
        else 0
    )

    return jsonify({
        "success": True,
        "quantity": quantity,
        "item_total": item_total,
        "subtotal": get_cart_subtotal(),
        "cart_count": get_cart_count()
    })


# =========================================================
# REMOVE CART ITEM
# =========================================================

@app.route(
    "/remove-from-cart",
    methods=["POST"]
)
def remove_from_cart():

    data = request.get_json(
        silent=True
    ) or {}

    slug = data.get("slug")
    size = data.get("size")

    cart = session.get("cart", [])

    new_cart = [
        item
        for item in cart
        if not (
            item.get("slug") == slug
            and item.get("size") == size
        )
    ]

    session["cart"] = new_cart
    session.modified = True

    return jsonify({
        "success": True,
        "subtotal": get_cart_subtotal(),
        "cart_count": get_cart_count()
    })


# =========================================================
# CLEAR CART
# =========================================================

@app.route(
    "/clear-cart",
    methods=["POST"]
)
def clear_cart():

    session["cart"] = []
    session.modified = True

    return jsonify({
        "success": True,
        "subtotal": 0,
        "cart_count": 0
    })


# =========================================================
# CHECKOUT PAGE
# =========================================================

@app.route("/checkout")
def checkout():

    stored_cart = session.get(
        "cart",
        []
    )

    if not stored_cart:
        return redirect(
            url_for("cart")
        )

    cart_items = []
    subtotal = 0

    for item in stored_cart:

        product = find_product(
            item.get("slug")
        )

        if product is None:
            continue

        try:
            quantity = int(
                item.get("quantity", 1)
            )
        except (TypeError, ValueError):
            quantity = 1

        quantity = max(
            1,
            min(quantity, 20)
        )

        item_total = (
            product["price"] * quantity
        )

        subtotal += item_total

        cart_items.append({
            "slug": product["slug"],
            "name": product["name"],
            "category": product["category"],
            "price": product["price"],
            "original_price": product.get(
                "original_price"
            ),
            "image": product["images"][0],
            "size": item.get(
                "size",
                "S"
            ),
            "quantity": quantity,
            "total": item_total
        })

    if not cart_items:
        session["cart"] = []

        return redirect(
            url_for("cart")
        )

    shipping = 0
    total = subtotal + shipping

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        razorpay_key_id=RAZORPAY_KEY_ID
    )


# =========================================================
# GENERATE ORDER NUMBER
# =========================================================

def generate_order_number():

    date_part = datetime.now().strftime(
        "%Y%m%d"
    )

    random_part = "".join(
        random.choices(
            string.ascii_uppercase
            + string.digits,
            k=4
        )
    )

    return (
        f"ALZ-{date_part}-{random_part}"
    )


# =========================================================
# RAZORPAY PAYMENT: CREATE ORDER
# =========================================================

@app.route("/create-razorpay-order", methods=["POST"])
def create_razorpay_order():

    data = request.get_json(silent=True) or {}

    required_fields = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "address",
        "city",
        "state",
        "pincode"
    ]

    for field in required_fields:
        value = str(data.get(field, "")).strip()
        if not value:
            return jsonify({
                "success": False,
                "message": f"Please enter your {field.replace('_', ' ')}."
            }), 400

    client = get_razorpay_client()
    if client is None:
        return jsonify({
            "success": False,
            "message": "Razorpay is not configured yet. Check the three values in your .env file and restart Flask."
        }), 503

    stored_cart = session.get("cart", [])
    if not stored_cart:
        return jsonify({
            "success": False,
            "message": "Your bag is empty."
        }), 400

    order_items = []
    subtotal = 0

    for item in stored_cart:
        product = find_product(item.get("slug"))
        if product is None:
            continue

        try:
            quantity = int(item.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1
        quantity = max(1, min(quantity, 20))

        item_total = product["price"] * quantity
        subtotal += item_total

        order_items.append({
            "slug": product["slug"],
            "name": product["name"],
            "category": product["category"],
            "image": product["images"][0],
            "size": item.get("size", "S"),
            "quantity": quantity,
            "price": product["price"],
            "original_price": product.get("original_price"),
            "total": item_total
        })

    if not order_items:
        return jsonify({
            "success": False,
            "message": "Unable to create your order."
        }), 400

    shipping = 0
    total = subtotal + shipping
    amount_paise = int(round(total * 100))

    try:
        razorpay_order = client.order.create(data={
            "amount": amount_paise,
            "currency": "INR",
            "receipt": generate_order_number(),
            "notes": {
                "brand": "ALZOR COUTURE",
                "customer_email": str(data.get("email", "")).strip()
            }
        })
    except Exception:
        app.logger.exception("Razorpay order creation failed")
        return jsonify({
            "success": False,
            "message": "Razorpay could not start the payment. Please verify your payment credentials or try again later."
        }), 502

    # Store customer/order details in PostgreSQL, not in the browser cookie or local files.
    pending = {
        "razorpay_order_id": razorpay_order["id"],
        "customer": {
            "first_name": str(data.get("first_name", "")).strip(),
            "last_name": str(data.get("last_name", "")).strip(),
            "email": str(data.get("email", "")).strip(),
            "phone": str(data.get("phone", "")).strip(),
            "address": str(data.get("address", "")).strip(),
            "city": str(data.get("city", "")).strip(),
            "state": str(data.get("state", "")).strip(),
            "pincode": str(data.get("pincode", "")).strip()
        },
        "items": order_items,
        "subtotal": subtotal,
        "shipping": shipping,
        "total": total,
        "amount_paise": amount_paise
    }
    try:
        save_pending_payment(razorpay_order["id"], pending)
    except Exception:
        app.logger.exception("Could not save pending payment to PostgreSQL")
        return jsonify({
            "success": False,
            "message": "We couldn't securely save your checkout. Please try again; no payment has been started yet."
        }), 503

    return jsonify({
        "success": True,
        "key_id": RAZORPAY_KEY_ID,
        "razorpay_order_id": razorpay_order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "brand": "ALZOR COUTURE",
        "customer": {
            "name": (
                str(data.get("first_name", "")).strip() + " " +
                str(data.get("last_name", "")).strip()
            ).strip(),
            "email": str(data.get("email", "")).strip(),
            "contact": str(data.get("phone", "")).strip()
        }
    })


# =========================================================
# RAZORPAY PAYMENT: VERIFY AND SAVE PAID ORDER
# =========================================================

@app.route("/verify-razorpay-payment", methods=["POST"])
def verify_razorpay_payment():

    data = request.get_json(silent=True) or {}
    razorpay_order_id = str(data.get("razorpay_order_id", "")).strip()
    razorpay_payment_id = str(data.get("razorpay_payment_id", "")).strip() 
    razorpay_signature = str(data.get("razorpay_signature", "")).strip()

    try:
        pending = load_pending_payment(razorpay_order_id)
    except Exception:
        app.logger.exception("Could not load pending payment from PostgreSQL")
        return jsonify({
            "success": False,
            "message": "Order storage is temporarily unavailable. Please contact support before trying to pay again."
        }), 503
    if not pending:
        return jsonify({
            "success": False,
            "message": "Your pending checkout was not found. Please return to checkout and try again."
        }), 400

    if (
        not razorpay_order_id or
        not razorpay_payment_id or
        not razorpay_signature or
        razorpay_order_id != pending.get("razorpay_order_id")
    ):
        return jsonify({
            "success": False,
            "message": "Payment details could not be verified. Please contact support if money was deducted."
        }), 400

    client = get_razorpay_client()
    if client is None:
        return jsonify({
            "success": False,
            "message": "Razorpay is not configured. Please restart Flask after checking your .env file."
        }), 503

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        })

        payment = client.payment.fetch(razorpay_payment_id)

        if payment.get("order_id") != razorpay_order_id:
            raise ValueError("Payment order mismatch")

        if int(payment.get("amount", 0)) != int(pending.get("amount_paise", -1)):
            raise ValueError("Payment amount mismatch")

        if str(payment.get("currency", "")).upper() != "INR":
            raise ValueError("Payment currency mismatch")

        if payment.get("status") == "authorized":
            payment = client.payment.capture(
                razorpay_payment_id,
                int(pending["amount_paise"]),
                {"currency": "INR"}
            )

        if payment.get("status") != "captured":
            return jsonify({
                "success": False,
                "message": "Payment has not been captured yet. Please check your Razorpay payment status before trying again."
            }), 402

    except Exception:
        app.logger.exception("Razorpay payment verification failed")
        return jsonify({
            "success": False,
            "message": "We could not verify the payment. If money was deducted, do not pay again yet—please contact support at contact@alzorcouture.in with your payment ID."
        }), 400

    # Prevent accidental duplicate order creation from a repeated verification request.
    try:
        existing = find_order_by_payment_id(razorpay_payment_id)
    except Exception:
        app.logger.exception("Could not check existing order in PostgreSQL")
        return jsonify({
            "success": False,
            "message": "Order storage is temporarily unavailable. Please contact support before trying to pay again."
        }), 503
    if existing:
        session["last_order_number"] = existing["order_number"]
        try:
            delete_pending_payment(razorpay_order_id)
        except Exception:
            app.logger.exception("Could not remove completed pending payment")
        return jsonify({
            "success": True,
            "message": "Payment verified.",
            "redirect_url": url_for(
                "order_confirmation",
                order_number=existing["order_number"]
            )
        })

    order_number = generate_order_number()
    order = {
        "order_number": order_number,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Order Placed",
        "payment_method": "Razorpay",
        "payment_status": "Paid",
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "customer": pending["customer"],
        "items": pending["items"],
        "subtotal": pending["subtotal"],
        "shipping": pending["shipping"],
        "total": pending["total"]
    }

    try:
        saved_order = save_order(order)
    except Exception:
        app.logger.exception("Could not save confirmed order to PostgreSQL")
        return jsonify({
            "success": False,
            "message": "Payment was verified, but order storage is temporarily unavailable. Do not pay again; please contact support with your Razorpay payment ID."
        }), 503

    order_number = saved_order["order_number"]
    session["cart"] = []
    session["last_order_number"] = order_number
    try:
        delete_pending_payment(razorpay_order_id)
    except Exception:
        app.logger.exception("Could not remove completed pending payment")
    session.modified = True

    return jsonify({
        "success": True,
        "message": "Payment verified and your order is confirmed.",
        "redirect_url": url_for(
            "order_confirmation",
            order_number=order_number
        )
    })


# =========================================================
# ORDER CONFIRMATION
# =========================================================

@app.route(
    "/order-confirmation/<order_number>"
)
def order_confirmation(order_number):

    try:
        selected_order = find_order_by_number(order_number)
    except Exception:
        app.logger.exception("Could not load order confirmation from PostgreSQL")
        return "Order storage is temporarily unavailable. Please try again shortly.", 503

    if selected_order is None:
        return "Order not found", 404

    # An order number is an identifier, not proof of ownership.
    # Only the browser session that completed payment can view its confirmation.
    if session.get("last_order_number") != order_number:
        return "Order not found", 404

    return render_template(
        "order_confirmation.html",
        order=selected_order
    )


# =========================================================
# CLIENT CONCIERGE & POLICIES
# =========================================================

@app.route("/shipping-policy")
def shipping_policy():
    body = """
    <div class="policy-section">
        <h2>Complimentary Pan-India Delivery</h2>
        <p>At Alzor Couture, every creation is handled with the utmost reverence. We provide complimentary insured standard shipping across India on all prepaid orders placed on alzorcouture.in.</p>
    </div>

    <div class="policy-section">
        <h2>Delivery Timelines</h2>
        <p>Our pieces are crafted and inspected by master artisans before dispatch:</p>
        <ul>
            <li><strong>Delhi NCR:</strong> 2 to 4 business days.</li>
            <li><strong>Metro Cities (Mumbai, Bengaluru, Kolkata, Chennai, Hyderabad, Pune):</strong> 3 to 5 business days.</li>
            <li><strong>Rest of India:</strong> 5 to 8 business days.</li>
            <li><strong>Custom Fits &amp; Bespoke Tailoring:</strong> 7 to 10 business days from size confirmation.</li>
        </ul>
    </div>

    <div class="policy-section">
        <h2>Courier Partners &amp; Real-Time Tracking</h2>
        <p>We partner exclusively with India's premier express logistics carriers — Blue Dart, Delhivery, and DTDC. As soon as your order leaves our atelier, you will receive an SMS and email notification with your live consignment tracking ID.</p>
        <p>You may also track your order status anytime on our <a href="/track-order" style="color:#ad8a51;font-weight:600;">Order Tracking Portal</a>.</p>
    </div>

    <div class="policy-section">
        <h2>Packaging &amp; Safe Transit</h2>
        <p>All garments are enclosed in archival garment bags with bespoke gold-stamped luxury packaging designed to protect delicate embroidery and fine textiles from humidity and transit creases.</p>
        <div class="policy-highlight-card">
            <h4>Important Notice upon Delivery</h4>
            <p>Please inspect the outer tamper-evident packaging before accepting delivery. If the seal appears compromised or damaged, please decline the parcel and notify us immediately via WhatsApp at +91 8527144345.</p>
        </div>
    </div>
    """
    return render_template(
        "policy.html",
        page_title="Shipping & Delivery Policy",
        meta_description="Read Alzor Couture's pan-India complimentary shipping timelines, luxury packaging standards, and delivery policies.",
        policy_heading="Shipping & Delivery",
        policy_subtitle="Complimentary pan-India insured delivery & bespoke packaging.",
        active_policy="shipping",
        policy_body=body
    )


@app.route("/returns-exchange")
def returns_exchange():
    body = """
    <div class="policy-section">
        <h2>7-Day Exchange Window</h2>
        <p>We take pride in the exceptional craftsmanship of every Alzor Couture silhouette. If you require a different size or wish to exchange for an alternative piece, we welcome exchanges within <strong>7 calendar days</strong> from the date of recorded delivery.</p>
    </div>

    <div class="policy-section">
        <h2>Garment Eligibility for Exchange</h2>
        <p>To preserve hygiene and couture presentation, returned pieces must satisfy the following conditions:</p>
        <ul>
            <li>The piece must be completely unworn, unwashed, and free of perfumes, makeup marks, or alterations.</li>
            <li>All original designer brand tags, security ribbons, and protective accessories must remain intact and attached.</li>
            <li>The piece must be returned in its original Alzor Couture luxury packaging box.</li>
        </ul>
    </div>

    <div class="policy-section">
        <h2>Custom Fits &amp; Bespoke Creations</h2>
        <p>Silhouettes tailored to individual custom measurements are created exclusively for your body contours. While custom pieces are non-refundable, our master tailors will gladly provide <strong>complimentary fit alterations</strong> to ensure perfection.</p>
    </div>

    <div class="policy-section">
        <h2>Damaged or Defective Deliveries</h2>
        <p>Every piece undergoes dual quality audits prior to dispatch. In the rare event an item reaches you with transit damage or a manufacturing flaw, please notify us within <strong>48 hours of delivery</strong> with unboxing photographs or video at <a href="mailto:contact@alzorcouture.in" style="color:#ad8a51;font-weight:600;">contact@alzorcouture.in</a> or via WhatsApp at <strong>+91 8527144345</strong>.</p>
    </div>

    <div class="policy-section">
        <h2>Refund Processing</h2>
        <p>Approved refunds are credited directly back to the original source of payment (via Razorpay Live) within <strong>5 to 7 business days</strong> following our atelier's quality inspection.</p>
    </div>
    """
    return render_template(
        "policy.html",
        page_title="Returns & Exchange Policy",
        meta_description="Alzor Couture 7-day exchange and refund policy. Learn about size exchanges, bespoke alterations, and returns.",
        policy_heading="Returns & Exchanges",
        policy_subtitle="Seamless 7-day exchanges for pristine, unworn couture.",
        active_policy="returns",
        policy_body=body
    )


@app.route("/privacy-policy")
def privacy_policy():
    body = """
    <div class="policy-section">
        <h2>Our Commitment to Privacy</h2>
        <p>Alzor Couture ("alzorcouture.in", "we", "us", "our") values your trust and is committed to protecting your personal data and privacy in full compliance with the Information Technology Act, 2000, and the Digital Personal Data Protection laws of India.</p>
    </div>

    <div class="policy-section">
        <h2>Information We Collect</h2>
        <p>When you browse, register, or complete a purchase on alzorcouture.in, we collect only the information necessary to fulfill your order:</p>
        <ul>
            <li><strong>Identity &amp; Contact:</strong> Full name, telephone number, and email address.</li>
            <li><strong>Delivery Information:</strong> Street address, city, state, postal PIN code, and landmark.</li>
            <li><strong>Transaction Records:</strong> Order items, selected sizes, order values, and Razorpay payment identifiers.</li>
        </ul>
    </div>

    <div class="policy-section">
        <h2>Payment Security via Razorpay</h2>
        <p>All financial payments on alzorcouture.in are processed through <strong>Razorpay</strong>, India's leading PCI-DSS Level 1 certified payment gateway.</p>
        <div class="policy-highlight-card">
            <h4>100% Secure Payment Architecture</h4>
            <p>Alzor Couture never captures, handles, or stores your credit/debit card numbers, CVVs, net banking credentials, or UPI PINs on our servers. All sensitive cardholder data is encrypted and processed directly through Razorpay's bank-grade encrypted channels.</p>
        </div>
    </div>

    <div class="policy-section">
        <h2>Data Usage &amp; Sharing</h2>
        <p>Your personal information is used exclusively to process orders, provide delivery tracking, and offer concierge client care. We do not sell, rent, or monetize customer data to third-party advertisers under any circumstance.</p>
    </div>

    <div class="policy-section">
        <h2>Grievance Redressal</h2>
        <p>For inquiries, data correction requests, or privacy concerns, please contact our designated Grievance Officer:</p>
        <p><strong>Grievance Officer:</strong> Alzor Couture Atelier<br>
        <strong>Email:</strong> <a href="mailto:contact@alzorcouture.in" style="color:#ad8a51;">contact@alzorcouture.in</a><br>
        <strong>Address:</strong> New Delhi, India</p>
    </div>
    """
    return render_template(
        "policy.html",
        page_title="Privacy Policy",
        meta_description="Alzor Couture Privacy Policy. Learn how we safeguard your personal data and ensure 100% secure Razorpay transactions.",
        policy_heading="Privacy Policy",
        policy_subtitle="Committed to protecting your personal data, confidentiality, and payment security.",
        active_policy="privacy",
        policy_body=body
    )


@app.route("/terms-of-service")
def terms_of_service():
    body = """
    <div class="policy-section">
        <h2>Agreement to Terms</h2>
        <p>By accessing or purchasing from <strong>alzorcouture.in</strong>, you agree to be bound by these Terms of Service and all applicable laws and regulations of India. If you do not agree with any of these terms, you are prohibited from using or accessing this site.</p>
    </div>

    <div class="policy-section">
        <h2>Product Information &amp; Craftsmanship</h2>
        <p>We make every effort to display the colors, fabrics, and silhouettes of our garments with maximum fidelity. Handcrafted embroideries and bespoke dyes possess unique artistic characteristics that are the hallmark of luxury Indian couture.</p>
    </div>

    <div class="policy-section">
        <h2>Pricing &amp; Taxes</h2>
        <p>All prices listed on alzorcouture.in are quoted in Indian Rupees (₹ INR) and are inclusive of all applicable Goods and Services Tax (GST). Prices are subject to change without prior notice, but orders already confirmed and paid will not be subject to price alterations.</p>
    </div>

    <div class="policy-section">
        <h2>Intellectual Property</h2>
        <p>All designs, silhouette patterns, photographs, videography, brand logos, copy, and visual trademarks appearing on alzorcouture.in are the sole proprietary property of Alzor Couture. Unauthorized reproduction, imitation, commercial exploitation, or distribution is strictly prohibited.</p>
    </div>

    <div class="policy-section">
        <h2>Governing Law &amp; Jurisdiction</h2>
        <p>These terms and any dispute arising out of or related to purchases on alzorcouture.in shall be governed by and construed in accordance with the laws of India, under the exclusive jurisdiction of the competent courts of New Delhi, India.</p>
    </div>
    """
    return render_template(
        "policy.html",
        page_title="Terms of Service",
        meta_description="Read the official Terms of Service governing purchases and access on Alzor Couture (alzorcouture.in).",
        policy_heading="Terms of Service",
        policy_subtitle="Terms and conditions governing use of alzorcouture.in and customer orders.",
        active_policy="terms",
        policy_body=body
    )


@app.route("/contact")
def contact():
    body = """
    <div class="policy-section">
        <h2>Atelier &amp; Client Concierge</h2>
        <p>Our concierge team is at your disposal for bespoke sizing, custom fit queries, order status updates, and styling advice.</p>
    </div>

    <div class="policy-section">
        <h2>Connect Directly</h2>
        <div class="policy-contact-cta">
            <a href="https://wa.me/918527144345?text=Hi%20Alzor%20Couture%2C%20I%20would%20like%20assistance%20with%20your%20collection." target="_blank" rel="noopener noreferrer" class="policy-whatsapp-btn">
                <svg width="18" height="18" viewBox="0 0 32 32" fill="currentColor"><path d="M16 3.5A12.4 12.4 0 0 0 5.2 21.9L3.8 27.8l6.1-1.6A12.4 12.4 0 1 0 16 3.5Zm0 2.4A10 10 0 0 1 24.1 22a9.9 9.9 0 0 1-8.1 4.1c-1.7 0-3.3-.4-4.7-1.2l-.5-.3-3.4.9.9-3.3-.3-.5A10 10 0 0 1 16 5.9Zm-4 4.1c-.3 0-.7.1-.9.4-.3.4-1.1 1.1-1.1 2.7 0 1.6 1.1 3.1 1.2 3.3.1.2 2.1 3.4 5.2 4.6 2.6 1 3.1.8 3.7.8.6-.1 1.9-.8 2.2-1.6.3-.8.3-1.5.2-1.6-.1-.1-.4-.2-.9-.4l-1.9-.9c-.4-.2-.7-.1-1 .2l-.7.9c-.2.2-.4.2-.8.1-.4-.2-1.5-.6-2.8-1.8-1-.9-1.7-2-1.9-2.4-.2-.4 0-.6.2-.8l.5-.6c.2-.2.2-.4.4-.7.1-.2.1-.5 0-.7l-.9-2.1c-.2-.5-.5-.8-.8-.8Z"/></svg>
                CHAT ON WHATSAPP: 8527144345
            </a>
            <a href="mailto:contact@alzorcouture.in" class="policy-email-btn">
                EMAIL: CONTACT@ALZORCOUTURE.IN
            </a>
        </div>
    </div>

    <div class="policy-section">
        <h2>Hours of Service</h2>
        <ul>
            <li><strong>Concierge Hours:</strong> Monday through Saturday, 10:00 AM – 7:00 PM IST</li>
            <li><strong>Online Store:</strong> Open 24/7 at <a href="https://alzorcouture.in" style="color:#ad8a51;">alzorcouture.in</a></li>
            <li><strong>Response Commitment:</strong> Queries received outside concierge hours are attended to the next business morning.</li>
            <li><strong>Atelier Location:</strong> New Delhi, India</li>
        </ul>
    </div>
    """
    return render_template(
        "policy.html",
        page_title="Contact & Concierge",
        meta_description="Contact Alzor Couture atelier for bespoke fits, styling consultations, and WhatsApp concierge support.",
        policy_heading="Client Concierge",
        policy_subtitle="Personalized assistance, styling consultations, and order support.",
        active_policy="contact",
        policy_body=body
    )


# =========================================================
# ORDER TRACKING
# =========================================================

@app.route("/track-order", methods=["GET", "POST"])
def track_order():
    error = None
    order = None
    order_number = ""
    contact_info = ""

    if request.method == "POST":
        order_number = request.form.get("order_number", "").strip().upper()
        contact_info = request.form.get("contact_info", "").strip().lower()

        if not order_number or not contact_info:
            error = "Please provide both your order number and contact information (phone or email)."
        else:
            try:
                found = find_order_by_number(order_number)
            except Exception:
                app.logger.exception("Error looking up order for tracking")
                found = None

            if not found:
                error = f"We could not find any order matching '{order_number}'. Please verify the order number from your confirmation email."
            else:
                cust_phone = (found.get("customer_phone") or "").strip().lower()
                cust_email = (found.get("customer_email") or "").strip().lower()
                clean_contact = contact_info.replace(" ", "").replace("-", "").replace("+91", "")
                clean_phone = cust_phone.replace(" ", "").replace("-", "").replace("+91", "")

                if contact_info == cust_email or (clean_contact and clean_contact in clean_phone) or (clean_phone and clean_phone in clean_contact):
                    order = found
                else:
                    error = "The contact details entered do not match our records for this order."

    return render_template(
        "track_order.html",
        order=order,
        error=error,
        order_number=order_number,
        contact_info=contact_info,
        active_policy="track"
    )


# =========================================================
# SEO: ROBOTS.TXT & SITEMAP.XML
# =========================================================

@app.route("/robots.txt")
def robots_txt():
    content = f"""User-agent: *
Allow: /
Disallow: /order-confirmation/
Disallow: /create-razorpay-order
Disallow: /verify-razorpay-payment
Disallow: /add-to-cart
Disallow: /update-cart
Disallow: /remove-from-cart
Disallow: /clear-cart

Sitemap: {SITE_URL}/sitemap.xml
"""
    return Response(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    pages = [
        {"loc": f"{SITE_URL}/", "priority": "1.0", "changefreq": "daily"},
        {"loc": f"{SITE_URL}/new-arrivals", "priority": "0.9", "changefreq": "daily"},
        {"loc": f"{SITE_URL}/co-ord-sets", "priority": "0.9", "changefreq": "weekly"},
        {"loc": f"{SITE_URL}/dresses", "priority": "0.9", "changefreq": "weekly"},
        {"loc": f"{SITE_URL}/wishlist", "priority": "0.6", "changefreq": "monthly"},
        {"loc": f"{SITE_URL}/search", "priority": "0.5", "changefreq": "monthly"},
        {"loc": f"{SITE_URL}/shipping-policy", "priority": "0.6", "changefreq": "monthly"},
        {"loc": f"{SITE_URL}/returns-exchange", "priority": "0.6", "changefreq": "monthly"},
        {"loc": f"{SITE_URL}/privacy-policy", "priority": "0.6", "changefreq": "monthly"},
        {"loc": f"{SITE_URL}/terms-of-service", "priority": "0.6", "changefreq": "monthly"},
        {"loc": f"{SITE_URL}/contact", "priority": "0.7", "changefreq": "monthly"},
        {"loc": f"{SITE_URL}/track-order", "priority": "0.7", "changefreq": "monthly"},
    ]
    for p in get_all_products():
        pages.append({
            "loc": f"{SITE_URL}/product/{p['slug']}",
            "priority": "0.8",
            "changefreq": "weekly"
        })
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for page in pages:
        lines.append("  <url>")
        lines.append(f"    <loc>{page['loc']}</loc>")
        lines.append(f"    <priority>{page['priority']}</priority>")
        lines.append(f"    <changefreq>{page['changefreq']}</changefreq>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return Response("\n".join(lines), mimetype="application/xml")


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if RAZORPAY_IS_LIVE:
        print(f"[ALZOR] Razorpay: LIVE MODE ACTIVE ({RAZORPAY_KEY_ID[:12]}...)")
    elif RAZORPAY_IS_TEST:
        print(f"[ALZOR WARNING] Razorpay: Running with TEST key ({RAZORPAY_KEY_ID[:12]}...). Switch to Live key in .env to accept real customer payments.")
    else:
        print("[ALZOR WARNING] Razorpay: No keys configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env.")

    if USE_POSTGRES:
        print("[ALZOR] Database: PostgreSQL connected.")
    else:
        print(f"[ALZOR] Database: Local SQLite storage active ({SQLITE_DB_PATH}).")

    print(f"[ALZOR] Domain: {SITE_URL}")

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "").strip().lower() == "true",
        use_reloader=False
    )
