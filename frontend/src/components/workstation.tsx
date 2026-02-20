"use client";

import { useMemo, useState } from "react";
import {
  accounts,
  backtestMetrics,
  contracts,
  logs,
  marketWall,
  orders,
  positions,
  strategyRows,
  ticks,
  trades,
} from "@/lib/mock-data";
import { useVnpyFeed } from "@/hooks/use-vnpy-feed";

type WorkspaceId =
  | "trade"
  | "contracts"
  | "backtest"
  | "strategy"
  | "data"
  | "algo"
  | "risk"
  | "market"
  | "station";

interface WorkspaceMeta {
  id: WorkspaceId;
  label: string;
  icon: string;
}

const workspaces: WorkspaceMeta[] = [
  { id: "trade", label: "交易", icon: "⇄" },
  { id: "contracts", label: "合约", icon: "⌗" },
  { id: "backtest", label: "CTA回测", icon: "▦" },
  { id: "strategy", label: "CTA策略", icon: "∑" },
  { id: "data", label: "数据管理", icon: "⛁" },
  { id: "algo", label: "算法交易", icon: "◉" },
  { id: "risk", label: "风控", icon: "⚑" },
  { id: "market", label: "报价墙", icon: "▣" },
  { id: "station", label: "Station", icon: "⌂" },
];

const topMenus = ["系统", "功能", "配置", "帮助"];

function deterministic(seed: number, min: number, max: number, precision = 0): number {
  const raw = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
  const ratio = raw - Math.floor(raw);
  const value = min + ratio * (max - min);
  return Number(value.toFixed(precision));
}

