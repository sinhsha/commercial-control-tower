import { useMemo } from 'react';
import { hotelApi } from '@/services/api';
import { useAsync } from './useAsync';
import type { Hotel } from '@/types/api';

export function useHotels(activeOnly = true) {
  const state = useAsync(
    () => hotelApi.list(activeOnly),
    [activeOnly]
  );

  const hotels: Hotel[] = useMemo(() => {
    if (state.status === 'success') return state.data.items;
    return [];
  }, [state]);

  return { ...state, hotels };
}
