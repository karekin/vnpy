from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib
from typing import Any, Literal


OptimizeEvalMode = Literal["thread", "process"]


@dataclass(frozen=True)
class CbQuantParallelConfig:
    job_workers: int
    optimize_task_workers: int
    optimize_shard_workers: int
    optimize_eval_workers: int
    optimize_eval_mode: OptimizeEvalMode
    optimize_shard_size: int
    optimize_min_shards_per_task: int


@dataclass(frozen=True)
class CbQuantScreeningConfig:
    stage1_threshold: int
    stage1_min_windows: int
    stage1_ratio: float
    stage1_min: int
    stage1_max: int
    shortlist_multiplier: int
    shortlist_min: int
    shortlist_max: int


@dataclass(frozen=True)
class CbQuantProfilingConfig:
    output_dir: str


@dataclass(frozen=True)
class CbQuantBundlingConfig:
    small_task_threshold: int
    target_combinations: int
    max_tasks_per_bundle: int


@dataclass(frozen=True)
class CbQuantRuntimeConfig:
    config_path: str | None
    parallel: CbQuantParallelConfig
    screening: CbQuantScreeningConfig
    bundling: CbQuantBundlingConfig
    profiling: CbQuantProfilingConfig


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _cpu_count() -> int:
    return max(1, int(os.cpu_count() or 8))


