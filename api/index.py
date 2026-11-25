import os
import sys

# Add root project directory to sys.path so app.py and templates/static resolve cleanly
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app

# Expose WSGI application for Vercel Serverless Function runtime
application = app
