"use client";

import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import WorkbenchHeader from "@/components/cb-quant/WorkbenchHeader";
import { TableCell, TableRow } from "@/components/ui/table";
import { AlertIcon } from "@/icons/index";
import React, { useEffect, useMemo, useRef, useState } from "react";

type StockRow = {
  code: string;
  name: string;
  now: number;
  changePct: number;
  volumeHand: number;
  amountWan: number;
  turnover: number;
  bid1: number;
  ask1: number;
  high: number;
  low: number;
  pe: number;
  pb: number;
  source: "tencent" | "sina";
  updateTime: string;
};

type BondRow = {
  bondId: string;
  bondName: string;
  price: number;
  increaseRt: string;
  premiumRt: string;
  convertValue: number;
  dblow: number;
  volumeWan: number;
  currIssAmtYi: number;
  rating: "AA" | "AA+" | "AAA";
  stockId: string;
  stockName: string;
  source: "jsl";
  updateTime: string;
};

type LineageRow = {
  field: string;
  meaning: string;
  stockSource: string;
  bondSource: string;
  usage: string;
  domain: "stock" | "bond" | "common";
};

const stockSnapshot: StockRow[] = [
  { code: "sz000001", name: "平安银行", now: 12.54, changePct: 1.21, volumeHand: 482356, amountWan: 60537, turnover: 1.76, bid1: 12.53, ask1: 12.54, high: 12.61, low: 12.38, pe: 5.88, pb: 0.62, source: "tencent", updateTime: "09:34:12" },
  { code: "sh600036", name: "招商银行", now: 34.87, changePct: 0.92, volumeHand: 216778, amountWan: 75318, turnover: 0.84, bid1: 34.86, ask1: 34.87, high: 35.06, low: 34.51, pe: 6.21, pb: 0.97, source: "tencent", updateTime: "09:34:12" },
  { code: "sz300750", name: "宁德时代", now: 186.2, changePct: -0.63, volumeHand: 98543, amountWan: 183760, turnover: 0.53, bid1: 186.19, ask1: 186.2, high: 188.4, low: 184.7, pe: 20.15, pb: 4.78, source: "tencent", updateTime: "09:34:12" },
  { code: "sh601318", name: "中国平安", now: 45.36, changePct: 0.41, volumeHand: 267522, amountWan: 121660, turnover: 0.77, bid1: 45.35, ask1: 45.36, high: 45.62, low: 44.98, pe: 7.05, pb: 0.86, source: "tencent", updateTime: "09:34:13" },
  { code: "sz000333", name: "美的集团", now: 63.42, changePct: 0.56, volumeHand: 131889, amountWan: 83702, turnover: 0.59, bid1: 63.41, ask1: 63.42, high: 63.88, low: 62.93, pe: 12.11, pb: 2.73, source: "tencent", updateTime: "09:34:13" },
  { code: "sh600519", name: "贵州茅台", now: 1658.5, changePct: -0.22, volumeHand: 9882, amountWan: 163885, turnover: 0.08, bid1: 1658.4, ask1: 1658.5, high: 1667.0, low: 1649.1, pe: 24.9, pb: 8.6, source: "sina", updateTime: "09:34:09" },
  { code: "sh601012", name: "隆基绿能", now: 24.18, changePct: -1.14, volumeHand: 319554, amountWan: 77466, turnover: 1.26, bid1: 24.17, ask1: 24.18, high: 24.55, low: 24.03, pe: 13.7, pb: 1.78, source: "sina", updateTime: "09:34:09" },
  { code: "sz002594", name: "比亚迪", now: 232.86, changePct: 1.48, volumeHand: 86550, amountWan: 201444, turnover: 0.89, bid1: 232.85, ask1: 232.86, high: 234.2, low: 229.5, pe: 25.6, pb: 5.05, source: "tencent", updateTime: "09:34:13" },
  { code: "sh601166", name: "兴业银行", now: 16.85, changePct: 0.36, volumeHand: 199806, amountWan: 33555, turnover: 0.96, bid1: 16.84, ask1: 16.85, high: 16.92, low: 16.71, pe: 4.96, pb: 0.56, source: "sina", updateTime: "09:34:08" },
  { code: "sz000651", name: "格力电器", now: 35.21, changePct: -0.31, volumeHand: 132448, amountWan: 46625, turnover: 0.73, bid1: 35.2, ask1: 35.21, high: 35.48, low: 35.02, pe: 7.62, pb: 1.8, source: "tencent", updateTime: "09:34:13" },
  { code: "sh688981", name: "中芯国际", now: 48.66, changePct: 2.15, volumeHand: 75660, amountWan: 36798, turnover: 1.11, bid1: 48.65, ask1: 48.66, high: 48.99, low: 47.8, pe: 42.2, pb: 3.54, source: "sina", updateTime: "09:34:08" },
  { code: "sz300059", name: "东方财富", now: 13.77, changePct: -0.86, volumeHand: 405990, amountWan: 55904, turnover: 2.1, bid1: 13.76, ask1: 13.77, high: 13.96, low: 13.72, pe: 28.8, pb: 2.65, source: "tencent", updateTime: "09:34:13" },
];