def _parse_int(value: Any, default: int, *, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(low, min(high, parsed))


def _parse_float(value: Any, default: float, *, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return max(low, min(high, parsed))


def _parse_mode(value: Any, default: OptimizeEvalMode) -> OptimizeEvalMode:
    text = str(value or "").strip().lower()
    if text in {"thread", "threads"}:
        return "thread"
    if text in {"process", "processes", "proc"}:
        return "process"
    return default


def _resolve_config_path() -> Path | None:
    explicit = os.getenv("CBQ_RUNTIME_CONFIG", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = (_project_root() / path).resolve()
        return path

    default_path = _project_root() / "config" / "cb_quant.toml"
    if default_path.exists():
        return default_path
    return None


def _load_toml_payload(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    if isinstance(raw.get("cb_quant"), dict):
        return dict(raw["cb_quant"])
    return raw


def load_cb_quant_runtime_config() -> CbQuantRuntimeConfig:
    cpu_count = _cpu_count()
    config_path = _resolve_config_path()
    payload = _load_toml_payload(config_path)
    parallel_payload = dict(payload.get("parallel") or {})
    screening_payload = dict(payload.get("screening") or {})
    bundling_payload = dict(payload.get("bundling") or {})
    profiling_payload = dict(payload.get("profiling") or {})

    job_workers = _parse_int(
        os.getenv("CBQ_JOB_WORKERS", parallel_payload.get("job_workers", cpu_count)),
        cpu_count,
        low=1,
        high=64,
    )
    optimize_task_workers = _parse_int(
        os.getenv("CBQ_OPT_TASK_WORKERS", parallel_payload.get("optimize_task_workers", min(8, cpu_count))),
        min(8, cpu_count),
        low=1,
        high=64,
    )
    optimize_shard_workers = _parse_int(
        os.getenv(
            "CBQ_OPT_SHARD_WORKERS",
            parallel_payload.get("optimize_shard_workers", min(16, cpu_count + max(2, cpu_count // 3))),
        ),
        min(16, cpu_count + max(2, cpu_count // 3)),
        low=1,
        high=128,
    )
    optimize_eval_workers = _parse_int(
        os.getenv("CBQ_OPT_WORKERS", parallel_payload.get("optimize_eval_workers", max(1, min(2, cpu_count // 6 or 1)))),
        max(1, min(2, cpu_count // 6 or 1)),
        low=1,
        high=32,
    )
    optimize_eval_mode = _parse_mode(
        os.getenv("CBQ_OPT_EVAL_MODE", parallel_payload.get("optimize_eval_mode", "process")),
        "process",
    )
    optimize_shard_size = _parse_int(
        os.getenv("CBQ_OPT_SHARD_SIZE", parallel_payload.get("optimize_shard_size", 120)),
        120,
        low=20,
        high=100_000,
    )
    optimize_min_shards_per_task = _parse_int(
        os.getenv("CBQ_OPT_MIN_SHARDS_PER_TASK", parallel_payload.get("optimize_min_shards_per_task", min(8, cpu_count))),
        min(8, cpu_count),
        low=1,
        high=64,
    )

    stage1_threshold = _parse_int(
        os.getenv("CBQ_OPT_STAGE1_THRESHOLD", screening_payload.get("stage1_threshold", 500)),
        500,
        low=10,
        high=5_000_000,
    )
    stage1_min_windows = _parse_int(
        os.getenv("CBQ_OPT_STAGE1_MIN_WINDOWS", screening_payload.get("stage1_min_windows", 1)),
        1,
        low=1,
        high=16,
    )
    stage1_ratio = _parse_float(
        os.getenv("CBQ_OPT_STAGE1_RATIO", screening_payload.get("stage1_ratio", 0.1)),
        0.1,
        low=0.01,
        high=1.0,
    )
    stage1_min = _parse_int(
        os.getenv("CBQ_OPT_STAGE1_MIN", screening_payload.get("stage1_min", 400)),
        400,
        low=20,
        high=1_000_000,
    )
    stage1_max = _parse_int(
        os.getenv("CBQ_OPT_STAGE1_MAX", screening_payload.get("stage1_max", 12_000)),
        12_000,
        low=50,
        high=2_000_000,
    )
    shortlist_multiplier = _parse_int(
        os.getenv("CBQ_OPT_SHORTLIST_MULTIPLIER", screening_payload.get("shortlist_multiplier", 8)),
        8,
        low=2,
        high=50,
    )
    shortlist_min = _parse_int(
        os.getenv("CBQ_OPT_SHORTLIST_MIN", screening_payload.get("shortlist_min", 120)),
        120,
        low=20,
        high=20_000,
    )
    shortlist_max = _parse_int(
        os.getenv("CBQ_OPT_SHORTLIST_MAX", screening_payload.get("shortlist_max", 3_000)),
        3_000,
        low=50,
        high=100_000,
    )
    small_task_threshold = _parse_int(
        os.getenv("CBQ_OPT_BUNDLE_SMALL_TASK_THRESHOLD", bundling_payload.get("small_task_threshold", 400)),
        400,
        low=1,
        high=5_000_000,
    )
    target_combinations = _parse_int(
        os.getenv("CBQ_OPT_BUNDLE_TARGET_COMBINATIONS", bundling_payload.get("target_combinations", 1_200)),
        1_200,
        low=1,
        high=5_000_000,
    )
    max_tasks_per_bundle = _parse_int(
        os.getenv("CBQ_OPT_BUNDLE_MAX_TASKS", bundling_payload.get("max_tasks_per_bundle", 6)),
        6,
        low=1,
        high=128,
    )

    output_dir = str(profiling_payload.get("output_dir", "out/cb_quant/profiles")).strip() or "out/cb_quant/profiles"

    return CbQuantRuntimeConfig(
        config_path=str(config_path) if config_path is not None else None,
        parallel=CbQuantParallelConfig(
            job_workers=job_workers,
            optimize_task_workers=optimize_task_workers,
            optimize_shard_workers=optimize_shard_workers,
            optimize_eval_workers=optimize_eval_workers,
            optimize_eval_mode=optimize_eval_mode,
            optimize_shard_size=optimize_shard_size,
            optimize_min_shards_per_task=optimize_min_shards_per_task,
        ),
        screening=CbQuantScreeningConfig(
            stage1_threshold=stage1_threshold,
            stage1_min_windows=stage1_min_windows,
            stage1_ratio=stage1_ratio,
            stage1_min=stage1_min,
            stage1_max=stage1_max,
            shortlist_multiplier=shortlist_multiplier,
            shortlist_min=shortlist_min,
            shortlist_max=shortlist_max,
        ),
        bundling=CbQuantBundlingConfig(
            small_task_threshold=small_task_threshold,
            target_combinations=target_combinations,
            max_tasks_per_bundle=max_tasks_per_bundle,
        ),
        profiling=CbQuantProfilingConfig(output_dir=output_dir),
    )
