"""
run_with_frontend.py  -  starts the SAME API from main.py, plus the web pages
==============================================================================
main.py does not know this file exists. This file imports `app` from main.py
and adds one thing to it: the pages in this folder, served at /app.

HOW TO RUN (from the Food_Delivery_Project folder, NOT from extra_frontend):
    python -m uvicorn extra_frontend.run_with_frontend:app --reload
Then open:
    http://127.0.0.1:8000/app/     the front end
    http://127.0.0.1:8000/docs     the usual FastAPI page (still works)

To remove the front end: delete the whole extra_frontend folder and run
`uvicorn main:app --reload` as before. Nothing else changes.
"""
import os

from fastapi.staticfiles import StaticFiles

from main import app

FRONTEND_FOLDER = os.path.dirname(os.path.abspath(__file__))
app.mount("/app", StaticFiles(directory=FRONTEND_FOLDER, html=True), name="frontend")
