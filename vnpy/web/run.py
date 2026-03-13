from __future__ import annotations

import argparse
import os
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run VN.PY Web API with CB Quant runtime config.")
    parser.add_argument("--host", default=os.getenv("VNPY_WEB_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("VNPY_WEB_PORT", "8000")))
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("VNPY_WEB_RELOAD", "").strip().lower() in {"1", "true", "yes", "y", "on"},
    )
    parser.add_argument(
        "--cbq-config",
        default=os.getenv("CBQ_RUNTIME_CONFIG", "").strip(),
        help="Path to cb_quant runtime TOML config.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.cbq_config:
        config_path = Path(args.cbq_config).expanduser()
        os.environ["CBQ_RUNTIME_CONFIG"] = str(config_path)

    import uvicorn
    from vnpy.web.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port, reload=bool(args.reload))


if __name__ == "__main__":
    main()
