from flask import Flask, render_template, request, session, jsonify, redirect, url_for, Response, send_from_directory
import base64
import csv
import io
import json
import logging
import os
import random
import re
import secrets
import sqlite3
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import string
from contextlib import contextmanager
from datetime import datetime
from werkzeug.utils import secure_filename

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
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.endpoint in ("order_confirmation", "admin_dashboard", "admin_login"):
        response.headers["Cache-Control"] = "no-store, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Vary"] = "Cookie"
    return response

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "alzor2026admin").strip()
RAZORPAY_IS_LIVE = RAZORPAY_KEY_ID.startswith("rzp_live_")
RAZORPAY_IS_TEST = RAZORPAY_KEY_ID.startswith("rzp_test_")


def get_razorpay_client():
    """Return a configured Razorpay client, or None when keys are missing."""
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return None
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587")) if os.getenv("SMTP_PORT", "").strip().isdigit() else 587
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "orders@alzorcouture.in")).strip()
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "contact@alzorcouture.in").strip()


def send_order_email(to_email, subject, html_content):
    """Send an HTML transactional email via SMTP if configured, or log safely."""
    if not to_email:
        return False
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        app.logger.info(f"[Transactional Email Simulation] To: {to_email} | Subject: {subject}")
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Alzor Couture <{SMTP_FROM}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        app.logger.info(f"Order email successfully dispatched to {to_email}")
        return True
    except Exception as e:
        app.logger.warning(f"Could not dispatch email to {to_email}: {e}")
        return False


# =========================================================
# CO-ORD SET PRODUCTS
# =========================================================

PRODUCTS =  [

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
    },

    {
        "name": "Denim Signature",
        "slug": "denim-signature",
        "category": "CO-ORD SET",
        "price": 7199,
        "images": [
            "dw 1.jpeg",
            "dw 2.jpeg",
            "dw 3.jpeg",
            "dw 4.jpeg",
            "dw 5.jpeg"
        ],
        "description":
            "A statement in contemporary denim, Denim Signature pairs a structured indigo waistcoat with elegantly flowing wide-leg trousers. Defined by its refined silhouette and coordinated design, this two-piece ensemble brings effortless sophistication to modern dressing.",
        "details": [
            "Indigo denim waistcoat",
            "Matching wide-leg trousers",
            "Two-piece co-ord set",
            "Contemporary tailored silhouette"
        ],
        "care":
            "Care instructions to be confirmed."
    },

        {
        "name": "Red Muse Co Ord Set",
        "slug": "red-muse-co-ord-set",
        "category": "CO-ORD SET",
        "price": 6999,
        "images": [
            "rw 1.jpeg",
            "rw 2.jpeg",
            "rw 3.jpeg",
            "rw 4.jpeg",
            "rw 5.jpeg"
        ],
        "description":
            "A captivating expression of modern elegance, the Red Muse Co Ord Set pairs a vibrant red statement top with delicate white floral appliqué detailing and elegantly tailored white wide-leg trousers. The striking contrast and graceful silhouette create a refined two-piece ensemble designed to make every occasion memorable.",
        "details": [
            "Vibrant red statement top",
            "White floral appliqué detailing",
            "White wide-leg trousers",
            "Elegant two-piece co-ord set",
            "Contemporary statement silhouette"
        ],
        "care":
            "Care instructions to be confirmed."
    },
        {
        "name": "Maroon Élan Co-ord Set",
        "slug": "maroon-elan-co-ord-set",
        "category": "CO-ORD SET",
        "price": 6799,
        "images": [
            "maroon 1.jpeg",
            "maroon 2.jpeg",
            "maroon 3.jpeg",
            "maroon 4.jpeg",
            "maroon 5.jpeg"
        ],
        "description":
            "A refined blend of elegance and contemporary style, Maroon Élan features a rich maroon design with delicate black bead embellishments. The button-front top, distinctive diagonal detailing and coordinated silhouette create a sophisticated look, perfect for evening outings and special occasions.",
        "details": [
            "Rich maroon colour",
            "Button-front top",
            "Delicate black bead embellishments",
            "Distinctive diagonal detailing",
            "Coordinated two-piece set"
        ]
    },
        {
        "name": "Denim Élan Co-ord Set",
        "slug": "denim-elan-co-ord-set",
        "category": "CO-ORD SET",
        "price": 6599,
        "images": [
            "denim elan 1.jpeg",
            "denim elan 2.jpeg",
            "denim elan 3.jpeg",
            "denim elan 4.jpeg",
            "denim elan 5.jpeg"
        ],
        "description":
            "A contemporary take on denim dressing, Denim Élan brings together a structured indigo shirt and matching wide-leg trousers, elevated with striking ivory fringe detailing. The contrasting textures and statement fringe panels create a distinctive silhouette that blends modern sophistication with effortless style.",
        "details": [
            "Indigo denim shirt",
            "Matching wide-leg trousers",
            "Contrasting ivory fringe detailing",
            "Statement two-piece co-ord set",
            "Contemporary silhouette"
        ]
    },
    
    {
        "name": "Denim Élan Fringe Short Set",
        "slug": "denim-elan-fringe-short-set",
        "category": "CO-ORD SET",
        "price": 5999,
        "images": [
            "denim elan 1 s.jpeg",
            "denim elan 2 s.jpeg",
            "denim elan 3 s.jpeg"
        ],
        "description":
            "A contemporary take on denim dressing, the Denim Élan Fringe Short Set pairs a relaxed button-front shirt with matching tailored shorts. Finished with striking ivory fringe accents, this coordinated two-piece brings playful movement and modern sophistication to a standout summer look.",
        "details": [
            "Blue denim shirt",
            "Matching denim shorts",
            "Contrasting ivory fringe detailing",
            "Two-piece co-ord set"
        ]
    },
        {
        "name": "Scarlet Muse Set",
        "slug": "scarlet-muse-set",
        "category": "CO-ORD SET",
        "price": 4599,
        "images": [
            "sm1.jpeg",
            "sm2.jpeg",
            "sm3.jpeg",
            "sm4.jpeg",
            "sm5.jpeg"
        ],
        "description":
            "A statement in colour and versatility, the Scarlet Muse Set features a striking multicolour strapless top designed to pair beautifully with two distinctive bottom styles. Choose the bold red wrap skirt for a playful, contemporary look or the elegant navy flared trousers for a more refined silhouette.",
        "details": [
            "Multicolour strapless top",
            "Red wrap skirt styling option",
            "Navy flared trousers styling option",
            "Versatile contemporary design"
        ],
        "care":
            "Care instructions to be confirmed."
    },
        {
        "name": "Midnight Muse Set",
        "slug": "midnight-muse-set",
        "category": "CO-ORD SET",
        "price": 5599,
        "images": [
            "MS-1.jpeg",
            "MS-2.jpeg",
            "MS-3.jpeg",
            "MS-4.jpeg",
            "MS-5.jpeg"
        ],
        "description":
            "A striking blend of colour and contemporary elegance, the Midnight Muse Set features a statement multicolour top paired with sophisticated navy wide-leg trousers. Its distinctive colour-block design and graceful silhouette create a confident, modern look for special occasions and stylish outings.",
        "details": [
            "Multicolour statement top",
            "Deep navy wide-leg trousers",
            "Two-piece co-ord set",
            "Contemporary colour-block design"
        ],
        "care":
            "Care instructions to be confirmed."
    },
        {
        "name": "Crimson Muse Set",
        "slug": "crimson-muse-set",
        "category": "CO-ORD SET",
        "price": 5999,
        "images": [
            "cm-1.jpeg",
            "cm-2.jpeg",
            "cm-3.jpeg",
            "cm-4.jpeg"
        ],
        "description":
            "A striking blend of colour and contemporary elegance, Crimson Muse Set features a statement colour-block strapless top paired with a sleek burgundy skirt. The rich combination of crimson, navy, black and burgundy creates a distinctive look, perfect for making an impression at special occasions.",
        "details": [
            "Strapless colour-block top",
            "Combination of crimson, navy, black and burgundy",
            "Matching burgundy skirt",
            "Contemporary two-piece set"
        ],
        "care":
            "Care instructions to be confirmed."
    },
        {
        "name": "Denim Éclat Lace Set",
        "slug": "denim-eclat-lace-set",
        "category": "CO-ORD SET",
        "price": 8999,
        "images": [
            "dt-1.jpeg",
            "dt-2.jpeg",
            "dt-3.jpeg",
            "dt-4.jpeg",
            "dt-5.jpeg"
        ],
        "description":
            "A refined expression of contemporary denim, the Denim Éclat Lace Set pairs a structured indigo denim shirt with delicate white crochet detailing and coordinated flared trousers. Intricate lace accents across the sleeves, hemline and trouser panels create a striking contrast, bringing together modern denim styling and artisanal elegance.",
        "details": [
            "Indigo denim shirt-style top",
            "White crochet lace detailing",
            "Coordinated flared denim trousers",
            "Statement lace panels on sleeves and trouser hems",
            "Two-piece co-ord set"
        ],
        "care": "Refer to the garment's care label."
    },
        {
        "name": "Teal Green Lelan Cape Co-ord Set",
        "slug": "teal-green-lelan-cape-coord-set",
        "category": "CO-ORD SET",
        "price": 8399,
        "images": [
            "gr-1.jpeg",
            "gr-2.jpeg",
            "gr-3.jpeg",
            "gr-4.jpeg",
            "gr-5.jpeg"
        ],
        "description":
            "A graceful blend of contemporary elegance and delicate detailing, the Teal Green Lelan Cape Co-ord Set features a flowing lace cape layered over a coordinated inner top, paired with elegant wide-leg trousers. The intricate floral lace, statement cape sleeves and refined waist buckle create a sophisticated silhouette, making this two-piece ensemble a distinctive addition to your wardrobe.",
        "details": [
            "Teal-green lace cape overlay",
            "Coordinated inner top",
            "Matching wide-leg trousers",
            "Floral lace detailing",
            "Statement waist buckle",
            "Two-piece co-ord set"
        ],
        "care": "Refer to the garment's care label."
    },
    
{
    "name": "Emerald Éclat Co-ord Set",
    "slug": "emerald-eclat-co-ord-set",
    "category": "CO-ORD SET",
    "price": 8999,
    "original_price": 9999,

    "images": [
        "1000195263.jpg.jpeg",
        "1000195260.jpg.jpeg",
        "1000195264.jpg.jpeg",
        "1000195262.jpg.jpeg",
        "1000195261.jpg.jpeg"
    ],

    "description": (
        "Make a sophisticated statement with the Emerald Éclat "
        "Co-ord Set by Alzor Couture. Designed in a rich dark "
        "emerald green shade, this elegant ensemble features a "
        "tailored cropped blazer with refined detailing and "
        "coordinated wide-leg trousers. A perfect blend of "
        "contemporary elegance and timeless sophistication."
    ),

    "details": [
        "Premium dark emerald green co-ord set",
        "Elegant tailored cropped blazer",
        "Intricate embellished shoulder detailing",
        "Coordinated wide-leg trousers",
        "Scalloped waistband detailing",
        "Sophisticated contemporary silhouette",
        "Perfect for parties, occasions and elegant outings"
    ],

    "care": "Dry clean recommended. Store carefully to preserve the embellishments."
},
    
