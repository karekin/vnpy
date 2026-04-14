# TenX Hunter 数据链路迁移说明

TenX Hunter 数据链路后端已经迁入 `vnpy` 仓库，并按前后端现有结构拆分。

## 落位

- 前端：`frontend/src/app/(admin)/tenx-hunter/` 与 `frontend/src/components/tenx-hunter/`
- 后端模块：`vnpy/web/tenx_hunter/`
- 测试：`tests/test_tenx_*.py`
- 工具脚本：`tools/tenx_hunter/`
- 样例与真实快照：`examples/tenx_hunter_data_pipeline/sample_data/`
- Docker 资产：`docker/tenx_hunter/` 与 `compose.tenx-hunter.yaml`

## 快速开始

```bash
cd vnpy

docker compose -f compose.tenx-hunter.yaml up -d postgres minio
docker compose -f compose.tenx-hunter.yaml run --rm pipeline bootstrap-real
docker compose -f compose.tenx-hunter.yaml run --rm pipeline run-all
docker compose -f compose.tenx-hunter.yaml run --rm pipeline show-ads
```

## 真实数据快照

TenX 抓取脚本现在位于：

```bash
python tools/tenx_hunter/fetch_real_snapshot.py
```

默认输出目录：

```text
examples/tenx_hunter_data_pipeline/sample_data/real_snapshot/
```

如果需要同步 ODS schema：

```bash
python tools/tenx_hunter/migrate_ods_schema.py
```

## 常用命令

```bash
docker compose -f compose.tenx-hunter.yaml run --rm pipeline bootstrap
docker compose -f compose.tenx-hunter.yaml run --rm pipeline bootstrap-real
docker compose -f compose.tenx-hunter.yaml run --rm pipeline run-all
docker compose -f compose.tenx-hunter.yaml run --rm pipeline demo
docker compose -f compose.tenx-hunter.yaml run --rm pipeline demo-real
docker compose -f compose.tenx-hunter.yaml run --rm pipeline show-ads
docker compose -f compose.tenx-hunter.yaml run --rm pipeline migrate-ods
docker compose -f compose.tenx-hunter.yaml run --rm pipeline test
```

## 环境变量

可通过 shell 环境变量，或 `tools/tenx_hunter/.env.local` 传入：

```bash
REAL_UNIVERSE_PRESET=us_growth_hunt_v1
# 或者覆盖成你自己的列表：
# REAL_SYMBOLS=NVDA,AMD,ANET,MNDY,NET
# REAL_SYMBOLS_FILE=config/tenx_hunter/universes/us_growth_hunt_v1.txt
# 也可以在 preset 基础上追加 / 排除：
# REAL_UNIVERSE_INCLUDE=HUBS,SHOP
# REAL_UNIVERSE_EXCLUDE=NVDA
TENX_UNIVERSE_NAME='US Growth Hunt'
PRICE_PROVIDER=yfinance
SEC_USER_AGENT='TenX Hunter Demo you@example.com'
POLYGON_API_KEY=
FRED_API_KEY=
PRICE_START_DATE=2026-04-01
PRICE_END_DATE=2026-04-11
INCLUDE_YFINANCE_SUPPLEMENT=true
PIPELINE_BOOTSTRAP_MODE=real
```

Key 说明：

- **先继续迭代代码时，不一定需要你现在就提供 key。**
- 如果走 `PRICE_PROVIDER=yfinance`：
  - **必须**：`SEC_USER_AGENT`（建议真实邮箱/联系方式）
  - **可选**：`POLYGON_API_KEY`
  - **可选**：`FRED_API_KEY`
- 如果走 `PRICE_PROVIDER=polygon`：
  - **必须**：`POLYGON_API_KEY`
  - **仍建议提供**：`SEC_USER_AGENT`

也就是说，**我现在还可以继续在“无 Polygon key”的模式下推进代码和基础 live pipeline**；但如果你希望尽快把新闻、ticker overview、corporate actions、earnings 等 Polygon 侧补全，我接下来就需要你的 `POLYGON_API_KEY`。

## 说明

- 当前迁入的是数据链路后端；`tenx-hunter` 前端页面已经存在于 `frontend/` 下，不需要再从原项目额外迁移。
- 默认研究宇宙已升级为可配置 preset / 文件 / 环境变量，不再被 4 只硬编码股票绑死。
- compose 默认现在直接走 `us_growth_hunt_v1` preset，而不是 4 只 mock/demo symbol。
- `security_analyst_estimate_raw` 已从当前主链路移除；Yahoo 免费 summary 接口在现环境下不稳定，不再作为正式评分输入。
- 旧 `real_snapshot` 里的财务 / 新闻元信息会在 bootstrap 时利用 `sec_companyfacts_raw.json` 与 `polygon_news_raw.json` 自动回填。
- 本地执行完整测试仍依赖 `psycopg` 与 `boto3`；仓库 `pyproject.toml` 已新增 `tenx` 可选依赖声明。
- TenX Docker 镜像使用 `docker/tenx_hunter/requirements.txt`，保持与主仓其他能力解耦。
