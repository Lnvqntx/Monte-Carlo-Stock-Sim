"""Vercel entrypoint: Vercel's FastAPI preset looks for an `app` in index.py at the project root.

The real app lives in api/main.py (run locally with `uvicorn api.main:app`); this file only
re-exports it so Vercel can find it. Keep it a one-line import - no behaviour here.
"""

from api.main import app

__all__ = ["app"]
