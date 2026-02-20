import { ContractRow, OrderRow, TickRow, TradeRow } from "@/lib/types";

const BASE_URL = process.env.NEXT_PUBLIC_VNPY_BASE_URL ?? "http://127.0.0.1:8000";

export interface AuthToken {
  access_token: string;
  token_type: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API ${response.status}: ${errorText}`);
  }

  return response.json() as Promise<T>;
}

export async function fetchToken(username: string, password: string): Promise<AuthToken> {
  const body = new URLSearchParams({ username, password });

  const response = await fetch(`${BASE_URL}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Token ${response.status}: ${errorText}`);
  }

  return response.json() as Promise<AuthToken>;
}

export async function fetchTicks(token: string): Promise<TickRow[]> {
  return request<TickRow[]>("/tick", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchOrders(token: string): Promise<OrderRow[]> {
  return request<OrderRow[]>("/order", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchTrades(token: string): Promise<TradeRow[]> {
  return request<TradeRow[]>("/trade", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchContracts(token: string): Promise<ContractRow[]> {
  return request<ContractRow[]>("/contract", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function sendOrder(
  token: string,
  payload: {
    symbol: string;
    exchange: string;
    direction: string;
    type: string;
    volume: number;
    price: number;
    offset: string;
    reference?: string;
  },
): Promise<string> {
  return request<string>("/order", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

export async function cancelOrder(token: string, vtOrderId: string): Promise<boolean> {
  return request<boolean>(`/order/${vtOrderId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function webSocketUrl(token: string): string {
  const base = BASE_URL.replace(/^http/, "ws");
  return `${base}/ws/?token=${encodeURIComponent(token)}`;
}
