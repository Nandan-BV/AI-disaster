"""
Root pytest configuration for RESQ-AI.

The repository is split across two import roots:

* ``backend/`` provides the ``app`` package (FastAPI service, models, API).
* the repository root provides the top-level ``ai`` package (multimodal models
  and Phase 2/3 AI services).

Tests import from both, so both roots are put on ``sys.path`` here instead of
requiring every invocation to set ``PYTHONPATH`` by hand.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.resolve()
BACKEND_ROOT = REPO_ROOT / "backend"

for path in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