const bondSnapshot: BondRow[] = [
  { bondId: "113063", bondName: "赛轮转债", price: 128.45, increaseRt: "0.82%", premiumRt: "14.32%", convertValue: 112.36, dblow: 142.77, volumeWan: 32688.2, currIssAmtYi: 19.86, rating: "AA", stockId: "601058", stockName: "赛轮轮胎", source: "jsl", updateTime: "09:34:05" },
  { bondId: "123107", bondName: "温氏转债", price: 121.12, increaseRt: "-0.15%", premiumRt: "11.48%", convertValue: 108.65, dblow: 132.6, volumeWan: 15891.6, currIssAmtYi: 81.62, rating: "AAA", stockId: "300498", stockName: "温氏股份", source: "jsl", updateTime: "09:34:05" },
  { bondId: "127089", bondName: "晶澳转债", price: 109.38, increaseRt: "-0.44%", premiumRt: "23.91%", convertValue: 88.27, dblow: 133.29, volumeWan: 9345.4, currIssAmtYi: 88.96, rating: "AA+", stockId: "002459", stockName: "晶澳科技", source: "jsl", updateTime: "09:34:05" },
  { bondId: "110085", bondName: "通22转债", price: 117.66, increaseRt: "0.51%", premiumRt: "17.12%", convertValue: 100.45, dblow: 134.78, volumeWan: 26888.0, currIssAmtYi: 59.11, rating: "AAA", stockId: "600438", stockName: "通威股份", source: "jsl", updateTime: "09:34:06" },
  { bondId: "113059", bondName: "福莱转债", price: 132.08, increaseRt: "1.21%", premiumRt: "8.44%", convertValue: 121.8, dblow: 140.52, volumeWan: 20562.9, currIssAmtYi: 26.73, rating: "AA+", stockId: "605305", stockName: "中际联合", source: "jsl", updateTime: "09:34:06" },
  { bondId: "127084", bondName: "柳工转2", price: 116.31, increaseRt: "-0.07%", premiumRt: "18.66%", convertValue: 98.01, dblow: 134.97, volumeWan: 7866.3, currIssAmtYi: 30.12, rating: "AA", stockId: "000528", stockName: "柳工", source: "jsl", updateTime: "09:34:06" },
  { bondId: "113061", bondName: "拓普转债", price: 122.15, increaseRt: "0.33%", premiumRt: "12.59%", convertValue: 108.49, dblow: 134.74, volumeWan: 14220.1, currIssAmtYi: 24.5, rating: "AA+", stockId: "601689", stockName: "拓普集团", source: "jsl", updateTime: "09:34:06" },
  { bondId: "123143", bondName: "胜蓝转债", price: 130.42, increaseRt: "1.02%", premiumRt: "9.12%", convertValue: 119.51, dblow: 139.54, volumeWan: 6120.2, currIssAmtYi: 5.81, rating: "AA", stockId: "300843", stockName: "胜蓝股份", source: "jsl", updateTime: "09:34:07" },
  { bondId: "113067", bondName: "燃23转债", price: 118.05, increaseRt: "0.14%", premiumRt: "13.07%", convertValue: 104.4, dblow: 131.12, volumeWan: 11240.7, currIssAmtYi: 37.96, rating: "AAA", stockId: "600803", stockName: "新奥股份", source: "jsl", updateTime: "09:34:07" },
  { bondId: "123176", bondName: "精测转2", price: 124.33, increaseRt: "-0.29%", premiumRt: "20.51%", convertValue: 103.17, dblow: 144.84, volumeWan: 7540.8, currIssAmtYi: 12.04, rating: "AA+", stockId: "300567", stockName: "精测电子", source: "jsl", updateTime: "09:34:07" },
  { bondId: "110090", bondName: "爱柯转债", price: 136.52, increaseRt: "1.83%", premiumRt: "7.14%", convertValue: 127.42, dblow: 143.66, volumeWan: 18265.9, currIssAmtYi: 8.46, rating: "AA", stockId: "688092", stockName: "爱科科技", source: "jsl", updateTime: "09:34:07" },
  { bondId: "127080", bondName: "声迅转债", price: 111.47, increaseRt: "-0.51%", premiumRt: "24.83%", convertValue: 89.29, dblow: 136.3, volumeWan: 4988.4, currIssAmtYi: 3.77, rating: "AA", stockId: "003004", stockName: "声迅股份", source: "jsl", updateTime: "09:34:08" },
];

