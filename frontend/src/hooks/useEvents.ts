import { eventsApi } from '@/services/api';
import { useAsync } from './useAsync';

export function useEvents(hotelId: string | null) {
  return useAsync(
    () => {
      if (!hotelId) return Promise.reject(new Error('No hotel selected'));
      return eventsApi.list(hotelId);
    },
    [hotelId],
  );
}
