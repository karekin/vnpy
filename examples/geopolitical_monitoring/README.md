# Realtime Geopolitical Monitoring (Engineering MVP)

你提到“当前不够工程化”，这个版本补齐了**数据链路 + 数据分层**，并提供当前完成度基线。

## 数据链路（Data Flow）
1. **采集层（Source）**：轮询 RSS/Atom 源。
2. **Bronze 层（原始层）**：原始条目落库（保留 title/link/summary/source/published/fetched）。
3. **Silver 层（标准化层）**：主题识别、可信度评分、标准化时间字段。
4. **Gold 层（事件层）**：事件去重、影响分计算、告警级别（P1/P2/P3）。
5. **输出层（Serve）**：stdout（pretty/jsonl），后续可替换为 Kafka/OpenSearch/Webhook。

## 数据分层实现
- SQLite 三张表：
  - `bronze_raw_items`
  - `silver_normalized_items`
  - `gold_events`
- 运行后可通过 `--show-stats` 查看层内记录数和完成度指标。

## 快速开始
```bash
python examples/geopolitical_monitoring/realtime_monitor.py --once --show-stats
```

使用自定义配置：
```bash
python examples/geopolitical_monitoring/realtime_monitor.py \
  --config examples/geopolitical_monitoring/config.example.json \
  --db-path examples/geopolitical_monitoring/monitor.db \
  --once --output jsonl --show-stats
```

持续运行：
```bash
python examples/geopolitical_monitoring/realtime_monitor.py \
  --config examples/geopolitical_monitoring/config.example.json \
  --db-path examples/geopolitical_monitoring/monitor.db \
  --show-stats
```

## 当前完成度（MVP）
- 数据采集：70%
- 分层落库（Bronze/Silver/Gold）：65%
- 去重与评分：60%
- 告警投递：30%
- 可观测性：20%
- 生产化（容错/回放/多活）：15%
- **总体完成度：45%**

## 下一步工程化建议
1. 输出层改造：接 Kafka/Redpanda + OpenSearch 索引。
2. 稳定性：增加重试队列、死信队列、断点续跑。
3. 质量：引入单元测试和回归样本集，校验误报率/漏报率。
4. 运维：加 Prometheus 指标（采集延迟、解析失败率、P1 触发量）。
