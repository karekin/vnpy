from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class UniverseBucket:
    slug: str
    label: str
    rationale: str
    symbols: list[str]


@dataclass(frozen=True)
class ResolvedUniverse:
    name: str
    strategy: str
    description: str
    symbols: list[str]
    buckets: list[UniverseBucket]
    source: str


def _dedupe(symbols: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for symbol in symbols:
        cleaned = symbol.strip().upper()
        if cleaned:
            seen.setdefault(cleaned, None)
    return list(seen.keys())


def parse_symbol_text(raw: str) -> list[str]:
    symbols: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        symbols.extend(part.strip().upper() for part in stripped.split(",") if part.strip())
    return _dedupe(symbols)


def _bucket_from_payload(payload: dict[str, object]) -> UniverseBucket:
    return UniverseBucket(
        slug=str(payload.get("slug") or "bucket"),
        label=str(payload.get("label") or payload.get("slug") or "Bucket"),
        rationale=str(payload.get("rationale") or ""),
        symbols=_dedupe([str(item) for item in payload.get("symbols", []) or []]),
    )


def load_universe_file(path: Path, *, source: str) -> ResolvedUniverse:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        buckets = [_bucket_from_payload(item) for item in payload.get("buckets", []) or []]
        root_symbols = _dedupe([str(item) for item in payload.get("symbols", []) or []])
        bucket_symbols = [symbol for bucket in buckets for symbol in bucket.symbols]
        symbols = _dedupe(root_symbols + bucket_symbols)
        if not buckets:
            buckets = [
                UniverseBucket(
                    slug="core",
                    label="Core Universe",
                    rationale=str(payload.get("description") or ""),
                    symbols=symbols,
                )
            ]
        return ResolvedUniverse(
            name=str(payload.get("name") or path.stem),
            strategy=str(payload.get("strategy") or "preset-buckets"),
            description=str(payload.get("description") or ""),
            symbols=symbols,
            buckets=buckets,
            source=source,
        )

    symbols = parse_symbol_text(path.read_text(encoding="utf-8"))
    return ResolvedUniverse(
        name=path.stem.replace("_", " ").title(),
        strategy="flat-list",
        description="Flat symbol list universe.",
        symbols=symbols,
        buckets=[
            UniverseBucket(
                slug="core",
                label="Core Universe",
                rationale="Loaded from a flat symbol list.",
                symbols=symbols,
            )
        ],
        source=source,
    )


def apply_symbol_overrides(
    universe: ResolvedUniverse,
    *,
    include_symbols: list[str] | None = None,
    exclude_symbols: list[str] | None = None,
) -> ResolvedUniverse:
    includes = _dedupe(include_symbols or [])
    excludes = set(_dedupe(exclude_symbols or []))
    merged_symbols = [symbol for symbol in _dedupe(universe.symbols + includes) if symbol not in excludes]

    updated_buckets: list[UniverseBucket] = []
    for bucket in universe.buckets:
        kept = [symbol for symbol in bucket.symbols if symbol not in excludes]
        if kept:
            updated_buckets.append(
                UniverseBucket(
                    slug=bucket.slug,
                    label=bucket.label,
                    rationale=bucket.rationale,
                    symbols=kept,
                )
            )

    extra_symbols = [symbol for symbol in includes if symbol not in {item for bucket in updated_buckets for item in bucket.symbols}]
    if extra_symbols:
        updated_buckets.append(
            UniverseBucket(
                slug="manual-overrides",
                label="Manual Overrides",
                rationale="Extra symbols injected through environment overrides.",
                symbols=extra_symbols,
            )
        )

    return ResolvedUniverse(
        name=universe.name,
        strategy=universe.strategy,
        description=universe.description,
        symbols=merged_symbols,
        buckets=updated_buckets or universe.buckets,
        source=universe.source,
    )
