from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from .real_sources import default_date_range
from .universe import ResolvedUniverse, apply_symbol_overrides, load_universe_file, parse_symbol_text


DEFAULT_REAL_UNIVERSE_PRESET = "us_growth_hunt_v1"
DEFAULT_CN_UNIVERSE_PRESET = "a_share_growth_hunt_v1"


@dataclass(frozen=True)
class Settings:
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    sample_data_dir: str
    sec_user_agent: str
    polygon_api_key: str | None
    real_symbols: list[str]
    real_symbols_source: str
    real_universe_name: str
    real_universe_strategy: str
    real_universe_description: str
    real_universe_buckets: list[dict[str, object]]
    price_provider: str
    price_start_date: str
    price_end_date: str
    include_yfinance_supplement: bool
    institutional_manager_symbols: list[str]
    scheduler_bootstrap_mode: str
    default_market: str
    market_universes: dict[str, ResolvedUniverse]

    @property
    def pg_dsn(self) -> str:
        return (
            f"host={self.pg_host} port={self.pg_port} dbname={self.pg_database} "
            f"user={self.pg_user} password={self.pg_password}"
        )


def _as_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _local_env_file() -> Path:
    return _repo_root() / "tools" / "tenx_hunter" / ".env.local"


def _load_local_env_defaults() -> None:
    path = _local_env_file()
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _default_sample_data_dir() -> Path:
    return _repo_root() / "examples" / "tenx_hunter_data_pipeline" / "sample_data"


def _default_universe_dir() -> Path:
    return _repo_root() / "config" / "tenx_hunter" / "universes"


def _parse_symbols(raw: str) -> list[str]:
    return parse_symbol_text(raw.replace(",", "\n"))


def _read_symbol_file(path: Path) -> list[str]:
    symbols: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        symbols.extend(_parse_symbols(line.replace(" ", "")))
    return list(dict.fromkeys(symbols))