const sourceLedger: LineageRow[] = [
  { field: "code / bondId", meaning: "交易标识", stockSource: "tencent.real(prefix=True) 返回 key", bondSource: "jsl.cb() -> row.id", usage: "跨表关联、去重、下单路由", domain: "common" },
  { field: "name / bond_nm", meaning: "标的名称", stockSource: "tencent/sina -> name", bondSource: "jsl.cb() -> row.cell.bond_nm", usage: "交易确认、审计追踪", domain: "common" },
  { field: "now", meaning: "股票最新价", stockSource: "tencent.real()['now']", bondSource: "N/A", usage: "正股动量与情绪判断", domain: "stock" },
  { field: "price", meaning: "转债最新价", stockSource: "N/A", bondSource: "jsl.cb() -> row.cell.price", usage: "转债排名与入场点", domain: "bond" },
  { field: "涨跌(%)", meaning: "股票涨跌幅", stockSource: "tencent.real()['涨跌(%)']", bondSource: "N/A", usage: "异动筛查", domain: "stock" },
  { field: "increase_rt", meaning: "转债涨跌幅", stockSource: "N/A", bondSource: "jsl.cb() -> row.cell.increase_rt", usage: "分时强弱监控", domain: "bond" },
  { field: "成交额(万)", meaning: "股票成交额", stockSource: "tencent.real()['成交额(万)']", bondSource: "N/A", usage: "流动性门槛", domain: "stock" },
  { field: "volume", meaning: "转债成交额", stockSource: "N/A", bondSource: "jsl.cb() -> row.cell.volume", usage: "容量评估", domain: "bond" },
  { field: "turnover", meaning: "股票换手率", stockSource: "tencent.real()['turnover'] / sina.turnover", bondSource: "N/A", usage: "拥挤度过滤", domain: "stock" },
  { field: "premium_rt", meaning: "转股溢价率", stockSource: "N/A", bondSource: "jsl.cb() -> row.cell.premium_rt", usage: "双低核心因子", domain: "bond" },
  { field: "convert_value", meaning: "转股价值", stockSource: "N/A", bondSource: "jsl.cb() -> row.cell.convert_value", usage: "股债性拆解", domain: "bond" },
  { field: "dblow", meaning: "双低值", stockSource: "N/A", bondSource: "jsl.cb() -> row.cell.dblow", usage: "排序主键", domain: "bond" },
  { field: "curr_iss_amt", meaning: "剩余规模", stockSource: "N/A", bondSource: "jsl.cb() -> row.cell.curr_iss_amt", usage: "仓位上限", domain: "bond" },
  { field: "rating_cd", meaning: "信用评级", stockSource: "N/A", bondSource: "jsl.cb() -> row.cell.rating_cd", usage: "信用风险过滤", domain: "bond" },
  { field: "date/time", meaning: "更新时间", stockSource: "sina.real()['date'/'time']", bondSource: "jsl.cb() -> row.cell.last_time", usage: "新鲜度监控", domain: "common" },
];

