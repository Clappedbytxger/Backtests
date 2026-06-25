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

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `API ${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

async function delJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: "DELETE", cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status} on ${path}`);
  return res.json() as Promise<T>;
}

export interface AgentResult {
  branch: string;
  num?: string;
  dir: string;
  slug: string;
  dups: [string, number][];
  context: string[];
  dry_run?: boolean;
  status?: string;
  sha?: string;
  run_py?: string;
  signal_code?: string;
  report?: string | null;
  stdout_tail?: string;
  instrument?: string | null;
  timeframe?: string | null;
  summary?: Record<string, number>;
  permutation?: {
    observed?: number;
    p_value?: number;
    null_mean?: number;
    null_std?: number;
    n_perm?: number;
  };
  bootstrap_ci?: { statistic?: string; point?: number; ci_low?: number; ci_high?: number };
  deflated_sharpe?: { psr_deflated?: number; observed_sharpe?: number };
  vs_benchmark?: {
    strategy_total_return?: number;
    buy_hold_total_return?: number;
    sp500_total_return?: number;
  };
  plots?: Record<string, string>;
  warning?: string | null;
  signal_error?: string | null;
  params?: Record<string, number>;
  param_grid?: Record<string, number[]>;
}

export interface AgentEvalResult {
  ok: boolean;
  error?: string;
  summary?: Record<string, number>;
  warning?: string | null;
  params?: Record<string, number>;
  vs_benchmark?: AgentResult["vs_benchmark"];
  instrument?: string | null;
  plots?: Record<string, string>;
}

export interface PromoteResult {
  ok: boolean;
  branch: string;
  num: string;
  dir: string;
  sha: string;
  catalog_row: string;
}

export interface AgentJob {
  job_id: string;
  status: "running" | "done" | "error";
  hypothesis: string;
  dry_run: boolean;
  result?: AgentResult;
  error?: string;
}

export const agentRun = (hypothesis: string, dry_run: boolean) =>
  postJson<{ job_id: string; status: string }>("/agent/run", { hypothesis, dry_run });
export const getAgentJob = (jobId: string) => getJson<AgentJob>(`/agent/job/${jobId}`);
export const agentEvaluate = (job_id: string, params: Record<string, number>) =>
  postJson<AgentEvalResult>("/agent/evaluate", { job_id, params });
export const agentPromote = (job_id: string) =>
  postJson<PromoteResult>("/agent/promote", { job_id });

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

// ── Charts / volume-footprint terminal (/api/charts/*) ──────────────────────
export type AssetClass = "futures" | "equities" | "crypto";

export interface Instrument {
  ticker: string;
  dataset: string;
  asset_class: AssetClass;
  native_tf: string;
  available_tfs: string[];
  footprint: boolean;
  start: string | null;
  end: string | null;
}

/** Candle time is unix seconds for intraday, or a "YYYY-MM-DD" string for 1D. */
export type ChartTime = number | string;

