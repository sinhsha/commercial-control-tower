import { ancillaryApi } from '@/services/api';
import type { AncillaryRecommendationResponse, GuestPersona } from '@/types/api';
import { useAsync } from './useAsync';

export function useAncillaryRecommendations(
  hotelId: string | null,
  persona: GuestPersona = 'hotel_wide',
  days = 14,
  limit = 5,
  category?: string
) {
  return useAsync(
    (): Promise<AncillaryRecommendationResponse> => {
      if (!hotelId) return Promise.reject(new Error('No hotel selected'));
      return ancillaryApi.recommendations(hotelId, {
        persona,
        days,
        limit,
        category,
      });
    },
    [hotelId, persona, days, limit, category]
  );
}
