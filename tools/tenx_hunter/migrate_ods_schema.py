#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from vnpy.web.tenx_hunter.config import load_settings
from vnpy.web.tenx_hunter.pipeline import ensure_schema


def main() -> int:
    settings = load_settings()
    ensure_schema(settings)
    print("ODS schema sync complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
