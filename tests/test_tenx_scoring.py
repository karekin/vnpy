import unittest

from vnpy.web.tenx_hunter.real_sources import build_financial_snapshot_from_sec, infer_theme_ids, normalize_symbols
from vnpy.web.tenx_hunter.scoring import (
    build_candidate_explanation,
    build_score_components,
    classify_stage,
    growth_score,
    risk_score,
    size_score,
    valuation_score,
)
from vnpy.web.tenx_hunter.signals import extract_signal


class ScoringTests(unittest.TestCase):
    def test_growth_score_rewards_growth(self) -> None:
        self.assertGreater(growth_score(0.60), growth_score(0.10))

    def test_valuation_score_penalizes_expensive_names(self) -> None:
        self.assertGreater(valuation_score(6.0), valuation_score(15.0))

    def test_size_score_prefers_midcaps_over_megacaps(self) -> None:
        self.assertGreater(size_score(15_000_000_000), size_score(500_000_000_000))

    def test_risk_score_penalizes_negative_events(self) -> None:
        self.assertGreater(risk_score(0, 0), risk_score(2, 1))

    def test_build_score_components_has_reasonable_total(self) -> None:
        components = build_score_components(
            revenue_yoy=0.55,
            op_margin=0.21,
            fcf_margin=0.18,
            return_5d=0.08,
            distance_from_high=-0.06,
            ps_ttm=12.0,
            market_cap=25_000_000_000,
            risk_count=1,
            negative_event_count=0,
            theme_count=2,
            positive_signal_count=2,
        )
        self.assertGreaterEqual(components.total, 0)
        self.assertLessEqual(components.total, 100)
        self.assertGreater(components.growth, 50)

    def test_classify_stage_marks_large_expensive_names_as_crowded(self) -> None:
        components = build_score_components(
            revenue_yoy=0.62,
            op_margin=0.28,
            fcf_margin=0.22,
            return_5d=0.12,
            distance_from_high=-0.01,
            ps_ttm=22.0,
            market_cap=800_000_000_000,
            risk_count=1,
            negative_event_count=0,
            theme_count=2,
            positive_signal_count=4,
        )
        stage = classify_stage(
            components,
            ps_ttm=22.0,
            market_cap=800_000_000_000,
            return_5d=0.12,
            distance_from_high=-0.01,
        )
        self.assertEqual(stage, "crowded")

    def test_candidate_explanation_calls_out_crowding_for_hot_large_names(self) -> None:
        components = build_score_components(
            revenue_yoy=0.62,
            op_margin=0.28,
            fcf_margin=0.22,
            return_5d=0.12,
            distance_from_high=-0.01,
            ps_ttm=22.0,
            market_cap=800_000_000_000,
            risk_count=1,
            negative_event_count=0,
            theme_count=2,
            positive_signal_count=4,
        )
        explanation = build_candidate_explanation(
            "crowded",
            components,
            ps_ttm=22.0,
            market_cap=800_000_000_000,
            return_5d=0.12,
            distance_from_high=-0.01,
        )
        self.assertIn("主候选池", explanation.selection_reason)
        self.assertIn("crowded", explanation.stage_reason)
        self.assertEqual(len(explanation.score_drivers), 3)



    def test_build_financial_snapshot_from_sec(self) -> None:
        payload = {
            "entityName": "Demo Corp",
            "facts": {
                "us-gaap": {
                    "Revenues": {"units": {"USD": [
                        {"val": 1200, "end": "2025-12-31", "fy": 2025, "fp": "Q4", "form": "10-K", "filed": "2026-02-01"},
                        {"val": 900, "end": "2024-12-31", "fy": 2024, "fp": "Q4", "form": "10-K", "filed": "2025-02-01"}
                    ]}},
                    "GrossProfit": {"units": {"USD": [{"val": 720, "end": "2025-12-31", "fy": 2025, "fp": "Q4", "form": "10-K", "filed": "2026-02-01"}]}},
                    "OperatingIncomeLoss": {"units": {"USD": [{"val": 240, "end": "2025-12-31", "fy": 2025, "fp": "Q4", "form": "10-K", "filed": "2026-02-01"}]}},
                    "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [{"val": 300, "end": "2025-12-31", "fy": 2025, "fp": "Q4", "form": "10-K", "filed": "2026-02-01"}]}},
                    "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [{"val": -60, "end": "2025-12-31", "fy": 2025, "fp": "Q4", "form": "10-K", "filed": "2026-02-01"}]}},
                    "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [{"val": 500, "end": "2025-12-31", "fy": 2025, "fp": "Q4", "form": "10-K", "filed": "2026-02-01"}]}},
                    "LongTermDebt": {"units": {"USD": [{"val": 100, "end": "2025-12-31", "fy": 2025, "fp": "Q4", "form": "10-K", "filed": "2026-02-01"}]}}
                },
                "dei": {
                    "EntityCommonStockSharesOutstanding": {"units": {"shares": [{"val": 10, "end": "2025-12-31", "fy": 2025, "fp": "Q4", "form": "10-K", "filed": "2026-02-01"}]}}
                }
            }
        }
        snapshot = build_financial_snapshot_from_sec("DEMO", payload)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.report_period, "2025-12-31")
        self.assertEqual(snapshot.fiscal_year, 2025)
        self.assertEqual(snapshot.period_type, "quarterly")
        self.assertEqual(snapshot.filed_date, "2026-02-01")
        self.assertEqual(snapshot.source_filing_id, None)
        self.assertEqual(snapshot.form_type, "10-K")
        self.assertEqual(snapshot.currency, "USD")
        self.assertEqual(snapshot.data_quality_flag, "parsed")
        self.assertAlmostEqual(snapshot.revenue_yoy or 0, (1200 - 900) / 900, places=6)
        self.assertAlmostEqual(snapshot.gross_margin or 0, 0.6, places=6)
        self.assertAlmostEqual(snapshot.op_margin or 0, 0.2, places=6)

class SignalTests(unittest.TestCase):
    def test_extract_signal_detects_theme_and_risk(self) -> None:
        signal = extract_signal(
            "Security breach triggered regulation risk, but cloud partnership demand remains strong."
        )
        self.assertIn("cloud", signal.theme_tags)
        self.assertIn("security", signal.risk_tags)
        self.assertIn(signal.sentiment, {"negative", "neutral"})


class RealSourceHelperTests(unittest.TestCase):
    def test_normalize_symbols(self) -> None:
        self.assertEqual(normalize_symbols(" nvda, snow ,,crwd "), ["NVDA", "SNOW", "CRWD"])

    def test_infer_theme_ids(self) -> None:
        themes = infer_theme_ids("AI data center platform", "cloud security")
        self.assertIn("ai_infra", themes)
        self.assertIn("cloud", themes)


if __name__ == '__main__':
    unittest.main()
