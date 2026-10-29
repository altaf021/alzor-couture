from flask import Flask, render_template, request, session, jsonify, redirect, url_for
import json
import os
import random
import string
from datetime import datetime

from dotenv import load_dotenv
import razorpay
import psycopg
from psycopg.types.json import Jsonb

load_dotenv()


# =========================================================
# BASIC CONFIGURATION
# =========================================================

AVAILABLE_SIZES = ["S", "M", "L", "XL", "XXL"]

app = Flask(__name__)

# Production must always use a strong secret configured in the environment.
# The fallback is allowed only for local development without DATABASE_URL.
_configured_secret = os.getenv("FLASK_SECRET_KEY", "").strip()
if not _configured_secret:
    if os.getenv("DATABASE_URL", "").strip():
        raise RuntimeError(
            "FLASK_SECRET_KEY must be configured in the production environment."
        )
    _configured_secret = "local-development-only-change-me"
app.secret_key = _configured_secret

# Avoid caching private order-confirmation details in shared browsers/proxies.
@app.after_request
def add_private_page_headers(response):
    if request.endpoint == "order_confirmation":
        response.headers["Cache-Control"] = "no-store, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Vary"] = "Cookie"
    return response

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()


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
# POSTGRESQL ORDER STORAGE
# =========================================================

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def get_database_url():
    """Return a normalized PostgreSQL URL, or raise a clear configuration error."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured in the Render environment.")
    # Some providers still supply the legacy postgres:// scheme.
    if DATABASE_URL.startswith("postgres://"):
        return "postgresql://" + DATABASE_URL[len("postgres://"):]
    return DATABASE_URL


def get_db_connection():
    """Open a short-lived PostgreSQL connection."""
    return psycopg.connect(get_database_url(), connect_timeout=8, autocommit=False)


def ensure_database_schema(conn):
    """Create the small storage tables if this is the first app run."""
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


def save_pending_payment(razorpay_order_id, pending):
    with get_db_connection() as conn:
        ensure_database_schema(conn)
        conn.execute(
            """INSERT INTO alzor_pending_payments (razorpay_order_id, payment_data)
               VALUES (%s, %s)
               ON CONFLICT (razorpay_order_id) DO UPDATE SET payment_data = EXCLUDED.payment_data""",
            (razorpay_order_id, Jsonb(pending)),
        )


def load_pending_payment(razorpay_order_id):
    if not razorpay_order_id:
        return None
    with get_db_connection() as conn:
        ensure_database_schema(conn)
        row = conn.execute(
            "SELECT payment_data FROM alzor_pending_payments WHERE razorpay_order_id = %s",
            (razorpay_order_id,),
        ).fetchone()
        return row[0] if row else None


def delete_pending_payment(razorpay_order_id):
    with get_db_connection() as conn:
        ensure_database_schema(conn)
        conn.execute(
            "DELETE FROM alzor_pending_payments WHERE razorpay_order_id = %s",
            (razorpay_order_id,),
        )


def find_order_by_payment_id(payment_id):
    with get_db_connection() as conn:
        ensure_database_schema(conn)
        row = conn.execute(
            "SELECT order_data FROM alzor_orders WHERE razorpay_payment_id = %s",
            (payment_id,),
        ).fetchone()
        return row[0] if row else None


def save_order(order):
    """Save a confirmed order once; payment ID uniqueness prevents duplicates."""
    with get_db_connection() as conn:
        ensure_database_schema(conn)
        conn.execute(
            """INSERT INTO alzor_orders (order_number, razorpay_payment_id, order_data)
               VALUES (%s, %s, %s)
               ON CONFLICT (razorpay_payment_id) DO NOTHING""",
            (order["order_number"], order["razorpay_payment_id"], Jsonb(order)),
        )
        row = conn.execute(
            "SELECT order_data FROM alzor_orders WHERE razorpay_payment_id = %s",
            (order["razorpay_payment_id"],),
        ).fetchone()
        return row[0] if row else order


def find_order_by_number(order_number):
    with get_db_connection() as conn:
        ensure_database_schema(conn)
        row = conn.execute(
            "SELECT order_data FROM alzor_orders WHERE order_number = %s",
            (order_number,),
        ).fetchone()
        return row[0] if row else None


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
        "cart_count": get_cart_count()
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

        return jsonify({
            "success": True,
            "message": (
                f"{product['name']} "
                "added to your bag."
            ),
            "cart_count": get_cart_count()
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
            "message": "Razorpay could not start the payment. Please check your Test Mode keys and try again."
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
                int(pending["amount_paise"])
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
            "message": "We could not verify the payment. If money was deducted, do not pay again yet—check your Razorpay Test Mode payment record."
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
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "").strip().lower() == "true",
        use_reloader=False
    )