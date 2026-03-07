from __future__ import annotations

import os
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vnpy.web.api.router import api_router
from vnpy.web.services import cb_history_service
from vnpy.web.ws.router import ws_router

@asynccontextmanager
async def _lifespan(_: FastAPI):
    def _sync_on_startup() -> None:
        try:
            cb_history_service.sync_today_from_market(mode="startup")
        except Exception:
            # Network/source failures should not block API startup.
            pass

    # 启动时只做一次当日行情快照同步，不再保留任何 legacy Excel bootstrap 逻辑。
    Thread(target=_sync_on_startup, name="cb-history-startup-sync", daemon=True).start()

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
