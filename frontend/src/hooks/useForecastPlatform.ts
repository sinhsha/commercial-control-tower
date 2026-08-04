/**
 * Hooks for the Enterprise Forecasting Platform.
 *
 * Each hook manages its own loading / error / data state so components
 * never call the API directly.
 */
import { useState, useEffect, useCallback } from 'react';
import { forecastPlatformApi } from '@/services/api';
import type {
  BacktestResult,
  ComparisonResult,
  EvaluationResult,
  ForecastHealthStatus,
  ForecastModelListResponse,
} from '@/types/api';

// ── Generic async state ───────────────────────────────────────────────────────

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

function useAsync<T>(
  fetchFn: () => Promise<T>,
  deps: unknown[],
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchFn()
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { data, loading, error, refetch };
}

// ── useForecastModels ─────────────────────────────────────────────────────────

export function useForecastModels(): AsyncState<ForecastModelListResponse> {
  return useAsync(() => forecastPlatformApi.models(), []);
}

// ── useForecastHealth ─────────────────────────────────────────────────────────

export function useForecastHealth(
  hotelId: string,
): AsyncState<ForecastHealthStatus> {
  return useAsync(
    () => forecastPlatformApi.health(hotelId),
    [hotelId],
  );
}

// ── useForecastComparison ─────────────────────────────────────────────────────

export function useForecastComparison(
  hotelId: string,
  days?: number,
): AsyncState<ComparisonResult> {
  return useAsync(
    () => forecastPlatformApi.comparison(hotelId, days),
    [hotelId, days],
  );
}

// ── useForecastEvaluation ─────────────────────────────────────────────────────

export function useForecastEvaluation(
  hotelId: string,
  window?: string,
  model?: string,
): AsyncState<EvaluationResult> {
  return useAsync(
    () => forecastPlatformApi.evaluation(hotelId, { window, model }),
    [hotelId, window, model],
  );
}

// ── useForecastBacktest ───────────────────────────────────────────────────────

export function useForecastBacktest(
  hotelId: string,
  window?: string,
  model?: string,
): AsyncState<BacktestResult> {
  return useAsync(
    () => forecastPlatformApi.backtest(hotelId, { window, model }),
    [hotelId, window, model],
  );
}
