import { roomPricingApi } from '@/services/api';
import { useAsync } from './useAsync';

export function useRoomPricing(hotelId: string | null, days = 14, asOf?: string) {
  return useAsync(
    () => {
      if (!hotelId) return Promise.reject(new Error('No hotel selected'));
      return roomPricingApi.recommendations(hotelId, { days, as_of: asOf });
    },
    [hotelId, days, asOf],
  );
}

export function useRoomCalendar(hotelId: string | null, days = 14, asOf?: string) {
  return useAsync(
    () => {
      if (!hotelId) return Promise.reject(new Error('No hotel selected'));
      return roomPricingApi.calendar(hotelId, { days, as_of: asOf });
    },
    [hotelId, days, asOf],
  );
}

export function useRoomInventory(hotelId: string | null, asOf?: string) {
  return useAsync(
    () => {
      if (!hotelId) return Promise.reject(new Error('No hotel selected'));
      return roomPricingApi.inventory(hotelId, { as_of: asOf });
    },
    [hotelId, asOf],
  );
}
