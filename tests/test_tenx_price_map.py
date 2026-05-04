from __future__ import annotations

import unittest

from vnpy.web.tenx_hunter import pipeline
from vnpy.web.tenx_hunter.price_map import build_price_map, build_technical_snapshot
from vnpy.web.tenx_hunter.price_map_deerflow import extract_json_object, price_map_from_deerflow_payload


class PriceMapTests(unittest.TestCase):
    def _price_rows(self) -> list[dict[str, object]]:
        return [
            {
                "trade_date": f"2026-04-{day:02d}",
                "open": 90 + day,
                "high": 92 + day,
                "low": 88 + day,
                "close": 90 + day,
                "volume": 1_000_000 + day * 1000,
                "pe_ttm": 25 + day / 10,
                "ps_ttm": 5.0,
            }
            for day in range(1, 21)
        ]

    def test_build_technical_snapshot_outputs_position_and_levels(self) -> None:
        technical = build_technical_snapshot(self._price_rows())

        self.assertIsNotNone(technical)
        assert technical is not None
        self.assertEqual(technical.close, 110)
        self.assertGreater(technical.position_52w or 0, 0.8)
        self.assertIsNotNone(technical.ma20)
        self.assertIsNotNone(technical.atr14)
        self.assertIsNotNone(technical.support_level)
        self.assertIsNotNone(technical.resistance_level)

    def test_build_price_map_outputs_three_scenarios_and_invalidation(self) -> None:
        technical = build_technical_snapshot(self._price_rows())
        assert technical is not None

        price_map = build_price_map(
            technical,
            {"pe_ttm": 27.0, "ps_ttm": 5.0},
            {"revenue_yoy": 35.0, "netprofit_yoy": 42.0, "shares_outstanding": 800_000_000},
            {"total_score": 78.0},
            None,
            None,
            None,
            ["filings/demo.txt"],
        )

        scenarios = {target.scenario for target in price_map.targets}
        self.assertEqual(scenarios, {"bear", "base", "bull"})
        base = next(target for target in price_map.targets if target.scenario == "base")
        bull = next(target for target in price_map.targets if target.scenario == "bull")
        bear = next(target for target in price_map.targets if target.scenario == "bear")
        self.assertGreater(base.target_mid or 0, technical.close)
        self.assertGreater(bull.target_mid or 0, base.target_mid or 0)
        self.assertLess(bear.target_mid or technical.close, technical.close)
        self.assertGreaterEqual(len(price_map.key_levels), 4)
        self.assertEqual(len(price_map.scenario_paths), 3)
        self.assertTrue(price_map.invalidation_rules)
        self.assertIn("next_watch", price_map.explanation)

    def test_us_option_summary_adds_option_levels_and_explanation(self) -> None:
        technical = build_technical_snapshot(self._price_rows())
        assert technical is not None

        price_map = build_price_map(
            technical,
            {"pe_ttm": 27.0, "ps_ttm": 5.0},
            {"revenue_yoy": 35.0, "netprofit_yoy": 42.0, "shares_outstanding": 800_000_000},
            {"total_score": 78.0},
            {
                "data_quality_flag": "ok",
                "flow_sentiment": "bullish",
                "flow_score": 72.0,
                "liquidity_score": 80.0,
                "call_put_volume_ratio": 2.0,
                "call_put_open_interest_ratio": 1.6,
                "max_pain_strike": 105.0,
            },
            None,
            None,
            ["filings/demo.txt"],
        )

        level_types = {level.level_type for level in price_map.key_levels}
        self.assertIn("max_pain", level_types)
        self.assertIn("options_flow_bias", level_types)
        self.assertIn("options", price_map.explanation)
        breakthrough = next(path for path in price_map.scenario_paths if path.path_name == "突破上修")
        self.assertGreaterEqual(breakthrough.probability, 40)

    def test_estimates_and_earnings_calendar_anchor_target_method(self) -> None:
        technical = build_technical_snapshot(self._price_rows())
        assert technical is not None

        price_map = build_price_map(
            technical,
            {"pe_ttm": 27.0, "ps_ttm": 5.0},
            {"revenue_yoy": 35.0, "netprofit_yoy": 42.0, "shares_outstanding": 800_000_000},
            {"total_score": 78.0},
            None,
            {
                "data_quality_flag": "ok",
                "fy1_eps": 5.0,
                "fy2_eps": 6.2,
                "fy1_revenue_estimate": 80_000_000_000,
                "fy2_revenue_estimate": 96_000_000_000,
                "fy1_analyst_count": 32,
                "fy2_analyst_count": 29,
            },
            {
                "data_quality_flag": "ok",
                "next_earnings_date": "2026-05-22",
                "days_to_earnings": 19,
            },
            ["filings/demo.txt"],
        )

        base = next(target for target in price_map.targets if target.scenario == "base")
        self.assertEqual(base.method, "analyst_eps_pe_hybrid")
        self.assertIn("fy1_eps", base.assumptions)
        self.assertIn("estimates", price_map.explanation)
        self.assertIn("earnings", price_map.explanation)

    def test_deerflow_price_map_payload_overrides_baseline(self) -> None:
        technical = build_technical_snapshot(self._price_rows())
        assert technical is not None
        baseline = build_price_map(
            technical,
            {"pe_ttm": 27.0, "ps_ttm": 5.0},
            {"revenue_yoy": 35.0, "netprofit_yoy": 42.0, "shares_outstanding": 800_000_000},
            {"total_score": 78.0},
            None,
            None,
            None,
            ["filings/demo.txt"],
        )
        payload = extract_json_object(
            """
            ```json
            {
              "posture": "near_base_target",
              "posture_label": "接近目标区",
              "confidence": "medium",
              "base_target": {"low": 118, "high": 126, "mid": 122, "method": "deerflow_price_analysis"},
              "bull_target": {"low": 138, "high": 152, "mid": 145, "method": "deerflow_price_analysis"},
              "bear_zone": {"low": 94, "high": 100, "mid": 97, "method": "deerflow_price_analysis"},
              "key_levels": [{"level_type": "current_price", "low": 110, "high": 110, "source": "deerflow", "note": "当前价格"}],
              "scenario_paths": [{"name": "震荡上修", "probability": 45, "confidence": "medium", "trigger": "站稳 118", "target_scenario": "base", "invalidation": "跌破 100", "explanation": "等待财报验证"}],
              "explanation": {"next_watch": "观察成交量和财报。"}
            }
            ```
            """
        )

        price_map = price_map_from_deerflow_payload(
            fallback=baseline,
            payload=payload,
            current_price=technical.close,
            deerflow_thread_id="tenx-price-map-us-nvda-2026-04-20",
        )

        base = next(target for target in price_map.targets if target.scenario == "base")
        self.assertEqual(price_map.posture, "near_base_target")
        self.assertEqual(price_map.confidence, "medium")
        self.assertEqual(base.method, "deerflow_price_analysis")
        self.assertEqual(base.target_mid, 122)
        self.assertIn("deerflow:tenx-price-map-us-nvda-2026-04-20", price_map.evidence_refs)
        self.assertIn("deerflow", price_map.explanation)

    def test_schema_sql_contains_price_map_tables(self) -> None:
        self.assertIn("CREATE TABLE IF NOT EXISTS dwd.security_price_technical_daily", pipeline.SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS dws.security_target_range_daily", pipeline.SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS dws.security_key_level_daily", pipeline.SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS dws.security_scenario_path_daily", pipeline.SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS ads.price_map_current", pipeline.SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS ods.us_analyst_estimate_raw", pipeline.SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS ods.us_earnings_calendar_raw", pipeline.SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS dwd.security_estimate_current", pipeline.SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS dwd.security_earnings_calendar_current", pipeline.SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS ads.price_map_history_daily", pipeline.SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS ads.price_map_hit_review_daily", pipeline.SCHEMA_SQL)


if __name__ == "__main__":
    unittest.main()
