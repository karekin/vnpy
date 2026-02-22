from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vnpy.web.api.router import api_router
from vnpy.web.ws.router import ws_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="VN.PY Web API",
        version="0.1.0",
        description="CB Quant frontend-backend integration API",
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
    port = int(os.getenv("VNPY_WEB_PORT", "9000"))
    uvicorn.run("vnpy.web.app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
