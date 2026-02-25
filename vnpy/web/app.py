from __future__ import annotations

import os
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vnpy.web.api.router import api_router
from vnpy.web.services import cb_history_service
from vnpy.web.ws.router import ws_router


def _legacy_history_sync_enabled() -> bool:
    value = os.getenv("CB_LEGACY_HISTORY_SYNC", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


@asynccontextmanager
async def _lifespan(_: FastAPI):
    if not _legacy_history_sync_enabled():
        # Default to tushare-only data pipeline to avoid mixed sources.
        yield
        return

    def _bootstrap_and_sync() -> None:
        try:
            cb_history_service.bootstrap_from_crawler_snapshots()
        except Exception:
            # Bootstrap is best-effort; runtime sync still works.
            pass

        try:
            cb_history_service.sync_today_from_market(mode="startup")
        except Exception:
            # Network/source failures should not block API startup.
            pass

    Thread(target=_bootstrap_and_sync, name="cb-history-bootstrap", daemon=True).start()

    cb_history_service.start_scheduler()
    try:
        yield
    finally:
        cb_history_service.stop_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(
        title="VN.PY Web API",
        version="0.1.0",
        description="CB Quant frontend-backend integration API",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(ws_router)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    host = os.getenv("VNPY_WEB_HOST", "0.0.0.0")
    port = int(os.getenv("VNPY_WEB_PORT", "8000"))
    uvicorn.run("vnpy.web.app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
