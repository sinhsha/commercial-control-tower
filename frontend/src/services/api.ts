import type {
  AdjustedForecastResponse,
  CopilotAskRequest,
  CopilotResponse,
  DashboardSummary,
  DailyMetricsListResponse,
  ExplainAncillaryRequest,
  ExplainCommercialRequest,
  EventListResponse,
  ForecastResponse,
  HealthResponse,
  HotelListResponse,
  Hotel,
} from '@/types/api';

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`API ${response.status}: ${text}`);
  }

  // 204 No Content — return undefined (caller typed as Promise<void>)
  if (response.status === 204) return undefined as unknown as T;

  return response.json() as Promise<T>;
}

// ── Hotels ────────────────────────────────────────────────────────────────────

export const hotelApi = {
  list: (activeOnly = true): Promise<HotelListResponse> =>
    request(`/hotels?active_only=${activeOnly}`),

  get: (id: string): Promise<Hotel> =>
    request(`/hotels/${id}`),
};

// ── Metrics ───────────────────────────────────────────────────────────────────

export const metricsApi = {
  dashboard: (hotelId: string, asOf?: string): Promise<DashboardSummary> => {
    const params = asOf ? `?as_of=${asOf}` : '';
    return request(`/metrics/dashboard/${hotelId}${params}`);
  },

  range: (
    hotelId: string,
    start: string,
    end: string
  ): Promise<DailyMetricsListResponse> =>
    request(`/metrics/range/${hotelId}?start=${start}&end=${end}`),
};

// ── Forecast ─────────────────────────────────────────────────────────────────

export const forecastApi = {
  get: (hotelId: string, days = 14, asOf?: string): Promise<ForecastResponse> => {
    const params = new URLSearchParams({ days: String(days) });
    if (asOf) params.set('as_of', asOf);
    return request(`/hotels/${hotelId}/forecast?${params}`);
  },
};

// ── Events ───────────────────────────────────────────────────────────────────

export interface CreateEventPayload {
  name: string;
  event_type: string;
  start_date: string;
  end_date: string;
  distance_miles: number;
  expected_attendance: number;
  impact_strength: number;
  confidence: number;
  status: string;
}

