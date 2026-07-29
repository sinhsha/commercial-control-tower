import { recommendationsApi } from '@/services/api';
import type { RecommendationCategory } from '@/types/api';
import { useAsync } from './useAsync';

export function useRecommendations(
  hotelId: string | null,
  days = 14,
  category?: RecommendationCategory,
  limit = 10
) {
  return useAsync(
    () => {
      if (!hotelId) return Promise.reject(new Error('No hotel selected'));
      return recommendationsApi.list(hotelId, {
        days,
        category,
        limit,
        status: 'proposed',
      });
    },
    [hotelId, days, category, limit]
  );
}
