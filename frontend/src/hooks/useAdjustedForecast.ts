import { adjustedForecastApi } from '@/services/api';
import { useAsync } from './useAsync';

export function useAdjustedForecast(
  hotelId: string | null,
  enabled: boolean,
  days = 14,
  asOf?: string,
) {
  return useAsync(
    () => {
      if (!hotelId || !enabled) return Promise.reject(new Error('Not enabled'));
      return adjustedForecastApi.get(hotelId, days, asOf);
    },
    [hotelId, enabled, days, asOf],
  );
}
