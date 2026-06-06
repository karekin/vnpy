from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from .config import load_settings
from .pipeline import bootstrap_real_data, bootstrap_sample_data, run_all


def main() -> None:
    settings = load_settings()
    interval_seconds = int(os.getenv("PIPELINE_INTERVAL_SECONDS", "43200"))
    while True:
        started_at = datetime.now(timezone.utc).isoformat()
        print(f"[{started_at}] scheduler run started ({settings.scheduler_bootstrap_mode})")
        if settings.scheduler_bootstrap_mode == "real":
            bootstrap_real_data(settings, reset=True, market=settings.default_market)
        else:
            bootstrap_sample_data(settings, reset=True)
        run_all(settings)
        try:
            from vnpy.web.services.tenx_hunter_service import TenxHunterService

            TenxHunterService().refresh_event_monitor(settings.default_market, fetch_remote=True)
        except Exception as exc:
            print(f"[{datetime.now(timezone.utc).isoformat()}] event monitor refresh failed: {exc}")
        finished_at = datetime.now(timezone.utc).isoformat()
        print(f"[{finished_at}] scheduler run finished; sleeping {interval_seconds}s")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
