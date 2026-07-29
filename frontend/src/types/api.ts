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

// ── Recommendations ──────────────────────────────────────────────────────────

export type RecommendationCategory =
  | 'pricing'
  | 'inventory'
  | 'restrictions'
  | 'upgrade'
  | 'package'
  | 'ancillary'
  | 'operational';

export type RecommendationAction =
  | 'increase_rate'
  | 'reduce_rate'
  | 'hold_rate'
  | 'protect_premium_inventory'
  | 'release_premium_inventory'
  | 'hold_rooms_for_late_demand'
  | 'close_discounted_rates'
  | 'add_minimum_length_of_stay'
  | 'remove_minimum_length_of_stay'
  | 'open_paid_upgrades'
  | 'restrict_complimentary_upgrades'
  | 'launch_breakfast_package'
  | 'launch_parking_package'
  | 'launch_event_package'
  | 'promote_late_checkout'
  | 'alert_revenue_manager'
  | 'alert_front_desk'
  | 'alert_housekeeping';

export type RecommendationPriority = 'critical' | 'high' | 'medium' | 'low';
export type RecommendationConfidence = 'high' | 'medium' | 'low';
export type RecommendationStatus = 'proposed' | 'approved' | 'rejected' | 'expired';

export interface Recommendation {
  id: string;
  hotel_id: string;
  category: RecommendationCategory;
  action: RecommendationAction;
  title: string;
  summary: string;
  effective_start_date: string;
  effective_end_date: string;
  current_value: number | null;
  recommended_value: number | null;
  unit: string;
  score: number;
  priority: RecommendationPriority;
  confidence: RecommendationConfidence;
  expected_revenue_impact: number;
  expected_occupancy_impact: number;
  reason_codes: string[];
  supporting_factors: string[];
  risk_flags: string[];
  status: RecommendationStatus;
  created_at: string;
}

export interface RecommendationSummary {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  estimated_revenue_opportunity: number;
}

export interface RecommendationResponse {
  hotel_id: string;
  generated_at: string;
  forecast_model: string;
  adjustment_model: string;
  recommendation_model: string;
  summary: RecommendationSummary;
  recommendations: Recommendation[];
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
