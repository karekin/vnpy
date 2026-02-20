export type Direction = "多" | "空";

export interface TickRow {
  symbol: string;
  exchange: string;
  name: string;
  lastPrice: number;
  volume: number;
  bid1: number;
  ask1: number;
  bidVolume1: number;
  askVolume1: number;
  time: string;
  gateway: string;
}

export interface OrderRow {
  orderid: string;
  reference: string;
  symbol: string;
  exchange: string;
  type: string;
  direction: Direction;
  offset: string;
  price: number;
  volume: number;
  traded: number;
  status: string;
  time: string;
  gateway: string;
}

export interface TradeRow {
  tradeid: string;
  orderid: string;
  symbol: string;
  exchange: string;
  direction: Direction;
  offset: string;
  price: number;
  volume: number;
  time: string;
  gateway: string;
}

export interface PositionRow {
  symbol: string;
  exchange: string;
  direction: Direction;
  volume: number;
  ydVolume: number;
  frozen: number;
  avgPrice: number;
  pnl: number;
  gateway: string;
}

export interface AccountRow {
  accountid: string;
  balance: number;
  frozen: number;
  available: number;
  gateway: string;
}

export interface ContractRow {
  vtSymbol: string;
  symbol: string;
  exchange: string;
  name: string;
  product: string;
  size: number;
  pricetick: number;
  minVolume: number;
  gateway: string;
}

export interface StrategyRow {
  strategyName: string;
  vtSymbol: string;
  className: string;
  inited: boolean;
  trading: boolean;
  pos: number;
  parameters: Record<string, number | string>;
  variables: Record<string, number | string>;
}

export interface LogRow {
  time: string;
  message: string;
  source: string;
}

export interface BacktestMetric {
  label: string;
  value: string;
}
