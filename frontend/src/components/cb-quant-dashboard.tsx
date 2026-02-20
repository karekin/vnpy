"use client";

import { useMemo, useState } from "react";

type StageId =
  | "mining"
  | "data"
  | "generation"
  | "backtest"
  | "execution"
  | "feedback";

interface WorkflowStage {
  id: StageId;
  label: string;
  subtitle: string;
  objective: string;
  automation: string;
  inputs: string[];
  outputs: string[];
  checks: string[];
}

const workflowStages: WorkflowStage[] = [
  {
    id: "mining",
    label: "信息挖掘",
    subtitle: "Reverse Engineering",
    objective: "从公开组合调仓、社区经验中提炼策略要素字典",
    automation: "半自动",
    inputs: ["持有封基调仓记录", "禄得网历史回测", "双低轮动经验库"],
    outputs: ["策略要素字典", "初始规则族", "Teacher 先验标签"],
    checks: ["规则可参数化", "字段可回溯", "样本时间覆盖近三年"],
  },
  {
    id: "data",
    label: "数据工程",
    subtitle: "Market Snapshot Pipeline",
    objective: "构建可转债 + 正股 + 交易约束的日更版本化数据层",
    automation: "全自动",
    inputs: ["可转债行情与基础字段", "正股行情", "停牌/流动性/强赎状态"],
    outputs: ["market_snapshot_YYYYMMDD", "质量报告", "特征缓存"],
    checks: ["缺失率阈值", "异常值告警", "交易日历对齐"],
  },
  {
    id: "generation",
    label: "策略生成",
    subtitle: "Strategy Factory",
    objective: "用 ≤30 参数表达过滤、打分、调仓、风控并批量生成候选策略",
    automation: "全自动",
    inputs: ["策略 DSL 配置", "参数空间定义", "资产池约束（A股+可转债）"],
    outputs: ["100k+ 候选策略", "参数采样日志", "策略版本ID"],
    checks: ["参数边界合法", "策略可解释", "交易约束可落地"],
  },
  {
    id: "backtest",
    label: "回测评估",
    subtitle: "Robustness First",
    objective: "多窗口硬约束筛选，确保近几年表现仍然强势",
    automation: "全自动",
    inputs: ["候选策略集", "交易成本/滑点模型", "市场分阶段标签"],
    outputs: ["leaderboard", "稳健区间参数簇", "淘汰原因分析"],
    checks: ["2018-2025 窗口", "近3年窗口", "近1年窗口"],
  },
  {
    id: "execution",
    label: "自动执行",
    subtitle: "Semi/Full Auto Trading",
    objective: "默认半自动确认执行，逐步过渡到自动下单与风控熔断",
    automation: "可切换",
    inputs: ["orders_today", "仓位与换手上限", "交易时段状态"],
    outputs: ["执行回报", "未成交归因", "成交偏差记录"],
    checks: ["单券仓位上限", "单日换手上限", "回撤熔断"],
  },
  {
    id: "feedback",
    label: "反馈迭代",
    subtitle: "Post-mortem & Re-Optimization",
    objective: "按周/月复盘归因，触发滚动再优化和参数再训练",
    automation: "全自动+人工复核",
    inputs: ["收益归因", "风险暴露", "策略漂移检测"],
    outputs: ["再优化任务", "新参数候选", "版本升级建议"],
    checks: ["近3月劣化检测", "基准跑输阈值", "重训练审计"],
  },
];

const objectives = [
  { label: "长期年化目标", value: "≈30%", note: "业务KPI" },
  { label: "候选策略规模", value: "100k+", note: "批量搜索" },
  { label: "参数上限", value: "≤30", note: "策略可控" },
  { label: "人工干预", value: "最小化", note: "默认确认执行" },
];

const milestonePlan = [
  { id: "M1", title: "数据与基准回测", period: "1-2周", deliverable: "双低最小可用策略 + 数据管道落库" },
  { id: "M2", title: "参数化与10万搜索", period: "2-4周", deliverable: "DSL + 多窗口评估器 + leaderboards" },
  { id: "M3", title: "公开组合规则反推", period: "2-6周", deliverable: "Teacher 模仿策略 + 先验融合" },
  { id: "M4", title: "自动推荐与监控", period: "持续迭代", deliverable: "每日推荐、报警、滚动再优化" },
];

const parameterGroups = [
  { name: "候选池过滤", count: 8, examples: "成交额阈值、停牌过滤、强赎风险阈值、到期天数阈值" },
  { name: "双低打分", count: 5, examples: "w1/w2 权重、rank方式、溢价截尾、价格截尾" },
  { name: "组合构建", count: 6, examples: "TopK、等权/风险平价、单券仓位上限、行业约束" },
  { name: "调仓机制", count: 5, examples: "日频/周频、换手上限、调仓触发阈值、缓冲区" },
  { name: "风控保护", count: 6, examples: "回撤熔断、波动率过滤、黑名单、交易失败重试策略" },
];

