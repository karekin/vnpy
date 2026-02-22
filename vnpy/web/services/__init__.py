from vnpy.web.services.cb_quant_service import CbQuantService
from vnpy.web.services.cb_market_service import CbMarketService

cb_quant_service = CbQuantService()
cb_market_service = CbMarketService()

__all__ = [
    "CbQuantService",
    "CbMarketService",
    "cb_quant_service",
    "cb_market_service",
]
