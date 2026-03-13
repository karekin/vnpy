from __future__ import annotations

from pathlib import Path

from vnpy.web.runtime_config import load_cb_quant_runtime_config


def test_load_cb_quant_runtime_config_should_read_toml_file(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "cb_quant.toml"
    config_path.write_text(
        "\n".join(
            [
                "[parallel]",
                "job_workers = 9",
                "optimize_task_workers = 7",
                'optimize_eval_mode = "process"',
                "optimize_eval_workers = 3",
                "optimize_shard_workers = 18",
                "optimize_shard_size = 80",
                "optimize_min_shards_per_task = 8",
                "",
                "[screening]",
                "stage1_threshold = 600",
                "stage1_min_windows = 2",
                "",
                "[bundling]",
                "small_task_threshold = 320",
                "target_combinations = 900",
                "max_tasks_per_bundle = 4",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CBQ_RUNTIME_CONFIG", str(config_path))

    config = load_cb_quant_runtime_config()

    assert config.config_path == str(config_path)
    assert config.parallel.job_workers == 9
    assert config.parallel.optimize_task_workers == 7
    assert config.parallel.optimize_eval_mode == "process"
    assert config.parallel.optimize_eval_workers == 3
    assert config.parallel.optimize_shard_workers == 18
    assert config.parallel.optimize_shard_size == 80
    assert config.parallel.optimize_min_shards_per_task == 8
    assert config.screening.stage1_threshold == 600
    assert config.screening.stage1_min_windows == 2
    assert config.bundling.small_task_threshold == 320
    assert config.bundling.target_combinations == 900
    assert config.bundling.max_tasks_per_bundle == 4


def test_load_cb_quant_runtime_config_should_allow_env_override(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "cb_quant.toml"
    config_path.write_text(
        "\n".join(
            [
                "[parallel]",
                "optimize_eval_mode = \"thread\"",
                "optimize_eval_workers = 1",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CBQ_RUNTIME_CONFIG", str(config_path))
    monkeypatch.setenv("CBQ_OPT_EVAL_MODE", "process")
    monkeypatch.setenv("CBQ_OPT_WORKERS", "4")

    config = load_cb_quant_runtime_config()

    assert config.parallel.optimize_eval_mode == "process"
    assert config.parallel.optimize_eval_workers == 4
