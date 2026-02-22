import { strategyTemplates, type StrategyTemplateRow } from "@/components/cb-quant/mockData";

export type CandidateWindow = "full" | "3y" | "1y";

export type StoredTemplateConfig = {
  templateId: string;
  templateName: string;
  factorKeys: string[];
  expressionDraft: string;
  updatedAt: string;
};

export type StoredCandidateRow = {
  rank: number;
  templateId: string;
  template: string;
  comboId: string;
  estCombos: number;
  passRate: number;
  window: CandidateWindow;
  runId: string;
  generatedAt: string;
};

export type StoredCandidateRun = {
  runId: string;
  templateId: string;
  templateName: string;
  status: "finished";
  createdAt: string;
  finishedAt: string;
  rows: StoredCandidateRow[];
  summary: {
    factorCount: number;
    expressionLength: number;
  };
};

const TEMPLATE_CONFIG_KEY = "cbq_template_config_v1";
const CANDIDATE_RUN_KEY = "cbq_candidate_runs_v1";
const TEMPLATE_LIST_KEY = "cbq_templates_v1";

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function safeParse<T>(value: string | null, fallback: T): T {
  if (!value) {
    return fallback;
  }
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function hashString(input: string): number {
  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash * 31 + input.charCodeAt(i)) >>> 0;
  }
  return hash;
}

function makeRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function round1(v: number): number {
  return Math.round(v * 10) / 10;
}

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

export function listTemplateConfigs(): StoredTemplateConfig[] {
  if (!canUseStorage()) {
    return [];
  }
  return safeParse<StoredTemplateConfig[]>(window.localStorage.getItem(TEMPLATE_CONFIG_KEY), []);
}

export function listTemplates(): StrategyTemplateRow[] {
  if (!canUseStorage()) {
    return strategyTemplates;
  }
  const raw = window.localStorage.getItem(TEMPLATE_LIST_KEY);
  if (!raw) {
    window.localStorage.setItem(TEMPLATE_LIST_KEY, JSON.stringify(strategyTemplates));
    return strategyTemplates;
  }
  const parsed = safeParse<StrategyTemplateRow[]>(raw, strategyTemplates);
  if (!parsed.length) {
    return strategyTemplates;
  }
  return parsed;
}

export function saveTemplates(templates: StrategyTemplateRow[]): void {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.setItem(TEMPLATE_LIST_KEY, JSON.stringify(templates));
}

export function getTemplateById(templateId: string): StrategyTemplateRow | null {
  return listTemplates().find((item) => item.id === templateId) ?? null;
}

export function upsertTemplate(template: StrategyTemplateRow): void {
  const templates = listTemplates();
  const index = templates.findIndex((item) => item.id === template.id);
  if (index >= 0) {
    templates[index] = template;
  } else {
    templates.unshift(template);
  }
  saveTemplates(templates);
}

export function deleteTemplate(templateId: string): void {
  const templates = listTemplates().filter((item) => item.id !== templateId);
  saveTemplates(templates);
}

export function getTemplateConfig(templateId: string): StoredTemplateConfig | null {
  const all = listTemplateConfigs();
  return all.find((item) => item.templateId === templateId) ?? null;
}

export function upsertTemplateConfig(config: StoredTemplateConfig): void {
  if (!canUseStorage()) {
    return;
  }
  const all = listTemplateConfigs();
  const idx = all.findIndex((item) => item.templateId === config.templateId);
  if (idx >= 0) {
    all[idx] = config;
  } else {
    all.unshift(config);
  }
  window.localStorage.setItem(TEMPLATE_CONFIG_KEY, JSON.stringify(all));
}

export function listCandidateRuns(): StoredCandidateRun[] {
  if (!canUseStorage()) {
    return [];
  }
  return safeParse<StoredCandidateRun[]>(window.localStorage.getItem(CANDIDATE_RUN_KEY), []);
}

export function saveCandidateRun(run: StoredCandidateRun): void {
  if (!canUseStorage()) {
    return;
  }
  const all = listCandidateRuns();
  all.unshift(run);
  window.localStorage.setItem(CANDIDATE_RUN_KEY, JSON.stringify(all.slice(0, 60)));
}

export function getLatestCandidateRun(templateId: string): StoredCandidateRun | null {
  return listCandidateRuns().find((item) => item.templateId === templateId) ?? null;
}

export function getPreviewCandidateRows(templateId?: string): StoredCandidateRow[] {
  const runs = listCandidateRuns();
  if (!runs.length) {
    return [];
  }

  if (templateId && templateId !== "all") {
    return runs
      .filter((run) => run.templateId === templateId)
      .flatMap((run) => run.rows)
      .sort((a, b) => b.passRate - a.passRate)
      .map((row, idx) => ({ ...row, rank: idx + 1 }));
  }

  const latestRunByTemplate = new Map<string, StoredCandidateRun>();
  runs.forEach((run) => {
    if (!latestRunByTemplate.has(run.templateId)) {
      latestRunByTemplate.set(run.templateId, run);
    }
  });

  return Array.from(latestRunByTemplate.values())
    .flatMap((run) => run.rows)
    .sort((a, b) => b.passRate - a.passRate)
    .map((row, idx) => ({ ...row, rank: idx + 1 }));
}

export function createMockCandidateRun(input: {
  templateId: string;
  templateName: string;
  factorCount: number;
  expressionDraft: string;
}): StoredCandidateRun {
  const now = new Date();
  const nowIso = now.toISOString();
  const nowCompact = nowIso.replace(/[-:TZ.]/g, "").slice(0, 12);
  const runId = `RUN-${input.templateId}-${nowCompact}`;
  const seed = hashString(`${input.templateId}|${input.factorCount}|${input.expressionDraft}|${nowIso}`);
  const random = makeRandom(seed);
  const windows: CandidateWindow[] = ["full", "3y", "1y"];

  const baseCombos = Math.max(
    6000,
    Math.round(input.factorCount * 4200 + input.expressionDraft.length * 35 + 5000 + random() * 2000),
  );
  const rows: StoredCandidateRow[] = [];

  for (let i = 0; i < 12; i += 1) {
    const window = windows[i % windows.length];
    const comboSeed = Math.floor(100000 + random() * 899999);
    const passRateRaw = 4.5 + input.factorCount * 0.18 + (window === "3y" ? 0.8 : window === "1y" ? -0.2 : 0) + random() * 4.5;
    rows.push({
      rank: i + 1,
      templateId: input.templateId,
      template: input.templateName,
      comboId: `CMB-${comboSeed}`,
      estCombos: Math.round(baseCombos * (0.6 + random() * 0.9)),
      passRate: round1(clamp(passRateRaw, 1.2, 28)),
      window,
      runId,
      generatedAt: now.toISOString().slice(0, 19).replace("T", " "),
    });
  }

  const rankedRows = rows
    .sort((a, b) => b.passRate - a.passRate)
    .map((row, idx) => ({ ...row, rank: idx + 1 }));

  return {
    runId,
    templateId: input.templateId,
    templateName: input.templateName,
    status: "finished",
    createdAt: nowIso,
    finishedAt: new Date().toISOString(),
    rows: rankedRows,
    summary: {
      factorCount: input.factorCount,
      expressionLength: input.expressionDraft.length,
    },
  };
}
