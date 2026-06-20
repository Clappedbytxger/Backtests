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

export interface BucketResponse {
  buckets: Record<string, number>;
  statuses: Record<string, number>;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status} on ${path}`);
  return res.json() as Promise<T>;
}

export const getStrategies = () => getJson<Strategy[]>("/strategies");
export const getBuckets = () => getJson<BucketResponse>("/strategies/buckets");
