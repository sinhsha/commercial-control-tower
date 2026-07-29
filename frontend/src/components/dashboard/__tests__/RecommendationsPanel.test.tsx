/**
 * Frontend tests for the Recommendation Engine UI components.
 *
 * Coverage:
 *  1. Recommendation loading state
 *  2. Recommendation rendering (title, priority, category)
 *  3. Category filtering
 *  4. Priority filtering
 *  5. Detail expansion (supporting factors, risk flags)
 *  6. Empty state
 *  7. Non-fatal API failure (error state)
 *  8. Currency formatting
 *  9. Estimated-impact label
 * 10. Multiple recommendations rendered
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { RecommendationsPanel } from '@/components/dashboard/RecommendationsPanel';
import { RecommendationCard } from '@/components/dashboard/RecommendationCard';
import type { Recommendation, RecommendationResponse } from '@/types/api';

// ── Fixtures ──────────────────────────────────────────────────────────────────

function makeRec(overrides: Partial<Recommendation> = {}): Recommendation {
  return {
    id: 'REC-hotel001-20250801-PRICING-001',
    hotel_id: 'hotel-001',
    category: 'pricing',
    action: 'increase_rate',
    title: 'Increase flexible rate by 8%',
    summary: 'Demand is forecast to exceed 90% occupancy over 3 nights.',
    effective_start_date: '2025-08-02',
    effective_end_date: '2025-08-04',
    current_value: 250,
    recommended_value: 270,
    unit: 'USD',
    score: 72.5,
    priority: 'high',
    confidence: 'high',
    expected_revenue_impact: 9200,
    expected_occupancy_impact: 0,
    reason_codes: ['high_forecast_occupancy', 'event_demand'],
    supporting_factors: ['Adjusted occupancy forecast: 91.4%', 'Competitor ADR: $315'],
    risk_flags: ['Rate increase capped by configured guardrail'],
    status: 'proposed',
    created_at: '2025-08-01T10:00:00Z',
    ...overrides,
  };
}

function makeResponse(recs: Recommendation[]): RecommendationResponse {
  return {
    hotel_id: 'hotel-001',
    generated_at: '2025-08-01T10:00:00Z',
    forecast_model: 'Seasonal Baseline',
    adjustment_model: 'Rule Based Event Engine',
    recommendation_model: 'Rule Based Commercial Engine',
    summary: {
      total: recs.length,
      critical: recs.filter((r) => r.priority === 'critical').length,
      high: recs.filter((r) => r.priority === 'high').length,
      medium: recs.filter((r) => r.priority === 'medium').length,
      low: recs.filter((r) => r.priority === 'low').length,
      estimated_revenue_opportunity: recs.reduce((s, r) => s + r.expected_revenue_impact, 0),
    },
    recommendations: recs,
  };
}

// ── Test 1: Loading state ─────────────────────────────────────────────────────

describe('RecommendationsPanel', () => {
  it('shows loading spinner when loading=true', () => {
    render(<RecommendationsPanel hotelId="hotel-001" loading={true} />);
    expect(screen.getByText(/generating commercial recommendations/i)).toBeInTheDocument();
  });

  // ── Test 2: Recommendation rendering ────────────────────────────────────────

  it('renders recommendation title and summary', () => {
    const rec = makeRec();
    render(<RecommendationsPanel hotelId="hotel-001" data={makeResponse([rec])} />);
    expect(screen.getByText('Increase flexible rate by 8%')).toBeInTheDocument();
    expect(screen.getByText(/demand is forecast to exceed 90%/i)).toBeInTheDocument();
  });

  it('renders priority badge', () => {
    const rec = makeRec({ priority: 'high' });
    render(<RecommendationsPanel hotelId="hotel-001" data={makeResponse([rec])} />);
    expect(screen.getByText('HIGH')).toBeInTheDocument();
  });

  it('renders category label', () => {
    const rec = makeRec({ category: 'pricing' });
    render(<RecommendationsPanel hotelId="hotel-001" data={makeResponse([rec])} />);
    expect(screen.getByText('pricing')).toBeInTheDocument();
  });

  // ── Test 3: Category filtering ───────────────────────────────────────────────

  it('filters recommendations by category', () => {
    const recs = [
      makeRec({ id: 'r1', category: 'pricing', title: 'Pricing Action' }),
      makeRec({ id: 'r2', category: 'operational', action: 'alert_front_desk', title: 'Operational Alert' }),
    ];
    render(<RecommendationsPanel hotelId="hotel-001" data={makeResponse(recs)} />);

    // Click "Operational" tab
    fireEvent.click(screen.getByText('Operational'));
    expect(screen.queryByText('Pricing Action')).not.toBeInTheDocument();
    expect(screen.getByText('Operational Alert')).toBeInTheDocument();
  });

  it('shows all recommendations when All filter is active', () => {
    const recs = [
      makeRec({ id: 'r1', category: 'pricing', title: 'Pricing Action' }),
      makeRec({ id: 'r2', category: 'inventory', action: 'protect_premium_inventory', title: 'Inventory Action' }),
    ];
    render(<RecommendationsPanel hotelId="hotel-001" data={makeResponse(recs)} />);
    expect(screen.getByText('Pricing Action')).toBeInTheDocument();
    expect(screen.getByText('Inventory Action')).toBeInTheDocument();
  });

  // ── Test 4: Priority filtering ───────────────────────────────────────────────

  it('filters by priority dropdown', () => {
    const recs = [
      makeRec({ id: 'r1', priority: 'high', title: 'High Priority Action' }),
      makeRec({ id: 'r2', priority: 'low', title: 'Low Priority Action', action: 'hold_rate' }),
    ];
    render(<RecommendationsPanel hotelId="hotel-001" data={makeResponse(recs)} />);

    const select = screen.getByLabelText('Filter by priority');
    fireEvent.change(select, { target: { value: 'high' } });
    expect(screen.getByText('High Priority Action')).toBeInTheDocument();
    expect(screen.queryByText('Low Priority Action')).not.toBeInTheDocument();
  });

  // ── Test 6: Empty state ──────────────────────────────────────────────────────

  it('shows empty state when no recommendations', () => {
    render(<RecommendationsPanel hotelId="hotel-001" data={makeResponse([])} />);
    expect(screen.getByText(/no commercial actions recommended/i)).toBeInTheDocument();
  });

  // ── Test 7: Non-fatal API failure ────────────────────────────────────────────

  it('shows non-fatal error without crashing other panels', () => {
    render(<RecommendationsPanel hotelId="hotel-001" error="503: engine unavailable" />);
    expect(screen.getByText(/recommendations unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/forecast and demand-sensing panels are not affected/i)).toBeInTheDocument();
  });

  // ── Test 10: Multiple recommendations rendered ───────────────────────────────

  it('renders all passed recommendations', () => {
    const recs = [
      makeRec({ id: 'r1', title: 'Action One' }),
      makeRec({ id: 'r2', title: 'Action Two', action: 'close_discounted_rates' }),
      makeRec({ id: 'r3', title: 'Action Three', action: 'alert_front_desk' }),
    ];
    render(<RecommendationsPanel hotelId="hotel-001" data={makeResponse(recs)} />);
    expect(screen.getByText('Action One')).toBeInTheDocument();
    expect(screen.getByText('Action Two')).toBeInTheDocument();
    expect(screen.getByText('Action Three')).toBeInTheDocument();
  });
});

// ── RecommendationCard tests ──────────────────────────────────────────────────

describe('RecommendationCard', () => {
  // ── Test 5: Detail expansion ─────────────────────────────────────────────────

  it('expands to show supporting factors on click', () => {
    const rec = makeRec({
      supporting_factors: ['Adjusted occupancy: 91.4%', 'Competitor ADR: $315'],
    });
    render(<RecommendationCard rec={rec} />);

    // Detail hidden before click
    expect(screen.queryByText('Adjusted occupancy: 91.4%')).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Adjusted occupancy: 91.4%')).toBeInTheDocument();
    expect(screen.getByText('Competitor ADR: $315')).toBeInTheDocument();
  });

  it('expands to show risk flags on click', () => {
    const rec = makeRec({ risk_flags: ['Rate increase capped by configured guardrail'] });
    render(<RecommendationCard rec={rec} />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText(/rate increase capped/i)).toBeInTheDocument();
  });

  it('collapses detail on second click', () => {
    const rec = makeRec();
    render(<RecommendationCard rec={rec} />);
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    // Text is inside a <li> – use getAllByText with substring
    expect(screen.getAllByText(/adjusted occupancy forecast/i).length).toBeGreaterThan(0);
    fireEvent.click(btn);
    expect(screen.queryAllByText(/adjusted occupancy forecast/i)).toHaveLength(0);
  });

  // ── Test 8: Currency formatting ──────────────────────────────────────────────

  it('formats revenue impact as USD currency', () => {
    const rec = makeRec({ expected_revenue_impact: 9200 });
    render(<RecommendationCard rec={rec} />);
    expect(screen.getByText(/\$9,200/)).toBeInTheDocument();
  });

  it('formats current and recommended values as USD', () => {
    const rec = makeRec({ current_value: 250, recommended_value: 270, unit: 'USD' });
    render(<RecommendationCard rec={rec} />);
    expect(screen.getByText('$250')).toBeInTheDocument();
    expect(screen.getByText('$270')).toBeInTheDocument();
  });

  // ── Test 9: Estimated-impact label ──────────────────────────────────────────

  it('shows "est. revenue" label on impact figure', () => {
    const rec = makeRec({ expected_revenue_impact: 5000 });
    render(<RecommendationCard rec={rec} />);
    expect(screen.getByText('est. revenue')).toBeInTheDocument();
  });

  it('shows estimates disclaimer in expanded detail', () => {
    const rec = makeRec({ expected_revenue_impact: 5000 });
    render(<RecommendationCard rec={rec} />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText(/impact figures are model estimates/i)).toBeInTheDocument();
  });
});
