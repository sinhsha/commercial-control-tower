/**
 * useCopilot hooks — thin wrappers around the copilot API.
 *
 * The executive summary hook auto-fetches on mount (like other data hooks).
 * The ask hook returns a manual trigger (not auto-fetch) so the chat box
 * only fires when the user submits a question.
 */
import { useState, useCallback } from 'react';
import { copilotApi } from '@/services/api';
import type {
  CopilotResponse,
  DashboardSummary,
  GuestPersona,
  RecommendationResponse,
  AncillaryRecommendationResponse,
} from '@/types/api';
import { useAsync } from './useAsync';

// ── Executive summary (auto-fetched) ─────────────────────────────────────────

export function useExecutiveSummary(
  hotelId: string | null,
  persona: GuestPersona = 'hotel_wide',
  days = 14
) {
  return useAsync(
    (): Promise<CopilotResponse> => {
      if (!hotelId) return Promise.reject(new Error('No hotel selected'));
      return copilotApi.executiveSummary(hotelId, { persona, days });
    },
    [hotelId, persona, days]
  );
}

// ── Q&A ask (manual trigger) ──────────────────────────────────────────────────

type AskState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: CopilotResponse }
  | { status: 'error'; error: string };

export function useCopilotAsk(
  hotelId: string | null,
  dashboard: DashboardSummary | undefined,
  recommendations: RecommendationResponse | undefined,
  ancillaryRecommendations: AncillaryRecommendationResponse | undefined,
  persona: GuestPersona = 'hotel_wide'
) {
  const [state, setState] = useState<AskState>({ status: 'idle' });

  const ask = useCallback(
    async (question: string) => {
      if (!hotelId || !dashboard) return;
      setState({ status: 'loading' });
      try {
        // Build grounding context from already-loaded dashboard state
        const topCommercial = (recommendations?.recommendations ?? [])
          .slice(0, 3)
          .map((r) => r.title);
        const topAncillary = (ancillaryRecommendations?.recommendations ?? [])
          .slice(0, 3)
          .map((r) => `${r.product.name} (#${r.rank}, $${r.recommended_price.toFixed(0)})`);

        const data = await copilotApi.ask(hotelId, {
          grounding: {
            question,
            hotel_name: dashboard.hotel_name,
            as_of_date: dashboard.as_of_date,
            current_occupancy_pct: dashboard.occupancy_pct,
            forecast_occupancy_pct: dashboard.forecasted_occupancy ?? dashboard.occupancy_pct,
            current_adr: dashboard.adr,
            competitor_adr: dashboard.compset_adr ?? dashboard.adr,
            active_events: [],
            top_commercial_actions: topCommercial,
            top_ancillary_offers: topAncillary,
            room_revenue_opportunity:
              recommendations?.summary?.estimated_revenue_opportunity ?? 0,
            ancillary_revenue_opportunity:
              ancillaryRecommendations?.summary?.total_revenue_opportunity ?? 0,
            persona,
          },
        });
        setState({ status: 'success', data });
      } catch (err) {
        setState({
          status: 'error',
          error: err instanceof Error ? err.message : 'Unknown error',
        });
      }
    },
    [hotelId, dashboard, recommendations, ancillaryRecommendations, persona]
  );

  return { state, ask };
}