const leaderboard = [
  { name: "DL-Robust-07", cagr: "33.8%", mdd: "15.7%", calmar: "2.15", y3: "29.4%", y1: "18.6%" },
  { name: "DL-Teacher-Blend", cagr: "31.2%", mdd: "13.8%", calmar: "2.26", y3: "27.9%", y1: "16.1%" },
  { name: "DL-LowPremium-21", cagr: "29.6%", mdd: "12.4%", calmar: "2.38", y3: "25.3%", y1: "14.8%" },
];

const sop = {
  daily: [
    "开盘前拉取可转债/正股/约束数据，生成 snapshot 版本",
    "运行数据质量校验（缺失、异常、交易日历）",
    "输出候选池与调仓建议，半自动模式下人工确认",
  ],
  weekly: [
    "复盘收益归因与未成交原因",
    "检查风险暴露（强赎、流动性、集中度）",
    "回放执行日志，修复策略/执行偏差",
  ],
  monthly: [
    "触发滚动重搜索（多窗口硬约束）",
    "筛选稳健区间参数簇而非单点最优",
    "发布新策略版本并保留可回滚版本",
  ],
};

const recommendations = [
  { symbol: "123130.SZ", name: "设研转债", bucket: "可转债", score: "92.4", action: "买入", weight: "8%" },
  { symbol: "127089.SZ", name: "晶澳转债", bucket: "可转债", score: "90.7", action: "买入", weight: "7%" },
  { symbol: "113641.SH", name: "华友转债", bucket: "可转债", score: "89.3", action: "调低", weight: "5%" },
  { symbol: "300750.SZ", name: "宁德时代", bucket: "股票", score: "81.2", action: "观察", weight: "0-3%" },
];

const riskSignals = [
  { title: "强赎风险暴露", value: "2只", status: "warning" },
  { title: "近20日最大回撤", value: "4.6%", status: "healthy" },
  { title: "执行偏差(滑点)", value: "0.17%", status: "healthy" },
  { title: "策略劣化告警", value: "未触发", status: "healthy" },
];