export interface Candle {
  time: ChartTime;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FootprintLevel {
  price: number;
  bid_volume: number;
  ask_volume: number;
  delta: number;
  total: number;
}

export interface FootprintCluster {
  time: ChartTime;
  open: number;
  high: number;
  low: number;
  close: number;
  total_volume: number;
  poc_price: number | null;
  value_area_high: number | null;
  value_area_low: number | null;
  bin_size: number;
  approx: boolean;
  delta_method: string;
  levels: FootprintLevel[];
}

export interface InstrumentsResponse {
  ok: boolean;
  error?: string;
  count: number;
  instruments: Instrument[];
}
export interface CandlesResponse {
  ok: boolean;
  error?: string;
  ticker: string;
  timeframe: string;
  rth: boolean;
  adjusted: boolean;
  count: number;
  has_more_past: boolean;
  candles: Candle[];
}
export interface FootprintResponse {
  ok: boolean;
  error?: string;
  ticker: string;
  timeframe: string;
  approx: boolean;
  delta_method: string;
  count: number;
  clusters: FootprintCluster[];
}

export const getInstruments = () =>
  getJson<InstrumentsResponse>("/api/charts/instruments");

// ── News terminal (/api/news/*) ─────────────────────────────────────────────
export type NewsCategory = "Makro" | "Krypto" | "Aktien" | "FX" | "Rohstoffe" | "Sonstiges";
export type NewsPriority = "Low" | "Medium" | "High";
export type ImpactDirection = "Bullish" | "Bearish" | "Neutral";
export type HypothesisStatus = "open" | "correct" | "incorrect" | "unverified";

export interface Hypothesis {
  direction: ImpactDirection;
  asset: string;
  scope: "asset" | "market";
  rationale: string;
  confidence: number;
  model: string;
  created_at: string;
  status: HypothesisStatus;
  verify_after_hours: number;
  verified_at: string | null;
  realized_return: number | null;
  feedback_source: string | null;
  lesson_id: string | null;
  provisional_return: number | null;
  provisional_status: "on_track" | "off_track" | "flat" | null;
  last_tracked_at: string | null;
}

export interface Briefing {
  en: string;
  de: string;
  model: string;
  generated_at: string;
}

export interface NewsItem {
  id: string;
  timestamp: string;
  source: string;
  title: string;
  content: string;
  url: string | null;
  category: NewsCategory;
  priority: NewsPriority;
  hypothesis: Hypothesis | null;
  document: Briefing | null;
}

export interface Lesson {
  id: string;
  created_at: string;
  news_id: string;
  headline: string;
  category: NewsCategory;
  predicted: ImpactDirection;
  actual: ImpactDirection;
  realized_return: number | null;
  rationale: string;
  takeaway: string;
}

export interface NewsStats {
  ok: boolean;
  n_items: number;
  n_evaluated: number;
  n_open: number;
  n_verified: number;
  n_correct: number;
  n_incorrect: number;
  accuracy: number | null;
  n_lessons: number;
}

export interface NewsItemsResponse {
  ok: boolean;
  count: number;
  items: NewsItem[];
}
export interface LessonsResponse {
  ok: boolean;
  count: number;
  lessons: Lesson[];
}
export interface VerifyResponse {
  ok: boolean;
  updated: number;
  correct: number;
  incorrect: number;
  unverified: number;
  lessons_total: number;
}

export const getNews = (opts: { category?: NewsCategory; priority?: NewsPriority; status?: HypothesisStatus } = {}) => {
  const p = new URLSearchParams();
  if (opts.category) p.set("category", opts.category);
  if (opts.priority) p.set("priority", opts.priority);
  if (opts.status) p.set("status", opts.status);
  const qs = p.toString();
  return getJson<NewsItemsResponse>(`/api/news/items${qs ? `?${qs}` : ""}`);
};
export const getNewsStats = () => getJson<NewsStats>("/api/news/stats");
export const getLessons = () => getJson<LessonsResponse>("/api/news/lessons");
export const ingestNews = (body: {
  title: string;
  content?: string;
  source?: string;
  category?: NewsCategory;
  priority?: NewsPriority;
}) => postJson<{ ok: boolean; item: NewsItem }>("/api/news/ingest", body);
export const seedNews = () => postJson<{ ok: boolean; seeded: number }>("/api/news/seed", {});
export const clearNews = (includeLessons = false) =>
  postJson<{ ok: boolean; cleared_items: number; cleared_lessons: number }>(
    `/api/news/clear${includeLessons ? "?include_lessons=true" : ""}`,
    {},
  );
export const verifyNews = (force = false) =>
  postJson<VerifyResponse>(`/api/news/verify${force ? "?force=true" : ""}`, {});
export const reevaluateNews = (id: string) =>
  postJson<{ ok: boolean; item: NewsItem }>(`/api/news/evaluate/${id}`, {});
export const newsFeedback = (id: string, correct: boolean, note = "") =>
  postJson<{ ok: boolean; item: NewsItem }>(`/api/news/feedback/${id}`, { correct, note });

export interface Bias {
  score: number;
  label: string;
  label_de: string;
  n: number;
  bullish: number;
  bearish: number;
  neutral: number;
}
export interface CategoryBias extends Bias {
  category: NewsCategory;
}
export interface MarketTop {
  id: string;
  title: string;
  category: NewsCategory;
  priority: NewsPriority;
  direction: ImpactDirection;
  asset: string;
  confidence: number;
  status: HypothesisStatus;
  provisional_status: "on_track" | "off_track" | "flat" | null;
  provisional_return: number | null;
}
export interface MarketSnapshot {
  overall: Bias;
  categories: CategoryBias[];
  top: MarketTop[];
  lookback_hours: number;
  narrative: string;
  narrative_model: string;
  narrative_at: string;
}

export interface LlmStatus {
  interval_s: number;
  running: boolean;
  seconds_until: number;
  hypotheses_upgraded: number;
  documents_generated: number;
  finished_at: number | null;
}

export interface TickResponse {
  ok: boolean;
  summary: {
    refreshed: number;
    refresh_error?: string;
    llm: { status: string; seconds_until?: number };
    llm_status: LlmStatus;
    track: { tracked: number; on_track: number; off_track: number; flat: number };
    settle: { updated: number; correct: number; incorrect: number; unverified: number; lessons_total: number };
    stats: Omit<NewsStats, "ok">;
    market: MarketSnapshot;
  };
  items: NewsItem[];
}

export const refreshNews = (limit = 40) =>
  postJson<{ ok: boolean; new: number; items?: NewsItem[]; error?: string }>(
    `/api/news/refresh?limit=${limit}`,
    {},
  );
/** One live-loop iteration: optional RSS refresh, then track + settle. */
export const tickNews = (refresh = false) =>
  postJson<TickResponse>(`/api/news/tick${refresh ? "?refresh=true" : ""}`, {});
export const getNewsDocument = (id: string, regenerate = false) =>
  getJson<{ ok: boolean; id: string; document: Briefing }>(
    `/api/news/document/${id}${regenerate ? "?regenerate=true" : ""}`,
  );

export const getCandles = (
  ticker: string,
  timeframe: string,
  opts: { start?: ChartTime; end?: ChartTime; limit?: number; rth?: boolean; adjust?: boolean } = {},
) => {
  const p = new URLSearchParams({ ticker, timeframe });
  if (opts.start != null) p.set("start", String(opts.start));
  if (opts.end != null) p.set("end", String(opts.end));
  if (opts.limit != null) p.set("limit", String(opts.limit));
  if (opts.rth) p.set("rth", "true");
  if (opts.adjust === false) p.set("adjust", "false"); // backend default = true
  return getJson<CandlesResponse>(`/api/charts/candles?${p.toString()}`);
};

// ── Quant Academy (/api/academy/*) ──────────────────────────────────────────
export type ModuleStatus = "locked" | "available" | "in_progress" | "completed";
export type ModuleLevel = "foundation" | "core" | "advanced" | "senior";

export interface AcademyModule {
  id: string;
  index: number;
  title: string;
  subtitle: string;
  level: ModuleLevel;
  track?: string;
  sessions: number;
  pos: { col: number; row: number };
  prerequisites: string[];
  repo_anchor: string;
  topics: string[];
  payoff: string;
  depth: string;
  viz: string[];
  content: string;
  // derived / merged with progress
  status: ModuleStatus;
  xp: number;
  completed_lessons: string[];
  quiz_scores: { at: string; score: number; n: number }[];
  progress_pct: number;
  content_md?: string | null;
}

export interface AcademyCurriculum {
  ok: boolean;
  title: string;
  subtitle: string;
  design_principle: string;
  active_module: string | null;
  totals: { xp: number; modules_completed: number; streak_days: number };
  modules: AcademyModule[];
}

export interface AcademyModuleDetail {
  ok: boolean;
  module: AcademyModule;
  progress: Record<string, unknown>;
  generated?: GeneratedContent | null;
}

export interface GeneratedContent {
  module_id: string;
  generated_at: string;
  source: string;
  cached?: boolean;
  exercises: { prompt: string; type: string }[];
  market_example: string;
  quiz: { question: string; options: string[]; answer_index: number }[];
  books: { title: string; author: string; category: string; rel: string; score: number }[];
}

export interface Book {
  path: string;
  rel: string;
  category: string;
  author: string;
  title: string;
}

export const getCurriculum = () => getJson<AcademyCurriculum>("/api/academy/curriculum");
export const getAcademyModule = (id: string, withGenerated = false) =>
  getJson<AcademyModuleDetail>(`/api/academy/module/${id}${withGenerated ? "?with_generated=true" : ""}`);
export const completeLesson = (module_id: string, lesson_id: string, xp = 20) =>
  postJson<AcademyCurriculum>("/api/academy/lesson/complete", { module_id, lesson_id, xp });
export const submitQuiz = (module_id: string, score: number, n: number) =>
  postJson<AcademyCurriculum>("/api/academy/quiz", { module_id, score, n });
export const getBooks = () =>
  getJson<{ ok: boolean; count: number; books: Book[] }>("/api/academy/books");
export const generateContent = (module_id: string, force = false) =>
  postJson<{ ok: boolean } & GeneratedContent>(
    `/api/academy/generate/${module_id}${force ? "?force=true" : ""}`,
    {},
  );

// ── Alpha Factory (/api/factory/*) ──────────────────────────────────────────
export interface FactoryState {
  updated: string;
  iterations: number;
  passed: number;
  rejected: number;
  errored: number;
  seen: number;
  elapsed_s: number;
  last_iter_s: number;
  rss_mb: number | null;
}
export interface FactoryStateResponse {
  ok: boolean;
  exists: boolean;
  running: boolean;
  age_s?: number | null;
  stop_pending?: boolean;
  state: FactoryState | null;
}
export interface PendingReport {
  name: string;
  title: string;
  mtime: string;
}
export interface RejectItem {
  ts: string;
  slug: string;
  reason: string;
  sharpe: number | null;
  oos_sharpe: number | null;
  perm_p: number | null;
  n_trades: number | null;
  hypothesis: string;
}

export const getFactoryState = () => getJson<FactoryStateResponse>("/api/factory/state");
export const getFactoryPending = () =>
  getJson<{ ok: boolean; count: number; reports: PendingReport[] }>("/api/factory/pending");
export const getFactoryReport = (name: string) =>
  getJson<{ ok: boolean; name: string; markdown: string; plots: string[] }>(
    `/api/factory/report?name=${encodeURIComponent(name)}`,
  );
export const factoryAssetUrl = (report: string, file: string) =>
  `${API_URL}/api/factory/asset?report=${encodeURIComponent(report)}&file=${encodeURIComponent(file)}`;
export const getFactoryRejects = (limit = 60) =>
  getJson<{ ok: boolean; count: number; items: RejectItem[] }>(`/api/factory/rejects?limit=${limit}`);
export const stopFactory = () =>
  postJson<{ ok: boolean; stop_pending: boolean }>("/api/factory/stop", {});

// ── Seasonality / Seasonal Calendar (/api/seasonal/*) ───────────────────────
export type SeasonalAssetClass =
  | "commodity" | "index" | "equity" | "crypto" | "other";
export type SeasonalStatus = "active" | "weak" | "decayed";
export type SeasonalDirection = "long" | "short";

export interface SeasonalUniverseItem {
  ticker: string;
  name: string;
  asset_class: SeasonalAssetClass;
  note: string;
}

export interface SeasonalPattern {
  ticker: string;
  name: string;
  asset_class: SeasonalAssetClass;
  direction: SeasonalDirection;
  start_md: [number, number];
  end_md: [number, number];
  window_label: string;
  calendar_days: number;
  n_years: number;
  mean_return: number; // fractional (0.05 = +5%)
  median_return: number;
  win_rate: number;
  std: number;
  sharpe: number;
  t_stat: number;
  p_value: number;
  recent_years: number | null;
  recent_mean: number | null;
  recent_win_rate: number | null;
  recent_p_value: number | null;
  status: SeasonalStatus;
  days_until_start: number | null;
  next_start: string | null;
  next_end: string | null;
}

export interface SeasonalCurvePoint {
  doy: number;
  label: string;
  cum_return: number; // percent
  mean_return: number; // percent (per day)
  hit_rate: number;
}
export interface SeasonalMonthly {
  month: string;
  mean_return: number; // percent (per ~month)
  hit_rate: number;
  p_value: number;
}
export interface SeasonalSpan {
  start: string;
  end: string;
  n_years: number;
}
export interface SeasonalMeta {
  ticker: string;
  name: string;
  asset_class: SeasonalAssetClass;
  note: string;
}

export interface SeasonalProfileResponse {
  ok: boolean;
  error?: string;
  ticker: string;
  meta: SeasonalMeta;
  span: SeasonalSpan;
  curve: SeasonalCurvePoint[];
  monthly: SeasonalMonthly[];
}
export interface SeasonalHeatmapResponse {
  ok: boolean;
  error?: string;
  ticker: string;
  meta: SeasonalMeta;
  years: number[];
  months: string[];
  matrix: (number | null)[][];
  monthly_avg: (number | null)[];
  yearly_total: (number | null)[];
}
export interface SeasonalPatternsResponse {
  ok: boolean;
  error?: string;
  ticker: string;
  meta: SeasonalMeta;
  span: SeasonalSpan;
  n_scanned: number;
  count: number;
  patterns: SeasonalPattern[];
}
export interface SeasonalPathPoint {
  t: number;
  value: number;
}
export interface SeasonalPatternDetailResponse {
  ok: boolean;
  error?: string;
  ticker: string;
  meta: SeasonalMeta;
  pattern: SeasonalPattern;
  path: SeasonalPathPoint[];
}
export interface SeasonalUpcomingResponse {
  ok: boolean;
  error?: string;
  exists?: boolean;
  asof: string;
  built_at?: string;
  horizon_days?: number;
  count: number;
  patterns: SeasonalPattern[];
  hint?: string;
}

export const getSeasonalUniverse = () =>
  getJson<{ ok: boolean; count: number; universe: SeasonalUniverseItem[] }>(
    "/api/seasonal/universe",
  );
export const getSeasonalProfile = (ticker: string, years?: number) =>
  getJson<SeasonalProfileResponse>(
    `/api/seasonal/profile?ticker=${encodeURIComponent(ticker)}${years ? `&years=${years}` : ""}`,
  );
export const getSeasonalHeatmap = (ticker: string) =>
  getJson<SeasonalHeatmapResponse>(
    `/api/seasonal/heatmap?ticker=${encodeURIComponent(ticker)}`,
  );
export const getSeasonalPatterns = (
  ticker: string,
  opts: { top?: number; bothDirections?: boolean; minWinRate?: number; maxPValue?: number } = {},
) => {
  const p = new URLSearchParams({ ticker });
  if (opts.top != null) p.set("top", String(opts.top));
  if (opts.bothDirections === false) p.set("both_directions", "false");
  if (opts.minWinRate != null) p.set("min_win_rate", String(opts.minWinRate));
  if (opts.maxPValue != null) p.set("max_p_value", String(opts.maxPValue));
  return getJson<SeasonalPatternsResponse>(`/api/seasonal/patterns?${p.toString()}`);
};
export const getSeasonalPattern = (
  ticker: string,
  start: string, // MM-DD
  end: string, // MM-DD
  direction: SeasonalDirection = "long",
) =>
  getJson<SeasonalPatternDetailResponse>(
    `/api/seasonal/pattern?ticker=${encodeURIComponent(ticker)}&start=${start}&end=${end}&direction=${direction}`,
  );
export const getSeasonalUpcoming = (horizon = 21, top = 20) =>
  getJson<SeasonalUpcomingResponse>(
    `/api/seasonal/upcoming?horizon=${horizon}&top=${top}`,
  );
export const runSeasonalScan = () =>
  postJson<{ ok: boolean; running: boolean; started?: boolean; already?: boolean }>(
    "/api/seasonal/scan",
    {},
  );
export interface SeasonalScanStatus {
  ok: boolean;
  exists: boolean;
  running: boolean;
  started_at: string | null;
  built_at: string | null;
  error: string | null;
  count: number;
  n_assets: number;
}
export const getSeasonalScanStatus = () =>
  getJson<SeasonalScanStatus>("/api/seasonal/scan/status");

// ── Intraday seasonality (/api/seasonal/intraday/*) ──────────────────────────
export interface IntradayInstrument {
  ticker: string;
  name: string;
  asset_class: SeasonalAssetClass;
  native_tf: string;
  start: string | null;
  end: string | null;
}
export interface IntradayHour {
  hour: number;
  mean_bps: number;
  hit_rate: number;
  n: number;
  p_value: number;
  cum_bps: number;
}
export interface IntradayWeekday {
  weekday: number;
  name: string;
  mean_bps: number;
  hit_rate: number;
  n: number;
  p_value: number;
}
export interface IntradayHeatmap {
  weekdays: string[];
  hours: number[];
  matrix: (number | null)[][];
}
export interface IntradayResponse {
  ok: boolean;
  error?: string;
  ticker: string;
  meta: { ticker: string; name: string; asset_class: SeasonalAssetClass; native_tf: string; note: string };
  tz: string;
  rth: boolean;
  span: { start: string; end: string; n_days: number };
  hours: IntradayHour[];
  weekdays: IntradayWeekday[];
  heatmap: IntradayHeatmap;
}

export const getIntradayInstruments = () =>
  getJson<{ ok: boolean; count: number; instruments: IntradayInstrument[] }>(
    "/api/seasonal/intraday/instruments",
  );
export const getIntraday = (ticker: string, years = 6, rth = true) =>
  getJson<IntradayResponse>(
    `/api/seasonal/intraday?ticker=${encodeURIComponent(ticker)}&years=${years}&rth=${rth}`,
  );

// ── Market Weather Radar / regime detection (/api/regime/*) ─────────────────
export type RegimeCode =
  | "high_vol_trend" | "low_vol_trend" | "high_vol_range" | "low_vol_range";
export type RegimeDirection = "bull" | "bear" | "neutral";

export interface RegimePaletteItem {
  code: RegimeCode;
  label: string;
  color: string;
  description: string;
}
export interface RegimeSnapshot {
  asof?: string;
  regime: RegimeCode | null;
  label: string;
  color: string;
  description?: string;
  direction?: RegimeDirection;
  direction_label?: string;
  vol_state?: "high" | "low";
  trend_state?: "trending" | "sideways";
  metrics?: {
    adx: number | null;
    plus_di: number | null;
    minus_di: number | null;
    atr_pct: number | null;
    hist_vol: number | null;
    vol_rank: number | null;
  };
}
export interface RegimeDistEntry {
  label: string;
  color: string;
  bars: number;
  pct: number;
}
export interface RegimeCurrentResponse {
  ok: boolean;
  error?: string;
  ticker: string;
  meta: { ticker: string; name: string; asset_class: string };
  snapshot: RegimeSnapshot;
  distribution: Record<RegimeCode, RegimeDistEntry>;
}
export interface RegimePricePoint {
  t: string;
  close: number | null;
  ema_fast: number | null;
  sma_mid: number | null;
  sma_slow: number | null;
  regime: RegimeCode | null;
}
export interface RegimeSpan {
  regime: RegimeCode;
  label: string;
  color: string;
  start: string;
  end: string;
  bars: number;
}
export interface RegimeTimelineResponse {
  ok: boolean;
  error?: string;
  ticker: string;
  meta: { ticker: string; name: string; asset_class: string };
  price: RegimePricePoint[];
  segments: RegimeSpan[];
  palette: Record<RegimeCode, string>;
}
export interface RegimePerfEntry {
  label: string;
  color: string;
  n: number;
  total_return: number;
  mean_bps: number;
  ann_return: number;
  sharpe: number;
  win_rate: number;
  max_drawdown: number;
  pct_of_time: number;
}
export interface RegimePerformanceResponse {
  ok: boolean;
  error?: string;
  ticker: string;
  meta: { ticker: string; name: string; asset_class: string };
  strategy: string;
  by_regime: Record<RegimeCode, RegimePerfEntry>;
  overall: { total_return: number; sharpe: number; n: number };
  order: RegimeCode[];
}
export interface RegimeOverviewItem {
  ticker: string;
  name: string;
  asset_class: string;
  snapshot: RegimeSnapshot | null;
  error?: string;
}
export interface RegimeOverviewResponse {
  ok: boolean;
  count: number;
  items: RegimeOverviewItem[];
  palette: Record<RegimeCode, { label: string; color: string }>;
}
export interface RegimeUniverseItem {
  ticker: string;
  name: string;
  asset_class: string;
  use_vix: boolean;
}

export const getRegimePalette = () =>
  getJson<{ ok: boolean; regimes: RegimePaletteItem[]; directions: Record<string, string> }>(
    "/api/regime/palette",
  );
export const getRegimeUniverse = () =>
  getJson<{ ok: boolean; count: number; universe: RegimeUniverseItem[] }>("/api/regime/universe");
export const getRegimeCurrent = (ticker: string, years = 8) =>
  getJson<RegimeCurrentResponse>(
    `/api/regime/current?ticker=${encodeURIComponent(ticker)}&years=${years}`,
  );
export const getRegimeTimeline = (ticker: string, years = 3) =>
  getJson<RegimeTimelineResponse>(
    `/api/regime/timeline?ticker=${encodeURIComponent(ticker)}&years=${years}`,
  );
export const getRegimePerformance = (ticker: string, strategy = "buy_hold", years = 8) =>
  getJson<RegimePerformanceResponse>(
    `/api/regime/performance?ticker=${encodeURIComponent(ticker)}&strategy=${strategy}&years=${years}`,
  );
export const getRegimeOverview = (years = 8) =>
  getJson<RegimeOverviewResponse>(`/api/regime/overview?years=${years}`);

// ── Statistical Arbitrage / Cointegration Explorer (/api/pairs/*) ───────────
export type PairSignal = "long_spread" | "short_spread" | "neutral";

export interface PairGroup {
  id: string;
  label: string;
  n_assets: number;
  n_pairs: number;
  tickers: string[];
}
export interface PairBacktestCurvePoint {
  t: string;
  equity: number;
}
export interface PairBacktest {
  beta_is: number | null;
  split_date: string | null;
  sharpe_full: number | null;
  sharpe_is: number | null;
  sharpe_oos: number | null;
  total_return: number | null;
  oos_return: number | null;
  max_drawdown: number | null;
  n_trades: number;
  win_rate: number | null;
  cost_bps: number | null;
  is_edge: boolean;
  curve?: PairBacktestCurvePoint[];
  split_index_frac?: number;
}
export interface PairStat {
  a: string;
  b: string;
  correlation: number | null;
  hedge_ratio: number | null;
  intercept: number | null;
  adf_stat: number | null;
  adf_pvalue: number | null;
  half_life: number | null;
  z_score: number | null;
  n_obs: number;
  cointegrated: boolean;
  signal: PairSignal;
  backtest?: PairBacktest | null;
}
export interface PairScanResponse {
  ok: boolean;
  error?: string;
  group: string;
  label: string;
  n_assets: number;
  n_possible_pairs: number;
  corr_threshold: number;
  years: number;
  stage1_survivors: number;
  n_cointegrated: number;
  n_edges: number;
  pairs: PairStat[];
}
export interface PairSeriesPoint {
  t: string;
  spread: number | null;
  z: number | null;
}
export interface PairMarker {
  t: string;
  z: number | null;
  kind: "long" | "short" | "exit";
}
export interface PairDetailResponse {
  ok: boolean;
  error?: string;
  a: string;
  b: string;
  stats: PairStat;
  z_window: number;
  use_log: boolean;
  series: PairSeriesPoint[];
  markers: PairMarker[];
  backtest?: PairBacktest | null;
}
export interface PairHeatmapResponse {
  ok: boolean;
  error?: string;
  group: string;
  label: string;
  tickers: string[];
  strength: (number | null)[][];
  pvalue: (number | null)[][];
}

export const getPairUniverse = () =>
  getJson<{ ok: boolean; groups: PairGroup[] }>("/api/pairs/universe");
export const getPairScan = (group: string, corr = 0.7, years = 6, zWindow = 60) =>
  getJson<PairScanResponse>(
    `/api/pairs/scan?group=${encodeURIComponent(group)}&corr=${corr}&years=${years}&z_window=${zWindow}`,
  );
export const getPairDetail = (a: string, b: string, years = 6, zWindow = 60) =>
  getJson<PairDetailResponse>(
    `/api/pairs/pair?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}&years=${years}&z_window=${zWindow}`,
  );
export const getPairHeatmap = (group: string, years = 6) =>
  getJson<PairHeatmapResponse>(
    `/api/pairs/heatmap?group=${encodeURIComponent(group)}&years=${years}`,
  );

// ── Risk Desk / institutional risk management (/api/risk/*) ─────────────────
export type RiskWarnLevel = "green" | "yellow" | "red" | "unknown";

export interface RiskVarEsCell {
  confidence: number;
  horizon: number;
  var_historical: number | null;
  var_parametric: number | null;
  es_historical: number | null;
  es_parametric: number | null;
}
export interface RiskStrategyMeta {
  num: string;
  label: string;
  name: string;
  status: string | null;
  category: string | null;
  n_trades: number;
  n_days: number;
  start: string;
  end: string;
  vol_annual: number | null;
  return_annual: number | null;
}
export interface RiskPerStrategy {
  strategy: string;
  weight: number;
  n_obs: number;
  vol_annual: number | null;
  return_annual: number | null;
  sharpe: number | null;
  risk_pct: number | null;
  var_95_1d: number | null;
  es_95_1d: number | null;
}
export interface RiskDiversification {
  diversification_ratio: number | null;
  benefit: number | null;
  weighted_avg_vol: number | null;
  portfolio_vol: number | null;
}
export interface RiskPortfolio {
  return_annual: number | null;
  vol_annual: number | null;
  sharpe: number | null;
  var_es: Record<string, RiskVarEsCell>;
  diversification: RiskDiversification;
  var_currency?: Record<string, number>;
  es_currency?: Record<string, number>;
}
export interface RiskSummary {
  n_strategies: number;
  n_obs: number;
  span: { start: string | null; end: string | null };
  portfolio: RiskPortfolio;
  per_strategy: RiskPerStrategy[];
  capital?: number;
}
export interface RiskAllocation {
  method: string;
  weights: Record<string, number>;
  exp_return: number | null;
  vol: number | null;
  sharpe: number | null;
  notes: string[];
  risk_contribution: Record<string, number>;
}
export interface RiskDashboard {
  ok: boolean;
  error?: string;
  window: string;
  weighting: string;
  weighting_label: string;
  capital: number;
  var_limit_pct: number;
  warn_level: RiskWarnLevel;
  n_obs: number;
  span: { start: string | null; end: string | null };
  summary: RiskSummary;
  allocations: Record<string, RiskAllocation>;
  active_weights: Record<string, number>;
  correlation: { labels: string[]; matrix: (number | null)[][] };
  strategies: RiskStrategyMeta[];
}
export interface RiskBook {
  ok: boolean;
  error?: string;
  count: number;
  strategies: RiskStrategyMeta[];
  default_selection: string[];
  weightings: { key: string; label: string }[];
  windows: { key: string; days: number | null; label: string }[];
  span: { start: string | null; end: string | null };
}
export interface RiskCorrelationSeries {
  ok: boolean;
  error?: string;
  a: string;
  b: string;
  rolling_window: number;
  full_correlation: number | null;
  series: { t: string; corr: number }[];
}

export const getRiskBook = () => getJson<RiskBook>("/api/risk/book");
export const getRiskDashboard = (opts: {
  window?: string;
  nums?: string[];
  capital?: number;
  weighting?: string;
  varLimitPct?: number;
} = {}) => {
  const p = new URLSearchParams();
  if (opts.window) p.set("window", opts.window);
  if (opts.nums && opts.nums.length) p.set("nums", opts.nums.join(","));
  if (opts.capital != null) p.set("capital", String(opts.capital));
  if (opts.weighting) p.set("weighting", opts.weighting);
  if (opts.varLimitPct != null) p.set("var_limit_pct", String(opts.varLimitPct));
  const qs = p.toString();
  return getJson<RiskDashboard>(`/api/risk/dashboard${qs ? `?${qs}` : ""}`);
};
export const getRiskCorrelation = (a: string, b: string, rollingWindow = 90) =>
  getJson<RiskCorrelationSeries>(
    `/api/risk/correlation?a=${a}&b=${b}&rolling_window=${rollingWindow}`,
  );

// ── Switchboard / dynamic strategy routing (/api/switchboard/*) ─────────────
export type RoutingStatus = "ACTIVE" | "PAUSED";
export type CellRating = "excellent" | "good" | "neutral" | "loss";

export interface SwitchboardCell {
  label: string;
  color: string;
  n: number;
  total_return: number;
  mean_bps: number;
  ann_return: number;
  sharpe: number;
  profit_factor: number;
  win_rate: number;
  max_drawdown: number;
  pct_of_time: number;
  qualified: boolean;
  rating: CellRating;
}
export interface SwitchboardRow {
  num: string;
  label: string;
  name: string;
  status_catalog: string | null;
  category: string | null;
  n_total: number;
  cells: Record<RegimeCode, SwitchboardCell>;
  active_regimes: RegimeCode[];
  status: RoutingStatus;
}
export interface SwitchboardBenchmark {
  ticker: string;
  name: string;
  asset_class: string;
}
export interface SwitchboardMatrixResponse {
  ok: boolean;
  error?: string;
  benchmark: string;
  benchmark_meta: { ticker: string; name: string; asset_class: string };
  years: number;
  current: RegimeSnapshot;
  switch: {
    current_regime: RegimeCode | null;
    previous_regime: RegimeCode | null;
    since: string | null;
    bars_in_regime: number;
  };
  distribution: Record<RegimeCode, RegimeDistEntry>;
  thresholds: {
    min_sharpe: number;
    min_profit_factor: number;
    min_trades: number;
    excellent_sharpe: number;
    excellent_profit_factor: number;
  };
  current_regime: RegimeCode | null;
  regimes: { code: RegimeCode; label: string; color: string }[];
  rating_colors: Record<CellRating, string>;
  rows: SwitchboardRow[];
  summary: { n_strategies: number; active: number; paused: number };
}

export const getSwitchboardBenchmarks = () =>
  getJson<{ ok: boolean; count: number; benchmarks: SwitchboardBenchmark[] }>(
    "/api/switchboard/benchmarks",
  );
export const getSwitchboardMatrix = (
  opts: { benchmark?: string; years?: number; minSharpe?: number; minProfitFactor?: number; minTrades?: number } = {},
) => {
  const p = new URLSearchParams();
  if (opts.benchmark) p.set("benchmark", opts.benchmark);
  if (opts.years != null) p.set("years", String(opts.years));
  if (opts.minSharpe != null) p.set("min_sharpe", String(opts.minSharpe));
  if (opts.minProfitFactor != null) p.set("min_profit_factor", String(opts.minProfitFactor));
  if (opts.minTrades != null) p.set("min_trades", String(opts.minTrades));
  const qs = p.toString();
  return getJson<SwitchboardMatrixResponse>(`/api/switchboard/matrix${qs ? `?${qs}` : ""}`);
};

// ── COT Institutional Positioning Desk (/api/cot/*) ─────────────────────────
export type CotGroup = "energy" | "metal" | "grain" | "livestock" | "fx" | "index";
export type CotBias = "bullish" | "bearish" | "neutral";

export interface CotMarket {
  root: string;
  name: string;
  group: CotGroup;
  price_ticker: string;
}
export interface CotSignal {
  status: string;
  bias: CotBias;
  severity: "extreme" | "elevated" | "mild" | "none";
}
export interface CotRow {
  t: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  comm_net: number;
  noncomm_net: number;
  comm_index: number | null;
  comm_z: number | null;
}
export interface CotLatest {
  ref_date: string;
  comm_net: number;
  noncomm_net: number;
  comm_index: number | null;
  comm_z: number | null;
  noncomm_index: number | null;
  noncomm_z: number | null;
  open_interest: number;
  hedging_pressure: number | null;
  signal: CotSignal;
}
export interface CotZones {
  index_low: number;
  index_high: number;
  extreme_z: number;
}
export interface CotAssetResponse {
  ok: boolean;
  error?: string;
  root: string;
  name: string;
  group: CotGroup;
  price_ticker: string;
  window: number;
  years: number;
  has_price: boolean;
  rows: CotRow[];
  latest: CotLatest;
  zones: CotZones;
}
export interface CotScanRow {
  root: string;
  name: string;
  group: CotGroup;
  ref_date: string;
  comm_net: number;
  noncomm_net: number;
  open_interest: number;
  comm_index: number;
  noncomm_index: number;
  comm_z: number | null;
  noncomm_z: number | null;
  hedging_pressure: number;
  signal: CotSignal;
}
export interface CotScanResponse {
  ok: boolean;
  error?: string;
  count: number;
  window: number;
  markets: CotScanRow[];
  zones: CotZones;
}

export const getCotUniverse = () =>
  getJson<{ ok: boolean; count: number; markets: CotMarket[] }>("/api/cot/universe");
export const getCotAsset = (root: string, window = 156, years = 5) =>
  getJson<CotAssetResponse>(
    `/api/cot/asset?root=${encodeURIComponent(root)}&window=${window}&years=${years}`,
  );
export const getCotScan = (window = 156) =>
  getJson<CotScanResponse>(`/api/cot/scan?window=${window}`);

// ── Alternative Data / Insights Desk (/api/altdata/*) ───────────────────────
export type AltSeverity = "info" | "warn" | "alert";
export type AltScoreKind = "commits" | "sentiment" | null;

export interface AltSource {
  ticker: string;
  name: string;
  asset_class: "equity" | "crypto";
  repo: string | null;
  cik: string | null;
}
export interface AltEvent {
  ts: string;
  kind: "sec_filing" | "github_commits" | "github_stars";
  ticker: string;
  title: string;
  value: number | null;
  severity: AltSeverity;
  url: string | null;
}
export interface AltPricePoint {
  t: string;
  close: number | null;
}
export interface AltScorePoint {
  t: string;
  value: number | null;
  z: number | null;
}
export interface AltFilingMarker {
  t: string;
  label: string;
  divergence: number | null;
  sentiment: number | null;
  url: string | null;
}
export interface AltSeriesResponse {
  ok: boolean;
  error?: string;
  ticker: string;
  name: string;
  score_kind: AltScoreKind;
  price: AltPricePoint[];
  score: AltScorePoint[];
  filings: AltFilingMarker[];
}
export interface AltAnomalyPoint {
  ticker: string;
  name: string;
  asset_class: "equity" | "crypto";
  kind: "commits" | "filing" | null;
  z: number | null;
  z_raw: number | null;
  price_ret_5d: number | null;
  size: number | null;
  detail: string;
}
export interface AltStatus {
  ok: boolean;
  store: {
    n_filings: number;
    n_events: number;
    n_repos_tracked: number;
    n_sources: number;
    last_event: string | null;
  };
  job: {
    status: "idle" | "running" | "done" | "error";
    started: number | null;
    finished: number | null;
    summary: unknown;
    error: string | null;
  };
}

export const getAltSources = () =>
  getJson<{ ok: boolean; count: number; sources: AltSource[] }>("/api/altdata/sources");
export const getAltStatus = () => getJson<AltStatus>("/api/altdata/status");
export const getAltEvents = (limit = 50) =>
  getJson<{ ok: boolean; events: AltEvent[] }>(`/api/altdata/events?limit=${limit}`);
export const getAltSeries = (ticker: string, years = 3) =>
  getJson<AltSeriesResponse>(
    `/api/altdata/series?ticker=${encodeURIComponent(ticker)}&years=${years}`,
  );
export const getAltAnomalies = () =>
  getJson<{ ok: boolean; points: AltAnomalyPoint[] }>("/api/altdata/anomalies");
export const ingestAltData = (tickers?: string[], days = 90) =>
  postJson<{ ok: boolean; status?: string; error?: string }>("/api/altdata/ingest", {
    tickers: tickers ?? null,
    days,
  });
export const seedAltData = () =>
  postJson<{ ok: boolean; n_filings: number; n_events: number }>("/api/altdata/seed", {});

// ── ML Feature Store / Feature-Health Desk (/api/features/*) ────────────────
export type FeatureGroup = "momentum" | "volatility" | "structure";

export interface FactorDef {
  name: string;
  group: FeatureGroup;
  description: string;
}
export interface FeatureTicker {
  ticker: string;
  name: string;
  built: boolean;
}
export interface FeatureStatusRow {
  ticker: string;
  factor: string;
  group: FeatureGroup;
  status: "up-to-date" | "stale";
  last_computed: number;
  age_days: number;
  compute_ms: number;
  n_rows: number;
  n_missing: number;
  missing_rate: number;
  disk_bytes: number;
}
export interface FeatureStatusResponse {
  ok: boolean;
  error?: string;
  ticker: string | null;
  count: number;
  total_disk_bytes: number;
  stale: number;
  rows: FeatureStatusRow[];
}
export interface FeatureCorrelation {
  ok: boolean;
  error?: string;
  ticker: string;
  labels: string[];
  matrix: (number | null)[][];
  n_rows: number;
}
export interface FeatureTimings {
  ok: boolean;
  error?: string;
  ticker: string;
  bars: { factor: string; group: FeatureGroup; compute_ms: number }[];
}
export interface FeatureLeakageFactor {
  ok: boolean;
  max_abs_diff: number;
  checks: number;
}
export interface FeatureLeakage {
  ok: boolean;
  error?: string;
  ticker: string;
  n_cutoffs: number;
  cutoffs: string[];
  factors: Record<string, FeatureLeakageFactor>;
}
export interface FeatureComputeResult {
  ok: boolean;
  error?: string;
  ticker: string;
  n_rows: number;
  n_factors: number;
  start: string | null;
  end: string | null;
}

export const getFeatureFactors = () =>
  getJson<{ ok: boolean; groups: FeatureGroup[]; count: number; factors: FactorDef[] }>(
    "/api/features/factors",
  );
export const getFeatureUniverse = () =>
  getJson<{ ok: boolean; tickers: FeatureTicker[] }>("/api/features/universe");
export const getFeatureStatus = (ticker?: string) =>
  getJson<FeatureStatusResponse>(
    `/api/features/status${ticker ? `?ticker=${encodeURIComponent(ticker)}` : ""}`,
  );
export const getFeatureCorrelation = (ticker: string) =>
  getJson<FeatureCorrelation>(`/api/features/correlation?ticker=${encodeURIComponent(ticker)}`);
export const getFeatureTimings = (ticker: string) =>
  getJson<FeatureTimings>(`/api/features/timings?ticker=${encodeURIComponent(ticker)}`);
export const getFeatureLeakage = (ticker: string) =>
  getJson<FeatureLeakage>(`/api/features/leakage?ticker=${encodeURIComponent(ticker)}`);
export const computeFeatures = (ticker: string, start = "2010-01-01") =>
  postJson<FeatureComputeResult>("/api/features/compute", { ticker, start });

// ── Execution Desk / Slippage Radar (/api/execution/*) ──────────────────────
export type LiquidityZone = "safe" | "caution" | "warning" | "danger" | "unknown";

export interface ExecDemo {
  key: string;
  strategy: string;
  ticker: string;
  name: string;
  kind: "trend" | "meanrev";
  capital: number;
}
export interface CostComponent {
  return_drag: number;
  pct_of_gross: number;
}
export interface ExecGauge {
  participation: number | null;
  zone: LiquidityZone;
  label: string;
  order_notional: number;
  dollar_adv: number;
}
export interface EquityPoint {
  t: string;
  v: number;
}
export interface ExecSimulation {
  ok: boolean;
  error?: string;
  strategy: string;
  ticker: string;
  name: string;
  kind: string;
  capital: number;
  impact_y: number;
  equity_theoretical: EquityPoint[];
  equity_realized: EquityPoint[];
  breakdown: {
    gross_total_return: number;
    net_total_return: number;
    spread: CostComponent;
    impact: CostComponent;
    commission: CostComponent;
    latency_bps: number;
    total_cost_return: number;
    n_trades: number;
    avg_participation: number;
    max_participation: number;
  };
  gauge: ExecGauge;
}
export interface ExecBreakdownRow {
  key: string;
  strategy: string;
  ticker: string;
  name: string;
  spread_bps: number;
  impact_bps: number;
  commission_bps: number;
  latency_bps: number;
  spread_pct: number;
  impact_pct: number;
  commission_pct: number;
  gross_return: number;
  net_return: number;
  n_trades: number;
  max_participation: number;
  gauge_zone: LiquidityZone;
  error?: string;
}
export interface ExecRadarStrategy {
  strategy: string;
  n: number;
  latency_bps: number;
  execution_bps: number;
  fee_bps: number;
  total_bps: number;
  latency_seconds: number | null;
}
export interface ExecRadar {
  ok: boolean;
  error?: string;
  n: number;
  by_strategy: ExecRadarStrategy[];
  overall: {
    n?: number;
    latency_bps?: number;
    execution_bps?: number;
    fee_bps?: number;
    total_bps?: number;
    latency_seconds?: number | null;
  };
  ledger_path?: string;
}

export const getExecUniverse = () =>
  getJson<{ ok: boolean; count: number; items: ExecDemo[] }>("/api/execution/universe");
export const getExecSimulation = (
  strategy: string,
  ticker: string,
  opts: { capital?: number; impactY?: number } = {},
) => {
  const p = new URLSearchParams({ strategy, ticker });
  if (opts.capital != null) p.set("capital", String(opts.capital));
  if (opts.impactY != null) p.set("impact_y", String(opts.impactY));
  return getJson<ExecSimulation>(`/api/execution/simulate?${p.toString()}`);
};
export const getExecBreakdown = (impactY = 0.5) =>
  getJson<{ ok: boolean; impact_y: number; rows: ExecBreakdownRow[] }>(
    `/api/execution/breakdown?impact_y=${impactY}`,
  );
export const getExecRadar = () => getJson<ExecRadar>("/api/execution/radar");
export const seedExecLedger = (nPerStrategy = 60) =>
  postJson<ExecRadar & { n_logged: number }>(
    `/api/execution/seed?n_per_strategy=${nPerStrategy}`,
    {},
  );

// ── Attribution Desk (/api/attribution/*) ──────────────────────────────────
export type Quadrant = "premium" | "leveraged" | "defensive" | "closet_beta";

export interface AttribStrategy {
  num: string;
  label: string;
  name: string;
  status: string | null;
  category: string | null;
  sector: string;
  n_trades: number;
  vol_annual: number;
  return_annual: number;
}
export interface AttribBook {
  ok: boolean;
  error?: string;
  count: number;
  strategies: AttribStrategy[];
  default_selection: string[];
  benchmarks: { key: string; label: string }[];
  windows: { key: string; days: number | null; label: string }[];
  sectors: Record<string, string>;
  span: { start: string | null; end: string | null };
}
export interface FactorPoint {
  num: string;
  label: string;
  name: string;
  sector: string;
  category: string | null;
  beta: number;
  alpha_annual: number;
  t_alpha: number;
  p_alpha: number;
  r_squared: number;
  n: number;
  quadrant: Quadrant;
}
export interface AttribFactors {
  ok: boolean;
  error?: string;
  benchmark: string;
  window: string;
  points: FactorPoint[];
  portfolio: Omit<FactorPoint, "num" | "label" | "name" | "sector" | "category"> | null;
}
export interface RollingPoint {
  t: string;
  beta: number;
  alpha: number;
  bench_dd: number;
}
export interface AttribRolling {
  ok: boolean;
  error?: string;
  num: string;
  label: string;
  benchmark: string;
  roll_window: number;
  series: RollingPoint[];
}
export interface BrinsonSector {
  sector: string;
  label: string;
  benchmark: string | null;
  n_sleeves: number;
  w_p: number;
  r_p: number;
  w_b: number;
  r_b: number;
  allocation: number;
  selection: number;
  interaction: number;
  total: number;
}
export interface WaterfallStep {
  label: string;
  kind: "start" | "effect" | "end";
  value: number;
  base?: number;
  cumulative: number;
}
export interface AttribBrinson {
  ok: boolean;
  error?: string;
  window: string;
  n_sectors: number;
  n_sectors_with_benchmark: number;
  portfolio_return: number;
  benchmark_return: number;
  active_return: number;
  allocation_total: number;
  selection_total: number;
  interaction_total: number;
  residual: number;
  sectors: BrinsonSector[];
  waterfall: WaterfallStep[];
}

export const getAttribBook = () => getJson<AttribBook>("/api/attribution/book");
export const getAttribFactors = (benchmark = "SPY", window = "full", nums?: string) =>
  getJson<AttribFactors>(
    `/api/attribution/factors?benchmark=${encodeURIComponent(benchmark)}&window=${window}${nums ? `&nums=${nums}` : ""}`,
  );
export const getAttribRolling = (num = "PORTFOLIO", benchmark = "SPY", rollWindow = 63) =>
  getJson<AttribRolling>(
    `/api/attribution/rolling?num=${encodeURIComponent(num)}&benchmark=${encodeURIComponent(benchmark)}&roll_window=${rollWindow}`,
  );
export const getAttribBrinson = (window = "252") =>
  getJson<AttribBrinson>(`/api/attribution/brinson?window=${window}`);

// ── GA Optimizer / Evolution Monitor (/api/optimize/*) ──────────────────────
export interface OptInstrument {
  ticker: string;
  name: string;
  asset_class: string;
  cost: string;
}
export interface OptParamDef {
  name: string;
  low: number;
  high: number;
  integer: boolean;
  step: number | null;
  label: string;
}
export interface OptStrategy {
  key: string;
  label: string;
  params: OptParamDef[];
  surface_axes: string[];
}
export interface OptConfig {
  ok: boolean;
  instruments: OptInstrument[];
  strategies: OptStrategy[];
  fitness_functions: { key: string; label: string }[];
  defaults: {
    population_size: number;
    generations: number;
    selection: string;
    crossover_prob: number;
    base_mutation_rate: number;
    min_mutation_rate: number;
    elitism: number;
    oos_fraction: number;
    haircut_reject_pct: number;
    seed: number;
  };
}
export interface OptGeneration {
  generation: number;
  best_fitness: number | null;
  avg_fitness: number | null;
  worst_fitness: number | null;
  diversity: number | null;
  mutation_rate: number | null;
  best_params: Record<string, number>;
}
export interface OptScore {
  sharpe: number | null;
  cagr: number | null;
  max_drawdown: number | null;
  calmar: number | null;
  annual_volatility: number | null;
  n_trades: number;
  fitness: number | null;
}
export interface OptTopRow {
  params: Record<string, number>;
  is: OptScore;
  oos: OptScore;
  haircut_pct: number | null;
  overfit: boolean;
}
export interface OptSurface {
  x_name: string;
  y_name: string;
  x: number[];
  y: number[];
  z: (number | null)[][];
  best_x: number | null;
  best_y: number | null;
}
export interface OptResult {
  param_names: string[];
  fitness_metric: string;
  oos_fraction: number;
  haircut_reject_pct: number;
  config: Record<string, number | string>;
  history: OptGeneration[];
  top: OptTopRow[];
  best: OptTopRow | null;
  surface: OptSurface | null;
  ticker: string;
  strategy: string;
  cost_model: string;
  span: { start: string; end: string; bars: number };
}
export interface OptJob {
  ok: boolean;
  job_id: string;
  status: "running" | "done" | "error";
  ticker: string;
  strategy: string;
  fitness_metric: string;
  generations: number;
  current_generation: number;
  progress: number;
  history: OptGeneration[];
  result?: OptResult;
  error?: string;
}
export interface OptimizeRequest {
  ticker?: string;
  strategy?: string;
  fitness_metric?: string;
  start?: string;
  end?: string | null;
  cost_model?: string | null;
  population_size?: number;
  generations?: number;
  selection?: string;
  crossover_prob?: number;
  base_mutation_rate?: number;
  min_mutation_rate?: number;
  elitism?: number;
  seed?: number;
  oos_fraction?: number;
  haircut_reject_pct?: number;
  top_n?: number;
  bounds?: Record<string, { low?: number; high?: number }>;
}

export const getOptimizeConfig = () => getJson<OptConfig>("/api/optimize/config");
export const startOptimize = (req: OptimizeRequest) =>
  postJson<{ ok: boolean; job_id: string; status: string }>("/api/optimize/run", req);
export const getOptimizeJob = (jobId: string) =>
  getJson<OptJob>(`/api/optimize/job/${jobId}`);

// ── Swarm Command Center / hybrid multi-agent desk (/api/swarm/*) ───────────
export type DroneStatus = "idle" | "computing" | "done" | "error";
export type Stance = "risk_on" | "risk_off" | "neutral";
export type RoutingAction = "ACTIVE" | "PAUSED";
export type SwarmJobStatus = "running" | "drones" | "commander" | "done" | "error";

export interface SwarmDroneSpec {
  key: string;
  label: string;
  task: string;
  accent: string;
}
export interface SwarmConfig {
  ok: boolean;
  drones: SwarmDroneSpec[];
  ollama: { base_url: string; model: string };
  gemini: { model: string; fallback_model: string };
}
export interface SwarmPing {
  ok: boolean;
  ollama: {
    base_url: string;
    model: string;
    reachable: boolean;
    models: string[];
    model_present: boolean;
  };
  gemini: { model: string; fallback_model: string; has_key: boolean };
}
export interface DroneTile {
  drone: string;
  label: string;
  task: string;
  accent: string;
  status: DroneStatus;
  ok: boolean | null;
  signal: Record<string, unknown> | null;
  headline: string | null;
  model: string | null;
  stance: Stance | null;
  elapsed_ms: number | null;
  rss_mb: number | null;
  error: string | null;
}
export interface SwarmAllocation {
  num: string;
  name: string | null;
  action: RoutingAction;
  weight: number;
  reason: string;
}
export interface SwarmVerdict {
  regime_summary: string;
  verdict: string;
  risk_note: string;
  allocations: SwarmAllocation[];
  model_used: string;
  source: "gemini" | "deterministic";
  commander_attempts: number;
  degraded_reason?: string;
}
export interface SwarmClientStatus {
  ollama: { base_url: string; model: string; reachable: boolean; models: string[] };
  gemini: { model: string; fallback_model: string; has_key: boolean };
}
export interface SwarmStrategyRef {
  num: string;
  name: string | null;
  category: string | null;
  sharpe: number | null;
  // Phase-2 regime-conditional fields (present when the book router ran)
  regime_status?: RoutingAction;
  allowed_regimes?: RegimeCode[];
  current_regime_sharpe?: number | null;
  current_regime_pf?: number | null;
}
export interface SwitchActor {
  num: string;
  name: string | null;
}
export interface SwarmRegimeSwitch {
  current_regime: RegimeCode | null;
  current_label: string | null;
  current_color?: string;
  previous_regime: RegimeCode | null;
  previous_label: string | null;
  since: string | null;
  bars_in_regime: number;
  just_switched: boolean;
  n_switches: number;
  benchmark?: string;
  delta?: {
    activated: SwitchActor[];
    deactivated: SwitchActor[];
    n_activated: number;
    n_deactivated: number;
  };
  summary?: { n_strategies: number; active: number; paused: number };
}
export interface SwarmJob {
  ok?: boolean;
  job_id?: string;
  status: SwarmJobStatus;
  started: number;
  finished: number | null;
  drones: DroneTile[];
  strategies: SwarmStrategyRef[];
  regime_switch: SwarmRegimeSwitch | null;
  verdict: SwarmVerdict | null;
  config: SwarmClientStatus | null;
  error: string | null;
}

// ── Conditional Backtesting / Regime Router (/api/conditional/*) ─────────────
export interface RegimeTradeStat {
  label: string;
  color: string;
  n_trades: number;
  win_rate: number;
  mean_return: number;
  total_return: number;
  profit_factor: number;
}
export interface StrategyRegimeMatrix {
  ok: boolean;
  error?: string;
  num: string;
  name: string | null;
  benchmark: string;
  matrix: {
    cells: Record<RegimeCode, SwitchboardCell>;
    allowed_market_regimes: RegimeCode[];
    best_regime: RegimeCode | null;
  } | null;
  allowed_market_regimes: RegimeCode[];
  best_regime: RegimeCode | null;
  n_trades: number;
  trade_stats: Record<RegimeCode, RegimeTradeStat> | null;
  tagged_trades: Record<string, unknown>[];
  regimes: { code: RegimeCode; label: string }[];
}

export const getStrategyRegimeMatrix = (num: string, benchmark = "SPY") =>
  getJson<StrategyRegimeMatrix>(
    `/api/conditional/strategy/${encodeURIComponent(num)}?benchmark=${benchmark}`,
  );

// ── Settings / BYOK encrypted vault (/api/settings/*) ────────────────────────
export interface KnownService {
  service: string;
  label: string;
  group: string;
  set: boolean;
}
export interface VaultStatus {
  ok: boolean;
  error?: string;
  vault_exists: boolean;
  unlocked: boolean;
  services_set: string[];
  known: KnownService[];
}

export const getVaultStatus = () => getJson<VaultStatus>("/api/settings/status");
export const initVault = (password: string) =>
  postJson<VaultStatus>("/api/settings/init", { password });
export const unlockVault = (password: string) =>
  postJson<VaultStatus>("/api/settings/unlock", { password });
export const lockVault = () => postJson<VaultStatus>("/api/settings/lock", {});
export const setVaultKey = (service: string, value: string) =>
  postJson<VaultStatus>("/api/settings/key", { service, value });
export const deleteVaultKey = (service: string) =>
  delJson<VaultStatus>(`/api/settings/key/${encodeURIComponent(service)}`);
export const changeVaultPassword = (old_password: string, new_password: string) =>
  postJson<VaultStatus>("/api/settings/password", { old_password, new_password });

// ── Unified data providers (/api/data/*) ────────────────────────────────────
export interface DataProvider {
  provider: string;
  label: string;
  available: boolean;
  needs_keys: boolean;
  reason: string;
}
export interface DataProvidersResponse {
  ok: boolean;
  providers: DataProvider[];
  timeframes: string[];
}
export interface DataBar {
  t: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
export interface DataBarsResponse {
  ok: boolean;
  error?: string;
  symbol: string;
  provider: string;
  timeframe: string;
  count: number;
  start: string | null;
  end: string | null;
  bars: DataBar[];
}

export const getDataProviders = () => getJson<DataProvidersResponse>("/api/data/providers");
export const getDataBars = (
  opts: { symbol?: string; provider?: string; timeframe?: string; start?: string; limit?: number } = {},
) => {
  const p = new URLSearchParams();
  if (opts.symbol) p.set("symbol", opts.symbol);
  if (opts.provider) p.set("provider", opts.provider);
  if (opts.timeframe) p.set("timeframe", opts.timeframe);
  if (opts.start) p.set("start", opts.start);
  if (opts.limit != null) p.set("limit", String(opts.limit));
  const qs = p.toString();
  return getJson<DataBarsResponse>(`/api/data/bars${qs ? `?${qs}` : ""}`);
};

export const getSwarmConfig = () => getJson<SwarmConfig>("/api/swarm/config");
export const getSwarmPing = () => getJson<SwarmPing>("/api/swarm/ping");
export const runSwarm = () =>
  postJson<{ ok: boolean; job_id: string; status: string }>("/api/swarm/run", {});
export const getSwarmJob = (id: string) => getJson<SwarmJob>(`/api/swarm/job/${id}`);
export const getSwarmLast = () =>
  getJson<{ ok: boolean; job_id: string | null; job: SwarmJob | null }>("/api/swarm/last");

export const getFootprint = (
  ticker: string,
  timeframe: string,
  start: ChartTime,
  end: ChartTime,
  opts: { rth?: boolean; binSize?: number; adjust?: boolean } = {},
) => {
  const p = new URLSearchParams({
    ticker,
    timeframe,
    start: String(start),
    end: String(end),
  });
  if (opts.rth) p.set("rth", "true");
  if (opts.binSize != null) p.set("bin_size", String(opts.binSize));
  if (opts.adjust === false) p.set("adjust", "false");
  return getJson<FootprintResponse>(`/api/charts/footprint?${p.toString()}`);
};
