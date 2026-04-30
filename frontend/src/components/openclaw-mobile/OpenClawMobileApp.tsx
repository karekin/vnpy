import Link from "next/link";
import type React from "react";
import {
  Activity,
  AlertTriangle,
  Bell,
  BookOpen,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  Database,
  FileText,
  Gauge,
  Home,
  Lock,
  RefreshCw,
  Search,
  Server,
  ShieldAlert,
  Smartphone,
  Wallet,
} from "lucide-react";
import {
  getOverviewMetrics,
  getTenxErrorMessage,
  loadTenxAlerts,
  loadTenxWorkspaceSnapshot,
  marketLabel,
  toMarketSlug,
} from "@/components/tenx-hunter/api";
import type {
  TenxAlertCenter,
  TenxAlertItem,
  TenxCandidate,
  TenxMarket,
  TenxTheme,
  TenxWatchlistItem,
  TenxWorkspaceSnapshot,
} from "@/components/tenx-hunter/types";

type OpenClawMobileView = "dashboard" | "portfolio" | "risk" | "research";

type OpenClawMobileAppProps = {
  view: OpenClawMobileView;
  market?: TenxMarket;
};

type MobileData = {
  snapshot: TenxWorkspaceSnapshot | null;
  alerts: TenxAlertCenter | null;
  error: string | null;
};

function defaultOpenClawMarket(): TenxMarket {
  return process.env.NEXT_PUBLIC_OPENCLAW_DEFAULT_MARKET?.toUpperCase() === "CN" ? "CN" : "US";
}

const viewCopy: Record<OpenClawMobileView, { title: string; kicker: string }> = {
  dashboard: {
    title: "今日投资总览",
    kicker: "打开手机先看这一屏",
  },
  portfolio: {
    title: "持仓与观察",
    kicker: "让 OpenClaw 维护验证清单",
  },
  risk: {
    title: "风险雷达",
    kicker: "先暴露风险，再谈机会",
  },
  research: {
    title: "标的研究库",
    kicker: "沉淀可复核的投资知识",
  },
};

const navItems = [
  { href: "/dashboard", label: "总览", view: "dashboard" as const, icon: Home },
  { href: "/portfolio", label: "持仓", view: "portfolio" as const, icon: Wallet },
  { href: "/risk", label: "风险", view: "risk" as const, icon: ShieldAlert },
  { href: "/research", label: "研究", view: "research" as const, icon: Search },
];

async function loadMobileData(market: TenxMarket): Promise<MobileData> {
  try {
    const [snapshot, alerts] = await Promise.all([
      loadTenxWorkspaceSnapshot(market),
      loadTenxAlerts(market).catch(() => null),
    ]);
    return { snapshot, alerts, error: null };
  } catch (error) {
    return {
      snapshot: null,
      alerts: null,
      error: getTenxErrorMessage(error),
    };
  }
}

