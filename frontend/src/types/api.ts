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

// ── Ancillaries ───────────────────────────────────────────────────────────────

export type GuestPersona =
  | 'hotel_wide'
  | 'business_traveler'
  | 'conference_attendee'
  | 'leisure_couple'
  | 'family'
  | 'resort_guest'
  | 'ev_traveler'
  | 'pet_traveler';

export type AncillaryCategory =
  | 'parking_transportation'
  | 'food_beverage'
  | 'meetings_events'
  | 'spa_wellness'
  | 'experiences'
  | 'workspace'
  | 'guest_commerce'
  | 'pet'
  | 'room_inventory';

export interface AncillaryProduct {
  code: string;
  name: string;
  description: string;
  category: AncillaryCategory;
  base_price: number;
  variable_cost: number;
  daily_capacity: number;
  current_utilization: number;
  revenue_impact_tier: 'high' | 'medium' | 'low';
  is_active: boolean;
  requires_vehicle_flag: boolean;
  requires_ev_flag: boolean;
  requires_pet_flag: boolean;
  target_segments: GuestPersona[];
  applicable_event_types: string[];
  base_propensity: number;
}

export interface AncillaryScoreComponents {
  propensity_score: number;
  margin_score: number;
  demand_relevance_score: number;
  segment_affinity_score: number;
  event_relevance_score: number;
  capacity_score: number;
  total: number;
}

export interface AncillaryRecommendation {
  id: string;
  hotel_id: string;
  rank: number;
  product: AncillaryProduct;
  persona: GuestPersona;
  base_price: number;
  recommended_price: number;
  price_change_pct: number;
  price_change_reason: string;
  propensity: number;
  eligible_guests: number;
  expected_conversions: number;
  expected_revenue: number;
  expected_margin: number;
  score: number;
  score_components: AncillaryScoreComponents;
  confidence: 'high' | 'medium' | 'low';
  reason_codes: string[];
  supporting_factors: string[];
  generated_at: string;
}

export interface AncillaryRecommendationSummary {
  eligible_products: number;
  shown: number;
  total_revenue_opportunity: number;
  total_margin_opportunity: number;
}

export interface AncillaryRecommendationResponse {
  hotel_id: string;
  generated_at: string;
  engine_model: string;
  persona: GuestPersona;
  horizon_days: number;
  summary: AncillaryRecommendationSummary;
  recommendations: AncillaryRecommendation[];
}