export const eventsApi = {
  list: (hotelId: string): Promise<EventListResponse> =>
    request(`/hotels/${hotelId}/events`),

  create: (hotelId: string, payload: CreateEventPayload): Promise<import('@/types/api').DemandEvent> =>
    request(`/hotels/${hotelId}/events`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  delete: (hotelId: string, eventId: string): Promise<void> =>
    request(`/hotels/${hotelId}/events/${eventId}`, { method: 'DELETE' }),
};

// ── Ancillaries ───────────────────────────────────────────────────────────────

export const ancillaryApi = {
  catalog: (hotelId: string): Promise<import('@/types/api').AncillaryCatalogResponse> =>
    request(`/hotels/${hotelId}/ancillaries`),

  recommendations: (
    hotelId: string,
    params?: {
      persona?: string;
      days?: number;
      limit?: number;
      category?: string;
      as_of?: string;
    }
  ): Promise<import('@/types/api').AncillaryRecommendationResponse> => {
    const p = new URLSearchParams();
    if (params?.persona) p.set('persona', params.persona);
    if (params?.days) p.set('days', String(params.days));
    if (params?.limit) p.set('limit', String(params.limit));
    if (params?.category) p.set('category', params.category);
    if (params?.as_of) p.set('as_of', params.as_of);
    const qs = p.toString();
    return request(`/hotels/${hotelId}/ancillary-recommendations${qs ? `?${qs}` : ''}`);
  },

  getOne: (
    hotelId: string,
    ancillaryCode: string,
    params?: { persona?: string; days?: number; as_of?: string }
  ): Promise<import('@/types/api').AncillaryRecommendation> => {
    const p = new URLSearchParams();
    if (params?.persona) p.set('persona', params.persona);
    if (params?.days) p.set('days', String(params.days));
    if (params?.as_of) p.set('as_of', params.as_of);
    const qs = p.toString();
    return request(`/hotels/${hotelId}/ancillary-recommendations/${ancillaryCode}${qs ? `?${qs}` : ''}`);
  },
};

// ── Recommendations ───────────────────────────────────────────────────────────

export const recommendationsApi = {
  list: (
    hotelId: string,
    params?: {
      days?: number;
      category?: string;
      priority?: string;
      status?: string;
      limit?: number;
      as_of?: string;
    }
  ): Promise<import('@/types/api').RecommendationResponse> => {
    const p = new URLSearchParams();
    if (params?.days) p.set('days', String(params.days));
    if (params?.category) p.set('category', params.category);
    if (params?.priority) p.set('priority', params.priority);
    if (params?.status) p.set('status', params.status);
    if (params?.limit) p.set('limit', String(params.limit));
    if (params?.as_of) p.set('as_of', params.as_of);
    const qs = p.toString();
    return request(`/hotels/${hotelId}/recommendations${qs ? `?${qs}` : ''}`);
  },

  get: (
    hotelId: string,
    recommendationId: string,
    params?: { days?: number; as_of?: string }
  ): Promise<import('@/types/api').Recommendation> => {
    const p = new URLSearchParams();
    if (params?.days) p.set('days', String(params.days));
    if (params?.as_of) p.set('as_of', params.as_of);
    const qs = p.toString();
    return request(`/hotels/${hotelId}/recommendations/${recommendationId}${qs ? `?${qs}` : ''}`);
  },
};

// ── Adjusted forecast ─────────────────────────────────────────────────────────

export const adjustedForecastApi = {
  get: (hotelId: string, days = 14, asOf?: string): Promise<AdjustedForecastResponse> => {
    const params = new URLSearchParams({ days: String(days) });
    if (asOf) params.set('as_of', asOf);
    return request(`/hotels/${hotelId}/forecast/adjusted?${params}`);
  },
};

// ── Copilot ───────────────────────────────────────────────────────────────────

export const copilotApi = {
  /** GET executive summary (fetches its own context server-side). */
  executiveSummary: (
    hotelId: string,
    params?: { persona?: string; days?: number; as_of?: string }
  ): Promise<CopilotResponse> => {
    const p = new URLSearchParams();
    if (params?.persona) p.set('persona', params.persona);
    if (params?.days) p.set('days', String(params.days));
    if (params?.as_of) p.set('as_of', params.as_of);
    const qs = p.toString();
    return request(`/hotels/${hotelId}/copilot/executive-summary${qs ? `?${qs}` : ''}`);
  },

  /** POST free-form revenue manager question. */
  ask: (hotelId: string, body: CopilotAskRequest): Promise<CopilotResponse> =>
    request(`/hotels/${hotelId}/copilot/ask`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** POST explanation for a commercial recommendation. */
  explainCommercial: (hotelId: string, body: ExplainCommercialRequest): Promise<CopilotResponse> =>
    request(`/hotels/${hotelId}/copilot/explain-commercial`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** POST explanation for an ancillary recommendation. */
  explainAncillary: (hotelId: string, body: ExplainAncillaryRequest): Promise<CopilotResponse> =>
    request(`/hotels/${hotelId}/copilot/explain-ancillary`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};

// ── Health ────────────────────────────────────────────────────────────────────

export const healthApi = {
  check: (): Promise<HealthResponse> => request('/health'),
};

// ── Forecast Platform ─────────────────────────────────────────────────────────

export const forecastPlatformApi = {
  models: (): Promise<import('@/types/api').ForecastModelListResponse> =>
    request('/forecast/models'),

  evaluation: (
    hotelId: string,
    params?: { window?: string; model?: string }
  ): Promise<import('@/types/api').EvaluationResult> => {
    const p = new URLSearchParams({ hotel_id: hotelId });
    if (params?.window) p.set('window', params.window);
    if (params?.model) p.set('model', params.model);
    return request(`/forecast/evaluation?${p}`);
  },

  comparison: (
    hotelId: string,
    days?: number
  ): Promise<import('@/types/api').ComparisonResult> => {
    const p = new URLSearchParams({ hotel_id: hotelId });
    if (days != null) p.set('days', String(days));
    return request(`/forecast/comparison?${p}`);
  },

  health: (hotelId: string): Promise<import('@/types/api').ForecastHealthStatus> =>
    request(`/forecast/health?hotel_id=${encodeURIComponent(hotelId)}`),

  backtest: (
    hotelId: string,
    params?: { window?: string; model?: string }
  ): Promise<import('@/types/api').BacktestResult> => {
    const p = new URLSearchParams({ hotel_id: hotelId });
    if (params?.window) p.set('window', params.window);
    if (params?.model) p.set('model', params.model);
    return request(`/forecast/backtest?${p}`);
  },
};