function formatDateTime(value?: string) {
  if (!value) {
    return "等待同步";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function recommendationFor(candidate: TenxCandidate) {
  if (candidate.riskLevel === "high" || candidate.stage === "crowded") {
    return "人工复核";
  }
  if (candidate.score >= 82 && candidate.momentum === "strengthening") {
    return "优先研究";
  }
  if (candidate.score >= 70) {
    return "继续跟踪";
  }
  return "等待证据";
}

function candidateTone(candidate: TenxCandidate) {
  const action = recommendationFor(candidate);
  if (action === "优先研究") {
    return "border-success-200 bg-success-50 text-success-700 dark:border-success-500/30 dark:bg-success-500/10 dark:text-success-300";
  }
  if (action === "人工复核") {
    return "border-error-200 bg-error-50 text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-300";
  }
  return "border-blue-light-200 bg-blue-light-50 text-blue-light-700 dark:border-blue-light-500/30 dark:bg-blue-light-500/10 dark:text-blue-light-300";
}

function riskTone(level: TenxCandidate["riskLevel"] | TenxWatchlistItem["riskLevel"]) {
  if (level === "high") {
    return "bg-error-50 text-error-700 ring-error-200 dark:bg-error-500/10 dark:text-error-300 dark:ring-error-500/30";
  }
  if (level === "medium") {
    return "bg-warning-50 text-warning-700 ring-warning-200 dark:bg-warning-500/10 dark:text-warning-300 dark:ring-warning-500/30";
  }
  return "bg-success-50 text-success-700 ring-success-200 dark:bg-success-500/10 dark:text-success-300 dark:ring-success-500/30";
}

function severityTone(severity: TenxAlertItem["severity"]) {
  if (severity === "P1") {
    return "bg-error-50 text-error-700 ring-error-200 dark:bg-error-500/10 dark:text-error-300 dark:ring-error-500/30";
  }
  if (severity === "P2") {
    return "bg-warning-50 text-warning-700 ring-warning-200 dark:bg-warning-500/10 dark:text-warning-300 dark:ring-warning-500/30";
  }
  return "bg-blue-light-50 text-blue-light-700 ring-blue-light-200 dark:bg-blue-light-500/10 dark:text-blue-light-300 dark:ring-blue-light-500/30";
}

function Pill({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${className}`}>
      {children}
    </span>
  );
}

function Panel({
  title,
  icon,
  action,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-theme-xs dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-700 dark:bg-white/[0.06] dark:text-gray-200">
            {icon}
          </span>
          <h2 className="truncate text-base font-semibold text-gray-900 dark:text-white">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function OfflineState({ error }: { error: string | null }) {
  return (
    <div className="rounded-lg border border-warning-200 bg-warning-50 p-4 text-warning-900 dark:border-warning-500/30 dark:bg-warning-500/10 dark:text-warning-100">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
        <div>
          <div className="font-semibold">OpenClaw 数据层未连接</div>
          <p className="mt-1 text-sm leading-6">
            页面不会展示伪造建议。请启动 vnpy.web / TenX API，或把 OpenClaw 分析结果写入现有 TenX 数据接口后刷新。
          </p>
          {error ? <p className="mt-2 break-words text-xs opacity-80">{error}</p> : null}
        </div>
      </div>
    </div>
  );
}

function CandidateCard({ candidate }: { candidate: TenxCandidate }) {
  const marketSlug = toMarketSlug(candidate.market);

  return (
    <Link
      href={`/tenx-hunter/${marketSlug}/research/${candidate.symbol}`}
      className="block rounded-lg border border-gray-200 bg-white p-4 transition hover:border-brand-300 hover:shadow-theme-sm dark:border-gray-800 dark:bg-gray-900/40 dark:hover:border-brand-500/50"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-semibold text-gray-900 dark:text-white">{candidate.symbol}</span>
            <Pill className={candidateTone(candidate)}>{recommendationFor(candidate)}</Pill>
          </div>
          <p className="mt-1 truncate text-sm text-gray-500 dark:text-gray-400">
            {candidate.name} · {candidate.theme}
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold text-gray-900 dark:text-white">{candidate.score}</div>
          <div className={candidate.scoreChange >= 0 ? "text-sm text-success-600" : "text-sm text-error-600"}>
            {candidate.scoreChange >= 0 ? "+" : ""}
            {candidate.scoreChange.toFixed(1)}
          </div>
        </div>
      </div>
      <p className="mt-3 line-clamp-3 text-sm leading-6 text-gray-600 dark:text-gray-300">
        {candidate.whySelected.summary || candidate.thesis}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Pill className={riskTone(candidate.riskLevel)}>{candidate.riskLevel}</Pill>
        <Pill className="bg-gray-50 text-gray-600 ring-gray-200 dark:bg-white/[0.04] dark:text-gray-300 dark:ring-gray-700">
          {candidate.evidenceCount} 条证据
        </Pill>
      </div>
    </Link>
  );
}

function DashboardView({ snapshot, alerts }: { snapshot: TenxWorkspaceSnapshot; alerts: TenxAlertCenter | null }) {
  const metrics = getOverviewMetrics(snapshot);
  const topCandidates = snapshot.candidates.slice(0, 3);
  const urgentAlerts = alerts?.items.slice(0, 2) ?? [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-white/[0.03]">
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400">{metric.label}</div>
            <div className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{metric.value}</div>
            <div className="mt-1 line-clamp-1 text-xs text-gray-500 dark:text-gray-400">{metric.delta}</div>
          </div>
        ))}
      </div>

      <Panel
        title="OpenClaw 今日摘要"
        icon={<BrainCircuit className="h-5 w-5" />}
        action={
          <Link href="/research" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 dark:text-brand-300">
            研究库 <ChevronRight className="h-4 w-4" />
          </Link>
        }
      >
        <div className="space-y-3">
          {topCandidates.length ? (
            topCandidates.map((candidate) => <CandidateCard key={candidate.symbol} candidate={candidate} />)
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">候选池为空，请先同步数据或让 OpenClaw 生成研究结果。</p>
          )}
        </div>
      </Panel>

      <Panel title="需要先看的风险" icon={<Bell className="h-5 w-5" />}>
        <div className="space-y-3">
          {urgentAlerts.length ? (
            urgentAlerts.map((item) => (
              <div key={item.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-semibold text-gray-900 dark:text-white">{item.symbol}</div>
                    <p className="mt-1 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.title}</p>
                  </div>
                  <Pill className={severityTone(item.severity)}>{item.severity}</Pill>
                </div>
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">{item.nextAction}</p>
              </div>
            ))
          ) : (
            <div className="rounded-lg bg-success-50 p-3 text-sm text-success-800 dark:bg-success-500/10 dark:text-success-200">
              暂无高优先级风险提醒。
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}

function PortfolioView({ snapshot }: { snapshot: TenxWorkspaceSnapshot }) {
  const watchlist = snapshot.watchlist;

  return (
    <div className="space-y-4">
      <Panel title="观察池状态" icon={<Wallet className="h-5 w-5" />}>
        <div className="space-y-3">
          {watchlist.length ? (
            watchlist.map((item) => (
              <Link
                key={item.symbol}
                href={`/tenx-hunter/${toMarketSlug(item.market)}/research/${item.symbol}`}
                className="block rounded-lg border border-gray-200 p-4 transition hover:border-brand-300 dark:border-gray-800 dark:hover:border-brand-500/50"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-base font-semibold text-gray-900 dark:text-white">{item.symbol}</span>
                      <Pill className={riskTone(item.riskLevel)}>{item.riskLevel}</Pill>
                    </div>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{item.name}</p>
                  </div>
                  <div className="text-right text-xl font-semibold text-gray-900 dark:text-white">{item.score}</div>
                </div>
                <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.lastEvent}</p>
                <div className="mt-3 flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400">
                  <RefreshCw className="h-4 w-4" />
                  {item.nextCheck}
                </div>
              </Link>
            ))
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">观察池为空。先从研究库把重点标的加入观察池。</p>
          )}
        </div>
      </Panel>

      <Panel title="托管边界" icon={<Lock className="h-5 w-5" />}>
        <div className="grid gap-3 text-sm text-gray-700 dark:text-gray-300 sm:grid-cols-2">
          <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/50">
            <CheckCircle2 className="mb-2 h-5 w-5 text-success-600" />
            OpenClaw 维护知识库、研究卡片、风险提醒。
          </div>
          <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/50">
            <AlertTriangle className="mb-2 h-5 w-5 text-warning-600" />
            默认不授予券商账户权限，不自动下单。
          </div>
        </div>
      </Panel>
    </div>
  );
}

function RiskView({ snapshot, alerts }: { snapshot: TenxWorkspaceSnapshot; alerts: TenxAlertCenter | null }) {
  const highRiskWatchlist = snapshot.watchlist.filter((item) => item.riskLevel === "high");
  const highRiskCandidates = snapshot.candidates.filter((item) => item.riskLevel === "high").slice(0, 4);
  const alertItems = alerts?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="text-xs text-gray-500 dark:text-gray-400">P1/P2</div>
          <div className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">
            {alertItems.filter((item) => item.severity !== "P3").length}
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="text-xs text-gray-500 dark:text-gray-400">高风险观察</div>
          <div className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{highRiskWatchlist.length}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="text-xs text-gray-500 dark:text-gray-400">候选复核</div>
          <div className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{highRiskCandidates.length}</div>
        </div>
      </div>

      <Panel title="风险提醒" icon={<ShieldAlert className="h-5 w-5" />}>
        <div className="space-y-3">
          {alertItems.length ? (
            alertItems.map((item) => (
              <div key={item.id} className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-semibold text-gray-900 dark:text-white">{item.symbol}</div>
                    <p className="mt-1 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.summary}</p>
                  </div>
                  <Pill className={severityTone(item.severity)}>{item.severity}</Pill>
                </div>
                <div className="mt-3 rounded-lg bg-gray-50 p-3 text-sm text-gray-600 dark:bg-gray-900/50 dark:text-gray-300">
                  {item.nextAction}
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">暂无风险提醒。若这是交易日，请确认 OpenClaw 数据任务已经完成。</p>
          )}
        </div>
      </Panel>

      <Panel title="需要人工复核的候选" icon={<Gauge className="h-5 w-5" />}>
        <div className="space-y-3">
          {highRiskCandidates.length ? (
            highRiskCandidates.map((candidate) => <CandidateCard key={candidate.symbol} candidate={candidate} />)
          ) : (
            <div className="rounded-lg bg-success-50 p-3 text-sm text-success-800 dark:bg-success-500/10 dark:text-success-200">
              当前候选池没有高风险标记。
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}

function ThemeCard({ theme }: { theme: TenxTheme }) {
  return (
    <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-semibold text-gray-900 dark:text-white">{theme.name}</div>
          <p className="mt-1 line-clamp-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{theme.driver}</p>
        </div>
        <div className="text-right text-xl font-semibold text-gray-900 dark:text-white">{theme.heat}</div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {theme.relatedSymbols.map((symbol) => (
          <span key={symbol} className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">
            {symbol}
          </span>
        ))}
      </div>
    </div>
  );
}

function ResearchView({ snapshot }: { snapshot: TenxWorkspaceSnapshot }) {
  return (
    <div className="space-y-4">
      <Panel
        title="优先研究"
        icon={<BookOpen className="h-5 w-5" />}
        action={
          <Link href="/tenx-hunter" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 dark:text-brand-300">
            TenX <ChevronRight className="h-4 w-4" />
          </Link>
        }
      >
        <div className="space-y-3">
          {snapshot.candidates.slice(0, 8).map((candidate) => (
            <CandidateCard key={candidate.symbol} candidate={candidate} />
          ))}
        </div>
      </Panel>

      <Panel title="主题知识库" icon={<FileText className="h-5 w-5" />}>
        <div className="space-y-3">
          {snapshot.themes.slice(0, 5).map((theme) => (
            <ThemeCard key={theme.slug} theme={theme} />
          ))}
        </div>
      </Panel>
    </div>
  );
}

function RuntimeStrip({ snapshot }: { snapshot: TenxWorkspaceSnapshot | null }) {
  return (
    <div className="grid grid-cols-3 gap-2 text-xs">
      <div className="rounded-lg bg-white p-3 ring-1 ring-gray-200 dark:bg-white/[0.03] dark:ring-gray-800">
        <Database className="mb-2 h-4 w-4 text-brand-600 dark:text-brand-300" />
        <div className="font-semibold text-gray-900 dark:text-white">数据</div>
        <div className="mt-1 text-gray-500 dark:text-gray-400">{snapshot?.freshness.dataComplete ? "完整" : "待确认"}</div>
      </div>
      <div className="rounded-lg bg-white p-3 ring-1 ring-gray-200 dark:bg-white/[0.03] dark:ring-gray-800">
        <Server className="mb-2 h-4 w-4 text-success-600 dark:text-success-300" />
        <div className="font-semibold text-gray-900 dark:text-white">托管</div>
        <div className="mt-1 text-gray-500 dark:text-gray-400">Mac Studio</div>
      </div>
      <div className="rounded-lg bg-white p-3 ring-1 ring-gray-200 dark:bg-white/[0.03] dark:ring-gray-800">
        <Smartphone className="mb-2 h-4 w-4 text-warning-600 dark:text-warning-300" />
        <div className="font-semibold text-gray-900 dark:text-white">入口</div>
        <div className="mt-1 text-gray-500 dark:text-gray-400">Tailscale</div>
      </div>
    </div>
  );
}

export default async function OpenClawMobileApp({ view, market = defaultOpenClawMarket() }: OpenClawMobileAppProps) {
  const data = await loadMobileData(market);
  const copy = viewCopy[view];
  const snapshot = data.snapshot;
  const updatedAt = formatDateTime(snapshot?.snapshotAt ?? snapshot?.freshness.updatedAt);

  return (
    <main className="mx-auto max-w-3xl pb-24">
      <div className="mb-4 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase text-brand-600 dark:text-brand-300">{copy.kicker}</div>
            <h1 className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">{copy.title}</h1>
            <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">
              OpenClaw 负责研究、复核、沉淀知识；你只在手机上看结论、风险和下一步。
            </p>
          </div>
          <div className="hidden shrink-0 rounded-lg bg-gray-100 p-3 text-gray-700 dark:bg-white/[0.06] dark:text-gray-200 sm:block">
            <Activity className="h-6 w-6" />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Pill className="bg-gray-50 text-gray-700 ring-gray-200 dark:bg-white/[0.04] dark:text-gray-300 dark:ring-gray-700">
            {marketLabel(market)}
          </Pill>
          <Pill className="bg-blue-light-50 text-blue-light-700 ring-blue-light-200 dark:bg-blue-light-500/10 dark:text-blue-light-300 dark:ring-blue-light-500/30">
            {updatedAt}
          </Pill>
          <Pill className="bg-success-50 text-success-700 ring-success-200 dark:bg-success-500/10 dark:text-success-300 dark:ring-success-500/30">
            私有访问
          </Pill>
        </div>
      </div>

      <RuntimeStrip snapshot={snapshot} />

      <div className="mt-4">
        {!snapshot ? (
          <OfflineState error={data.error} />
        ) : view === "dashboard" ? (
          <DashboardView snapshot={snapshot} alerts={data.alerts} />
        ) : view === "portfolio" ? (
          <PortfolioView snapshot={snapshot} />
        ) : view === "risk" ? (
          <RiskView snapshot={snapshot} alerts={data.alerts} />
        ) : (
          <ResearchView snapshot={snapshot} />
        )}
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-gray-200 bg-white/95 px-3 py-2 shadow-theme-lg backdrop-blur dark:border-gray-800 dark:bg-gray-900/95 xl:hidden">
        <div className="mx-auto grid max-w-md grid-cols-4 gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.view === view;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center justify-center rounded-lg px-2 py-2 text-xs font-semibold ${
                  active
                    ? "bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300"
                    : "text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-white/[0.06]"
                }`}
              >
                <Icon className="mb-1 h-5 w-5" />
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </main>
  );
}