function Panel({ title, children, actions }: { title: string; children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <section className="panel">
      <header className="panel-header">
        <h3>{title}</h3>
        <div>{actions}</div>
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="table-wrap">
      <table className="desk-table">
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TrendChart({ color = "var(--accent-cyan)" }: { color?: string }) {
  return (
    <svg className="trend-chart" viewBox="0 0 560 180" preserveAspectRatio="none" role="img" aria-label="trend chart">
      <polyline
        fill="none"
        stroke="var(--line-muted)"
        strokeWidth="1"
        points="0,125 60,115 120,104 180,110 240,96 300,88 360,92 420,78 480,84 560,74"
      />
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="3"
        points="0,132 60,116 120,118 180,90 240,95 300,82 360,63 420,69 480,52 560,57"
      />
    </svg>
  );
}

function ProfitBars() {
  const values = [25, 40, 18, 52, -31, 22, -45, 68, -27, 14, 36, -39, 44, 11, -34];

  return (
    <div className="profit-bars">
      {values.map((value, idx) => (
        <span
          key={idx}
          style={{ height: `${Math.abs(value)}%` }}
          className={value >= 0 ? "bar-up" : "bar-down"}
        />
      ))}
    </div>
  );
}

function TradeWorkspace() {
  return (
    <div className="trade-body">
      <Panel title="交易委托">
        <form className="form-grid">
          {[
            ["交易所", "DCE"],
            ["代码", "m2205"],
            ["名称", "豆粕2205"],
            ["方向", "空"],
            ["开平", "平"],
            ["类型", "限价"],
            ["价格", "4120"],
            ["数量", "5"],
            ["接口", "CTP"],
          ].map(([label, value]) => (
            <label key={label}>
              <span>{label}</span>
              <input readOnly value={value} />
            </label>
          ))}
          <button type="button" className="primary-btn">
            委托
          </button>
          <button type="button" className="ghost-btn">
            全撤
          </button>
        </form>

        <div className="quote-ticker">
          <p className="up">4134.0</p>
          <p>241</p>
          <p>4133.0</p>
          <p>-2.04%</p>
          <p className="down">4133.0</p>
          <p className="down">65</p>
        </div>
      </Panel>

      <div className="trade-panels">
        <Panel title="行情">
          <Table
            headers={["代码", "交易所", "名称", "最新价", "成交量", "买1", "买1量", "卖1", "卖1量", "时间", "接口"]}
            rows={ticks.map((item) => [
              item.symbol,
              item.exchange,
              item.name,
              item.lastPrice,
              item.volume,
              <span key={`${item.symbol}-b`} className="down">
                {item.bid1}
              </span>,
              item.bidVolume1,
              <span key={`${item.symbol}-a`} className="up">
                {item.ask1}
              </span>,
              item.askVolume1,
              item.time,
              item.gateway,
            ])}
          />
        </Panel>

        <Panel title="委托">
          <Table
            headers={["委托号", "来源", "代码", "交易所", "类型", "方向", "开平", "价格", "总数量", "已成交", "状态", "时间", "接口"]}
            rows={orders.map((item) => [
              item.orderid,
              item.reference,
              item.symbol,
              item.exchange,
              item.type,
              <span key={`${item.orderid}-d`} className={item.direction === "多" ? "up" : "down"}>
                {item.direction}
              </span>,
              item.offset,
              item.price,
              item.volume,
              item.traded,
              item.status,
              item.time,
              item.gateway,
            ])}
          />
        </Panel>

        <Panel title="成交">
          <Table
            headers={["成交号", "委托号", "代码", "交易所", "方向", "开平", "价格", "数量", "时间", "接口"]}
            rows={trades.map((item) => [
              item.tradeid,
              item.orderid,
              item.symbol,
              item.exchange,
              <span key={`${item.tradeid}-d`} className={item.direction === "多" ? "up" : "down"}>
                {item.direction}
              </span>,
              item.offset,
              item.price,
              item.volume,
              item.time,
              item.gateway,
            ])}
          />
        </Panel>

        <div className="triple-row">
          <Panel title="日志">
            <Table
              headers={["时间", "信息", "接口"]}
              rows={logs.map((item) => [item.time, item.message, item.source])}
            />
          </Panel>

          <Panel title="资金">
            <Table
              headers={["账号", "余额", "冻结", "可用", "接口"]}
              rows={accounts.map((item) => [
                item.accountid,
                item.balance.toLocaleString(),
                item.frozen,
                item.available.toLocaleString(),
                item.gateway,
              ])}
            />
          </Panel>

          <Panel title="持仓">
            <Table
              headers={["代码", "交易所", "方向", "数量", "昨仓", "冻结", "均价", "盈亏", "接口"]}
              rows={positions.map((item) => [
                item.symbol,
                item.exchange,
                <span key={`${item.symbol}-${item.direction}`} className={item.direction === "多" ? "up" : "down"}>
                  {item.direction}
                </span>,
                item.volume,
                item.ydVolume,
                item.frozen,
                item.avgPrice,
                <span key={`${item.symbol}-pnl`} className={item.pnl >= 0 ? "up" : "down"}>
                  {item.pnl}
                </span>,
                item.gateway,
              ])}
            />
          </Panel>
        </div>
      </div>
    </div>
  );
}

function ContractWorkspace() {
  return (
    <div className="single-workspace">
      <Panel
        title="合约查询"
        actions={
          <div className="inline-actions">
            <input className="mini-input" value="输入合约代码或者交易所，留空则查询所有合约" readOnly />
            <button type="button" className="ghost-btn small">
              查询
            </button>
          </div>
        }
      >
        <Table
          headers={["本地代码", "代码", "交易所", "名称", "合约分类", "合约乘数", "价格跳动", "最小委托量", "交易接口"]}
          rows={Array.from({ length: 30 }).map((_, index) => {
            const base = contracts[index % contracts.length];
            return [
              `${base.symbol}.${base.exchange}`,
              base.symbol,
              base.exchange,
              base.name,
              base.product,
              base.size,
              base.pricetick,
              base.minVolume,
              base.gateway,
            ];
          })}
        />
      </Panel>
    </div>
  );
}

function BacktestWorkspace() {
  return (
    <div className="backtest-layout">
      <Panel title="回测配置">
        <form className="form-grid">
          {[
            ["交易策略", "AtrRsiStrategy"],
            ["本地代码", "IF888.CFFEX"],
            ["K线周期", "1m"],
            ["开始日期", "2017-01-02"],
            ["结束日期", "2022-03-16"],
            ["手续费率", "0.0"],
            ["交易滑点", "0.0"],
            ["合约乘数", "300.0"],
            ["价格跳动", "0.2"],
            ["回测资金", "1000000.0"],
            ["合约模式", "正向"],
          ].map(([label, value]) => (
            <label key={label}>
              <span>{label}</span>
              <input readOnly value={value} />
            </label>
          ))}

          <button type="button" className="primary-btn">
            开始回测
          </button>
          <button type="button" className="ghost-btn">
            下载数据
          </button>
        </form>

        <div className="metric-grid">
          {backtestMetrics.map((metric) => (
            <div key={metric.label} className="metric-item">
              <p>{metric.label}</p>
              <strong>{metric.value}</strong>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="回测图表">
        <div className="chart-grid">
          <div className="chart-card">
            <h4>账户净值</h4>
            <TrendChart color="var(--accent-yellow)" />
          </div>
          <div className="chart-card">
            <h4>净值回撤</h4>
            <TrendChart color="var(--accent-blue)" />
          </div>
          <div className="chart-card">
            <h4>每日盈亏</h4>
            <ProfitBars />
          </div>
          <div className="chart-card">
            <h4>盈亏分布</h4>
            <TrendChart color="var(--accent-red)" />
          </div>
        </div>
      </Panel>

      <Panel title="K线回放">
        <div className="kline-canvas">
          <div className="kline-legend">红线: 盈利交易 | 绿线: 亏损交易 | 黄箭头: Buy | 紫箭头: Sell</div>
          <TrendChart color="var(--accent-green)" />
          <div className="volume-overlay" />
        </div>
      </Panel>
    </div>
  );
}

function StrategyWorkspace() {
  return (
    <div className="strategy-layout">
      <Panel title="CTA策略池">
        <div className="strategy-list">
          {strategyRows.map((item) => (
            <article key={item.strategyName + item.vtSymbol} className="strategy-card">
              <header>
                <h4>
                  {item.strategyName} · {item.vtSymbol}
                </h4>
                <p>
                  {item.className} · 状态: {item.trading ? "运行中" : "已停止"}
                </p>
              </header>

              <div className="strategy-btns">
                <button type="button" className="ghost-btn small">
                  初始化
                </button>
                <button type="button" className="primary-btn small">
                  启动
                </button>
                <button type="button" className="ghost-btn small">
                  停止
                </button>
                <button type="button" className="ghost-btn small">
                  编辑
                </button>
              </div>

              <div className="strategy-tables">
                <div>
                  <h5>参数</h5>
                  <ul>
                    {Object.entries(item.parameters).map(([key, value]) => (
                      <li key={key}>
                        <span>{key}</span>
                        <strong>{String(value)}</strong>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h5>变量</h5>
                  <ul>
                    {Object.entries(item.variables).map(([key, value]) => (
                      <li key={key}>
                        <span>{key}</span>
                        <strong>{String(value)}</strong>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </article>
          ))}
        </div>
      </Panel>

      <Panel title="停止委托和日志">
        <Table
          headers={["停止委托号", "本地代码", "方向", "开平", "价格", "数量", "状态", "时间", "策略名"]}
          rows={Array.from({ length: 10 }).map((_, index) => [
            `STOP.${index + 1}`,
            "IF2203.CFFEX",
            <span key={`dir-${index}`} className={index % 2 ? "up" : "down"}>
              {index % 2 ? "多" : "空"}
            </span>,
            "平",
            (4050 + index * 2.4).toFixed(1),
            "1.0",
            index % 3 === 0 ? "等待中" : "已撤销",
            `22:2${index}:47.3${index}`,
            "IF",
          ])}
        />

        <div className="log-list">
          {logs.concat(logs).map((item, idx) => (
            <p key={`${item.time}-${idx}`}>
              <span>{item.time}</span>
              <strong>[{item.source}]</strong>
              {item.message}
            </p>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function DataWorkspace() {
  return (
    <div className="data-layout">
      <Panel title="数据目录">
        <div className="tree-box">
          <p>▾ 分钟线</p>
          <p className="tree-child">├─ IF888.CFFEX</p>
          <p className="tree-child">├─ IH2204.CFFEX</p>
          <p className="tree-child">├─ cu2205.SHFE</p>
          <p className="tree-child">└─ rb2205.SHFE</p>
          <p>▾ 小时线</p>
          <p>▾ 日线</p>
        </div>

        <form className="import-form">
          <h4>CSV 导入参数</h4>
          {[
            ["代码", "cu2205"],
            ["交易所", "SHFE"],
            ["周期", "MINUTE"],
            ["时区", "Asia/Shanghai"],
            ["时间戳", "datetime"],
            ["开盘价", "open"],
            ["最高价", "high"],
            ["最低价", "low"],
            ["收盘价", "close"],
            ["成交量", "volume"],
          ].map(([label, value]) => (
            <label key={label}>
              <span>{label}</span>
              <input readOnly value={value} />
            </label>
          ))}
        </form>
      </Panel>

      <Panel title="历史数据">
        <Table
          headers={["时间", "开盘价", "最高价", "最低价", "收盘价", "成交量", "成交额", "持仓量"]}
          rows={Array.from({ length: 30 }).map((_, index) => {
            const base = 4820 + index;
            const high = base + deterministic(index + 1, 0, 12);
            const low = base - deterministic(index + 31, 0, 12);
            const close = base + deterministic(index + 61, -5, 5);
            const volume = 100 + deterministic(index + 91, 0, 500);
            const turnover = 30000000 + deterministic(index + 121, 0, 90000000);
            const oi = 76000 + deterministic(index + 151, 0, 400);
            return [
              `2021-11-10 09:${String(30 + index).padStart(2, "0")}:00`,
              base,
              high,
              low,
              close,
              volume,
              `${turnover.toFixed(0)}`,
              `${oi.toFixed(0)}`,
            ];
          })}
        />
      </Panel>
    </div>
  );
}

function AlgoWorkspace() {
  return (
    <div className="algo-layout">
      <Panel title="算法配置">
        <form className="form-grid">
          {[
            ["算法", "Iceberg"],
            ["本地代码", "cu2205.DCE"],
            ["方向", "多"],
            ["价格", "2860"],
            ["数量", "10"],
            ["挂出数量", "1"],
            ["每轮间隔(秒)", "5"],
            ["开平", "开"],
          ].map(([label, value]) => (
            <label key={label}>
              <span>{label}</span>
              <input readOnly value={value} />
            </label>
          ))}
          <button type="button" className="primary-btn">
            启动算法
          </button>
          <button type="button" className="ghost-btn">
            CSV启动
          </button>
        </form>
      </Panel>

      <Panel title="执行中 / 已结束">
        <Table
          headers={["算法", "参数", "状态"]}
          rows={Array.from({ length: 8 }).map((_, index) => [
            `IcebergAlgo_${index + 1}`,
            `代码: c2205.DCE, 方向: ${index % 2 ? "空" : "多"}, 价格: ${2860 + index * 10}, 数量: ${10 + index}`,
            `算法状态: ${index % 3 ? "False" : "True"}, 成交数量: ${deterministic(index + 201, 0, 15)}`,
          ])}
        />

        <div className="config-grid">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="config-card">
              <p>c_iceberg_{index + 1}</p>
              <span>使用</span>
              <span>移除</span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function RiskWorkspace() {
  return (
    <div className="risk-layout">
      <Panel title="交易风控">
        <form className="risk-form">
          {[
            ["风控运行状态", "启动"],
            ["委托流控上限(笔)", "20"],
            ["委托流控清空(秒)", "1"],
            ["单笔委托上限(数量)", "50"],
            ["总成交上限(笔)", "200"],
            ["活动委托上限(笔)", "10"],
            ["合约撤单上限(笔)", "450"],
          ].map(([label, value]) => (
            <label key={label}>
              <span>{label}</span>
              <input readOnly value={value} />
            </label>
          ))}

          <button type="button" className="primary-btn">
            保存
          </button>
        </form>
      </Panel>

      <Panel title="风控监控">
        <Table
          headers={["代码", "今日委托", "今日成交", "撤单笔数", "成交持仓比例"]}
          rows={Array.from({ length: 10 }).map((_, index) => [
            ["IF2204", "IH2204", "cu2205"][index % 3],
            20 + index * 3,
            14 + index * 2,
            5 + index,
            `${(0.22 + index * 0.07).toFixed(2)}`,
          ])}
        />
      </Panel>
    </div>
  );
}

function MarketWallWorkspace() {
  return (
    <div className="single-workspace">
      <Panel title="期货市场报价跟踪">
        <div className="market-wall">
          {marketWall.map((symbol, idx) => {
            const base = 470 + idx * 12;
            const delta = deterministic(idx + 301, -4, 4, 1).toFixed(1);
            const positive = Number(delta) >= 0;
            const midPrice = (base + deterministic(idx + 401, 0, 10, 1)).toFixed(1);
            const bidWidth = `${deterministic(idx + 501, 35, 85)}%`;
            const askWidth = `${deterministic(idx + 601, 30, 80)}%`;

            return (
              <article key={symbol} className="market-card">
                <header>
                  <p>{symbol}</p>
                  <strong>原油{2209 + idx}</strong>
                </header>
                <h4>{midPrice}</h4>
                <p className={positive ? "up" : "down"}>{delta}%</p>
                <div className="depth-bar">
                  <span className="bid" style={{ width: bidWidth }} />
                  <span className="ask" style={{ width: askWidth }} />
                </div>
              </article>
            );
          })}
        </div>

        <div className="market-bottom">
          <Panel title="最新成交">
            <TrendChart color="var(--accent-orange)" />
          </Panel>
          <Panel title="月间日历价差">
            <ProfitBars />
          </Panel>
        </div>
      </Panel>
    </div>
  );
}

function StationWorkspace() {
  return (
    <div className="station-layout">
      <Panel title="VEIGHNA STATION · 交易模块启动器">
        <div className="station-body">
          <div className="station-list">
            <h4>交易接口</h4>
            {[
              "中泰XTP",
              "国泰君安统一交易网关",
              "东方证券OST",
              "盈透证券",
              "易盛9.0外盘",
              "TTS",
              "RPC服务",
            ].map((item) => (
              <label key={item}>
                <input type="checkbox" defaultChecked={item === "RPC服务"} />
                <span>{item}</span>
              </label>
            ))}

            <h4>应用模块</h4>
            {[
              "CtaStrategy",
              "CtaBacktester",
              "SpreadTrading",
              "AlgoTrading",
              "OptionMaster",
              "PortfolioStrategy",
              "DataManager",
            ].map((item) => (
              <label key={item}>
                <input type="checkbox" defaultChecked />
                <span>{item}</span>
              </label>
            ))}

            <button type="button" className="primary-btn">
              启动
            </button>
          </div>

          <div className="station-log">
            <Table
              headers={["时间", "运行日志"]}
              rows={logs.concat(logs).map((item) => [item.time, `${item.message}（${item.source}）`])}
            />
          </div>
        </div>
      </Panel>
    </div>
  );
}

export function Workstation() {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>("trade");
  const [token] = useState<string>("");
  const feed = useVnpyFeed(token);

  const activeLabel = useMemo(
    () => workspaces.find((item) => item.id === activeWorkspace)?.label ?? "交易",
    [activeWorkspace],
  );

  const latestTopic = feed.latest?.topic ?? "离线模拟";

  return (
    <div className="terminal-root">
      <aside className="side-rail">
        <div className="brand-mark">VN</div>

        <nav className="side-nav">
          {workspaces.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`side-nav-btn ${activeWorkspace === item.id ? "active" : ""}`}
              onClick={() => setActiveWorkspace(item.id)}
              title={item.label}
            >
              <span className="glyph">{item.icon}</span>
              <span className="text">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="side-footer">
          <p className="up">4134.0</p>
          <p>241</p>
          <p>4133.0</p>
          <p className="down">-2.04%</p>
        </div>
      </aside>

      <main className="workspace-root">
        <header className="workspace-top">
          <div className="menu-group">
            {topMenus.map((item) => (
              <button key={item} type="button">
                {item}
              </button>
            ))}
          </div>

          <div className="title-group">
            <h1>{activeLabel}</h1>
            <p>VeighNa Web Workstation</p>
          </div>

          <div className="status-group">
            <span className={`status-dot ${feed.connected ? "online" : "offline"}`} />
            <div>
              <p>{feed.connected ? "已连接" : "未连接"}</p>
              <small>{latestTopic}</small>
            </div>
          </div>
        </header>

        <div className="workspace-tabs">
          {workspaces.map((item) => (
            <button
              key={item.id}
              type="button"
              className={activeWorkspace === item.id ? "tab active" : "tab"}
              onClick={() => setActiveWorkspace(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <section className="workspace-content">
          {activeWorkspace === "trade" && <TradeWorkspace />}
          {activeWorkspace === "contracts" && <ContractWorkspace />}
          {activeWorkspace === "backtest" && <BacktestWorkspace />}
          {activeWorkspace === "strategy" && <StrategyWorkspace />}
          {activeWorkspace === "data" && <DataWorkspace />}
          {activeWorkspace === "algo" && <AlgoWorkspace />}
          {activeWorkspace === "risk" && <RiskWorkspace />}
          {activeWorkspace === "market" && <MarketWallWorkspace />}
          {activeWorkspace === "station" && <StationWorkspace />}
        </section>
      </main>
    </div>
  );
}