export interface AncillaryCatalogResponse {
  hotel_id: string;
  total: number;
  items: AncillaryProduct[];
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

// ── Copilot / Grounded Explanation Service ────────────────────────────────────

export type CopilotSurface =
  | 'commercial_recommendation'
  | 'ancillary_recommendation'
  | 'executive_summary'
  | 'copilot_question';

export type CopilotStatus = 'ok' | 'unavailable' | 'error';

export interface CopilotResponse {
  surface: CopilotSurface;
  status: CopilotStatus;
  explanation: string;
  model_used: string;
  tokens_used: number;
  generated_at: string;
  fallback_reason: string | null;
}

/** Structured context for a commercial recommendation explanation. */
export interface CommercialGrounding {
  hotel_name: string;
  as_of_date: string;
  current_occupancy_pct: number;
  forecast_occupancy_pct: number;
  current_adr: number;
  competitor_adr: number;
  booking_pace_index: number;
  active_events: Array<Record<string, unknown>>;
  recommendation_title: string;
  recommendation_action: string;
  recommendation_category: string;
  current_value: number | null;
  recommended_value: number | null;
  unit: string;
  expected_revenue_impact: number;
  reason_codes: string[];
  supporting_factors: string[];
  risk_flags: string[];
  priority: string;
  confidence: string;
}

/** Structured context for an ancillary recommendation explanation. */
export interface AncillaryGrounding {
  hotel_name: string;
  persona: string;
  forecast_occupancy_pct: number;
  active_events: Array<Record<string, unknown>>;
  ancillary_name: string;
  ancillary_category: string;
  rank: number;
  base_price: number;
  recommended_price: number;
  price_change_pct: number;
  purchase_probability: number;
  expected_revenue: number;
  expected_margin: number;
  opportunity_score: number;
  reason_codes: string[];
  supporting_factors: string[];
  guardrails_applied: string[];
  score_components: Record<string, number>;
}

/** Free-form Q&A context sent with each copilot question. */
export interface CopilotQuestion {
  question: string;
  hotel_name: string;
  as_of_date: string;
  current_occupancy_pct: number;
  forecast_occupancy_pct: number;
  current_adr: number;
  competitor_adr: number;
  active_events: Array<Record<string, unknown>>;
  top_commercial_actions: string[];
  top_ancillary_offers: string[];
  room_revenue_opportunity: number;
  ancillary_revenue_opportunity: number;
  persona: string;
}

export interface CopilotAskRequest {
  grounding: CopilotQuestion;
}

export interface ExplainCommercialRequest {
  grounding: CommercialGrounding;
}

export interface ExplainAncillaryRequest {
  grounding: AncillaryGrounding;
}

// ── Enterprise Forecasting Platform ───────────────────────────────────────────

export type ForecastModelStatus = 'active' | 'inactive' | 'degraded';

export interface ForecastModelInfo {
  model_id: string;
  name: string;
  version: string;
  provider: string;
  device: string;
  supported_horizons: number[];
  capabilities: string[];
  status: ForecastModelStatus;
}

export interface ForecastModelListResponse {
  total: number;
  models: ForecastModelInfo[];
}

export interface EvaluationMetrics {
  model_id: string;
  model_name: string;
  window: string;
  mae: number;
  rmse: number;
  mape: number;
  wape: number;
  bias: number;
  mean_error: number;
  coverage: number;
  runtime_ms: number;
  evaluated_at: string;
}

/** Alias — matches the backend EvaluationResult schema. */
export type EvaluationResult = EvaluationMetrics;

export interface ComparisonResult {
  hotel_id: string;
  window: string;
  models: EvaluationMetrics[];
  recommended_model_id: string;
  evaluated_at: string;
}

export type ForecastHealthStatusLevel = 'healthy' | 'warning' | 'degraded';

export interface ForecastHealthStatus {
  hotel_id: string;
  status: ForecastHealthStatusLevel;
  active_model: string;
  active_model_version: string;
  fallback_active: boolean;
  last_validation: string;
  warnings: string[];
}

export interface BacktestPoint {
  date: string;
  actual: number;
  predicted: number;
  lower_bound: number;
  upper_bound: number;
  residual: number;
}

export interface BacktestResult {
  model_id: string;
  model_name: string;
  window: string;
  points: BacktestPoint[];
  mae: number;
  rmse: number;
  bias: number;
}

/** Enriched forecast response returned by the ForecastManagerService. */
export interface ManagedForecastResult {
  forecast_id: string;
  hotel_id: string;
  model_used: string;
  model_version: string;
  generated_at: string;
  runtime_ms: number;
  device: string;
  training_context_days: number;
  prediction_horizon: number;
  validation_status: 'passed' | 'warning' | 'failed';
  fallback_used: boolean;
  fallback_reason: string | null;
  confidence_score: number;
  evaluation_metrics: EvaluationMetrics | null;
  warnings: string[];
  forecast: ForecastPoint[];
}

// ── Room Pricing & Inventory Optimization ─────────────────────────────────────

export type ProtectionStatus = 'open' | 'protected' | 'hold' | 'closed';
export type PricingConfidence = 'high' | 'medium' | 'low';
export type LosRecommendation = 'min_2' | 'min_3' | 'close_arrival' | 'open_arrival' | null;

export interface RoomTypePricingRecommendation {
  room_type_id: string;
  code: string;
  display_name: string;
  room_rank: number;
  capacity: number;
  inventory_count: number;
  current_available: number;
  current_price: number;
  recommended_price: number;
  price_change_pct: number;
  minimum_price: number;
  maximum_price: number;
  demand_multiplier: number;
  scarcity_multiplier: number;
  competitor_multiplier: number;
  premium_factor: number;
  confidence: PricingConfidence;
  reason_codes: string[];
  supporting_factors: string[];
  guardrails_applied: string[];
  protection_status: ProtectionStatus;
  upgrade_recommendation: string | null;
  los_recommendation: LosRecommendation;
}

export interface RoomPricingResponse {
  hotel_id: string;
  generated_at: string;
  as_of_date: string;
  forecast_occupancy_pct: number;
  competitor_adr: number;
  active_events: Array<Record<string, unknown>>;
  recommendations: RoomTypePricingRecommendation[];
  projected_adr: number;
  projected_revpar: number;
  projected_room_revenue: number;
  projected_occupancy_pct: number;
  projected_revenue_opportunity: number;
}

export interface RoomCalendarDay {
  date: string;
  recommended_price: number;
  current_price: number;
  price_change_pct: number;
  confidence: string;
  forecast_occupancy_pct: number;
  protection_status: string;
}

export interface RoomTypeCalendar {
  room_type_id: string;
  code: string;
  display_name: string;
  room_rank: number;
  days: RoomCalendarDay[];
}

export interface RoomCalendarResponse {
  hotel_id: string;
  generated_at: string;
  horizon_days: number;
  room_types: RoomTypeCalendar[];
}

export interface InventoryStatus {
  room_type_id: string;
  code: string;
  display_name: string;
  room_rank: number;
  inventory_count: number;
  sold: number;
  remaining: number;
  occupancy_pct: number;
  protection_status: string;
  upgrade_eligible: boolean;
  revenue_at_risk: number;
}

export interface InventoryResponse {
  hotel_id: string;
  as_of_date: string;
  total_rooms: number;
  total_sold: number;
  total_available: number;
  overall_occupancy_pct: number;
  room_types: InventoryStatus[];
}
