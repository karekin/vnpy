from fastapi import APIRouter

from vnpy.web.api import cb_quant, system, tenx_hunter

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system.router)
api_router.include_router(cb_quant.router)
api_router.include_router(tenx_hunter.router)