const traderChecklist = [
  "09:25 前检查 jsl 数据可用性；无 cookie 时切换到昨日完整快照。",
  "开盘后 5 分钟内只观测不交易，避免竞价噪声触发误判。",
  "优先看成交额与盘口深度，分数靠后；不满足流动性不入池。",
  "对溢价率突变且成交稀疏标的标黄灯，推迟加入候选池。",
];

const tips = [
  { title: "Tip: prefix=True", text: "避免指数与个股同代码冲突，确保下游映射唯一。" },
  { title: "Tip: jsl 字段动态", text: "jsl.cb() 返回 row.cell 字典，字段可能调整，前端应容忍字段增减。" },
  { title: "Tip: 双低不是单因子", text: "双低值需配合流动性和评级，否则实盘可成交性差。" },
  { title: "Tip: 前端职责", text: "前端负责展示与追溯；数据清洗、回填、纠错由后端执行。" },
];

const sourceOptions = [
  { value: "all", label: "全部来源" },
  { value: "tencent", label: "tencent" },
  { value: "sina", label: "sina" },
];

const ratingOptions = [
  { value: "all", label: "全部评级" },
  { value: "AAA", label: "AAA" },
  { value: "AA+", label: "AA+" },
  { value: "AA", label: "AA" },
];

const lineageDomainOptions = [
  { value: "all", label: "全部域" },
  { value: "stock", label: "股票域" },
  { value: "bond", label: "转债域" },
  { value: "common", label: "公共域" },
];

const pageSizeOptions = [
  { value: "5", label: "每页 5 条" },
  { value: "10", label: "每页 10 条" },
  { value: "20", label: "每页 20 条" },
];

const tabOptions = [
  { key: "stock", title: "股票底表" },
  { key: "bond", title: "转债主表" },
  { key: "lineage", title: "字段台账" },
] as const;

const percentToNumber = (value: string): number => Number(value.replace("%", ""));

