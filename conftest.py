"""Make ``src/`` importable so tests run with a bare ``pytest`` (no install)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
