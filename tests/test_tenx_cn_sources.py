from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from vnpy.web.tenx_hunter.cn_sources import build_cn_stock_bundle
from vnpy.web.tenx_hunter.config import load_settings


def _frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TenxCnSourcesTests(unittest.TestCase):
    def test_build_cn_stock_bundle_should_map_tushare_rows(self) -> None:
        responses = {
            "stock_basic": _frame(
                [
                    {
                        "ts_code": "300308.SZ",
                        "name": "中际旭创",
                        "industry": "元件",
                        "market": "创业板",
                        "exchange": "SZSE",
                        "list_status": "L",
                        "list_date": "20120410",
                    }
                ]
            ),
            "trade_cal": _frame([{"cal_date": "20260415"}]),
            "daily": _frame(
                [
                    {
                        "ts_code": "300308.SZ",
                        "open": 101.0,
                        "high": 103.0,
                        "low": 100.0,
                        "close": 102.0,
                        "vol": 123456,
                    }
                ]
            ),
            "daily_basic": _frame(
                [
                    {
                        "ts_code": "300308.SZ",
                        "pe_ttm": 22.5,
                        "pb": 3.4,
                        "turnover_rate": 0.03,
                        "total_mv": 200000,
                    }
                ]
            ),
            "fina_indicator": _frame(
                [
                    {
                        "ts_code": "300308.SZ",
                        "end_date": "20251231",
                        "ann_date": "20260330",
                        "tr_yoy": 36.0,
                        "netprofit_yoy": 41.0,
                        "grossprofit_margin": 31.0,
                        "op_of_gr": 17.0,
                        "rd_exp_ratio": 0.11,
                    }
                ]
            ),
            "income": _frame(
                [
                    {
                        "ts_code": "300308.SZ",
                        "end_date": "20251231",
                        "ann_date": "20260330",
                        "revenue": 12000000000,
                        "n_income_attr_p": 2300000000,
                    }
                ]
            ),
            "balancesheet": _frame(
                [
                    {
                        "ts_code": "300308.SZ",
                        "end_date": "20251231",
                        "ann_date": "20260330",
                        "money_cap": 4500000000,
                        "total_liab": 2200000000,
                        "total_share": 800000000,
                    }
                ]
            ),
            "cashflow": _frame(
                [
                    {
                        "ts_code": "300308.SZ",
                        "end_date": "20251231",
                        "ann_date": "20260330",
                        "n_cashflow_act": 2600000000,
                    }
                ]
            ),
        }

        def fake_query(self, api_name: str, **_params):
            return responses.get(api_name, pd.DataFrame())

        with patch("vnpy.web.tenx_hunter.cn_sources._TushareClient.query", new=fake_query):
            with patch("vnpy.web.tenx_hunter.cn_sources.CbTushareService._load_token", return_value="demo-token"):
                with patch("vnpy.web.tenx_hunter.cn_sources.CbTushareService._load_http_url", return_value="http://demo"):
                    settings = load_settings()
                    bundle = build_cn_stock_bundle(settings)

        self.assertEqual(bundle["securities"][0]["market"], "CN")
        self.assertEqual(bundle["securities"][0]["symbol"], "300308.SZ")
        self.assertEqual(bundle["prices"][0]["market"], "CN")
        self.assertEqual(bundle["prices"][0]["raw_payload"]["pe_ttm"], 22.5)
        self.assertEqual(bundle["financials"][0]["market"], "CN")
        self.assertEqual(bundle["financials"][0]["report_period"], "2025-12-31")


if __name__ == "__main__":
    unittest.main()