def _resolve_symbol_file(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return (_repo_root() / path).resolve()


def _humanize_universe_name(source: str) -> str:
    if source.startswith("preset:"):
        preset = source.split(":", 1)[1]
        return preset.replace("_", " ").replace(" v", " V").title().replace("V1", "v1")
    if source.startswith("file:"):
        return "Custom Research Universe"
    if source.startswith("env:"):
        return "Env Research Universe"
    return "US Growth Hunt"


def _serialize_buckets(universe: ResolvedUniverse) -> list[dict[str, object]]:
    return [
        {
            "slug": bucket.slug,
            "label": bucket.label,
            "rationale": bucket.rationale,
            "symbols": bucket.symbols,
        }
        for bucket in universe.buckets
    ]


def _normalize_market(value: str | None) -> str:
    lowered = (value or "CN").strip().upper()
    return lowered if lowered in {"CN", "US"} else "CN"


def _resolve_real_universe() -> tuple[ResolvedUniverse, str]:
    raw_symbols = os.getenv("REAL_SYMBOLS")
    if raw_symbols:
        universe = ResolvedUniverse(
            name="Env Research Universe",
            strategy="env-symbol-list",
            description="Universe assembled directly from REAL_SYMBOLS.",
            symbols=_parse_symbols(raw_symbols),
            buckets=[],
            source="env:REAL_SYMBOLS",
        )
        return apply_symbol_overrides(
            universe,
            include_symbols=_parse_symbols(os.getenv("REAL_UNIVERSE_INCLUDE", "")),
            exclude_symbols=_parse_symbols(os.getenv("REAL_UNIVERSE_EXCLUDE", "")),
        ), "env:REAL_SYMBOLS"

    raw_file = os.getenv("REAL_SYMBOLS_FILE")
    if raw_file:
        path = _resolve_symbol_file(raw_file)
        if path.exists():
            universe = load_universe_file(path, source=f"file:{path.name}")
            return apply_symbol_overrides(
                universe,
                include_symbols=_parse_symbols(os.getenv("REAL_UNIVERSE_INCLUDE", "")),
                exclude_symbols=_parse_symbols(os.getenv("REAL_UNIVERSE_EXCLUDE", "")),
            ), f"file:{path.name}"

    preset = (os.getenv("REAL_UNIVERSE_PRESET") or DEFAULT_REAL_UNIVERSE_PRESET).strip() or DEFAULT_REAL_UNIVERSE_PRESET
    preset_dir = _default_universe_dir()
    for candidate in (preset_dir / f"{preset}.json", preset_dir / f"{preset}.txt"):
        if candidate.exists():
            universe = load_universe_file(candidate, source=f"preset:{preset}")
            return apply_symbol_overrides(
                universe,
                include_symbols=_parse_symbols(os.getenv("REAL_UNIVERSE_INCLUDE", "")),
                exclude_symbols=_parse_symbols(os.getenv("REAL_UNIVERSE_EXCLUDE", "")),
            ), f"preset:{preset}"

    fallback = ResolvedUniverse(
        name="Demo Universe",
        strategy="fallback",
        description="Fallback demo universe used when no preset can be resolved.",
        symbols=["NVDA", "SNOW", "CRWD", "ARM"],
        buckets=[],
        source="fallback:demo",
    )
    return fallback, "fallback:demo"


def _resolve_market_universe(
    *,
    market: str,
    env_prefix: str,
    default_preset: str,
    fallback_name: str,
    fallback_strategy: str,
    fallback_description: str,
    fallback_symbols: list[str],
) -> tuple[ResolvedUniverse, str]:
    raw_symbols = os.getenv(f"{env_prefix}_SYMBOLS")
    if raw_symbols:
        universe = ResolvedUniverse(
            name=f"{market} Env Research Universe",
            strategy="env-symbol-list",
            description=f"Universe assembled directly from {env_prefix}_SYMBOLS.",
            symbols=_parse_symbols(raw_symbols),
            buckets=[],
            source=f"env:{env_prefix}_SYMBOLS",
        )
        return apply_symbol_overrides(
            universe,
            include_symbols=_parse_symbols(os.getenv(f"{env_prefix}_INCLUDE", "")),
            exclude_symbols=_parse_symbols(os.getenv(f"{env_prefix}_EXCLUDE", "")),
        ), f"env:{env_prefix}_SYMBOLS"

    raw_file = os.getenv(f"{env_prefix}_FILE")
    if raw_file:
        path = _resolve_symbol_file(raw_file)
        if path.exists():
            universe = load_universe_file(path, source=f"file:{path.name}")
            return apply_symbol_overrides(
                universe,
                include_symbols=_parse_symbols(os.getenv(f"{env_prefix}_INCLUDE", "")),
                exclude_symbols=_parse_symbols(os.getenv(f"{env_prefix}_EXCLUDE", "")),
            ), f"file:{path.name}"

    preset = (os.getenv(f"{env_prefix}_PRESET") or default_preset).strip() or default_preset
    preset_dir = _default_universe_dir()
    for candidate in (preset_dir / f"{preset}.json", preset_dir / f"{preset}.txt"):
        if candidate.exists():
            universe = load_universe_file(candidate, source=f"preset:{preset}")
            return apply_symbol_overrides(
                universe,
                include_symbols=_parse_symbols(os.getenv(f"{env_prefix}_INCLUDE", "")),
                exclude_symbols=_parse_symbols(os.getenv(f"{env_prefix}_EXCLUDE", "")),
            ), f"preset:{preset}"

    fallback = ResolvedUniverse(
        name=fallback_name,
        strategy=fallback_strategy,
        description=fallback_description,
        symbols=fallback_symbols,
        buckets=[],
        source=f"fallback:{market.lower()}",
    )
    return fallback, f"fallback:{market.lower()}"


def load_settings() -> Settings:
    _load_local_env_defaults()
    default_start, default_end = default_date_range()
    universe, symbols_source = _resolve_real_universe()
    cn_universe, _cn_symbols_source = _resolve_market_universe(
        market="CN",
        env_prefix="TENX_CN_UNIVERSE",
        default_preset=DEFAULT_CN_UNIVERSE_PRESET,
        fallback_name="A Share Growth Hunt",
        fallback_strategy="fallback-cn",
        fallback_description="Fallback CN universe used when no preset can be resolved.",
        fallback_symbols=["300308.SZ", "002594.SZ", "300502.SZ", "688041.SH"],
    )
    us_universe, _us_symbols_source = _resolve_market_universe(
        market="US",
        env_prefix="TENX_US_UNIVERSE",
        default_preset=DEFAULT_REAL_UNIVERSE_PRESET,
        fallback_name="US Growth Hunt",
        fallback_strategy="fallback-us",
        fallback_description="Fallback US universe used when no preset can be resolved.",
        fallback_symbols=["NVDA", "SNOW", "CRWD", "ARM"],
    )
    symbols = universe.symbols
    universe_name = (os.getenv("TENX_UNIVERSE_NAME") or universe.name or _humanize_universe_name(symbols_source)).strip()
    return Settings(
        pg_host=os.getenv("PGHOST", "localhost"),
        pg_port=int(os.getenv("PGPORT", "5432")),
        pg_database=os.getenv("PGDATABASE", "tenx"),
        pg_user=os.getenv("PGUSER", "tenx"),
        pg_password=os.getenv("PGPASSWORD", "tenx"),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        minio_bucket=os.getenv("MINIO_BUCKET", "tenx-ods"),
        sample_data_dir=os.getenv("SAMPLE_DATA_DIR", str(_default_sample_data_dir())),
        sec_user_agent=os.getenv("SEC_USER_AGENT") or "TenX Hunter Demo contact@tenxhunter.local",
        polygon_api_key=os.getenv("POLYGON_API_KEY") or None,
        real_symbols=symbols,
        real_symbols_source=symbols_source,
        real_universe_name=universe_name,
        real_universe_strategy=universe.strategy,
        real_universe_description=universe.description,
        real_universe_buckets=_serialize_buckets(universe),
        price_provider=(os.getenv("PRICE_PROVIDER") or "yfinance").strip().lower(),
        price_start_date=os.getenv("PRICE_START_DATE") or default_start,
        price_end_date=os.getenv("PRICE_END_DATE") or default_end,
        include_yfinance_supplement=_as_bool(os.getenv("INCLUDE_YFINANCE_SUPPLEMENT"), default=True),
        institutional_manager_symbols=_parse_symbols(os.getenv("TENX_INSTITUTIONAL_MANAGER_SYMBOLS") or "NVDA"),
        scheduler_bootstrap_mode=(os.getenv("PIPELINE_BOOTSTRAP_MODE") or "real").strip().lower(),
        default_market=_normalize_market(os.getenv("TENX_DEFAULT_MARKET")),
        market_universes={
            "CN": cn_universe,
            "US": us_universe,
        },
    )
