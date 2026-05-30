"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, ArrowRight, BadgeCheck, BrainCircuit, Database, FileUp, Gauge, Search, ShieldCheck, Sparkles, Target } from "lucide-react";
import {
  importInvestmentLedgerCsv,
  loadInvestmentCopilotActionDecisions,
  preflightInvestmentCopilotAction,
  recordInvestmentCopilotActionDecision,
  updateInvestmentCopilotPolicy,
} from "@/components/investment-copilot/api";
import type {
  InvestmentCopilotActionCard,
  InvestmentCopilotActionDecision,
  InvestmentCopilotActionPreflight,
  InvestmentCopilotActionStatus,
  InvestmentCopilotDailyBrief,
  InvestmentCopilotInvestorPolicy,
  InvestmentCopilotSeverity,
  InvestmentCopilotSource,
  InvestmentLedgerImportFormat,
} from "@/components/investment-copilot/types";

function money(value: number) {
  return `$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function pct(value: number | null) {
  if (value === null || !Number.isFinite(value)) {
    return "N/A";
  }
  return `${value.toFixed(1)}%`;
}

function severityTone(severity: InvestmentCopilotSeverity) {
  if (severity === "critical") return "border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200";
  if (severity === "warning") return "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200";
  if (severity === "watch") return "border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-900/60 dark:bg-sky-950/30 dark:text-sky-200";
  return "border-gray-200 bg-gray-50 text-gray-700 dark:border-gray-800 dark:bg-gray-900/60 dark:text-gray-200";
}

function sourceLabel(source: InvestmentCopilotSource) {
  if (source === "portfolio") return "账户";
  if (source === "research") return "研究";
  if (source === "cb_quant") return "可转债";
  return "数据";
}

function sourceIcon(source: InvestmentCopilotSource) {
  if (source === "portfolio") return <ShieldCheck className="h-4 w-4" />;
  if (source === "research") return <BrainCircuit className="h-4 w-4" />;
  if (source === "cb_quant") return <Activity className="h-4 w-4" />;
  return <Database className="h-4 w-4" />;
}

function statusLabel(status: InvestmentCopilotActionStatus) {
  if (status === "accepted") return "已接受";
  if (status === "ignored") return "已忽略";
  if (status === "executed") return "已执行";
  if (status === "reviewed") return "已复盘";
  return "待处理";
}

function statusTone(status: InvestmentCopilotActionStatus) {
  if (status === "accepted") return "bg-sky-100 text-sky-700 dark:bg-sky-950/50 dark:text-sky-200";
  if (status === "ignored") return "bg-gray-100 text-gray-600 dark:bg-gray-900 dark:text-gray-300";
  if (status === "executed") return "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-200";
  if (status === "reviewed") return "bg-violet-100 text-violet-700 dark:bg-violet-950/50 dark:text-violet-200";
  return "bg-white/70 text-gray-700 dark:bg-black/20 dark:text-gray-200";
}

function MetricCard({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: ReactNode;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{label}</p>
        <span className="rounded-lg bg-gray-100 p-2 text-gray-600 dark:bg-gray-900 dark:text-gray-300">{icon}</span>
      </div>
      <p className="mt-4 truncate text-2xl font-semibold text-gray-900 dark:text-white">{value}</p>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{detail}</p>
    </div>
  );
}

function percentInputValue(value: number) {
  return Number.isFinite(value) ? String(Math.round(value * 100)) : "0";
}

function policyFromForm(policy: InvestmentCopilotInvestorPolicy, updates: Partial<InvestmentCopilotInvestorPolicy>) {
  return {
    ...policy,
    ...updates,
  };
}

function parseAmount(raw: string) {
  const parsed = Number(raw.replace(/[$,\s]/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function rawCsvWithOptionalCash(rawRows: string, cashValue: number, format: InvestmentLedgerImportFormat) {
  const trimmed = rawRows.trim();
  if (cashValue <= 0 || format !== "generic_csv") {
    return trimmed;
  }
  const lines = trimmed.split(/\r?\n/);
  const header = lines[0]?.toLowerCase() ?? "";
  const cashRow = `USD,cash,${cashValue},${cashValue}`;
  if (header.includes("symbol") && header.includes("market")) {
    return [lines[0], cashRow, ...lines.slice(1)].join("\n");
  }
  return ["symbol,asset_type,quantity,market_value", cashRow, trimmed].filter(Boolean).join("\n");
}

function ActionCard({
  card,
  onDecision,
  onPreflight,
  preflight,
}: {
  card: InvestmentCopilotActionCard;
  onDecision: (actionId: string, status: InvestmentCopilotActionStatus, note: string) => Promise<void>;
  onPreflight: (actionId: string, intendedAction: string) => Promise<void>;
  preflight?: InvestmentCopilotActionPreflight;
}) {
  const [note, setNote] = useState(card.user_note || card.decision_reason || "");
  const [saving, setSaving] = useState<InvestmentCopilotActionStatus | null>(null);
  const [checking, setChecking] = useState(false);

  const saveDecision = async (status: InvestmentCopilotActionStatus) => {
    setSaving(status);
    try {
      await onDecision(card.id, status, note);
    } finally {
      setSaving(null);
    }
  };

  const runPreflight = async () => {
    setChecking(true);
    try {
      await onPreflight(card.id, note);
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className={`rounded-xl border p-4 ${severityTone(card.severity)}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          {sourceIcon(card.source)}
          <span>{sourceLabel(card.source)}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusTone(card.status)}`}>{statusLabel(card.status)}</span>
          <span className="rounded-full bg-white/70 px-2.5 py-1 text-xs font-semibold dark:bg-black/20">P{card.priority}</span>
        </div>
      </div>
      <h3 className="mt-3 text-base font-semibold">{card.title}</h3>
      <p className="mt-2 text-sm leading-6 opacity-90">{card.rationale}</p>
      <div className="mt-3 rounded-lg bg-white/65 p-3 text-sm font-medium dark:bg-black/20">{card.suggested_action}</div>
      {card.evidence.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {card.evidence.filter(Boolean).slice(0, 3).map((item) => (
            <span key={item} className="rounded-full bg-white/70 px-2.5 py-1 text-xs dark:bg-black/20">
              {item}
            </span>
          ))}
        </div>
      ) : null}
      {card.href ? (
        <Link href={card.href} className="mt-4 inline-flex items-center gap-2 text-sm font-semibold">
          打开处理 <ArrowRight className="h-4 w-4" />
        </Link>
      ) : null}
      <div className="mt-4 rounded-lg bg-white/55 p-3 dark:bg-black/15">
        <label className="text-xs font-semibold opacity-80" htmlFor={`note-${card.id}`}>
          决策备注
        </label>
        <textarea
          id={`note-${card.id}`}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          className="mt-2 min-h-16 w-full rounded-lg border border-white/70 bg-white/70 px-3 py-2 text-sm outline-none focus:border-brand-300 dark:border-white/10 dark:bg-black/20"
          placeholder="记录为什么接受、忽略或执行这条建议..."
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={runPreflight}
            disabled={checking || saving !== null}
            className="rounded-lg bg-gray-900 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-200"
          >
            {checking ? "预检中..." : "执行预检"}
          </button>
          {([
            ["accepted", "接受"],
            ["ignored", "忽略"],
            ["executed", "已执行"],
            ["reviewed", "复盘"],
          ] as [InvestmentCopilotActionStatus, string][]).map(([status, label]) => (
            <button
              key={status}
              type="button"
              onClick={() => saveDecision(status)}
              disabled={saving !== null}
              className="rounded-lg bg-white/80 px-3 py-2 text-xs font-semibold shadow-sm transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60 dark:bg-black/20 dark:hover:bg-black/30"
            >
              {saving === status ? "保存中..." : label}
            </button>
          ))}
        </div>
        {preflight ? (
          <div className={`mt-3 rounded-lg border p-3 text-xs ${preflight.allowed ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-200" : "border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200"}`}>
            <div className="flex items-center justify-between gap-3 font-semibold">
              <span>{preflight.allowed ? "预检通过" : "预检阻断"}</span>
              <span>{preflight.generated_at}</span>
            </div>
            {preflight.blockers.length ? (
              <ul className="mt-2 list-inside list-disc space-y-1">
                {preflight.blockers.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
            {preflight.warnings.length ? (
              <div className="mt-2 space-y-1">
                {preflight.warnings.map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
            ) : null}
            <p className="mt-2 opacity-75">Checklist {preflight.checklist.length} 项</p>
          </div>
        ) : null}
        {card.decided_at ? <p className="mt-2 text-xs opacity-70">上次记录：{card.decided_at}</p> : null}
      </div>
    </div>
  );
}

export default function InvestmentCopilotDashboard({ brief }: { brief: InvestmentCopilotDailyBrief }) {
  const [cards, setCards] = useState(brief.action_cards);
  const [ledger, setLedger] = useState(brief.ledger);
  const [reconciliation, setReconciliation] = useState(brief.reconciliation);
  const [preflights, setPreflights] = useState<Record<string, InvestmentCopilotActionPreflight>>({});
  const [decisionJournal, setDecisionJournal] = useState<InvestmentCopilotActionDecision[]>(
    brief.action_cards
      .filter((card) => card.status !== "pending")
      .map((card) => ({
        action_id: card.id,
        status: card.status,
        user_note: card.user_note,
        decision_reason: card.decision_reason,
        updated_at: card.decided_at ?? brief.generated_at,
      })),
  );
  const [policy, setPolicy] = useState(brief.investor_policy);
  const [savingPolicy, setSavingPolicy] = useState(false);
  const [policySavedAt, setPolicySavedAt] = useState<string | null>(brief.investor_policy.updated_at);
  const [ledgerAccountId, setLedgerAccountId] = useState("main");
  const [ledgerAccountName, setLedgerAccountName] = useState("Main Brokerage");
  const [ledgerCashValue, setLedgerCashValue] = useState("");
  const [ledgerRows, setLedgerRows] = useState("symbol,asset_type,quantity,market_value\nNVDA,equity,3,3000\nAMD260116C200,option,1,500");
  const [ledgerImportFormat, setLedgerImportFormat] = useState<InvestmentLedgerImportFormat>("generic_csv");
  const [ledgerImportError, setLedgerImportError] = useState("");
  const [savingLedger, setSavingLedger] = useState(false);
  const [journalSearch, setJournalSearch] = useState("");
  const [journalStatus, setJournalStatus] = useState<InvestmentCopilotActionStatus | "all">("all");
  const marginRatio = brief.portfolio.margin_limit > 0 ? brief.portfolio.margin_used / brief.portfolio.margin_limit : 0;
  const healthySources = brief.source_health.filter((item) => item.ok).length;
  const policyRules = useMemo(
    () => [
      `现金底线 ${(policy.cash_floor_ratio * 100).toFixed(0)}%`,
      `单股上限 ${(policy.max_single_stock_ratio * 100).toFixed(0)}%`,
      `期权上限 ${(policy.max_options_ratio * 100).toFixed(0)}%`,
      `保证金上限 ${(policy.max_margin_ratio * 100).toFixed(0)}%`,
    ],
    [policy],
  );
  const filteredDecisionJournal = useMemo(() => {
    const query = journalSearch.trim().toLowerCase();
    return decisionJournal.filter((item) => {
      const statusMatch = journalStatus === "all" || item.status === journalStatus;
      const queryMatch =
        !query ||
        item.action_id.toLowerCase().includes(query) ||
        item.user_note.toLowerCase().includes(query) ||
        item.decision_reason.toLowerCase().includes(query);
      return statusMatch && queryMatch;
    });
  }, [decisionJournal, journalSearch, journalStatus]);

  useEffect(() => {
    let mounted = true;
    loadInvestmentCopilotActionDecisions()
      .then((items) => {
        if (mounted) {
          setDecisionJournal(items);
        }
      })
      .catch(() => {
        // The action cards still show embedded decision state if the journal endpoint is unavailable.
      });
    return () => {
      mounted = false;
    };
  }, []);

  const updatePolicyRatio = (key: "cash_floor_ratio" | "max_single_stock_ratio" | "max_options_ratio" | "max_margin_ratio", rawValue: string) => {
    const parsed = Number(rawValue);
    const normalized = Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) / 100 : 0;
    setPolicy((current) => policyFromForm(current, { [key]: normalized }));
  };

  const savePolicy = async () => {
    setSavingPolicy(true);
    try {
      const saved = await updateInvestmentCopilotPolicy(policy);
      setPolicy(saved);
      setPolicySavedAt(saved.updated_at);
    } finally {
      setSavingPolicy(false);
    }
  };

  const handleDecision = async (actionId: string, status: InvestmentCopilotActionStatus, note: string) => {
    const decision = await recordInvestmentCopilotActionDecision(
      actionId,
      {
        status,
        user_note: note,
        decision_reason: note,
      },
      brief.research.market || "US",
    );
    setDecisionJournal((current) => [decision, ...current.filter((item) => item.action_id !== decision.action_id)]);
    setCards((current) =>
      current.map((card) =>
        card.id === actionId
          ? {
              ...card,
              status: decision.status,
              user_note: decision.user_note,
              decision_reason: decision.decision_reason,
              decided_at: decision.updated_at,
            }
          : card,
      ),
    );
  };

  const handlePreflight = async (actionId: string, intendedAction: string) => {
    const preflight = await preflightInvestmentCopilotAction(actionId, {
      market: brief.research.market || "US",
      intended_action: intendedAction,
      acknowledged_human_confirmation: false,
    });
    setPreflights((current) => ({ ...current, [actionId]: preflight }));
  };

  const handleLedgerBootstrap = async () => {
    const accountId = ledgerAccountId.trim();
    const accountName = ledgerAccountName.trim();
    if (!accountId || !accountName) {
      setLedgerImportError("请先填写账户 ID 和账户名称。");
      return;
    }

    const rawCsv = rawCsvWithOptionalCash(ledgerRows, parseAmount(ledgerCashValue), ledgerImportFormat);
    if (!rawCsv) {
      setLedgerImportError("至少录入一段 CSV 持仓数据。");
      return;
    }

    setSavingLedger(true);
    setLedgerImportError("");
    try {
      const response = await importInvestmentLedgerCsv({
        account: {
          account_id: accountId,
          name: accountName,
          account_type: "brokerage",
          currency: "USD",
          base_currency: "USD",
          active: true,
        },
        raw_csv: rawCsv,
        format: ledgerImportFormat,
        default_currency: "USD",
      });
      setLedger(response.summary);
      setReconciliation({
        ok: false,
        summary: "已写入账本，刷新后会按最新 Smart Allocation 快照重新对账。",
        total_equity_delta: response.summary.total_equity - brief.portfolio.total_equity,
        cash_delta: response.summary.cash_value - brief.portfolio.cash_value,
        options_delta: response.summary.options_value - brief.portfolio.options_value,
        delta_ratio: brief.portfolio.total_equity > 0 ? Math.abs(response.summary.total_equity - brief.portfolio.total_equity) / brief.portfolio.total_equity : 0,
        tolerance_ratio: brief.reconciliation.tolerance_ratio,
      });
      setCards((current) => current.filter((card) => card.id !== "ledger:bootstrap"));
      if (response.rejected_row_count > 0) {
        setLedgerImportError(`已导入 ${response.imported_holding_count} 条，跳过 ${response.rejected_row_count} 条：${response.errors[0]?.message ?? "存在无法解析的行"}`);
      }
    } catch (error) {
      setLedgerImportError(error instanceof Error ? error.message : "账本初始化失败。");
    } finally {
      setSavingLedger(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2 text-sm font-semibold text-brand-600 dark:text-brand-300">
              <Sparkles className="h-4 w-4" />
              AI 原生投资驾驶舱
            </div>
            <h1 className="mt-3 text-2xl font-semibold text-gray-900 dark:text-white md:text-3xl">{brief.headline}</h1>
            <p className="mt-3 text-sm leading-6 text-gray-500 dark:text-gray-400">
              汇总账户风控、研究候选和可转债策略状态，默认生成行动建议单；所有交易动作仍需要人工确认。
            </p>
          </div>
          <div className="rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/70 dark:text-gray-300">
            生成时间：{brief.generated_at}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="账户健康度" value={`${brief.portfolio.health_score}`} detail={`风险等级 ${brief.portfolio.risk_level}`} icon={<Gauge className="h-5 w-5" />} />
        <MetricCard label="总权益" value={money(ledger.total_equity || brief.portfolio.total_equity)} detail={`账本账户 ${ledger.account_count} 个`} icon={<Target className="h-5 w-5" />} />
        <MetricCard label="保证金占用" value={`${(marginRatio * 100).toFixed(1)}%`} detail={`${money(brief.portfolio.margin_used)} / ${money(brief.portfolio.margin_limit)}`} icon={<ShieldCheck className="h-5 w-5" />} />
        <MetricCard label="数据源" value={`${healthySources}/${brief.source_health.length}`} detail="账户、研究、策略链路" icon={<Database className="h-5 w-5" />} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">今日行动卡片</h2>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">按优先级排序，先处理风控和数据质量。</p>
            </div>
            <BadgeCheck className="h-5 w-5 text-emerald-500" />
          </div>
          <div className="mt-5 space-y-4">
            {cards.map((card) => (
              <ActionCard key={card.id} card={card} onDecision={handleDecision} onPreflight={handlePreflight} preflight={preflights[card.id]} />
            ))}
          </div>
        </section>

        <div className="space-y-6">
          <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Portfolio Ledger</h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              统一账户账本 · {ledger.updated_at ?? "尚未初始化"}
            </p>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
                <p className="text-gray-500 dark:text-gray-400">账本权益</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(ledger.total_equity)}</p>
              </div>
              <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
                <p className="text-gray-500 dark:text-gray-400">现金</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(ledger.cash_value)}</p>
              </div>
              <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
                <p className="text-gray-500 dark:text-gray-400">持仓条目</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{ledger.holding_count}</p>
              </div>
              <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
                <p className="text-gray-500 dark:text-gray-400">最大持仓</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{(ledger.largest_position_weight * 100).toFixed(1)}%</p>
              </div>
            </div>
            <div className={`mt-4 rounded-xl border p-3 text-sm ${reconciliation.ok ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-200" : "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200"}`}>
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold">账本对账</span>
                <span>{(reconciliation.delta_ratio * 100).toFixed(1)}%</span>
              </div>
              <p className="mt-2 leading-6">{reconciliation.summary}</p>
              <div className="mt-2 flex flex-wrap gap-2 text-xs">
                <span>权益差 {money(reconciliation.total_equity_delta)}</span>
                <span>现金差 {money(reconciliation.cash_delta)}</span>
                <span>期权差 {money(reconciliation.options_delta)}</span>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {ledger.top_positions.length ? ledger.top_positions.slice(0, 3).map((item) => (
                <div key={`${item.account_id}-${item.symbol}-${item.asset_type}`} className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 px-3 py-2 text-sm dark:border-gray-800">
                  <span className="font-semibold text-gray-900 dark:text-white">{item.symbol}</span>
                  <span className="text-gray-500 dark:text-gray-400">{money(item.market_value)} · {(item.weight * 100).toFixed(1)}%</span>
                </div>
              )) : (
                <p className="rounded-xl bg-gray-50 p-3 text-sm text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">账本还没有持仓。先录入账户和持仓，驾驶舱会从这里读取资产事实。</p>
              )}
            </div>
            <div className="mt-5 rounded-xl border border-dashed border-gray-300 p-4 dark:border-gray-700">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                <FileUp className="h-4 w-4" />
                快速初始化账本
              </div>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  账户 ID
                  <input
                    value={ledgerAccountId}
                    onChange={(event) => setLedgerAccountId(event.target.value)}
                    className="mt-1 h-10 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm text-gray-900 outline-none focus:border-brand-300 dark:border-gray-800 dark:bg-gray-900/60 dark:text-white"
                  />
                </label>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  账户名称
                  <input
                    value={ledgerAccountName}
                    onChange={(event) => setLedgerAccountName(event.target.value)}
                    className="mt-1 h-10 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm text-gray-900 outline-none focus:border-brand-300 dark:border-gray-800 dark:bg-gray-900/60 dark:text-white"
                  />
                </label>
              </div>
              <label className="mt-3 block text-sm font-medium text-gray-700 dark:text-gray-300">
                现金余额
                <input
                  value={ledgerCashValue}
                  onChange={(event) => setLedgerCashValue(event.target.value)}
                  inputMode="decimal"
                  className="mt-1 h-10 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm text-gray-900 outline-none focus:border-brand-300 dark:border-gray-800 dark:bg-gray-900/60 dark:text-white"
                  placeholder="10000"
                />
              </label>
              <label className="mt-3 block text-sm font-medium text-gray-700 dark:text-gray-300">
                导入格式
                <select
                  value={ledgerImportFormat}
                  onChange={(event) => setLedgerImportFormat(event.target.value as InvestmentLedgerImportFormat)}
                  className="mt-1 h-10 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm text-gray-900 outline-none focus:border-brand-300 dark:border-gray-800 dark:bg-gray-900/60 dark:text-white"
                >
                  <option value="generic_csv">Generic CSV</option>
                  <option value="schwab_positions">Schwab Positions</option>
                  <option value="ibkr_positions">IBKR Positions</option>
                </select>
              </label>
              <label className="mt-3 block text-sm font-medium text-gray-700 dark:text-gray-300">
                持仓导入
                <textarea
                  value={ledgerRows}
                  onChange={(event) => setLedgerRows(event.target.value)}
                  className="mt-1 min-h-24 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 font-mono text-sm text-gray-900 outline-none focus:border-brand-300 dark:border-gray-800 dark:bg-gray-900/60 dark:text-white"
                  placeholder="NVDA,equity,3,3000"
                />
              </label>
              <label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-700 transition hover:border-brand-300 dark:border-gray-800 dark:text-gray-300">
                <FileUp className="h-4 w-4" />
                读取 CSV 文件
                <input
                  type="file"
                  accept=".csv,text/csv,text/plain"
                  className="sr-only"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (!file) {
                      return;
                    }
                    file
                      .text()
                      .then((text) => setLedgerRows(text))
                      .catch(() => setLedgerImportError("CSV 文件读取失败。"));
                  }}
                />
              </label>
              {ledgerImportError ? <p className="mt-2 text-sm text-red-600 dark:text-red-300">{ledgerImportError}</p> : null}
              <button
                type="button"
                onClick={handleLedgerBootstrap}
                disabled={savingLedger}
                className="mt-3 inline-flex items-center gap-2 rounded-lg bg-gray-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-200"
              >
                <FileUp className="h-4 w-4" />
                {savingLedger ? "写入中..." : "写入账本"}
              </button>
            </div>
          </section>

          <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">研究雷达</h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {brief.research.market} · {brief.research.universe || "暂无 universe"}
            </p>
            <div className="mt-4 space-y-3">
              {brief.research.top_candidates.length ? brief.research.top_candidates.map((item) => (
                <Link key={item.symbol} href={`/tenx-hunter/${brief.research.market.toLowerCase()}/research/${item.symbol}`} className="block rounded-xl border border-gray-200 p-3 hover:border-brand-300 dark:border-gray-800 dark:hover:border-brand-500">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-gray-900 dark:text-white">{item.symbol}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">{item.name}</p>
                    </div>
                    <span className="text-xl font-semibold text-gray-900 dark:text-white">{item.score}</span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm text-gray-600 dark:text-gray-300">{item.thesis}</p>
                </Link>
              )) : (
                <p className="rounded-xl bg-gray-50 p-3 text-sm text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">暂无研究候选，请检查 TenX 数据链路。</p>
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">可转债策略状态</h2>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
                <p className="text-gray-500 dark:text-gray-400">最新交易日</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{brief.cb_quant.latest_trade_date ?? "N/A"}</p>
              </div>
              <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
                <p className="text-gray-500 dark:text-gray-400">债券数</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{brief.cb_quant.latest_bond_count}</p>
              </div>
              <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
                <p className="text-gray-500 dark:text-gray-400">运行任务</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{brief.cb_quant.running_jobs + brief.cb_quant.queued_jobs}</p>
              </div>
              <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
                <p className="text-gray-500 dark:text-gray-400">榜首 CAGR</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{pct(brief.cb_quant.top_cagr)}</p>
              </div>
            </div>
          </section>
        </div>
      </div>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">决策硬规则</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {policyRules.map((rule) => (
              <span key={rule} className="rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-700 dark:bg-gray-900 dark:text-gray-300">
                {rule}
              </span>
            ))}
          </div>
          <div className="mt-4 space-y-3">
            {brief.decision_policy.hard_rules.map((rule) => (
              <div key={rule} className="flex gap-3 text-sm text-gray-600 dark:text-gray-300">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                <span>{rule}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Investor Policy</h2>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">这是 AI 副驾的边界，不是建议文本的小装饰。</p>
            </div>
            <button
              type="button"
              onClick={savePolicy}
              disabled={savingPolicy}
              className="rounded-lg bg-brand-500 px-3 py-2 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {savingPolicy ? "保存中..." : "保存政策"}
            </button>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            {([
              ["cash_floor_ratio", "现金底线"],
              ["max_single_stock_ratio", "单股上限"],
              ["max_options_ratio", "期权上限"],
              ["max_margin_ratio", "保证金上限"],
            ] as const).map(([key, label]) => (
              <label key={key} className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {label}
                <div className="mt-1 flex items-center rounded-lg border border-gray-200 bg-gray-50 px-3 dark:border-gray-800 dark:bg-gray-900/60">
                  <input
                    value={percentInputValue(policy[key])}
                    onChange={(event) => updatePolicyRatio(key, event.target.value)}
                    className="h-10 w-full bg-transparent text-sm text-gray-900 outline-none dark:text-white"
                    inputMode="numeric"
                  />
                  <span className="text-sm text-gray-500">%</span>
                </div>
              </label>
            ))}
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {([
              ["require_human_confirmation", "所有行动需要人工确认"],
              ["allow_leaps", "允许 LEAPS"],
              ["allow_wheel", "允许 Wheel"],
              ["allow_cb_quant", "允许可转债策略"],
            ] as const).map(([key, label]) => (
              <label key={key} className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 px-3 py-2 text-sm text-gray-700 dark:border-gray-800 dark:text-gray-300">
                <span>{label}</span>
                <input
                  type="checkbox"
                  checked={policy[key]}
                  onChange={(event) => setPolicy((current) => policyFromForm(current, { [key]: event.target.checked }))}
                  className="h-4 w-4"
                />
              </label>
            ))}
          </div>
          <label className="mt-4 block text-sm font-medium text-gray-700 dark:text-gray-300">
            禁买清单
            <input
              value={policy.forbidden_symbols.join(", ")}
              onChange={(event) =>
                setPolicy((current) =>
                  policyFromForm(current, {
                    forbidden_symbols: event.target.value
                      .split(",")
                      .map((item) => item.trim().toUpperCase())
                      .filter(Boolean),
                  }),
                )
              }
              className="mt-1 h-10 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm text-gray-900 outline-none focus:border-brand-300 dark:border-gray-800 dark:bg-gray-900/60 dark:text-white"
              placeholder="NVDA, TSLA"
            />
          </label>
          <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
            {policySavedAt ? `上次保存：${policySavedAt}` : "尚未保存自定义政策"}
          </p>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">决策日志</h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">接受、忽略、执行和复盘都会沉淀在这里，供后续 AI 建议引用。</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_150px]">
            <label className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 dark:border-gray-800 dark:bg-gray-900/60">
              <Search className="h-4 w-4 text-gray-400" />
              <input
                value={journalSearch}
                onChange={(event) => setJournalSearch(event.target.value)}
                className="h-10 w-full bg-transparent text-sm text-gray-900 outline-none dark:text-white"
                placeholder="搜索 action 或备注"
              />
            </label>
            <select
              value={journalStatus}
              onChange={(event) => setJournalStatus(event.target.value as InvestmentCopilotActionStatus | "all")}
              className="h-10 rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm text-gray-900 outline-none dark:border-gray-800 dark:bg-gray-900/60 dark:text-white"
            >
              <option value="all">全部状态</option>
              <option value="accepted">已接受</option>
              <option value="ignored">已忽略</option>
              <option value="executed">已执行</option>
              <option value="reviewed">已复盘</option>
            </select>
          </div>
          <div className="mt-4 space-y-3">
            {filteredDecisionJournal.length ? filteredDecisionJournal.slice(0, 8).map((item) => (
              <div key={`${item.action_id}-${item.updated_at}`} className="rounded-xl border border-gray-200 p-3 text-sm dark:border-gray-800">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold text-gray-900 dark:text-white">{item.action_id}</span>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusTone(item.status)}`}>{statusLabel(item.status)}</span>
                </div>
                <p className="mt-2 text-gray-600 dark:text-gray-300">{item.user_note || item.decision_reason || "没有备注。"}</p>
                <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{item.updated_at}</p>
              </div>
            )) : (
              <p className="rounded-xl bg-gray-50 p-3 text-sm text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">没有匹配的决策记录。</p>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">数据源状态</h2>
          <div className="mt-4 space-y-3">
            {brief.source_health.map((item) => (
              <div key={item.source} className="flex items-start gap-3 rounded-xl bg-gray-50 p-3 text-sm dark:bg-gray-900/60">
                {item.ok ? <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />}
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">{item.source}</p>
                  <p className="mt-1 text-gray-600 dark:text-gray-300">{item.summary}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
