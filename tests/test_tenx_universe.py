from __future__ import annotations

import unittest
from pathlib import Path

from vnpy.web.tenx_hunter.universe import apply_symbol_overrides, load_universe_file


ROOT = Path(__file__).resolve().parents[1]


class TenxUniverseTests(unittest.TestCase):
    def test_json_universe_file_loads_bucket_metadata(self) -> None:
        universe = load_universe_file(
            ROOT / "config" / "tenx_hunter" / "universes" / "us_growth_hunt_v1.json",
            source="preset:us_growth_hunt_v1",
        )

        self.assertEqual(universe.strategy, "bucketed-growth-research")
        self.assertGreater(len(universe.buckets), 1)
        self.assertIn("NVDA", universe.symbols)

    def test_symbol_overrides_can_add_and_exclude(self) -> None:
        universe = load_universe_file(
            ROOT / "config" / "tenx_hunter" / "universes" / "us_growth_hunt_v1.json",
            source="preset:us_growth_hunt_v1",
        )
        overridden = apply_symbol_overrides(
            universe,
            include_symbols=["HUBS"],
            exclude_symbols=["NVDA"],
        )

        self.assertIn("HUBS", overridden.symbols)
        self.assertNotIn("NVDA", overridden.symbols)
        self.assertTrue(any(bucket.slug == "manual-overrides" for bucket in overridden.buckets))


if __name__ == "__main__":
    unittest.main()
