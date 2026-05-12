const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type PortfolioSummary = {
  as_of: string | null;
  total_cad: number;
  positions: number;
  unrealized: number;
  usd_cad: number;
  top_position: string | null;
};

export type AllocationPayload = {
  security_type: Array<Record<string, unknown>>;
  currency: Array<Record<string, unknown>>;
  accounts: Array<Record<string, unknown>>;
  symbols: Array<Record<string, unknown>>;
};

export type ReturnsPayload = {
  rows: Array<Record<string, unknown>>;
  account_history: Array<Record<string, unknown>>;
  symbol_history: Array<Record<string, unknown>>;
  summary: Record<string, number>;
};

export type Universe = {
  key: string;
  label: string;
  symbols: string[];
};

export type Flag = {
  severity: string;
  title: string;
  detail: string;
  symbols: string[];
};

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} failed with ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  summary: () => getJson<PortfolioSummary>("/api/portfolio/summary"),
  holdings: () => getJson<Array<{ data: Record<string, unknown> }>>("/api/portfolio/holdings"),
  allocation: () => getJson<AllocationPayload>("/api/portfolio/allocation"),
  returns: () => getJson<ReturnsPayload>("/api/returns/history"),
  universes: () => getJson<Universe[]>("/api/markets/universes"),
  activity: () => getJson<Array<Record<string, unknown>>>("/api/activity"),
  journal: () => getJson<Array<Record<string, unknown>>>("/api/journal"),
  goals: () => getJson<Record<string, unknown>>("/api/goals"),
  alerts: () => getJson<Flag[]>("/api/alerts")
};

export function formatCad(value: unknown): string {
  const n = Number(value ?? 0);
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0
  }).format(Number.isFinite(n) ? n : 0);
}

export function asText(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2);
  }
  return String(value);
}
