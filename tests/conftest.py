"""Pytest configuration for Elite Voice Agent tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable (for agents/, models, crm, etc.)
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

# Load .env so LiveKit Cloud credentials are available to behavioral tests
from dotenv import load_dotenv
load_dotenv(_root / ".env")
