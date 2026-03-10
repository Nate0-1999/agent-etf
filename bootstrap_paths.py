"""Runtime path bootstrap for monorepo local imports."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

_PATHS = [
    "libs/contracts",
    "libs/broker-adapters",
    "libs/audit",
    "services/research",
    "services/backtest",
    "services/execution",
    "services/llm-gateway",
    "workers/temporal",
]


def add_project_paths() -> None:
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    for relative in _PATHS:
        candidate = str(root / relative)
        if candidate not in sys.path:
            sys.path.append(candidate)
