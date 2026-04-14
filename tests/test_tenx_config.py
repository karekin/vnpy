from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy.web.tenx_hunter.config import _load_local_env_defaults, load_settings


class TenxConfigTests(unittest.TestCase):
    def test_default_settings_load_preset_universe(self) -> None:
        with patch.dict(
            os.environ,
            {
                "REAL_SYMBOLS": "",
                "REAL_SYMBOLS_FILE": "",
                "REAL_UNIVERSE_PRESET": "us_growth_hunt_v1",
                "TENX_UNIVERSE_NAME": "",
            },
            clear=False,
        ):
            settings = load_settings()

        self.assertGreater(len(settings.real_symbols), 4)
        self.assertTrue(settings.real_symbols_source.startswith("preset:"))
        self.assertIn("Growth", settings.real_universe_name)
        self.assertEqual(settings.real_universe_strategy, "bucketed-growth-research")
        self.assertGreater(len(settings.real_universe_buckets), 1)

    def test_real_symbols_env_override_takes_priority(self) -> None:
        with patch.dict(
            os.environ,
            {
                "REAL_SYMBOLS": "nvda, amd , net",
                "REAL_UNIVERSE_PRESET": "us_growth_hunt_v1",
            },
            clear=False,
        ):
            settings = load_settings()

        self.assertEqual(settings.real_symbols, ["NVDA", "AMD", "NET"])
        self.assertEqual(settings.real_symbols_source, "env:REAL_SYMBOLS")

    def test_default_bootstrap_mode_prefers_real_pipeline(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PIPELINE_BOOTSTRAP_MODE": "",
            },
            clear=False,
        ):
            settings = load_settings()

        self.assertEqual(settings.scheduler_bootstrap_mode, "real")

    def test_local_env_file_should_supply_defaults_without_overriding_existing_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_file = root / "tools" / "tenx_hunter" / ".env.local"
            env_file.parent.mkdir(parents=True, exist_ok=True)
            env_file.write_text(
                "\n".join(
                    [
                        "PGHOST=localhost",
                        "PGPORT=54329",
                        "SEC_USER_AGENT=TenX Hunter 445923692@qq.com",
                    ]
                ),
                encoding="utf-8",
            )
            with patch("vnpy.web.tenx_hunter.config._repo_root", return_value=root):
                with patch.dict(os.environ, {"PGHOST": "db.internal"}, clear=False):
                    _load_local_env_defaults()

                    self.assertEqual(os.environ["PGHOST"], "db.internal")
                    self.assertEqual(os.environ["PGPORT"], "54329")
                    self.assertEqual(os.environ["SEC_USER_AGENT"], "TenX Hunter 445923692@qq.com")


if __name__ == "__main__":
    unittest.main()