{
    "name": "Ivory Allure Set",
    "slug": "ivory-allure-set",
    "category": "CO-ORD SET",
    "price": 9699,

    "images": [
        "1000195309.jpg.jpeg",
        "1000195311.jpg.jpeg",
        "1000195306.jpg.jpeg",
        "1000195310.jpg.jpeg",
        "1000195273.jpg.jpeg"
    ],

    "description": (
        "Discover understated luxury with the Ivory Allure Set "
        "by Alzor Couture. Featuring a beautifully tailored "
        "champagne-yellow top with delicate embellished detailing, "
        "paired with elegant ivory trousers. This sophisticated "
        "ensemble brings together contemporary design and timeless "
        "elegance, making it perfect for refined occasions and "
        "special outings."
    ),

    "details": [
        "Elegant champagne-yellow top",
        "Intricate embellished neckline detailing",
        "Sophisticated tailored silhouette",
        "Coordinated ivory trousers",
        "Premium contemporary styling",
        "Perfect for parties and special occasions"
    ],

    "care": "Dry clean recommended."
},
    
{
    "name": "Ivory Royale Co-ord Set",
    "slug": "ivory-royale-co-ord-set",
    "category": "CO-ORD SET",
    "price": 15999,

    "images": [
        "1000195297.jpg.jpeg",
        "1000195294.jpg.jpeg",
        "1000195298.jpg.jpeg",
        "1000195300.jpg.jpeg",
        "1000195278.jpg.jpeg"
    ],

    "description": (
        "Introducing the Ivory Royale Co-ord Set by Alzor Couture, "
        "a statement of refined luxury and contemporary elegance. "
        "Featuring a sophisticated white cropped jacket adorned "
        "with exquisite gold metallic detailing across the collar, "
        "pockets and cuffs, paired with beautifully coordinated "
        "wide-leg trousers featuring matching gold accents. "
        "An exclusive ensemble designed for those who appreciate "
        "exceptional detailing and timeless sophistication."
    ),

    "details": [
        "Premium white co-ord ensemble",
        "Elegant cropped zip-front jacket",
        "Exquisite gold metallic detailing",
        "Gold-accented collar and cuffs",
        "Decorative front pocket detailing",
        "Coordinated wide-leg trousers",
        "Matching gold trouser accents",
        "Luxury occasion and statement wear"
    ],

    "care": (
        "Professional dry cleaning recommended. "
        "Handle metallic detailing with care."
    )
},




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
    },
    
        {
        "name": "Scarlet Petal Dress",
        "slug": "scarlet-petal-dress",
        "category": "DRESS",
        "price": 9999,
        "images": [
            "rb 1.jpeg",
            "rb 2.jpeg",
            "rb 3.jpeg",
            "rb 4.jpeg"
        ],
        "description":
            "A striking expression of contemporary elegance, Scarlet Petal features a bold red-and-black design adorned with beautiful floral appliqué detailing. Its sleek silhouette and contrasting colours create a sophisticated statement, making it a distinctive choice for evening occasions and special moments.",
        "details": [
            "Red and black colour combination",
            "Floral appliqué detailing",
            "Sleeveless design",
            "Contemporary dress silhouette"
        ]
    },
        {
        "name": "Ivory Blossom Gown",
        "slug": "ivory-blossom-gown",
        "category": "DRESS",
        "price": 15999,
        "images": [
            "IBG-1.jpeg",
            "IBG-2.jpeg",
            "IBG-3.jpeg",
            "IBG-4.jpeg",
            "IBG-5.jpeg"
        ],
        "description":
            "A celebration of understated elegance, the Ivory Blossom Gown features delicate three-dimensional floral appliqués complemented by intricate embellished vine detailing. Designed with a graceful full-length silhouette and refined long sleeves, this statement piece brings timeless sophistication to special occasions and elegant evenings.",
        "details": [
            "Three-dimensional floral appliqués",
            "Delicate embellished vine detailing",
            "Elegant full-length silhouette",
            "Refined long sleeves"
        ]
    },
        {
        "name": "Classic Dottie",
        "slug": "classic-dottie",
        "category": "DRESS",
        "price": 4599,
        "images": [
            "CD-1.jpeg",
            "CD-2.jpeg",
            "CD-3.jpeg",
            "CD-4.jpeg"
        ],
        "description":
            "A timeless blend of playful charm and effortless elegance, the Classic Dottie Dress features a crisp white base adorned with classic black polka dots. Designed with delicate spaghetti straps, a flattering V-neckline and a beautifully gathered waist, this chic silhouette makes a stylish choice for brunches, outings and casual occasions.",
        "details": [
            "White dress with black polka-dot pattern",
            "Delicate spaghetti straps",
            "Flattering V-neckline",
            "Gathered waist detail"
        ]
    },
        {
        "name": "Alzor Lime Élan",
        "slug": "alzor-lime-elan",
        "category": "DRESS",
        "price": 5299,
        "images": [
            "GR-1.jpeg",
            "GR-2.jpeg",
            "GR-3.jpeg",
            "GR-4.jpeg",
            "GR-5.jpeg",
            "GR-6.jpeg"
        ],
        "description":
            "A graceful expression of modern elegance, Alzor Lime Élan features a soft lime-toned dress with delicate layered flutter sleeves, a flattering V-neckline and a beautifully defined waist. Finished with delicate floral detailing and an elegant asymmetrical hemline, this design brings effortless charm to special occasions and daytime celebrations.",
        "details": [
            "Soft lime-toned dress",
            "Layered flutter sleeves",
            "Flattering V-neckline",
            "Decorative floral detailing",
            "Elegant asymmetrical hemline"
        ],
        "care":
            "Care instructions to be confirmed."
    },
    
{
    "name": "Verdant Muse Dress",
    "slug": "verdant-muse-dress",
    "category": "DRESS",
    "price": 11199,

    "images": [
        "1000195301.jpg.jpeg",
        "1000195308.jpg.jpeg",
        "1000195303.jpg.jpeg",
        "1000195305.jpg.jpeg",
        "1000195276.jpg.jpeg"
    ],

    "description": (
        "Make a statement with the Verdant Muse Dress by "
        "Alzor Couture. Featuring a sophisticated black "
        "silhouette enhanced with striking lime-green "
        "botanical detailing, this elegant dress brings "
        "together contemporary artistry and timeless style. "
        "Designed with delicate textured accents and a "
        "beautifully flowing A-line silhouette, it is a "
        "distinctive choice for stylish occasions."
    ),

    "details": [
        "Elegant black dress",
        "Lime-green botanical detailing",
        "Sophisticated A-line silhouette",
        "Long sleeves",
        "Distinctive textured embellishments",
        "Statement contemporary design",
        "Suitable for parties and special occasions"
    ],

    "care": "Professional dry cleaning recommended."
},

]


# =========================================================
# INSTAGRAM
# =========================================================

INSTAGRAM_URL = "https://www.instagram.com/alzor.couture?vrfl=MWJvY3hqYjZldXdmYQ=="

