"""
BNB Agent Marketplace — Vercel serverless entry point.
Exposes the FastAPI app as a Vercel serverless function.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path so `app.*` imports work in Vercel's runtime
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app as fastapi_app  # noqa: E402

# Export for Vercel
app = fastapi_app
