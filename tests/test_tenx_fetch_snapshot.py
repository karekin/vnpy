from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.tenx_hunter import fetch_real_snapshot


class TenxFetchSnapshotTests(unittest.TestCase):
    def test_write_bundle_snapshot_supports_yfinance_sec_mode_without_optional_keys(self) -> None:
        bundle = SimpleNamespace(
            securities=[
                SimpleNamespace(
                    symbol="DEMO",
                    company_name="Demo Corp",
                    exchange_name="XNAS",
                    cik="0000000001",
                    currency="USD",
                    listing_status="active",
                    sector="SOFTWARE",
                    industry="SOFTWARE",
                    source_vendor="sec+yfinance",
                )
            ],
            security_themes=[{"security_id": "1", "theme_id": "cloud", "source_note": "seed"}],
            prices=[
                SimpleNamespace(
                    symbol="DEMO",
                    trade_date="2026-04-11",
                    open=10.0,
                    high=11.0,
                    low=9.8,
                    close=10.8,
                    adj_close=10.8,
                    volume=1000,
                    source_vendor="yfinance",
                )
            ],
            financials=[],
            filings=[],
            news=[],
            watch_actions=[{"action_id": "watch-1", "user_id": "demo_user", "symbol": "DEMO", "action": "watch", "action_time": "2026-04-11T00:00:00Z"}],
        )

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            with patch.object(fetch_real_snapshot, "OUT_DIR", out_dir):
                rc = fetch_real_snapshot.write_bundle_snapshot(
                    bundle,
                    symbols=["DEMO"],
                    start_date="2026-04-01",
                    end_date="2026-04-11",
                    mode="yfinance+sec",
                )

            self.assertEqual(rc, 0)
            self.assertTrue((out_dir / "securities.csv").exists())
            self.assertTrue((out_dir / "price_daily.csv").exists())
            self.assertTrue((out_dir / "manifest.json").exists())
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["mode"], "yfinance+sec")


if __name__ == "__main__":
    unittest.main()
