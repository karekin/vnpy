from fastapi import APIRouter

from vnpy.web.api import cb_quant, investment_copilot, smart_allocation, social_hot_stocks, system, tenx_hunter

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system.router)
api_router.include_router(cb_quant.router)
api_router.include_router(tenx_hunter.router)
api_router.include_router(social_hot_stocks.router)
api_router.include_router(smart_allocation.router)
api_router.include_router(investment_copilot.router)
