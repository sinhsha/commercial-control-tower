import { forecastApi } from '@/services/api';
import { useAsync } from './useAsync';

export function useForecast(hotelId: string | null, days = 14, asOf?: string) {
  return useAsync(
    () => {
      if (!hotelId) return Promise.reject(new Error('No hotel selected'));
      return forecastApi.get(hotelId, days, asOf);
    },
    [hotelId, days, asOf],
  );
}
