import type {
  AdjustedForecastResponse,
  DashboardSummary,
  DailyMetricsListResponse,
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

export const eventsApi = {
  list: (hotelId: string): Promise<EventListResponse> =>
    request(`/hotels/${hotelId}/events`),
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

// ── Health ────────────────────────────────────────────────────────────────────

export const healthApi = {
  check: (): Promise<HealthResponse> => request('/health'),
};