export function CbQuantDashboard() {
  const [activeStageId, setActiveStageId] = useState<StageId>("generation");
  const [mode, setMode] = useState<"semi" | "full">("semi");

  const activeStage = useMemo(
    () => workflowStages.find((stage) => stage.id === activeStageId) ?? workflowStages[0],
    [activeStageId],
  );

  return (
    <div className="cb-shell">
      <header className="cb-topbar">
        <div className="brand">
          <div className="brand-logo">CB</div>
          <div>
            <h1>Convertible Bond Quant Lab</h1>
            <p>A股 + 可转债量化闭环系统（前端重构版）</p>
          </div>
        </div>
        <div className="chip-row">
          <span className="chip">资产范围: 股票 / 可转债</span>
          <span className="chip muted">期货模块: 已移除</span>
          <span className="chip success">系统状态: 设计中</span>
        </div>
      </header>

      <main className="cb-main">
        <section className="hero">
          <article className="mission-card">
            <p className="eyebrow">目标引擎</p>
            <h2>从信息挖掘到自动执行，形成“可解释 + 可回测 + 可迭代”的交易闭环</h2>
            <p>
              核心策略围绕双低轮动展开，叠加流动性、强赎、仓位与换手控制。搜索引擎优先筛选“近几年仍强势”的稳健参数区间，避免过拟合历史单点最优。
            </p>
          </article>

          <div className="objective-grid">
            {objectives.map((item) => (
              <article key={item.label} className="objective-card">
                <p>{item.label}</p>
                <strong>{item.value}</strong>
                <small>{item.note}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="workflow">
          <div className="section-head">
            <h3>全流程架构</h3>
            <p>信息挖掘 → 数据接入 → 策略生成 → 回测评估 → 自动执行 → 反馈迭代</p>
          </div>

          <div className="stage-tabs">
            {workflowStages.map((stage) => (
              <button
                key={stage.id}
                type="button"
                className={`stage-tab ${stage.id === activeStageId ? "active" : ""}`}
                onClick={() => setActiveStageId(stage.id)}
              >
                <span>{stage.label}</span>
                <small>{stage.subtitle}</small>
              </button>
            ))}
          </div>

          <article className="stage-panel">
            <header>
              <div>
                <h4>{activeStage.label}</h4>
                <p>{activeStage.objective}</p>
              </div>
              <span className="automation-tag">自动化: {activeStage.automation}</span>
            </header>

            <div className="stage-columns">
              <div>
                <h5>输入</h5>
                <ul>
                  {activeStage.inputs.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h5>输出</h5>
                <ul>
                  {activeStage.outputs.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h5>质量门禁</h5>
                <ul>
                  {activeStage.checks.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          </article>
        </section>

        <section className="split">
          <article className="panel">
            <div className="panel-head">
              <h3>策略参数工厂（≤30参数）</h3>
              <span>支持 100k+ 策略批量搜索</span>
            </div>
            <div className="param-list">
              {parameterGroups.map((group) => (
                <div key={group.name} className="param-row">
                  <div>
                    <h4>{group.name}</h4>
                    <p>{group.examples}</p>
                  </div>
                  <strong>{group.count}</strong>
                </div>
              ))}
            </div>
          </article>

          <article className="panel">
            <div className="panel-head">
              <h3>稳健回测排行榜（示例）</h3>
              <span>硬约束: 全周期 + 近3年 + 近1年</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>策略ID</th>
                    <th>CAGR</th>
                    <th>MDD</th>
                    <th>Calmar</th>
                    <th>近3年</th>
                    <th>近1年</th>
                  </tr>
                </thead>
                <tbody>
                  {leaderboard.map((row) => (
                    <tr key={row.name}>
                      <td>{row.name}</td>
                      <td>{row.cagr}</td>
                      <td>{row.mdd}</td>
                      <td>{row.calmar}</td>
                      <td>{row.y3}</td>
                      <td>{row.y1}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </section>

        <section className="panel milestone-panel">
          <div className="panel-head">
            <h3>里程碑计划</h3>
            <span>M1 → M4 逐步从研究走向自动化运行</span>
          </div>
          <div className="milestone-grid">
            {milestonePlan.map((item) => (
              <article key={item.id} className="milestone-card">
                <p>{item.id}</p>
                <h4>{item.title}</h4>
                <small>{item.period}</small>
                <span>{item.deliverable}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="split">
          <article className="panel">
            <div className="panel-head">
              <h3>SOP 日常运行</h3>
              <span>每天 / 每周 / 每月标准化执行</span>
            </div>
            <div className="sop-grid">
              <div>
                <h4>Daily</h4>
                <ol>
                  {sop.daily.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
              </div>
              <div>
                <h4>Weekly</h4>
                <ol>
                  {sop.weekly.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
              </div>
              <div>
                <h4>Monthly</h4>
                <ol>
                  {sop.monthly.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
              </div>
            </div>
          </article>

          <article className="panel">
            <div className="panel-head">
              <h3>执行中心</h3>
              <div className="mode-toggle">
                <button
                  type="button"
                  className={mode === "semi" ? "active" : ""}
                  onClick={() => setMode("semi")}
                >
                  半自动
                </button>
                <button
                  type="button"
                  className={mode === "full" ? "active" : ""}
                  onClick={() => setMode("full")}
                >
                  全自动
                </button>
              </div>
            </div>
            <p className="mode-tip">
              当前模式: {mode === "semi" ? "半自动确认执行（推荐）" : "全自动执行（需模拟盘验证后启用）"}
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>标的</th>
                    <th>名称</th>
                    <th>类型</th>
                    <th>综合评分</th>
                    <th>动作</th>
                    <th>目标权重</th>
                  </tr>
                </thead>
                <tbody>
                  {recommendations.map((row) => (
                    <tr key={row.symbol}>
                      <td>{row.symbol}</td>
                      <td>{row.name}</td>
                      <td>{row.bucket}</td>
                      <td>{row.score}</td>
                      <td>{row.action}</td>
                      <td>{row.weight}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </section>

        <section className="split">
          <article className="panel">
            <div className="panel-head">
              <h3>风控看板</h3>
              <span>运行中关键风险信号</span>
            </div>
            <div className="risk-grid">
              {riskSignals.map((item) => (
                <div key={item.title} className={`risk-card ${item.status}`}>
                  <p>{item.title}</p>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          </article>

          <article className="panel">
            <div className="panel-head">
              <h3>反馈闭环</h3>
              <span>自动触发条件</span>
            </div>
            <div className="feedback-flow">
              <div>
                <h4>触发器</h4>
                <p>近3个月跑输基准 &gt; 5% / 回撤突破阈值 / 数据异常连续3日</p>
              </div>
              <div>
                <h4>动作</h4>
                <p>自动创建再优化任务，重跑参数搜索并输出候选策略簇</p>
              </div>
              <div>
                <h4>产物</h4>
                <p>新版本策略报告、回滚建议、上线变更单</p>
              </div>
            </div>
          </article>
        </section>
      </main>
    </div>
  );
}
