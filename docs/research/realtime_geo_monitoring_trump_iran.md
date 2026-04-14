# 特朗普与美伊局势实时信息采集方案（调研 + 技术设计）

## 1. 目标与范围

### 1.1 监控目标
- 人物线：特朗普（Donald Trump）相关言论、政策主张、竞选活动、司法动态。
- 地缘线：美伊局势（制裁、军事摩擦、外交谈判、代理人冲突、航运与油价冲击）。

### 1.2 输出目标
- **分钟级预警**：突发新闻/官方声明/高可信账号发帖后 1~5 分钟内告警。
- **事件级归并**：把“同一事件”不同来源的重复信息聚合成一条事件卡片。
- **可信度分层**：官方源 > 主流媒体 > 社媒爆料，支持人工复核。

---

## 2. 调研结论（可直接落地的开源组合）

> 结论：推荐采用“**RSSHub + Huginn + Kafka/Redpanda + OpenSearch + 告警机器人**”的开源主干，外加 GDELT 做全球新闻补充。

### 2.1 采集与自动化
1. **RSSHub**（开源）  
   - 价值：将大量站点转为 RSS，适合作为统一入口。  
   - 仓库：https://github.com/DIYgod/RSSHub
2. **Huginn**（开源）  
   - 价值：可配置 Agent 流程（抓取、规则判断、去重、通知）。  
   - 仓库：https://github.com/huginn/huginn
3. **n8n**（开源）  
   - 价值：可视化编排，适合非研发人员维护关键词规则与通知链路。  
   - 仓库：https://github.com/n8n-io/n8n

### 2.2 存储、检索与告警
1. **OpenSearch + Alerting**（开源）  
   - 价值：全文检索、聚合分析、告警触发（Webhook/邮件等）。  
   - 仓库：https://github.com/opensearch-project/alerting
2. **Kafka 或 Redpanda**（开源）  
   - 价值：事件流总线，便于多下游（检索、模型、看板）并行消费。

### 2.3 新闻与事件数据源
1. **GDELT 2.0**（公开数据）  
   - 价值：覆盖多语种全球新闻，可用于美伊冲突全球视角补全。  
   - 文档入口：https://docs.gdeltproject.org/
2. **官方站点/声明页（建议优先）**  
   - 白宫、美国国务院、美国财政部 OFAC、伊朗外交部/国家通讯社等。
3. **主流媒体源（次优先）**  
   - Reuters、AP、BBC、Al Jazeera、WSJ、NYT 等（按可用协议接入）。

### 2.4 现成项目能不能“开箱即用”？
- **可开箱到 60~70%**：RSSHub/Huginn/OpenSearch 可较快拼出 MVP。
- **仍需自研 30~40%**：
  - 事件去重与归并（同一事件多源合并）。
  - 风险评分模型（来源可信度 + 文本置信度 + 传播速度）。
  - 主题词典维护（特朗普、美伊相关实体/别名/组织）。

---

## 3. 技术方案（推荐架构）

## 3.1 架构分层
1. **Source Layer（采集层）**
   - RSSHub 路由 + 官方 RSS/API + GDELT 拉取任务 + 重点社媒采集（合规前提）。
2. **Stream Layer（流处理层）**
   - Kafka/Redpanda Topic：`raw_news`、`raw_social`、`normalized_events`、`alerts`。
3. **Process Layer（处理层）**
   - 标准化（时间、语言、来源、URL 指纹）。
   - 去重（SimHash/MinHash + 时间窗）。
   - 事件抽取（实体识别：Trump、IRGC、OFAC、Strait of Hormuz 等）。
   - 风险评分（规则 + 轻量模型）。
4. **Serve Layer（服务层）**
   - OpenSearch 索引：`geo_events_*`。
   - Dashboard：OpenSearch Dashboards/Grafana。
   - 告警：Slack/Telegram/飞书/邮件。

## 3.2 关键数据模型（建议）
- `event_id`: 事件主键（去重后）。
- `first_seen_at` / `last_seen_at`: 首次/最近出现时间。
- `actors`: 实体列表（人物、组织、国家）。
- `locations`: 地点列表。
- `themes`: 主题（sanction, strike, nuclear_talk, election_statement）。
- `credibility_score`: 来源可信度分（0-100）。
- `impact_score`: 影响分（市场/军事/外交）。
- `urgency_level`: P1/P2/P3。

## 3.3 告警规则示例
- **P1（立即）**：
  - 官方源出现“军事行动/制裁升级/使馆警报/航道封锁”等关键词。
- **P2（5 分钟内）**：
  - 2 家以上主流媒体对同一事件独立报道。
- **P3（观察）**：
  - 社媒单源爆料，未被高可信源证实。

---

## 4. 实施路线图

### Phase 1（1~2 周）：MVP
- 接入 RSSHub + GDELT + 5~10 个官方/主流媒体源。
- 打通 OpenSearch 检索与基础关键词告警。
- 输出第一版“特朗普/美伊局势”看板。

### Phase 2（2~4 周）：增强
- 增加多语种（英/波斯语/阿拉伯语）翻译与归一化。
- 上线事件归并与风险评分。
- 建立“人工复核台”与反馈回流机制。

### Phase 3（持续迭代）
- 引入知识图谱（人物-组织-事件关系）。
- 引入市场联动（油价、黄金、指数波动）做事件影响验证。

---

## 5. 合规与风险控制
- 严格遵守目标平台 ToS、robots、API 使用条款。
- 对社媒内容标注“未经证实”状态，避免误报直推决策。
- 记录全链路审计日志（采集时间、原始链接、处理规则版本）。

---

## 6. 你可以直接采用的最小可行技术栈（推荐）
- 采集：RSSHub + 官方源 + GDELT
- 编排：Huginn（或 n8n）
- 流式：Redpanda（轻运维）
- 检索：OpenSearch
- 告警：Webhook + Telegram/Slack
- 部署：Docker Compose 起步，后续迁移 K8s

---

## 7. 参考链接（调研来源）
- RSSHub: https://github.com/DIYgod/RSSHub
- Huginn: https://github.com/huginn/huginn
- n8n: https://github.com/n8n-io/n8n
- OpenSearch Alerting: https://github.com/opensearch-project/alerting
- GDELT 文档入口: https://docs.gdeltproject.org/
