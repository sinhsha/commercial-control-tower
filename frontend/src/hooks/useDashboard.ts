import { metricsApi } from '@/services/api';
import { useAsync } from './useAsync';

export function useDashboard(hotelId: string | null, asOf?: string) {
  return useAsync(
    () => {
      if (!hotelId) return Promise.reject(new Error('No hotel selected'));
      return metricsApi.dashboard(hotelId, asOf);
    },
    [hotelId, asOf]
  );
}