INSTAGRAM_POSTS = [

    {
        "image": "insta-1.jpeg",
        "url": INSTAGRAM_URL
    },

    {
        "image": "insta-2.jpeg",
        "url": INSTAGRAM_URL
    },

    {
        "image": "insta-3.jpeg",
        "url": INSTAGRAM_URL
    },

    {
        "image": "insta-4.jpeg",
        "url": INSTAGRAM_URL
    },

    {
        "image": "insta-5.jpeg",
        "url": INSTAGRAM_URL
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
    """Create the storage tables and seed initial data if this is the first app run."""
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_coupons (
                code TEXT PRIMARY KEY,
                discount_type TEXT NOT NULL DEFAULT 'percentage',
                discount_value NUMERIC NOT NULL DEFAULT 0,
                min_order_amount NUMERIC NOT NULL DEFAULT 0,
                max_discount_amount NUMERIC NOT NULL DEFAULT 0,
                start_date TEXT,
                expiry_date TEXT,
                usage_limit INTEGER NOT NULL DEFAULT 0,
                used_count INTEGER NOT NULL DEFAULT 0,
                per_customer_limit INTEGER NOT NULL DEFAULT 1,
                first_order_only BOOLEAN NOT NULL DEFAULT FALSE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_coupon_redemptions (
                id SERIAL PRIMARY KEY,
                coupon_code TEXT NOT NULL,
                order_number TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                discount_amount NUMERIC NOT NULL DEFAULT 0,
                redeemed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_admin_notifications (
                id SERIAL PRIMARY KEY,
                order_number TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                amount NUMERIC NOT NULL DEFAULT 0,
                customer_name TEXT,
                customer_phone TEXT,
                is_read BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_inventory (
                product_slug TEXT NOT NULL,
                size TEXT NOT NULL,
                stock INTEGER NOT NULL DEFAULT 15,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (product_slug, size)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_custom_products (
                slug TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'CO-ORD SET',
                price INTEGER NOT NULL DEFAULT 0,
                original_price INTEGER NOT NULL DEFAULT 0,
                images JSONB NOT NULL DEFAULT '[]',
                description TEXT NOT NULL DEFAULT '',
                details JSONB NOT NULL DEFAULT '[]',
                care TEXT NOT NULL DEFAULT 'Dry clean recommended.',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_uploaded_images (
                filename TEXT PRIMARY KEY,
                content_type TEXT NOT NULL,
                data_base64 TEXT NOT NULL,
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_coupons (
                code TEXT PRIMARY KEY,
                discount_type TEXT NOT NULL DEFAULT 'percentage',
                discount_value REAL NOT NULL DEFAULT 0,
                min_order_amount REAL NOT NULL DEFAULT 0,
                max_discount_amount REAL NOT NULL DEFAULT 0,
                start_date TEXT,
                expiry_date TEXT,
                usage_limit INTEGER NOT NULL DEFAULT 0,
                used_count INTEGER NOT NULL DEFAULT 0,
                per_customer_limit INTEGER NOT NULL DEFAULT 1,
                first_order_only INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_coupon_redemptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coupon_code TEXT NOT NULL,
                order_number TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                discount_amount REAL NOT NULL DEFAULT 0,
                redeemed_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_admin_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                customer_name TEXT,
                customer_phone TEXT,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_inventory (
                product_slug TEXT NOT NULL,
                size TEXT NOT NULL,
                stock INTEGER NOT NULL DEFAULT 15,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (product_slug, size)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_custom_products (
                slug TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'CO-ORD SET',
                price INTEGER NOT NULL DEFAULT 0,
                original_price INTEGER NOT NULL DEFAULT 0,
                images TEXT NOT NULL DEFAULT '[]',
                description TEXT NOT NULL DEFAULT '',
                details TEXT NOT NULL DEFAULT '[]',
                care TEXT NOT NULL DEFAULT 'Dry clean recommended.',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alzor_uploaded_images (
                filename TEXT PRIMARY KEY,
                content_type TEXT NOT NULL,
                data_base64 TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

    seed_initial_data(conn, is_postgres)


def seed_initial_data(conn, is_postgres=True):
    """Seed initial coupons and inventory stock if not yet populated."""
    cur = conn.cursor()
    try:
        # Seed default coupons
        cur.execute("SELECT COUNT(*) FROM alzor_coupons")
        cnt = cur.fetchone()[0]
        if cnt == 0:
            initial_coupons = [
                ("WELCOME10", "percentage", 10, 3000, 1500, "", "", 0, 0, 1, False if is_postgres else 0, True if is_postgres else 1),
                ("SAVE100", "fixed", 100, 2000, 100, "", "", 0, 0, 2, False if is_postgres else 0, True if is_postgres else 1),
                ("FREESHIP", "free_shipping", 0, 1000, 0, "", "", 0, 0, 0, False if is_postgres else 0, True if is_postgres else 1),
                ("FIRST15", "percentage", 15, 4000, 2000, "", "", 0, 0, 1, True if is_postgres else 1, True if is_postgres else 1),
            ]
            ph = "%s" if is_postgres else "?"
            sql = f"""INSERT INTO alzor_coupons
                      (code, discount_type, discount_value, min_order_amount, max_discount_amount, start_date, expiry_date, usage_limit, used_count, per_customer_limit, first_order_only, is_active)
                      VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})"""
            for cp in initial_coupons:
                cur.execute(sql, cp)

        # Seed initial inventory for all catalog pieces & sizes
        all_prods = PRODUCTS + DRESSES
        for prod in all_prods:
            slug = prod.get("slug")
            if not slug:
                continue
            for sz in AVAILABLE_SIZES:
                if is_postgres:
                    cur.execute(
                        "INSERT INTO alzor_inventory (product_slug, size, stock) VALUES (%s, %s, 15) ON CONFLICT (product_slug, size) DO NOTHING",
                        (slug, sz)
                    )
                else:
                    cur.execute(
                        "INSERT OR IGNORE INTO alzor_inventory (product_slug, size, stock) VALUES (?, ?, 15)",
                        (slug, sz)
                    )
    except Exception as e:
        app.logger.warning(f"Error seeding initial database data: {e}")
    finally:
        cur.close()


_schema_ensured = False


@contextmanager
def get_db_cursor():
    """Context manager yielding (cursor, is_postgres). Handles commits/rollbacks."""
    global _schema_ensured
    if USE_POSTGRES:
        with psycopg.connect(get_database_url(), connect_timeout=8, autocommit=False) as conn:
            if not _schema_ensured:
                ensure_database_schema(conn, is_postgres=True)
                _schema_ensured = True
            with conn.cursor() as cur:
                yield cur, True
            conn.commit()
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        try:
            if not _schema_ensured:
                ensure_database_schema(conn, is_postgres=False)
                _schema_ensured = True
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


def load_all_orders(limit=150):
    with get_db_cursor() as (cur, is_pg):
        param_char = "%s" if is_pg else "?"
        cur.execute(
            f"SELECT order_data, created_at FROM alzor_orders ORDER BY created_at DESC LIMIT {param_char}",
            (limit,),
        )
        rows = cur.fetchall()
        orders = []
        for row in rows:
            data = row[0]
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    continue
            orders.append(data)
        return orders


def load_all_pending_payments(limit=50):
    with get_db_cursor() as (cur, is_pg):
        param_char = "%s" if is_pg else "?"
        cur.execute(
            f"SELECT payment_data, created_at FROM alzor_pending_payments ORDER BY created_at DESC LIMIT {param_char}",
            (limit,),
        )
        rows = cur.fetchall()
        pending = []
        for row in rows:
            data = row[0]
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    continue
            pending.append(data)
        return pending


def update_order_status(order_number, new_status, note=None, admin_name="Atelier Admin"):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                data = json.loads(data)
            except Exception:
                return None

        old_status = data.get("status", "")
        data["status"] = str(new_status).strip()
        data["updated_at"] = now_str

        # Maintain status timeline history
        timeline = data.get("timeline") or []
        timeline.append({
            "status": new_status,
            "time": now_str,
            "admin": admin_name,
            "note": note or f"Status updated from '{old_status}' to '{new_status}'."
        })
        data["timeline"] = timeline

        # Restore inventory if cancelled, returned, or refunded
        if new_status in ("Cancelled", "Returned", "Refunded") and not data.get("stock_restored"):
            for item in data.get("items", []):
                slug = item.get("slug")
                size = item.get("size", "S")
                qty = int(item.get("quantity", 1))
                if slug:
                    restore_stock(slug, size, qty)
            data["stock_restored"] = True

        if is_pg:
            cur.execute(
                "UPDATE alzor_orders SET order_data = %s WHERE order_number = %s",
                (Jsonb(data), order_number),
            )
        else:
            cur.execute(
                "UPDATE alzor_orders SET order_data = ? WHERE order_number = ?",
                (json.dumps(data, ensure_ascii=False), order_number),
            )
        return data


def add_order_admin_note(order_number, note_text, admin_name="Atelier Admin"):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                data = json.loads(data)
            except Exception:
                return None

        notes = data.get("admin_notes") or []
        notes.append({
            "time": now_str,
            "admin": admin_name,
            "note": note_text.strip()
        })
        data["admin_notes"] = notes

        if is_pg:
            cur.execute(
                "UPDATE alzor_orders SET order_data = %s WHERE order_number = %s",
                (Jsonb(data), order_number),
            )
        else:
            cur.execute(
                "UPDATE alzor_orders SET order_data = ? WHERE order_number = ?",
                (json.dumps(data, ensure_ascii=False), order_number),
            )
        return data


# =========================================================
# PROMO CODE & COUPON HELPERS
# =========================================================

def get_coupon(code):
    if not code:
        return None
    code = str(code).strip().upper()
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        cur.execute(f"SELECT code, discount_type, discount_value, min_order_amount, max_discount_amount, start_date, expiry_date, usage_limit, used_count, per_customer_limit, first_order_only, is_active, created_at FROM alzor_coupons WHERE UPPER(code) = {ph}", (code,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "code": row[0],
            "discount_type": row[1],
            "discount_value": float(row[2] or 0),
            "min_order_amount": float(row[3] or 0),
            "max_discount_amount": float(row[4] or 0),
            "start_date": row[5] or "",
            "expiry_date": row[6] or "",
            "usage_limit": int(row[7] or 0),
            "used_count": int(row[8] or 0),
            "per_customer_limit": int(row[9] or 1),
            "first_order_only": bool(row[10]),
            "is_active": bool(row[11]),
            "created_at": str(row[12] or "")
        }


def get_all_coupons():
    with get_db_cursor() as (cur, is_pg):
        cur.execute("SELECT code, discount_type, discount_value, min_order_amount, max_discount_amount, start_date, expiry_date, usage_limit, used_count, per_customer_limit, first_order_only, is_active, created_at FROM alzor_coupons ORDER BY created_at DESC")
        rows = cur.fetchall()
        coupons = []
        for row in rows:
            coupons.append({
                "code": row[0],
                "discount_type": row[1],
                "discount_value": float(row[2] or 0),
                "min_order_amount": float(row[3] or 0),
                "max_discount_amount": float(row[4] or 0),
                "start_date": row[5] or "",
                "expiry_date": row[6] or "",
                "usage_limit": int(row[7] or 0),
                "used_count": int(row[8] or 0),
                "per_customer_limit": int(row[9] or 1),
                "first_order_only": bool(row[10]),
                "is_active": bool(row[11]),
                "created_at": str(row[12] or "")
            })
        return coupons


def create_coupon(data):
    code = str(data.get("code", "")).strip().upper()
    if not code:
        return False, "Promo code name is required."
    existing = get_coupon(code)
    if existing:
        return False, f"Promo code '{code}' already exists."

    discount_type = str(data.get("discount_type", "percentage")).strip().lower()
    if discount_type not in ("percentage", "fixed", "free_shipping"):
        discount_type = "percentage"

    try:
        discount_value = float(data.get("discount_value", 0))
    except (ValueError, TypeError):
        discount_value = 0.0

    try:
        min_order_amount = float(data.get("min_order_amount", 0))
    except (ValueError, TypeError):
        min_order_amount = 0.0

    try:
        max_discount_amount = float(data.get("max_discount_amount", 0))
    except (ValueError, TypeError):
        max_discount_amount = 0.0

    start_date = str(data.get("start_date", "")).strip()
    expiry_date = str(data.get("expiry_date", "")).strip()

    try:
        usage_limit = int(data.get("usage_limit", 0))
    except (ValueError, TypeError):
        usage_limit = 0

    try:
        per_customer_limit = int(data.get("per_customer_limit", 1))
    except (ValueError, TypeError):
        per_customer_limit = 1

    first_order_only = bool(data.get("first_order_only", False))
    is_active = bool(data.get("is_active", True))

    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        fo_val = True if is_pg else (1 if first_order_only else 0)
        ia_val = True if is_pg else (1 if is_active else 0)
        cur.execute(
            f"""INSERT INTO alzor_coupons
               (code, discount_type, discount_value, min_order_amount, max_discount_amount, start_date, expiry_date, usage_limit, used_count, per_customer_limit, first_order_only, is_active)
               VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 0, {ph}, {ph}, {ph})""",
            (code, discount_type, discount_value, min_order_amount, max_discount_amount, start_date, expiry_date, usage_limit, per_customer_limit, fo_val, ia_val)
        )
    return True, f"Promo code '{code}' created successfully."


def toggle_coupon(code, is_active=None):
    coupon = get_coupon(code)
    if not coupon:
        return False, "Promo code not found."
    new_state = (not coupon["is_active"]) if is_active is None else bool(is_active)
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        val = True if is_pg else (1 if new_state else 0)
        cur.execute(f"UPDATE alzor_coupons SET is_active = {ph} WHERE UPPER(code) = {ph}", (val, code.upper()))
    return True, f"Promo code '{code}' {'activated' if new_state else 'deactivated'}."


def delete_coupon(code):
    coupon = get_coupon(code)
    if not coupon:
        return False, "Promo code not found."
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        cur.execute(f"DELETE FROM alzor_coupons WHERE UPPER(code) = {ph}", (code.upper(),))
    return True, f"Promo code '{code}' deleted successfully."


def record_coupon_redemption(code, order_number, email, phone, discount):
    if not code:
        return
    code = code.strip().upper()
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        cur.execute(
            f"""INSERT INTO alzor_coupon_redemptions (coupon_code, order_number, customer_email, customer_phone, discount_amount)
               VALUES ({ph}, {ph}, {ph}, {ph}, {ph})""",
            (code, order_number, email.strip().lower(), phone.strip(), float(discount))
        )
        cur.execute(f"UPDATE alzor_coupons SET used_count = used_count + 1 WHERE UPPER(code) = {ph}", (code,))


def get_coupon_redemptions(code):
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        cur.execute(f"SELECT order_number, customer_email, customer_phone, discount_amount, redeemed_at FROM alzor_coupon_redemptions WHERE UPPER(coupon_code) = {ph} ORDER BY redeemed_at DESC", (code.upper(),))
        rows = cur.fetchall()
        redemptions = []
        for r in rows:
            redemptions.append({
                "order_number": r[0],
                "customer_email": r[1],
                "customer_phone": r[2],
                "discount_amount": float(r[3] or 0),
                "redeemed_at": str(r[4] or "")
            })
        return redemptions


def validate_coupon(code, subtotal, customer_email="", customer_phone=""):
    """
    Validate coupon against subtotal and customer redemption limits.
    Returns: (is_valid: bool, message: str, discount: int, coupon: dict or None)
    """
    if not code:
        return False, "Please enter a promo code.", 0, None
    coupon = get_coupon(code)
    if not coupon:
        return False, f"Promo code '{code.upper()}' is not valid.", 0, None
    if not coupon["is_active"]:
        return False, f"Promo code '{coupon['code']}' is currently inactive.", 0, None

    today_str = datetime.now().strftime("%Y-%m-%d")
    if coupon["start_date"] and today_str < coupon["start_date"]:
        return False, f"Promo code '{coupon['code']}' is not yet active (starts on {coupon['start_date']}).", 0, None
    if coupon["expiry_date"] and today_str > coupon["expiry_date"]:
        return False, f"Promo code '{coupon['code']}' has expired.", 0, None

    if coupon["usage_limit"] > 0 and coupon["used_count"] >= coupon["usage_limit"]:
        return False, f"Promo code '{coupon['code']}' has reached its maximum usage limit.", 0, None

    if coupon["min_order_amount"] > 0 and subtotal < coupon["min_order_amount"]:
        return False, f"Promo code '{coupon['code']}' requires a minimum bag value of ₹{int(coupon['min_order_amount']):,}.", 0, None

    clean_email = str(customer_email or "").strip().lower()
    clean_phone = str(customer_phone or "").strip().replace(" ", "").replace("-", "").replace("+91", "")

    if clean_email or clean_phone:
        with get_db_cursor() as (cur, is_pg):
            ph = "%s" if is_pg else "?"
            if coupon["first_order_only"]:
                cur.execute(
                    f"SELECT COUNT(*) FROM alzor_orders WHERE (order_data::text ILIKE {ph} OR order_data::text ILIKE {ph})" if is_pg else
                    f"SELECT COUNT(*) FROM alzor_orders WHERE (order_data LIKE {ph} OR order_data LIKE {ph})",
                    (f"%{clean_email}%" if clean_email else "___NOMATCH___", f"%{clean_phone}%" if clean_phone else "___NOMATCH___")
                )
                past_orders_count = cur.fetchone()[0]
                if past_orders_count > 0:
                    return False, f"Promo code '{coupon['code']}' is exclusive to first-time couture orders.", 0, None

            if coupon["per_customer_limit"] > 0:
                cur.execute(
                    f"""SELECT COUNT(*) FROM alzor_coupon_redemptions
                       WHERE UPPER(coupon_code) = {ph} AND (LOWER(customer_email) = {ph} OR customer_phone = {ph})""",
                    (coupon["code"].upper(), clean_email if clean_email else "___NOMATCH___", clean_phone if clean_phone else "___NOMATCH___")
                )
                used_by_cust = cur.fetchone()[0]
                if used_by_cust >= coupon["per_customer_limit"]:
                    return False, f"You have already redeemed '{coupon['code']}' the maximum allowed ({coupon['per_customer_limit']} time(s)).", 0, None

    discount = 0
    t = coupon["discount_type"]
    if t == "percentage":
        discount = (subtotal * coupon["discount_value"]) / 100.0
        if coupon["max_discount_amount"] > 0 and discount > coupon["max_discount_amount"]:
            discount = coupon["max_discount_amount"]
    elif t == "fixed":
        discount = min(coupon["discount_value"], subtotal)
    elif t == "free_shipping":
        discount = 0

    discount_int = int(round(discount))
    return True, f"Code '{coupon['code']}' applied! You save ₹{discount_int:,}.", discount_int, coupon


# =========================================================
# INVENTORY MANAGEMENT HELPERS
# =========================================================

def get_product_stock(slug, size):
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        cur.execute(f"SELECT stock FROM alzor_inventory WHERE product_slug = {ph} AND size = {ph}", (slug, size))
        row = cur.fetchone()
        return int(row[0]) if row else 15


def deduct_stock(slug, size, quantity=1):
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        if is_pg:
            cur.execute(
                f"UPDATE alzor_inventory SET stock = GREATEST(0, stock - {ph}), updated_at = NOW() WHERE product_slug = {ph} AND size = {ph}",
                (int(quantity), slug, size)
            )
        else:
            cur.execute(
                f"UPDATE alzor_inventory SET stock = MAX(0, stock - {ph}), updated_at = datetime('now') WHERE product_slug = {ph} AND size = {ph}",
                (int(quantity), slug, size)
            )


def restore_stock(slug, size, quantity=1):
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        if is_pg:
            cur.execute(
                f"UPDATE alzor_inventory SET stock = stock + {ph}, updated_at = NOW() WHERE product_slug = {ph} AND size = {ph}",
                (int(quantity), slug, size)
            )
        else:
            cur.execute(
                f"UPDATE alzor_inventory SET stock = stock + {ph}, updated_at = datetime('now') WHERE product_slug = {ph} AND size = {ph}",
                (int(quantity), slug, size)
            )


def update_stock(slug, size, new_stock):
    new_stock = max(0, int(new_stock))
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        if is_pg:
            cur.execute(
                f"""INSERT INTO alzor_inventory (product_slug, size, stock, updated_at)
                   VALUES ({ph}, {ph}, {ph}, NOW())
                   ON CONFLICT (product_slug, size) DO UPDATE SET stock = EXCLUDED.stock, updated_at = NOW()""",
                (slug, size, new_stock)
            )
        else:
            cur.execute(
                f"""INSERT OR REPLACE INTO alzor_inventory (product_slug, size, stock, updated_at)
                   VALUES ({ph}, {ph}, {ph}, datetime('now'))""",
                (slug, size, new_stock)
            )


def get_all_inventory():
    all_prods = get_all_products()
    prod_map = {p["slug"]: p for p in all_prods if p.get("slug")}
    inv_list = []
    with get_db_cursor() as (cur, is_pg):
        cur.execute("SELECT product_slug, size, stock, updated_at FROM alzor_inventory ORDER BY product_slug ASC, size ASC")
        rows = cur.fetchall()
        for r in rows:
            slug, size, stock, upd = r[0], r[1], int(r[2]), str(r[3])
            prod = prod_map.get(slug, {})
            inv_list.append({
                "slug": slug,
                "name": prod.get("name", slug),
                "category": prod.get("category", "CO-ORD SET"),
                "image": prod.get("images", [""])[0] if prod.get("images") else "",
                "price": prod.get("price", 0),
                "size": size,
                "stock": stock,
                "updated_at": upd
            })
    return inv_list


# =========================================================
# ADMIN NOTIFICATIONS HELPERS
# =========================================================

def create_admin_notification(order_number, title, message, amount=0, customer_name="", customer_phone=""):
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        is_read_val = False if is_pg else 0
        cur.execute(
            f"""INSERT INTO alzor_admin_notifications
               (order_number, title, message, amount, customer_name, customer_phone, is_read)
               VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
            (order_number, title, message, float(amount or 0), customer_name, customer_phone, is_read_val)
        )


def get_admin_notifications(limit=50):
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        cur.execute(
            f"""SELECT id, order_number, title, message, amount, customer_name, customer_phone, is_read, created_at
               FROM alzor_admin_notifications ORDER BY created_at DESC LIMIT {ph}""",
            (limit,)
        )
        rows = cur.fetchall()
        notifs = []
        for r in rows:
            notifs.append({
                "id": r[0],
                "order_number": r[1],
                "title": r[2],
                "message": r[3],
                "amount": float(r[4] or 0),
                "customer_name": r[5] or "",
                "customer_phone": r[6] or "",
                "is_read": bool(r[7]),
                "created_at": str(r[8] or "")
            })
        return notifs


def get_unread_notification_count():
    with get_db_cursor() as (cur, is_pg):
        cur.execute("SELECT COUNT(*) FROM alzor_admin_notifications WHERE is_read = FALSE" if is_pg else "SELECT COUNT(*) FROM alzor_admin_notifications WHERE is_read = 0")
        row = cur.fetchone()
        return int(row[0]) if row else 0


def mark_notification_read(notif_id):
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        val = True if is_pg else 1
        cur.execute(f"UPDATE alzor_admin_notifications SET is_read = {ph} WHERE id = {ph}", (val, notif_id))


def mark_all_notifications_read():
    with get_db_cursor() as (cur, is_pg):
        cur.execute("UPDATE alzor_admin_notifications SET is_read = TRUE" if is_pg else "UPDATE alzor_admin_notifications SET is_read = 1")


# =========================================================
# TRANSACTIONAL EMAIL TEMPLATE BUILDER
# =========================================================

def build_order_confirmation_email_html(order):
    cust = order.get("customer", {})
    order_num = order.get("order_number", "")
    items = order.get("items", [])
    subtotal = order.get("subtotal", 0)
    discount = order.get("discount", 0)
    coupon_code = order.get("coupon_code", "")
    shipping = order.get("shipping", 0)
    total = order.get("total", 0)
    name = f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip() or "Valued Client"

    items_html = ""
    for it in items:
        items_html += f"""
        <tr>
            <td style="padding:12px;border-bottom:1px solid #eee;">
                <strong>{it.get('name', '')}</strong><br>
                <span style="font-size:12px;color:#777;">Size: {it.get('size', 'S')} &bull; Qty: {it.get('quantity', 1)}</span>
            </td>
            <td style="padding:12px;border-bottom:1px solid #eee;text-align:right;">
                ₹{it.get('price', 0) * it.get('quantity', 1):,}
            </td>
        </tr>
        """

    discount_row = ""
    if discount > 0:
        discount_row = f"""
        <tr>
            <td style="padding:6px 12px;color:#ad8a51;">Discount ({coupon_code or 'PROMO'})</td>
            <td style="padding:6px 12px;text-align:right;color:#ad8a51;">-₹{discount:,}</td>
        </tr>
        """

    track_url = f"{SITE_URL}/track-order"
    invoice_url = f"{SITE_URL}/order-invoice/{order_num}"

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fbfaf7;color:#181818;margin:0;padding:24px;">
        <div style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #e0dad0;padding:36px 32px;">
            <div style="text-align:center;padding-bottom:20px;border-bottom:2px solid #ad8a51;margin-bottom:24px;">
                <h1 style="font-family:Georgia,serif;font-size:24px;letter-spacing:2px;margin:0 0 6px;">ALZOR COUTURE</h1>
                <p style="font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#ad8a51;margin:0;">ORDER CONFIRMATION</p>
            </div>
            <p style="font-size:14px;margin-bottom:16px;">Dear {name},</p>
            <p style="font-size:13.5px;color:#555;line-height:1.6;margin-bottom:20px;">
                Thank you for choosing Alzor Couture. We are delighted to confirm that your order <strong>{order_num}</strong> has been received and your payment has been successfully verified.
            </p>
            <div style="background:#fcfbf9;border:1px solid #ece7df;padding:16px;margin-bottom:24px;">
                <p style="margin:0 0 6px;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#888;">ORDER SUMMARY</p>
                <p style="margin:0;font-size:14px;"><strong>Order ID:</strong> {order_num}</p>
                <p style="margin:4px 0 0;font-size:13px;color:#666;"><strong>Date:</strong> {order.get('created_at', '')}</p>
                <p style="margin:4px 0 0;font-size:13px;color:#28a745;"><strong>Payment Status:</strong> Paid (Razorpay Verified)</p>
            </div>
            <table style="width:100%;border-collapse:collapse;margin-bottom:20px;font-size:13px;">
                <thead>
                    <tr style="background:#f7f4ee;">
                        <th style="padding:10px 12px;text-align:left;font-size:10px;letter-spacing:1px;text-transform:uppercase;">Piece</th>
                        <th style="padding:10px 12px;text-align:right;font-size:10px;letter-spacing:1px;text-transform:uppercase;">Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html}
                </tbody>
                <tfoot>
                    <tr>
                        <td style="padding:8px 12px 4px;">Subtotal</td>
                        <td style="padding:8px 12px 4px;text-align:right;">₹{subtotal:,}</td>
                    </tr>
                    {discount_row}
                    <tr>
                        <td style="padding:4px 12px;">Pan-India Delivery</td>
                        <td style="padding:4px 12px;text-align:right;color:#28a745;">FREE</td>
                    </tr>
                    <tr style="font-size:15px;font-weight:bold;border-top:2px solid #181818;">
                        <td style="padding:12px;">Total Paid</td>
                        <td style="padding:12px;text-align:right;color:#ad8a51;">₹{total:,}</td>
                    </tr>
                </tfoot>
            </table>
            <div style="background:#fbfaf7;border-left:3px solid #ad8a51;padding:14px;margin-bottom:24px;font-size:12.5px;color:#555;">
                <strong>Delivery Address:</strong><br>
                {cust.get('address', '')}<br>
                {cust.get('city', '')}, {cust.get('state', '')} — {cust.get('pincode', '')}<br>
                Phone: {cust.get('phone', '')}
            </div>
            <div style="text-align:center;margin:28px 0;">
                <a href="{invoice_url}" style="display:inline-block;padding:12px 24px;background:#181818;color:#ffffff;text-decoration:none;font-size:11px;letter-spacing:2px;text-transform:uppercase;font-weight:600;margin-right:8px;">VIEW / PRINT INVOICE</a>
                <a href="{track_url}" style="display:inline-block;padding:12px 24px;background:#f5f2eb;color:#181818;border:1px solid #d4cdbe;text-decoration:none;font-size:11px;letter-spacing:2px;text-transform:uppercase;font-weight:600;">TRACK ORDER</a>
            </div>
            <div style="border-top:1px solid #ece7df;padding-top:18px;text-align:center;font-size:11px;color:#888;line-height:1.6;">
                Need assistance? Connect with our atelier concierge via WhatsApp at <strong>+91 8527144345</strong> or email us at <strong>contact@alzorcouture.in</strong>.<br>
                &copy; 2026 ALZOR COUTURE &bull; alzorcouture.in
            </div>
        </div>
    </body>
    </html>
    """


# =========================================================
# ALL PRODUCTS & CUSTOM CATALOG
# =========================================================

def slugify(text):
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def get_custom_products(include_inactive=False):
    """Fetch custom products from database, ordered newest first."""
    prods = []
    try:
        with get_db_cursor() as (cur, is_pg):
            cond = "" if include_inactive else ("WHERE is_active = TRUE" if is_pg else "WHERE is_active = 1")
            cur.execute(
                f"""SELECT slug, name, category, price, original_price, images, description, details, care, is_active
                    FROM alzor_custom_products {cond}
                    ORDER BY created_at DESC"""
            )
            rows = cur.fetchall()
            for r in rows:
                slug, name, category, price, orig_price, images_raw, desc, details_raw, care, active = r
                if isinstance(images_raw, str):
                    try:
                        images = json.loads(images_raw)
                    except Exception:
                        images = [images_raw] if images_raw else []
                elif isinstance(images_raw, list):
                    images = images_raw
                else:
                    images = []

                if isinstance(details_raw, str):
                    try:
                        details = json.loads(details_raw)
                    except Exception:
                        details = [d.strip() for d in details_raw.split("\n") if d.strip()]
                elif isinstance(details_raw, list):
                    details = details_raw
                else:
                    details = []

                prods.append({
                    "slug": slug,
                    "name": name,
                    "category": category or "CO-ORD SET",
                    "price": int(price or 0),
                    "original_price": int(orig_price or 0) if orig_price else None,
                    "images": images if images else ["logo.png"],
                    "description": desc or "",
                    "details": details,
                    "care": care or "Dry clean recommended.",
                    "is_custom": True,
                    "is_active": bool(active)
                })
    except Exception:
        app.logger.exception("Failed to load custom products from database")
    return prods


def save_custom_product(product_data, is_edit=False):
    """Insert or update a custom product in the database and inventory."""
    name = (product_data.get("name") or "").strip()
    slug = (product_data.get("slug") or "").strip()
    if not slug:
        slug = slugify(name)
    category = (product_data.get("category") or "CO-ORD SET").strip().upper()
    try:
        price = int(product_data.get("price") or 0)
    except (ValueError, TypeError):
        price = 0

    orig_price = product_data.get("original_price")
    try:
        orig_price = int(orig_price) if orig_price else 0
    except (ValueError, TypeError):
        orig_price = 0

    images = product_data.get("images", [])
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            images = [images] if images else []

    description = (product_data.get("description") or "").strip()
    details = product_data.get("details", [])
    if isinstance(details, str):
        details = [d.strip() for d in details.split("\n") if d.strip()]

    care = (product_data.get("care") or "Dry clean recommended.").strip()
    is_active = product_data.get("is_active", True)

    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        img_val = Jsonb(images) if is_pg else json.dumps(images, ensure_ascii=False)
        det_val = Jsonb(details) if is_pg else json.dumps(details, ensure_ascii=False)
        act_val = True if is_pg else 1
        if not is_active:
            act_val = False if is_pg else 0

        if is_pg:
            cur.execute(
                f"""INSERT INTO alzor_custom_products
                    (slug, name, category, price, original_price, images, description, details, care, is_active, updated_at)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, NOW())
                    ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    price = EXCLUDED.price,
                    original_price = EXCLUDED.original_price,
                    images = EXCLUDED.images,
                    description = EXCLUDED.description,
                    details = EXCLUDED.details,
                    care = EXCLUDED.care,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW()""",
                (slug, name, category, price, orig_price, img_val, description, det_val, care, act_val)
            )
        else:
            cur.execute(
                f"""INSERT OR REPLACE INTO alzor_custom_products
                    (slug, name, category, price, original_price, images, description, details, care, is_active, updated_at)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, datetime('now'))""",
                (slug, name, category, price, orig_price, img_val, description, det_val, care, act_val)
            )

        # Update or initialize stock per size
        stock_map = product_data.get("stock", {})
        sizes = product_data.get("sizes", AVAILABLE_SIZES)
        if isinstance(sizes, str):
            sizes = [s.strip() for s in sizes.split(",") if s.strip()]
        for sz in sizes:
            stk = 15
            if isinstance(stock_map, dict):
                try:
                    stk = int(stock_map.get(sz, 15))
                except (ValueError, TypeError):
                    stk = 15
            if is_pg:
                cur.execute(
                    """INSERT INTO alzor_inventory (product_slug, size, stock, updated_at)
                       VALUES (%s, %s, %s, NOW())
                       ON CONFLICT (product_slug, size) DO UPDATE SET
                       stock = EXCLUDED.stock,
                       updated_at = NOW()""",
                    (slug, sz, stk)
                )
            else:
                cur.execute(
                    """INSERT OR REPLACE INTO alzor_inventory (product_slug, size, stock, updated_at)
                       VALUES (?, ?, ?, datetime('now'))""",
                    (slug, sz, stk)
                )

    return slug


def delete_custom_product(slug):
    """Delete a custom product or deactivate a catalog product."""
    with get_db_cursor() as (cur, is_pg):
        ph = "%s" if is_pg else "?"
        base_slugs = {p.get("slug") for p in (PRODUCTS + DRESSES) if p.get("slug")}
        if slug in base_slugs:
            act_val = False if is_pg else 0
            if is_pg:
                cur.execute(
                    """INSERT INTO alzor_custom_products (slug, name, is_active, updated_at)
                       VALUES (%s, %s, %s, NOW())
                       ON CONFLICT (slug) DO UPDATE SET is_active = FALSE, updated_at = NOW()""",
                    (slug, slug, act_val)
                )
            else:
                cur.execute(
                    """INSERT OR REPLACE INTO alzor_custom_products (slug, name, is_active, updated_at)
                       VALUES (?, ?, ?, datetime('now'))""",
                    (slug, slug, act_val)
                )
        else:
            cur.execute(f"DELETE FROM alzor_custom_products WHERE slug = {ph}", (slug,))
        cur.execute(f"DELETE FROM alzor_inventory WHERE product_slug = {ph}", (slug,))


def get_all_products():
    """Return all products: active custom products first, then non-hidden catalog pieces."""
    all_custom = get_custom_products(include_inactive=True)
    custom_map = {p["slug"]: p for p in all_custom}
    active_custom = [p for p in all_custom if p.get("is_active")]
    base = [p for p in (PRODUCTS + DRESSES) if p.get("slug") not in custom_map]
    return active_custom + base


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
    effective_site_url = os.getenv("SITE_URL", "").strip().rstrip("/")
    if not effective_site_url:
        try:
            effective_site_url = request.host_url.rstrip("/")
        except Exception:
            effective_site_url = SITE_URL
    return {
        "available_sizes": AVAILABLE_SIZES,
        "cart_count": get_cart_count(),
        "site_url": effective_site_url,
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
        products=get_all_products(),
        instagram_posts=INSTAGRAM_POSTS
    )


# =========================================================
# NEW ARRIVALS
# =========================================================

@app.route("/new-arrivals")
def new_arrivals():
    return render_template(
        "newarrival.html",
        products=get_all_products()
    )


# =========================================================
# DRESSES
# =========================================================

@app.route("/dresses")
def dresses():
    dress_prods = [
        product for product in get_all_products()
        if product.get("category", "").upper() == "DRESS"
    ]
    return render_template(
        "dresses.html",
        dresses=dress_prods
    )


# =========================================================
# CO-ORD SETS
# =========================================================

@app.route("/co-ord-sets")
def co_ord_sets():
    co_ord_products = [
        product
        for product in get_all_products()
        if product.get("category", "").upper() == "CO-ORD SET"
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
# PROMO CODE API (CHECKOUT)
# =========================================================

@app.route("/api/apply-coupon", methods=["POST"])
def api_apply_coupon():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip().upper()
    email = str(data.get("email", "")).strip()
    phone = str(data.get("phone", "")).strip()

    subtotal = get_cart_subtotal()
    if subtotal <= 0:
        return jsonify({"success": False, "message": "Your bag is empty."}), 400

    is_valid, msg, discount, coupon = validate_coupon(code, subtotal, email, phone)
    if not is_valid:
        return jsonify({"success": False, "message": msg}), 400

    session["applied_coupon"] = {
        "code": coupon["code"],
        "discount": discount
    }
    session.modified = True

    new_total = max(0, subtotal - discount)
    return jsonify({
        "success": True,
        "message": msg,
        "code": coupon["code"],
        "discount": discount,
        "subtotal": subtotal,
        "shipping": 0,
        "new_total": new_total
    })


@app.route("/api/remove-coupon", methods=["POST"])
def api_remove_coupon():
    session.pop("applied_coupon", None)
    session.modified = True
    subtotal = get_cart_subtotal()
    return jsonify({
        "success": True,
        "message": "Promo code removed.",
        "subtotal": subtotal,
        "shipping": 0,
        "total": subtotal
    })


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

    # Verify inventory availability for all items before initiating payment
    for item in stored_cart:
        product = find_product(item.get("slug"))
        if product is None:
            continue
        sz = str(item.get("size", "S")).strip().upper()
        try:
            qty = max(1, int(item.get("quantity", 1)))
        except (ValueError, TypeError):
            qty = 1
        available_stock = get_product_stock(product["slug"], sz)
        if available_stock < qty:
            return jsonify({
                "success": False,
                "message": f"Sorry, '{product['name']}' in Size {sz} currently has only {available_stock} piece(s) available in atelier inventory."
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

    # Coupon validation on server
    applied_coupon_code = str(data.get("coupon_code") or session.get("applied_coupon", {}).get("code") or "").strip().upper()
    discount = 0
    if applied_coupon_code:
        is_val, val_msg, calc_discount, _ = validate_coupon(
            applied_coupon_code,
            subtotal,
            customer_email=str(data.get("email", "")),
            customer_phone=str(data.get("phone", ""))
        )
        if is_val:
            discount = calc_discount
        else:
            applied_coupon_code = ""
            discount = 0

    shipping = 0
    total = max(0, subtotal - discount + shipping)
    amount_paise = int(round(total * 100))

    try:
        razorpay_order = client.order.create(data={
            "amount": amount_paise,
            "currency": "INR",
            "receipt": generate_order_number(),
            "notes": {
                "brand": "ALZOR COUTURE",
                "customer_email": str(data.get("email", "")).strip(),
                "coupon_code": applied_coupon_code or "NONE"
            }
        })
    except Exception:
        app.logger.exception("Razorpay order creation failed")
        return jsonify({
            "success": False,
            "message": "Razorpay could not start the payment. Please verify your payment credentials or try again later."
        }), 502

    # Store customer/order details in PostgreSQL/SQLite, not in browser cookies
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
        "discount": discount,
        "coupon_code": applied_coupon_code,
        "shipping": shipping,
        "total": total,
        "amount_paise": amount_paise
    }
    try:
        save_pending_payment(razorpay_order["id"], pending)
    except Exception:
        app.logger.exception("Could not save pending payment to database")
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
        app.logger.exception("Could not load pending payment from database")
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

    # Prevent accidental duplicate order creation
    try:
        existing = find_order_by_payment_id(razorpay_payment_id)
    except Exception:
        app.logger.exception("Could not check existing order in database")
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
    coupon_code = pending.get("coupon_code", "")
    discount = pending.get("discount", 0)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    order = {
        "order_number": order_number,
        "created_at": now_str,
        "status": "Confirmed",
        "payment_method": "Razorpay",
        "payment_status": "Paid",
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "customer": pending["customer"],
        "items": pending["items"],
        "subtotal": pending["subtotal"],
        "discount": discount,
        "coupon_code": coupon_code,
        "shipping": pending["shipping"],
        "total": pending["total"],
        "stock_restored": False,
        "timeline": [
            {
                "status": "Confirmed",
                "time": now_str,
                "admin": "System (Payment Verified)",
                "note": "Payment verified via Razorpay and order confirmed."
            }
        ],
        "admin_notes": []
    }

    try:
        saved_order = save_order(order)
    except Exception:
        app.logger.exception("Could not save confirmed order to database")
        return jsonify({
            "success": False,
            "message": "Payment was verified, but order storage is temporarily unavailable. Do not pay again; please contact support with your Razorpay payment ID."
        }), 503

    order_number = saved_order["order_number"]

    # 1. Deduct stock for each piece ordered
    for item in pending.get("items", []):
        try:
            deduct_stock(item.get("slug"), item.get("size", "S"), item.get("quantity", 1))
        except Exception:
            app.logger.exception(f"Error deducting stock for {item.get('slug')} {item.get('size')}")

    # 2. Record coupon redemption if coupon used
    if coupon_code and discount > 0:
        try:
            record_coupon_redemption(
                coupon_code,
                order_number,
                pending["customer"].get("email", ""),
                pending["customer"].get("phone", ""),
                discount
            )
        except Exception:
            app.logger.exception(f"Error recording coupon redemption for {coupon_code}")

    # 3. Create admin notification
    cust_name = f"{pending['customer'].get('first_name', '')} {pending['customer'].get('last_name', '')}".strip() or "Valued Client"
    cust_phone = pending["customer"].get("phone", "")
    items_desc = ", ".join([f"{it.get('name')} ({it.get('size')}x{it.get('quantity')})" for it in pending.get("items", [])])
    try:
        create_admin_notification(
            order_number=order_number,
            title=f"New Order Confirmed: {order_number}",
            message=f"Customer {cust_name} ({cust_phone}) placed order of ₹{pending['total']:,} for {items_desc}.",
            amount=pending["total"],
            customer_name=cust_name,
            customer_phone=cust_phone
        )
    except Exception:
        app.logger.exception("Error creating admin notification")

    # 4. Dispatch confirmation emails
    try:
        email_html = build_order_confirmation_email_html(order)
        send_order_email(pending["customer"].get("email"), f"Order Confirmed #{order_number} — Alzor Couture", email_html)
        send_order_email(ADMIN_EMAIL, f"[NEW ORDER] #{order_number} — ₹{pending['total']:,} by {cust_name}", email_html)
    except Exception:
        app.logger.exception("Error sending confirmation emails")

    session["cart"] = []
    session.pop("applied_coupon", None)
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

@app.route("/order-confirmation/<order_number>")
def order_confirmation(order_number):

    try:
        selected_order = find_order_by_number(order_number)
    except Exception:
        app.logger.exception("Could not load order confirmation from database")
        return "Order storage is temporarily unavailable. Please try again shortly.", 503

    if selected_order is None:
        return "Order not found", 404

    # Allow if this browser completed the checkout, or if admin is signed in
    if session.get("last_order_number") != order_number and not session.get("alzor_admin_authenticated"):
        return redirect(url_for("track_order", order_number=order_number))

    return render_template(
        "order_confirmation.html",
        order=selected_order
    )


# =========================================================
# PRINTABLE TAX INVOICE
# =========================================================

@app.route("/order-invoice/<order_number>")
def order_invoice(order_number):
    try:
        order = find_order_by_number(order_number)
    except Exception:
        app.logger.exception("Could not retrieve order for invoice")
        return "Invoice temporarily unavailable.", 503

    if not order:
        return "Invoice not found.", 404

    # Allow access if admin, or session matches last_order_number, or query param contact matches
    is_admin = bool(session.get("alzor_admin_authenticated"))
    is_last_order = session.get("last_order_number") == order_number

    contact_param = request.args.get("contact", "").strip().lower()
    matches_contact = False
    if contact_param:
        cust = order.get("customer", {})
        cust_email = (cust.get("email") or "").lower()
        cust_phone = (cust.get("phone") or "").replace(" ", "").replace("-", "").replace("+91", "")
        clean_param = contact_param.replace(" ", "").replace("-", "").replace("+91", "")
        matches_contact = bool(contact_param == cust_email or (clean_param and clean_param in cust_phone))

    if not (is_admin or is_last_order or matches_contact):
        return redirect(url_for("track_order", order_number=order_number))

    return render_template("invoice.html", order=order)


@app.route("/admin/order/<order_number>/invoice")
def admin_order_invoice(order_number):
    if not session.get("alzor_admin_authenticated"):
        return redirect(url_for("admin_login"))
    order = find_order_by_number(order_number)
    if not order:
        return "Order not found", 404
    return render_template("invoice.html", order=order)


# =========================================================
# RAZORPAY WEBHOOK (INDEPENDENT SERVER-SIDE CONFIRMATION)
# =========================================================

@app.route("/api/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    webhook_secret = RAZORPAY_WEBHOOK_SECRET
    webhook_body = request.get_data(as_text=True)
    webhook_signature = request.headers.get("X-Razorpay-Signature", "")

    client = get_razorpay_client()
    if client is None:
        app.logger.warning("Razorpay webhook received but keys are not configured.")
        return jsonify({"status": "error", "message": "Razorpay client not configured"}), 503

    if webhook_secret:
        try:
            client.utility.verify_webhook_signature(
                webhook_body,
                webhook_signature,
                webhook_secret
            )
        except Exception:
            app.logger.warning("Razorpay webhook signature verification failed.")
            return jsonify({"status": "error", "message": "Invalid webhook signature"}), 400

    try:
        event = json.loads(webhook_body)
    except Exception:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    event_type = event.get("event")
    payload = event.get("payload", {})
    payment_entity = payload.get("payment", {}).get("entity", {})
    order_entity = payload.get("order", {}).get("entity", {})

    razorpay_payment_id = payment_entity.get("id")
    razorpay_order_id = payment_entity.get("order_id") or order_entity.get("id")

    if not razorpay_payment_id:
        return jsonify({"status": "ignored", "message": "No payment entity found"}), 200

    # Idempotent check: if order already exists in database, do not create duplicate
    existing = find_order_by_payment_id(razorpay_payment_id)
    if existing:
        return jsonify({"status": "success", "message": "Order already processed"}), 200

    if event_type in ("payment.captured", "order.paid"):
        pending = load_pending_payment(razorpay_order_id) if razorpay_order_id else None
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if pending:
            order_number = generate_order_number()
            coupon_code = pending.get("coupon_code", "")
            discount = pending.get("discount", 0)

            order = {
                "order_number": order_number,
                "created_at": now_str,
                "status": "Confirmed",
                "payment_method": "Razorpay (Webhook Verified)",
                "payment_status": "Paid",
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "customer": pending["customer"],
                "items": pending["items"],
                "subtotal": pending["subtotal"],
                "discount": discount,
                "coupon_code": coupon_code,
                "shipping": pending["shipping"],
                "total": pending["total"],
                "stock_restored": False,
                "timeline": [
                    {
                        "status": "Confirmed",
                        "time": now_str,
                        "admin": "Razorpay Webhook",
                        "note": "Payment captured and order verified via Webhook."
                    }
                ],
                "admin_notes": []
            }
            save_order(order)
            delete_pending_payment(razorpay_order_id)

            # Deduct stock
            for item in pending.get("items", []):
                try:
                    deduct_stock(item.get("slug"), item.get("size", "S"), item.get("quantity", 1))
                except Exception:
                    pass

            # Coupon redemption
            if coupon_code and discount > 0:
                try:
                    record_coupon_redemption(coupon_code, order_number, pending["customer"].get("email", ""), pending["customer"].get("phone", ""), discount)
                except Exception:
                    pass

            # Notification
            cust_name = f"{pending['customer'].get('first_name', '')} {pending['customer'].get('last_name', '')}".strip() or "Valued Client"
            try:
                create_admin_notification(
                    order_number=order_number,
                    title=f"New Order Confirmed: {order_number}",
                    message=f"Customer {cust_name} placed order of ₹{pending['total']:,} via Webhook.",
                    amount=pending["total"],
                    customer_name=cust_name,
                    customer_phone=pending["customer"].get("phone", "")
                )
            except Exception:
                pass

            # Email
            try:
                email_html = build_order_confirmation_email_html(order)
                send_order_email(pending["customer"].get("email"), f"Order Confirmed #{order_number} — Alzor Couture", email_html)
                send_order_email(ADMIN_EMAIL, f"[NEW ORDER] #{order_number} — ₹{pending['total']:,} by {cust_name}", email_html)
            except Exception:
                pass

            app.logger.info(f"Order {order_number} created via webhook for payment {razorpay_payment_id}")
        else:
            order_number = generate_order_number()
            amount_rupees = int(payment_entity.get("amount", 0)) // 100
            order = {
                "order_number": order_number,
                "created_at": now_str,
                "status": "Confirmed",
                "payment_method": "Razorpay (Direct Webhook)",
                "payment_status": "Paid",
                "razorpay_order_id": razorpay_order_id or "direct",
                "razorpay_payment_id": razorpay_payment_id,
                "customer": {
                    "first_name": payment_entity.get("notes", {}).get("brand", "Client"),
                    "last_name": "",
                    "email": payment_entity.get("email", ""),
                    "phone": payment_entity.get("contact", ""),
                    "address": "Captured via Razorpay Webhook",
                    "city": "",
                    "state": "",
                    "pincode": ""
                },
                "items": [],
                "subtotal": amount_rupees,
                "discount": 0,
                "coupon_code": "",
                "shipping": 0,
                "total": amount_rupees,
                "stock_restored": False,
                "timeline": [
                    {
                        "status": "Confirmed",
                        "time": now_str,
                        "admin": "Razorpay Direct Webhook",
                        "note": "Payment captured directly without prior pending record."
                    }
                ],
                "admin_notes": []
            }
            save_order(order)
            try:
                create_admin_notification(
                    order_number=order_number,
                    title=f"Direct Order: {order_number}",
                    message=f"Direct payment captured: ₹{amount_rupees:,} for payment ID {razorpay_payment_id}",
                    amount=amount_rupees,
                    customer_name="Client",
                    customer_phone=payment_entity.get("contact", "")
                )
            except Exception:
                pass
            app.logger.info(f"Direct order {order_number} created via webhook for payment {razorpay_payment_id}")

        return jsonify({"status": "success", "message": "Payment captured and order recorded"}), 200

    elif event_type == "payment.failed":
        app.logger.warning(f"Payment failed via webhook: {razorpay_payment_id} for order {razorpay_order_id}")
        return jsonify({"status": "recorded", "message": "Payment failure noted"}), 200

    return jsonify({"status": "ignored", "event": event_type}), 200


# =========================================================
# CUSTOMER ORDER CANCELLATION API
# =========================================================

@app.route("/api/order/cancel", methods=["POST"])
def api_order_cancel():
    data = request.get_json(silent=True) or request.form
    order_number = str(data.get("order_number", "")).strip().upper()
    contact_info = str(data.get("contact_info", "")).strip().lower()
    reason = str(data.get("reason", "Cancelled by customer request")).strip()

    if not order_number or not contact_info:
        return jsonify({"success": False, "message": "Order number and contact information are required."}), 400

    order = find_order_by_number(order_number)
    if not order:
        return jsonify({"success": False, "message": f"Order '{order_number}' not found."}), 404

    cust = order.get("customer", {})
    cust_phone = (cust.get("phone") or "").replace(" ", "").replace("-", "").replace("+91", "")
    cust_email = (cust.get("email") or "").lower()
    clean_contact = contact_info.replace(" ", "").replace("-", "").replace("+91", "")

    if not (contact_info == cust_email or (clean_contact and clean_contact in cust_phone)):
        return jsonify({"success": False, "message": "Contact details do not match this order."}), 403

    current_status = order.get("status", "")
    cancellable_statuses = ["Pending", "Confirmed", "Order Placed", "In Production", "Processing"]
    if current_status not in cancellable_statuses:
        return jsonify({
            "success": False,
            "message": f"This order is currently '{current_status}' and cannot be automatically cancelled online. Please contact our concierge via WhatsApp at +91 8527144345."
        }), 400

    updated = update_order_status(order_number, "Cancelled", note=f"Customer cancellation request: {reason}", admin_name="Client Concierge")
    create_admin_notification(
        order_number=order_number,
        title=f"Order Cancelled by Customer: {order_number}",
        message=f"Customer requested cancellation. Reason: {reason}",
        amount=order.get("total", 0),
        customer_name=f"{cust.get('first_name')} {cust.get('last_name')}",
        customer_phone=cust.get("phone")
    )

    return jsonify({"success": True, "message": "Your order has been cancelled successfully. Any payment refund will be processed to the original payment source within 5-7 business days."})


# =========================================================
# ATELIER ADMIN PORTAL
# =========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if session.get("alzor_admin_authenticated"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        password = request.form.get("password", "").strip()
        admin_pass = ADMIN_PASSWORD
        if password and password == admin_pass:
            session["alzor_admin_authenticated"] = True
            session.permanent = True
            return redirect(url_for("admin_dashboard"))
        else:
            error = "Invalid Atelier Passcode. Please enter the authorized administrator key."

    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("alzor_admin_authenticated", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@app.route("/admin/orders")
@app.route("/admin/products")
def admin_dashboard():
    if not session.get("alzor_admin_authenticated"):
        return redirect(url_for("admin_login"))

    active_tab = "products" if "products" in request.path else "orders"

    try:
        orders = load_all_orders(limit=250)
    except Exception:
        app.logger.exception("Failed to load orders for admin dashboard")
        orders = []

    try:
        pending = load_all_pending_payments(limit=50)
    except Exception:
        app.logger.exception("Failed to load pending payments for admin dashboard")
        pending = []

    today_str = datetime.now().strftime("%Y-%m-%d")
    total_revenue = 0
    today_revenue = 0
    today_orders_count = 0
    total_discounts = 0
    status_counts = {}

    for o in orders:
        if isinstance(o, dict):
            st = o.get("status", "Confirmed")
            status_counts[st] = status_counts.get(st, 0) + 1
            if o.get("payment_status") == "Paid":
                amt = int(o.get("total") or 0)
                disc = int(o.get("discount") or 0)
                total_revenue += amt
                total_discounts += disc
                created = str(o.get("created_at") or "")
                if created.startswith(today_str):
                    today_revenue += amt
                    today_orders_count += 1

    try:
        coupons = get_all_coupons()
    except Exception:
        coupons = []

    try:
        inventory = get_all_inventory()
    except Exception:
        inventory = []

    try:
        all_catalog_products = get_all_products()
    except Exception:
        all_catalog_products = []

    products_count = len(all_catalog_products)
    custom_products_count = len([p for p in all_catalog_products if p.get("is_custom")])

    try:
        notifications = get_admin_notifications(limit=30)
        unread_notifs = get_unread_notification_count()
    except Exception:
        notifications = []
        unread_notifs = 0

    return render_template(
        "admin.html",
        orders=orders,
        pending=pending,
        total_revenue=total_revenue,
        today_revenue=today_revenue,
        today_orders_count=today_orders_count,
        total_discounts=total_discounts,
        status_counts=status_counts,
        coupons=coupons,
        coupons_count=len(coupons),
        inventory=inventory,
        inventory_count=len(inventory),
        products=all_catalog_products,
        products_count=products_count,
        custom_products_count=custom_products_count,
        notifications=notifications,
        unread_notifs=unread_notifs,
        orders_count=len(orders),
        pending_count=len(pending),
        active_tab=active_tab,
        is_live=RAZORPAY_IS_LIVE,
        razorpay_key_preview=RAZORPAY_KEY_ID[:12] if RAZORPAY_KEY_ID else "NOT_CONFIGURED"
    )


@app.route("/admin/order/<order_number>/status", methods=["POST"])
def admin_update_order_status(order_number):
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form
    new_status = data.get("status", "").strip()
    status_note = data.get("note", "").strip()
    valid_statuses = [
        "Pending", "Confirmed", "Order Placed", "In Production", "Processing",
        "Packed", "Shipped", "Out for Delivery", "Delivered",
        "Cancelled", "Returned", "Refunded"
    ]

    if new_status not in valid_statuses:
        return jsonify({"success": False, "message": f"Invalid status: {new_status}"}), 400

    updated = update_order_status(order_number, new_status, note=status_note, admin_name="Atelier Admin")
    if not updated:
        return jsonify({"success": False, "message": "Order not found"}), 404

    return jsonify({"success": True, "message": f"Order status updated to {new_status}", "order": updated})


@app.route("/admin/order/<order_number>/note", methods=["POST"])
def admin_add_order_note(order_number):
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form
    note_text = data.get("note", "").strip()
    if not note_text:
        return jsonify({"success": False, "message": "Note cannot be empty."}), 400
    updated = add_order_admin_note(order_number, note_text, admin_name="Atelier Admin")
    if not updated:
        return jsonify({"success": False, "message": "Order not found."}), 404
    return jsonify({"success": True, "message": "Admin note saved.", "admin_notes": updated.get("admin_notes", [])})


@app.route("/admin/orders/export-csv")
def admin_export_orders_csv():
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    orders = load_all_orders(limit=1000)
    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM
    writer = csv.writer(output)

    writer.writerow([
        "Order Number",
        "Order Date",
        "Order Status",
        "Payment Status",
        "Payment Method",
        "Razorpay Payment ID",
        "Razorpay Order ID",
        "Customer Name",
        "Customer Phone",
        "Customer Email",
        "Address",
        "City",
        "State",
        "Pincode",
        "Items Summary",
        "Subtotal (INR)",
        "Promo Code",
        "Discount (INR)",
        "Shipping (INR)",
        "Total (INR)"
    ])

    for o in orders:
        cust = o.get("customer", {})
        first = cust.get("first_name", "")
        last = cust.get("last_name", "")
        full_name = f"{first} {last}".strip()
        items = o.get("items", [])
        items_str = "; ".join([f"{it.get('name')} (Size {it.get('size')}, Qty {it.get('quantity')})" for it in items])

        writer.writerow([
            o.get("order_number", ""),
            o.get("created_at", ""),
            o.get("status", ""),
            o.get("payment_status", ""),
            o.get("payment_method", ""),
            o.get("razorpay_payment_id", ""),
            o.get("razorpay_order_id", ""),
            full_name,
            cust.get("phone", ""),
            cust.get("email", ""),
            cust.get("address", ""),
            cust.get("city", ""),
            cust.get("state", ""),
            cust.get("pincode", ""),
            items_str,
            o.get("subtotal", 0),
            o.get("coupon_code", ""),
            o.get("discount", 0),
            o.get("shipping", 0),
            o.get("total", 0)
        ])

    csv_data = output.getvalue()
    filename = f"alzor_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# =========================================================
# ADMIN NOTIFICATIONS API
# =========================================================

@app.route("/admin/api/notifications", methods=["GET"])
def admin_api_notifications():
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    notifs = get_admin_notifications(limit=30)
    unread = get_unread_notification_count()
    return jsonify({"success": True, "notifications": notifs, "unread_count": unread})


@app.route("/admin/api/notifications/mark-read/<int:notif_id>", methods=["POST"])
def admin_api_mark_notification_read(notif_id):
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    mark_notification_read(notif_id)
    return jsonify({"success": True, "unread_count": get_unread_notification_count()})


@app.route("/admin/api/notifications/mark-all-read", methods=["POST"])
def admin_api_mark_all_notifications_read():
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    mark_all_notifications_read()
    return jsonify({"success": True, "unread_count": 0})


# =========================================================
# ADMIN COUPONS API
# =========================================================

@app.route("/admin/api/coupons/create", methods=["POST"])
def admin_api_create_coupon():
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form
    success, msg = create_coupon(data)
    if not success:
        return jsonify({"success": False, "message": msg}), 400
    return jsonify({"success": True, "message": msg})


@app.route("/admin/api/coupons/<code>/toggle", methods=["POST"])
def admin_api_toggle_coupon(code):
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    success, msg = toggle_coupon(code)
    if not success:
        return jsonify({"success": False, "message": msg}), 404
    return jsonify({"success": True, "message": msg})


@app.route("/admin/api/coupons/<code>/delete", methods=["POST"])
def admin_api_delete_coupon(code):
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    success, msg = delete_coupon(code)
    if not success:
        return jsonify({"success": False, "message": msg}), 404
    return jsonify({"success": True, "message": msg})


@app.route("/admin/api/coupons/<code>/redemptions", methods=["GET"])
def admin_api_coupon_redemptions(code):
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    redemptions = get_coupon_redemptions(code)
    return jsonify({"success": True, "code": code.upper(), "redemptions": redemptions})


# =========================================================
# ADMIN INVENTORY API
# =========================================================

@app.route("/admin/api/inventory/update", methods=["POST"])
def admin_api_update_inventory():
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form
    slug = data.get("slug", "").strip()
    size = data.get("size", "").strip()
    try:
        new_stock = int(data.get("stock", 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid stock value."}), 400
    if not slug or not size:
        return jsonify({"success": False, "message": "Product slug and size required."}), 400
    update_stock(slug, size, new_stock)
    return jsonify({"success": True, "message": f"Stock updated to {new_stock} units for {slug} ({size})."})


# =========================================================
# ADMIN PRODUCT CATALOG API (IMAGE UPLOADS, CREATE, EDIT, DELETE)
# =========================================================

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "jfif", "avif", "heic"}


@app.route("/admin/api/products", methods=["GET"])
def admin_api_get_products():
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify({
        "success": True,
        "products": get_all_products()
    })


@app.route("/admin/api/products/<slug>", methods=["GET"])
def admin_api_get_product(slug):
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    p = find_product(slug)
    if not p:
        return jsonify({"success": False, "message": "Product not found"}), 404

    stock_map = {}
    for sz in AVAILABLE_SIZES:
        stock_map[sz] = get_product_stock(slug, sz)

    prod_data = dict(p)
    prod_data["stock"] = stock_map
    return jsonify({"success": True, "product": prod_data})


@app.route("/admin/api/products/upload-images", methods=["POST"])
def admin_api_upload_images():
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    files = request.files.getlist("images") or request.files.getlist("images[]") or request.files.getlist("file")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"success": False, "message": "No photos selected. Please pick images from your device."}), 400

    upload_dir = os.path.join(app.root_path, "static", "images")
    os.makedirs(upload_dir, exist_ok=True)

    saved_filenames = []

    for f in files:
        if not f or not f.filename:
            continue
        original_name = f.filename.lower()
        ext = original_name.rsplit(".", 1)[-1] if "." in original_name else "jpg"
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            ext = "jpg"

        unique_token = secrets.token_hex(4)
        timestamp = int(datetime.now().timestamp())
        filename = f"prod_{timestamp}_{unique_token}.{ext}"
        filepath = os.path.join(upload_dir, filename)

        try:
            file_bytes = f.read()
        except Exception as e:
            app.logger.warning(f"Error reading file bytes: {e}")
            continue

        if not file_bytes:
            continue

        # 1. Write to static/images on disk
        try:
            with open(filepath, "wb") as out_f:
                out_f.write(file_bytes)
        except Exception as e:
            app.logger.warning(f"Could not write image to disk ({filepath}): {e}")

        # 2. Persist to database (alzor_uploaded_images) for durable cross-restart recovery
        try:
            b64_data = base64.b64encode(file_bytes).decode("utf-8")
            mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
            with get_db_cursor() as (cur, is_pg):
                ph = "%s" if is_pg else "?"
                if is_pg:
                    cur.execute(
                        f"""INSERT INTO alzor_uploaded_images (filename, content_type, data_base64, created_at)
                           VALUES ({ph}, {ph}, {ph}, NOW())
                           ON CONFLICT (filename) DO NOTHING""",
                        (filename, mime, b64_data)
                    )
                else:
                    cur.execute(
                        f"""INSERT OR IGNORE INTO alzor_uploaded_images (filename, content_type, data_base64, created_at)
                           VALUES ({ph}, {ph}, {ph}, datetime('now'))""",
                        (filename, mime, b64_data)
                    )
        except Exception as e:
            app.logger.exception(f"Failed to persist image in DB: {e}")

        saved_filenames.append(filename)

    if not saved_filenames:
        return jsonify({"success": False, "message": "Failed to process selected images."}), 500

    return jsonify({
        "success": True,
        "filenames": saved_filenames,
        "urls": [f"/static/images/{fn}" for fn in saved_filenames]
    })


@app.route("/admin/api/products/save", methods=["POST"])
def admin_api_save_product():
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Product name is required."}), 400

    raw_slug = (data.get("slug") or "").strip()
    slug = slugify(raw_slug) if raw_slug else slugify(name)
    if not slug:
        slug = f"prod-{secrets.token_hex(4)}"

    try:
        price = int(data.get("price") or 0)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid price value."}), 400

    if price <= 0:
        return jsonify({"success": False, "message": "Price must be greater than ₹0."}), 400

    orig_price = data.get("original_price")
    try:
        orig_price = int(orig_price) if orig_price else 0
    except (ValueError, TypeError):
        orig_price = 0

    images = data.get("images", [])
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            images = [images] if images else []

    if not images:
        images = ["logo.png"]

    category = (data.get("category") or "CO-ORD SET").strip().upper()
    description = (data.get("description") or "").strip()
    details = data.get("details", [])
    if isinstance(details, str):
        details = [d.strip() for d in details.split("\n") if d.strip()]
    care = (data.get("care") or "Dry clean recommended.").strip()
    is_active = bool(data.get("is_active", True))

    sizes = data.get("sizes", AVAILABLE_SIZES)
    if isinstance(sizes, str):
        sizes = [s.strip() for s in sizes.split(",") if s.strip()]

    stock = data.get("stock", {})
    if isinstance(stock, str):
        try:
            stock = json.loads(stock)
        except Exception:
            stock = {}

    is_edit = bool(data.get("is_edit", False))

    saved_slug = save_custom_product({
        "name": name,
        "slug": slug,
        "category": category,
        "price": price,
        "original_price": orig_price,
        "images": images,
        "description": description,
        "details": details,
        "care": care,
        "is_active": is_active,
        "sizes": sizes,
        "stock": stock
    }, is_edit=is_edit)

    return jsonify({
        "success": True,
        "slug": saved_slug,
        "message": f"Product '{name}' successfully {'updated' if is_edit else 'published'} to atelier!"
    })


@app.route("/admin/api/products/<slug>/delete", methods=["POST"])
def admin_api_delete_product(slug):
    if not session.get("alzor_admin_authenticated"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    delete_custom_product(slug)
    return jsonify({
        "success": True,
        "message": f"Product '{slug}' successfully removed from custom catalog."
    })


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
            <a href="https://www.instagram.com/alzor.couture?vrfl=MWJvY3hqYjZldXdmYQ==" target="_blank" rel="noopener noreferrer" class="policy-email-btn" style="border-color:#ad8a51;color:#ad8a51;">
                INSTAGRAM: @ALZOR.COUTURE
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
                customer = found.get("customer") or {}
                cust_phone = (customer.get("phone") or found.get("customer_phone") or "").strip().lower()
                cust_email = (customer.get("email") or found.get("customer_email") or "").strip().lower()
                clean_contact = contact_info.replace(" ", "").replace("-", "").replace("+91", "")
                clean_phone = cust_phone.replace(" ", "").replace("-", "").replace("+91", "")

                matches_email = bool(cust_email and contact_info == cust_email)
                matches_phone = bool(clean_contact and clean_phone and (clean_contact in clean_phone or clean_phone in clean_contact))

                if matches_email or matches_phone:
                    found["total_amount"] = found.get("total") if found.get("total") is not None else (found.get("total_amount") or 0)
                    first = customer.get("first_name", "")
                    last = customer.get("last_name", "")
                    found["customer_name"] = f"{first} {last}".strip() or found.get("customer_name") or "Valued Client"
                    found["city"] = customer.get("city") or found.get("city") or ""
                    found["state"] = customer.get("state") or found.get("state") or ""
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
Disallow: /admin
Disallow: /admin/
Disallow: /api/
Disallow: /checkout
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


@app.route("/healthz")
@app.route("/ping")
def healthz():
    """Keep-alive ping endpoint to prevent Render sleep and verify server health."""
    return jsonify({
        "status": "ok",
        "app": "alzor-couture",
        "mode": "live" if RAZORPAY_IS_LIVE else "test",
        "database": "postgresql" if USE_POSTGRES else "sqlite",
        "timestamp": datetime.now().isoformat()
    }), 200


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static", "images"),
        "logo.png",
        mimetype="image/png"
    )


@app.errorhandler(404)
def page_not_found(e):
    # Dynamic fallback: if a custom-uploaded image is missing from local disk, serve it from DB
    if request.path.startswith("/static/images/"):
        filename = os.path.basename(request.path)
        try:
            with get_db_cursor() as (cur, is_pg):
                ph = "%s" if is_pg else "?"
                cur.execute(f"SELECT content_type, data_base64 FROM alzor_uploaded_images WHERE filename = {ph}", (filename,))
                row = cur.fetchone()
                if row:
                    mime, b64_data = row[0], row[1]
                    raw_bytes = base64.b64decode(b64_data)
                    # Cache to local static folder if writable
                    try:
                        upload_dir = os.path.join(app.root_path, "static", "images")
                        os.makedirs(upload_dir, exist_ok=True)
                        with open(os.path.join(upload_dir, filename), "wb") as out_f:
                            out_f.write(raw_bytes)
                    except Exception:
                        pass
                    resp = Response(raw_bytes, mimetype=mime)
                    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                    return resp
        except Exception:
            pass

    return render_template(
        "404.html",
        site_url=SITE_URL
    ), 404


@app.errorhandler(500)
def server_error(e):
    return render_template(
        "404.html",
        site_url=SITE_URL,
        error_title="TEMPORARILY UNAVAILABLE",
        error_message="Our atelier service is undergoing a brief refinement. Please return shortly or connect with our concierge."
    ), 500


@app.route("/domain-setup")
def domain_setup():
    return send_from_directory("static", "domain-setup.html")


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
