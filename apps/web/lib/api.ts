// Thin client for the Quant-OS FastAPI backend.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Strategy {
  num: string;
  slug: string | null;
  name: string | null;
  category: string | null;
  status: string | null;
  bucket: string | null;
  sharpe: number | null;
  cagr: string | null;
  has_metrics: number;
}

export interface StrategyDetail extends Strategy {
  hypothesis: string | null;
  note: string | null;
  rel_path: string | null;
  maxdd: string | null;
  n_trades: string | null;
  p_value: number | null;
  dsr: number | null;
  metrics: Record<string, number | string>;
}

export interface Overview {
  n_strategies: number;
  buckets: Record<string, number>;
  categories: Record<string, number>;
  sharpes: number[];
  top: { num: string; name: string | null; sharpe: number; bucket: string | null }[];
}

export interface Idea {
  ID: string;
  Titel: string;
  Markt: string;
  Kategorie: string;
  Kernidee_kurz: string;
  Prioritaet: string;
  Status: string;
  [k: string]: string;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status} on ${path}`);
  return res.json() as Promise<T>;
}

export interface LiveBook {
  ok: boolean;
  error?: string;
  cached?: boolean;
  asof?: string | null;
  book_sharpe?: number | null;
  gross_exposure_pct?: number;
  positions?: { instrument: string; weight_pct: number }[];
  context?: Record<string, unknown>;
}

export const getStrategies = () => getJson<Strategy[]>("/strategies");
export const getLiveBook = (refresh = false) =>
  getJson<LiveBook>(`/live/book${refresh ? "?refresh=true" : ""}`);
export const getOverview = () => getJson<Overview>("/overview");
export const getStrategy = (num: string) => getJson<StrategyDetail>(`/strategies/${num}`);
export const getPlots = (num: string) =>
  getJson<{ num: string; plots: string[] }>(`/strategies/${num}/plots`);
export const plotUrl = (num: string, file: string) =>
  `${API_URL}/strategies/${num}/plot/${file}`;
export const getIdeas = () =>
  getJson<{ exists: boolean; count: number; ideas: Idea[] }>("/ideas");