function NumberBadge({ value }: { value: number }) {
  const positive = value >= 0;
  return (
    <span
      className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
        positive
          ? "bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-300"
          : "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300"
      }`}
    >
      {positive ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}

export default function CbQuantInfoMiningPage() {
  const [activeTab, setActiveTab] = useState<"stock" | "bond" | "lineage">("stock");

  const [stockKeyword, setStockKeyword] = useState<string>("");
  const [stockSource, setStockSource] = useState<string>("all");
  const [stockMinAmount, setStockMinAmount] = useState<string>("");
  const [stockPageSize, setStockPageSize] = useState<number>(5);
  const [stockPage, setStockPage] = useState<number>(1);

  const [bondKeyword, setBondKeyword] = useState<string>("");
  const [bondRating, setBondRating] = useState<string>("all");
  const [bondMaxPremium, setBondMaxPremium] = useState<string>("");
  const [bondMinVolume, setBondMinVolume] = useState<string>("");
  const [bondPageSize, setBondPageSize] = useState<number>(5);
  const [bondPage, setBondPage] = useState<number>(1);

  const [lineageKeyword, setLineageKeyword] = useState<string>("");
  const [lineageDomain, setLineageDomain] = useState<string>("all");
  const [lineagePageSize, setLineagePageSize] = useState<number>(5);
  const [lineagePage, setLineagePage] = useState<number>(1);
  const [showFilter, setShowFilter] = useState<boolean>(false);
  const filterRef = useRef<HTMLDivElement>(null);

  const filteredStocks = useMemo(() => {
    const keyword = stockKeyword.trim().toLowerCase();
    const minAmount = stockMinAmount ? Number(stockMinAmount) : null;

    return stockSnapshot.filter((row) => {
      const matchKeyword = !keyword || row.code.toLowerCase().includes(keyword) || row.name.toLowerCase().includes(keyword);
      const matchSource = stockSource === "all" || row.source === stockSource;
      const matchAmount = minAmount === null || row.amountWan >= minAmount;
      return matchKeyword && matchSource && matchAmount;
    });
  }, [stockKeyword, stockSource, stockMinAmount]);

  const filteredBonds = useMemo(() => {
    const keyword = bondKeyword.trim().toLowerCase();
    const maxPremium = bondMaxPremium ? Number(bondMaxPremium) : null;
    const minVolume = bondMinVolume ? Number(bondMinVolume) : null;

    return bondSnapshot.filter((row) => {
      const matchKeyword =
        !keyword ||
        row.bondId.toLowerCase().includes(keyword) ||
        row.bondName.toLowerCase().includes(keyword) ||
        row.stockId.toLowerCase().includes(keyword) ||
        row.stockName.toLowerCase().includes(keyword);
      const matchRating = bondRating === "all" || row.rating === bondRating;
      const matchPremium = maxPremium === null || percentToNumber(row.premiumRt) <= maxPremium;
      const matchVolume = minVolume === null || row.volumeWan >= minVolume;
      return matchKeyword && matchRating && matchPremium && matchVolume;
    });
  }, [bondKeyword, bondRating, bondMaxPremium, bondMinVolume]);

  const filteredLineage = useMemo(() => {
    const keyword = lineageKeyword.trim().toLowerCase();

    return sourceLedger.filter((row) => {
      const matchKeyword =
        !keyword ||
        row.field.toLowerCase().includes(keyword) ||
        row.meaning.toLowerCase().includes(keyword) ||
        row.usage.toLowerCase().includes(keyword) ||
        row.stockSource.toLowerCase().includes(keyword) ||
        row.bondSource.toLowerCase().includes(keyword);
      const matchDomain = lineageDomain === "all" || row.domain === lineageDomain;
      return matchKeyword && matchDomain;
    });
  }, [lineageKeyword, lineageDomain]);

  const stockTotalPages = Math.max(1, Math.ceil(filteredStocks.length / stockPageSize));
  const bondTotalPages = Math.max(1, Math.ceil(filteredBonds.length / bondPageSize));
  const lineageTotalPages = Math.max(1, Math.ceil(filteredLineage.length / lineagePageSize));

  useEffect(() => {
    if (stockPage > stockTotalPages) {
      setStockPage(stockTotalPages);
    }
  }, [stockPage, stockTotalPages]);

  useEffect(() => {
    if (bondPage > bondTotalPages) {
      setBondPage(bondTotalPages);
    }
  }, [bondPage, bondTotalPages]);

  useEffect(() => {
    if (lineagePage > lineageTotalPages) {
      setLineagePage(lineageTotalPages);
    }
  }, [lineagePage, lineageTotalPages]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(event.target as Node)) {
        setShowFilter(false);
      }
    };
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  useEffect(() => {
    setShowFilter(false);
  }, [activeTab]);

  const pagedStocks = useMemo(() => {
    const start = (stockPage - 1) * stockPageSize;
    return filteredStocks.slice(start, start + stockPageSize);
  }, [filteredStocks, stockPage, stockPageSize]);

  const pagedBonds = useMemo(() => {
    const start = (bondPage - 1) * bondPageSize;
    return filteredBonds.slice(start, start + bondPageSize);
  }, [filteredBonds, bondPage, bondPageSize]);

  const pagedLineage = useMemo(() => {
    const start = (lineagePage - 1) * lineagePageSize;
    return filteredLineage.slice(start, start + lineagePageSize);
  }, [filteredLineage, lineagePage, lineagePageSize]);

  const searchValue =
    activeTab === "stock"
      ? stockKeyword
      : activeTab === "bond"
      ? bondKeyword
      : lineageKeyword;

  const searchPlaceholder =
    activeTab === "stock"
      ? "Search stock code/name..."
      : activeTab === "bond"
      ? "Search bond/stock code/name..."
      : "Search field/meaning/source...";

  const handleSearchChange = (value: string) => {
    if (activeTab === "stock") {
      setStockKeyword(value);
      setStockPage(1);
      return;
    }
    if (activeTab === "bond") {
      setBondKeyword(value);
      setBondPage(1);
      return;
    }
    setLineageKeyword(value);
    setLineagePage(1);
  };

  const escapeCsv = (value: string | number) => {
    const normalized = String(value ?? "");
    if (normalized.includes(",") || normalized.includes("\"") || normalized.includes("\n")) {
      return `"${normalized.replace(/"/g, "\"\"")}"`;
    }
    return normalized;
  };

  const handleExport = () => {
    let headers: string[] = [];
    let rows: Array<Array<string | number>> = [];

    if (activeTab === "stock") {
      headers = ["代码", "名称", "现价", "涨跌幅", "成交量(手)", "成交额(万)", "换手率", "买一", "卖一", "最高", "最低", "PE", "PB", "来源", "更新时间"];
      rows = filteredStocks.map((row) => [
        row.code,
        row.name,
        row.now.toFixed(2),
        `${row.changePct.toFixed(2)}%`,
        row.volumeHand,
        row.amountWan,
        `${row.turnover.toFixed(2)}%`,
        row.bid1.toFixed(2),
        row.ask1.toFixed(2),
        row.high.toFixed(2),
        row.low.toFixed(2),
        row.pe.toFixed(2),
        row.pb.toFixed(2),
        `easyquotation.${row.source}.real()`,
        row.updateTime,
      ]);
    } else if (activeTab === "bond") {
      headers = ["转债代码", "转债名称", "现价", "涨跌幅", "转股溢价率", "转股价值", "双低值", "成交额(万)", "剩余规模(亿)", "评级", "正股代码", "正股名称", "来源", "更新时间"];
      rows = filteredBonds.map((row) => [
        row.bondId,
        row.bondName,
        row.price.toFixed(2),
        row.increaseRt,
        row.premiumRt,
        row.convertValue.toFixed(2),
        row.dblow.toFixed(2),
        row.volumeWan.toFixed(2),
        row.currIssAmtYi.toFixed(2),
        row.rating,
        row.stockId,
        row.stockName,
        `easyquotation.${row.source}.cb()`,
        row.updateTime,
      ]);
    } else {
      headers = ["字段", "业务含义", "股票来源", "可转债来源", "策略用途", "数据域"];
      rows = filteredLineage.map((row) => [row.field, row.meaning, row.stockSource, row.bondSource, row.usage, row.domain]);
    }

    const csv = [headers, ...rows].map((row) => row.map((cell) => escapeCsv(cell)).join(",")).join("\n");
    const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cb-quant-${activeTab}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const filterPanel = (
    <div className="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-gray-200 bg-white p-4 shadow-lg dark:border-gray-700 dark:bg-gray-800">
      {activeTab === "stock" && (
        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">Source</label>
            <select
              value={stockSource}
              onChange={(e) => {
                setStockSource(e.target.value);
                setStockPage(1);
              }}
              className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-10 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              {sourceOptions.map((option) => (
                <option key={option.value} value={option.value} className="dark:bg-gray-900">
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">Min Amount (万)</label>
            <input
              type="number"
              value={stockMinAmount}
              onChange={(e) => {
                setStockMinAmount(e.target.value);
                setStockPage(1);
              }}
              placeholder="Input amount..."
              className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-10 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
            />
          </div>
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">Page Size</label>
            <select
              value={String(stockPageSize)}
              onChange={(e) => {
                setStockPageSize(Number(e.target.value));
                setStockPage(1);
              }}
              className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-10 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              {pageSizeOptions.map((option) => (
                <option key={option.value} value={option.value} className="dark:bg-gray-900">
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
      {activeTab === "bond" && (
        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">Rating</label>
            <select
              value={bondRating}
              onChange={(e) => {
                setBondRating(e.target.value);
                setBondPage(1);
              }}
              className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-10 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              {ratingOptions.map((option) => (
                <option key={option.value} value={option.value} className="dark:bg-gray-900">
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">Max Premium (%)</label>
            <input
              type="number"
              value={bondMaxPremium}
              onChange={(e) => {
                setBondMaxPremium(e.target.value);
                setBondPage(1);
              }}
              placeholder="Input premium..."
              className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-10 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
            />
          </div>
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">Min Volume (万)</label>
            <input
              type="number"
              value={bondMinVolume}
              onChange={(e) => {
                setBondMinVolume(e.target.value);
                setBondPage(1);
              }}
              placeholder="Input volume..."
              className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-10 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
            />
          </div>
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">Page Size</label>
            <select
              value={String(bondPageSize)}
              onChange={(e) => {
                setBondPageSize(Number(e.target.value));
                setBondPage(1);
              }}
              className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-10 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              {pageSizeOptions.map((option) => (
                <option key={option.value} value={option.value} className="dark:bg-gray-900">
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
      {activeTab === "lineage" && (
        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">Domain</label>
            <select
              value={lineageDomain}
              onChange={(e) => {
                setLineageDomain(e.target.value);
                setLineagePage(1);
              }}
              className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-10 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              {lineageDomainOptions.map((option) => (
                <option key={option.value} value={option.value} className="dark:bg-gray-900">
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">Page Size</label>
            <select
              value={String(lineagePageSize)}
              onChange={(e) => {
                setLineagePageSize(Number(e.target.value));
                setLineagePage(1);
              }}
              className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-10 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              {pageSizeOptions.map((option) => (
                <option key={option.value} value={option.value} className="dark:bg-gray-900">
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
      <button
        onClick={() => setShowFilter(false)}
        className="bg-brand-500 hover:bg-brand-600 mt-4 h-10 w-full rounded-lg px-3 py-2 text-sm font-medium text-white"
      >
        Apply
      </button>
    </div>
  );

  return (
    <CbQuantPageShell
      title="信息挖掘行动页"
      subtitle="交易者数据工作台：按 Invoices 风格展示概览、筛选与明细表，突出高频操作与审计可追溯。"
    >
      <div className="space-y-6">
        <div className="rounded-2xl border border-gray-200 bg-white p-4 sm:p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-semibold text-gray-800 dark:text-white/90">Overview</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">信息挖掘阶段关键样本规模、审计覆盖与数据风险。</p>
            </div>
            <button className="bg-brand-500 shadow-theme-xs hover:bg-brand-600 inline-flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-medium text-white transition">
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M10 3.33325V16.6666M3.33398 9.99992H16.6673" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              刷新快照
            </button>
          </div>
          <div className="grid grid-cols-1 rounded-xl border border-gray-200 sm:grid-cols-2 lg:grid-cols-4 lg:divide-x lg:divide-y-0 dark:divide-gray-800 dark:border-gray-800">
            <div className="border-b p-5 sm:border-r lg:border-b-0 dark:border-gray-800">
              <p className="mb-1.5 text-sm text-gray-400 dark:text-gray-500">A股快照</p>
              <h3 className="text-3xl text-gray-800 dark:text-white/90">{filteredStocks.length}</h3>
            </div>
            <div className="border-b p-5 lg:border-b-0 dark:border-gray-800">
              <p className="mb-1.5 text-sm text-gray-400 dark:text-gray-500">可转债快照</p>
              <h3 className="text-3xl text-gray-800 dark:text-white/90">{filteredBonds.length}</h3>
            </div>
            <div className="border-b p-5 sm:border-r sm:border-b-0 dark:border-gray-800">
              <p className="mb-1.5 text-sm text-gray-400 dark:text-gray-500">字段追踪</p>
              <h3 className="text-3xl text-gray-800 dark:text-white/90">{filteredLineage.length}</h3>
            </div>
            <div className="p-5">
              <div className="mb-1.5 flex items-center gap-1.5 text-sm text-yellow-700 dark:text-yellow-300">
                <AlertIcon className="h-4 w-4" />
                <span>风险提示</span>
              </div>
              <p className="text-sm font-medium text-yellow-700 dark:text-yellow-300">jsl 无 cookie 可能字段不全</p>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">建议启用 cookie + 昨日快照回退</p>
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          <WorkbenchHeader
            title="信息挖掘数据台"
            description="股票、转债、字段台账"
            tabs={tabOptions}
            activeTab={activeTab}
            onTabChange={(tab) => setActiveTab(tab)}
            searchPlaceholder={searchPlaceholder}
            searchValue={searchValue}
            onSearchChange={handleSearchChange}
            filterOpen={showFilter}
            onToggleFilter={() => setShowFilter(!showFilter)}
            filterPanel={filterPanel}
            filterRef={filterRef}
            onExport={handleExport}
          />

          {activeTab === "stock" && (
            <div className="p-5">
              <ScrollableDataTable
                headers={["代码", "名称", "现价", "涨跌幅", "成交量(手)", "成交额(万)", "换手率", "买一/卖一", "最高/最低", "PE/PB", "来源", "更新时间"]}
                minTableWidthClass="min-w-[1500px]"
                colSpan={12}
                isEmpty={!pagedStocks.length}
              >
                {pagedStocks.map((row) => (
                  <TableRow key={row.code} className="border-b border-gray-100 dark:border-gray-800">
                    <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.code}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.name}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.now.toFixed(2)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm whitespace-nowrap"><NumberBadge value={row.changePct} /></TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.volumeHand.toLocaleString()}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.amountWan.toLocaleString()}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.turnover.toFixed(2)}%</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.bid1.toFixed(2)} / {row.ask1.toFixed(2)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.high.toFixed(2)} / {row.low.toFixed(2)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.pe.toFixed(2)} / {row.pb.toFixed(2)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">easyquotation.{row.source}.real()</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap dark:text-gray-400">{row.updateTime}</TableCell>
                  </TableRow>
                ))}
              </ScrollableDataTable>
              <TablePaginationBar
                totalItems={filteredStocks.length}
                currentPage={stockPage}
                totalPages={stockTotalPages}
                onPageChange={setStockPage}
              />
            </div>
          )}

          {activeTab === "bond" && (
            <div className="p-5">
              <ScrollableDataTable
                headers={["转债代码", "转债名称", "现价", "涨跌幅", "转股溢价率", "转股价值", "双低值", "成交额(万)", "剩余规模(亿)", "评级", "正股", "来源", "更新时间"]}
                minTableWidthClass="min-w-[1720px]"
                colSpan={13}
                isEmpty={!pagedBonds.length}
              >
                {pagedBonds.map((row) => (
                  <TableRow key={row.bondId} className="border-b border-gray-100 dark:border-gray-800">
                    <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.bondId}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.bondName}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.price.toFixed(2)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.increaseRt}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.premiumRt}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.convertValue.toFixed(2)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.dblow.toFixed(2)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.volumeWan.toLocaleString()}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.currIssAmtYi.toFixed(2)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.rating}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.stockId} {row.stockName}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">easyquotation.{row.source}.cb()</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap dark:text-gray-400">{row.updateTime}</TableCell>
                  </TableRow>
                ))}
              </ScrollableDataTable>
              <TablePaginationBar
                totalItems={filteredBonds.length}
                currentPage={bondPage}
                totalPages={bondTotalPages}
                onPageChange={setBondPage}
              />
            </div>
          )}

          {activeTab === "lineage" && (
            <div className="p-5">
              <ScrollableDataTable
                headers={["字段", "业务含义", "股票来源", "可转债来源", "策略用途", "数据域"]}
                minTableWidthClass="min-w-[1680px]"
                colSpan={6}
                isEmpty={!pagedLineage.length}
              >
                {pagedLineage.map((row) => (
                  <TableRow key={row.field} className="border-b border-gray-100 align-top dark:border-gray-800">
                    <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.field}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.meaning}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.stockSource}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.bondSource}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.usage}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.domain}</TableCell>
                  </TableRow>
                ))}
              </ScrollableDataTable>
              <TablePaginationBar
                totalItems={filteredLineage.length}
                currentPage={lineagePage}
                totalPages={lineageTotalPages}
                onPageChange={setLineagePage}
              />
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
            <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">开盘检查</h3>
            <div className="mt-3 space-y-2">
              {traderChecklist.map((item, idx) => (
                <div key={item} className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-300">
                  <span className="mr-1 text-brand-500">{idx + 1}.</span>
                  {item}
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
            <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">概念 Tips</h3>
            <div className="mt-3 space-y-2">
              {tips.map((tip) => (
                <div key={tip.title} className="rounded-lg border border-gray-200 px-3 py-2 dark:border-gray-700">
                  <p className="text-sm font-semibold text-gray-800 dark:text-white/90">{tip.title}</p>
                  <p className="mt-0.5 text-sm text-gray-600 dark:text-gray-400">{tip.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </CbQuantPageShell>
  );
}
