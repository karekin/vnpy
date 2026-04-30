# DeerFlow + Temporal Compose Deployment

This deployment follows the Obsidian plan for a single-machine long task chain:

```text
frontend / position-api
  -> Temporal schedule
  -> DailyStockRecommendationBatchWorkflow
  -> StockRecommendationWorkflow(symbol)
  -> collect context / rule scores
  -> DeerFlow thread + agent run
  -> JSON validation
  -> JSONL audit result
```

## Files

- `compose/docker-compose.yml` starts PostgreSQL, Temporal, Temporal UI, Redis, Qdrant, the VN.PY API, the Temporal stock worker, an ops CLI, and the frontend.
- `env/agent.env.example` documents deploy-time variables. Copy it to `env/agent.env` for local secrets.
- `Dockerfile.api` and `Dockerfile.worker` build minimal Python images without changing the project `pyproject.toml`.
- `../vnpy/web/agent_chain/temporal_worker.py` defines the Temporal workflows and activities.

## Start

```bash
cd deploy/compose
cp ../env/agent.env.example ../env/agent.env
docker compose up -d postgres redis qdrant temporal temporal-ui
docker compose up -d position-api stock-worker frontend
```

`docker-compose.yml` loads `agent.env.example` so it is runnable without local
secrets. For real keys, either export them in your shell before `docker compose`
or run Compose with `--env-file ../env/agent.env`.

Temporal UI: `http://localhost:8088`

Position API health: `http://localhost:8000/api/v1/system/health`

Frontend: `http://localhost:3000`

## TenX Hunter Data Pipeline

The Compose project stores TenX data inside the unified `vnpy-position-agent`
stack. TenX tables live in the shared `postgres` container as database `tenx`;
MinIO data lives in the project-scoped `tenx-minio-data` volume.

Local endpoints:

- TenX Postgres: `127.0.0.1:54329`, database `tenx`, user `tenx`
- TenX MinIO API: `http://localhost:9000`
- TenX MinIO Console: `http://localhost:9001`

Run one-off pipeline commands through the ops profile:

```bash
cd deploy/compose
docker compose --profile tenx-ops run --rm tenx-pipeline help
docker compose --profile tenx-ops run --rm tenx-pipeline show-ads
```

Start the persistent TenX scheduler when you want the pipeline loop online:

```bash
cd deploy/compose
docker compose --profile tenx-scheduler up -d tenx-scheduler
```

## DeerFlow

DeerFlow runs from the local upstream repository and joins the
`vnpy-position-agent_agent` Docker network via
`docker/docker-compose.vnpy.yaml`. The deployment uses DeerFlow gateway mode to
keep the runtime to three containers: `deer-flow-nginx`,
`deer-flow-frontend`, and `deer-flow-gateway`.

```bash
cd /Users/karekin/Downloads/coding/project/deer-flow
export DEER_FLOW_HOME=$PWD/backend/.deer-flow
export DEER_FLOW_REPO_ROOT=$PWD
export DEER_FLOW_CONFIG_PATH=$PWD/config.yaml
export DEER_FLOW_EXTENSIONS_CONFIG_PATH=$PWD/extensions_config.json
export DEER_FLOW_DOCKER_SOCKET=/var/run/docker.sock
export BETTER_AUTH_SECRET=$(cat "$DEER_FLOW_HOME/.better-auth-secret")
export LANGGRAPH_UPSTREAM=gateway:8001
export LANGGRAPH_REWRITE=/api/
export APT_MIRROR=mirrors.aliyun.com
docker compose -p deer-flow \
  -f docker/docker-compose.yaml \
  -f docker/docker-compose.vnpy.yaml \
  up -d --remove-orphans frontend gateway nginx
```

If DeerFlow is not on the same Docker network, set this in `deploy/env/agent.env`:

```bash
TENX_DEERFLOW_URL=http://host.docker.internal:2026
```

When DeerFlow is attached to `vnpy-position-agent_agent`, the default
`TENX_DEERFLOW_URL=http://deerflow-nginx:2026` can be used.
The default assistant id is `tenx-hunter-agent`, matching the local DeerFlow
agent under `backend/.deer-flow/agents/tenx-hunter-agent`.

MiniMax is configured in the DeerFlow repository:

- `config.yaml` uses `deerflow.models.patched_minimax:PatchedChatMiniMax`
  with model `MiniMax-M2.7`.
- `.env` provides `MINIMAX_API_KEY`.
- The MiniMax OpenAI-compatible endpoint is `https://api.minimaxi.com/v1`.

## Create The Daily Schedule

```bash
cd deploy/compose
docker compose --profile ops run --rm scheduler-cli
```

Defaults:

- `STOCK_RECOMMENDATION_CRON=0 8 * * 1-5`
- `STOCK_RECOMMENDATION_TIME_ZONE=Asia/Shanghai`
- `STOCK_RECOMMENDATION_SYMBOLS=AAPL,MSFT,NVDA,QQQ,SPY`
- `OPTIONS_CHAIN_EXPIRATION_LIMIT=4` controls how many Yahoo Finance expirations are refreshed per US symbol.

## Manual Batch

```bash
cd deploy/compose
docker compose run --rm stock-worker python -m vnpy.web.agent_chain run-daily \
  --trade-date 2026-04-29 \
  --market US \
  --symbols AAPL,MSFT,NVDA
```

Results are appended to `/data/agent_chain/strategy_fit_reviews.jsonl` in the
`app-data` volume. The option-chain data product is also persisted in Postgres:

- `ods.us_option_chain_raw` stores normalized contracts.
- `dws.security_option_chain_summary_daily` stores daily liquidity, IV, flow, and selection scores.
- `ads.option_target_recommendation_daily` stores the Agent's daily target recommendation.

Daily target recommendations are portfolio-aware. The worker reads the active
smart-allocation profile and snapshot from `VNPY_SMART_ALLOCATION_DB_PATH`, then
passes portfolio fit into the Agent prompt. A symbol can only be marked
`recommend` when account-level checks allow it: Wheel budget, single-symbol
concentration, margin room, and current holding exposure must all fit the
current snapshot. If the snapshot has not been loaded yet, the chain degrades to
watch/avoid instead of emitting a trade-ready recommendation.

DeerFlow output is accepted only if it is valid JSON and its Wheel / LEAPS
status values match the allowed enums.
