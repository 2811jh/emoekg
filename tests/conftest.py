"""Pytest shared fixtures for emoekg."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure `src/` layout is importable without an editable install.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
