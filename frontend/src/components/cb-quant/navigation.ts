export type CbQuantNavItem = {
  name: string;
  path: string;
};

export const cbQuantNavItems: CbQuantNavItem[] = [
  { name: "总览", path: "/cb-quant" },
  { name: "信息挖掘", path: "/cb-quant/info-mining" },
  { name: "策略生成", path: "/cb-quant/strategy-generation" },
  { name: "回测评估", path: "/cb-quant/backtest-evaluation" },
  { name: "自动执行", path: "/cb-quant/auto-execution" },
  { name: "反馈复盘", path: "/cb-quant/review" },
  { name: "持续迭代", path: "/cb-quant/continuous-iteration" },
];
