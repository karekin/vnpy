from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MainEngineAdapter:
    """Thin adapter placeholder for future MainEngine/EventEngine bindings."""

    engine: Any | None = None

    def health(self) -> dict[str, str]:
        if self.engine is None:
            return {"mode": "mock", "engine": "disconnected"}
        return {"mode": "live", "engine": "connected"}
