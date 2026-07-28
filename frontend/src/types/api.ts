// ── Hotel ─────────────────────────────────────────────────────────────────────

export interface Hotel {
  id: string;
  name: string;
  brand: string;
  city: string;
  country: string;
  star_rating: number;
  total_rooms: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface HotelListResponse {
  total: number;
  items: Hotel[];
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export interface DemandPoint {
  date: string;
  demand_index: number;
  occupancy_pct: number;
  adr: number;
}

export interface DashboardSummary {
  hotel_id: string;
  hotel_name: string;
  as_of_date: string;

  // Core KPIs
  occupancy_pct: number;
  adr: number;
  revpar: number;
  available_rooms: number;
  total_rooms: number;
  occupied_rooms: number;
  demand_index: number;
  compset_adr: number | null;

  // Trend
  demand_trend: DemandPoint[];

  // AI extension fields (null until engines are wired in)
  forecasted_occupancy: number | null;
  recommended_rate: number | null;
  ai_insight: string | null;
}

export interface DailyMetricsResponse {
  id: string;
  hotel_id: string;
  date: string;
  occupied_rooms: number;
  total_rooms: number;
  adr: number;
  revenue: number;
  demand_index: number;
  compset_adr: number | null;
  occupancy_pct: number;
  revpar: number;
  available_rooms: number;
  created_at: string;
}

export interface DailyMetricsListResponse {
  total: number;
  items: DailyMetricsResponse[];
}

// ── Forecast ─────────────────────────────────────────────────────────────────

export interface ForecastPoint {
  forecast_date: string;
  occupancy_pct: number;
  lower_bound: number;
  upper_bound: number;
}

export interface ForecastResponse {
  hotel_id: string;
  model_name: string;
  origin_date: string;
  horizon: number;
  forecast: ForecastPoint[];
}

// ── Events ───────────────────────────────────────────────────────────────────

export interface DemandEvent {
  id: string;
  hotel_id: string;
  name: string;
  event_type: string;
  start_date: string;
  end_date: string;
  distance_miles: number;
  expected_attendance: number;
  impact_strength: number;
  /** Confidence score 0.0–1.0: how certain we are of the event details. */
  confidence: number;
  status: string;
}

export interface EventListResponse {
  total: number;
  items: DemandEvent[];
}

// ── Adjusted forecast ─────────────────────────────────────────────────────────

export interface EventInfluence {
  event_id: string;
  event_name: string;
  event_type: string;
  /** Confidence-weighted occupancy points added by this event. */
  uplift_points: number;
  /** Engine confidence in this uplift (0–1). */
  confidence: number;
  explanation: string;
}

/** One day in the event-adjusted forecast (matches API spec). */
export interface AdjustedForecastDay {
  date: string;
  baseline: number;
  adjusted: number;
  uplift: number;
  confidence_low: number;
  confidence_high: number;
  reasons: string[];
  /** Full influence objects for drill-down (optional). */
  influences: EventInfluence[];
}

/** Legacy alias kept so existing code that uses AdjustedForecastPoint still compiles. */
export type AdjustedForecastPoint = AdjustedForecastDay;

export interface AdjustedForecastResponse {
  hotel_id: string;
  /** Name of the baseline forecasting model. */
  model: string;
  /** Name of the event-adjustment engine. */
  adjustment_model: string;
  origin_date: string;
  horizon: number;
  days: AdjustedForecastDay[];
}

// ── Health ────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  version: string;
  database: string;
  timestamp: string;
}

// ── Generic API wrapper ───────────────────────────────────────────────────────

export type ApiState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string };
