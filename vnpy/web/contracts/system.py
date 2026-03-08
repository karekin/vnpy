from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "vnpy-web"
    version: str = "v1"


class OperationResponse(BaseModel):
    ok: bool = True
    message: str = "ok"
