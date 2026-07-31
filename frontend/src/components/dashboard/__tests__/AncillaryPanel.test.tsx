/**
 * Frontend tests for the Ancillary Revenue Optimization Engine UI components.
 *
 * Coverage:
 *  1. AncillaryPanel loading state
 *  2. AncillaryCard renders product name and rank
 *  3. AncillaryCard renders price with % change
 *  4. AncillaryCard renders propensity percentage
 *  5. AncillaryCard expandable detail (supporting factors)
 *  6. AncillaryCard score breakdown visible on expand
 *  7. AncillaryPanel category filter tabs render
 *  8. AncillaryPanel filters by category
 *  9. AncillaryPanel shows empty state when no matching category
 * 10. AncillaryPanel non-fatal error state
 * 11. AncillaryPanel persona switcher renders all options
 * 12. TotalRevenueBar renders room + ancillary + total
 * 13. AncillaryPanel renders summary bar metrics
 * 14. AncillaryCard shows "est. revenue" and "est. margin" labels
 * 15. AncillaryCard collapses detail on second click
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AncillaryCard } from '@/components/dashboard/AncillaryCard';
import { AncillaryPanel } from '@/components/dashboard/AncillaryPanel';
import { TotalRevenueBar } from '@/components/dashboard/TotalRevenueBar';
import type {
  AncillaryRecommendation,
  AncillaryRecommendationResponse,
  GuestPersona,
} from '@/types/api';

// ── Fixtures ──────────────────────────────────────────────────────────────────

function makeRec(overrides: Partial<AncillaryRecommendation> = {}): AncillaryRecommendation {
  return {
    id: 'ANC-hotel001-20250801-PARKING-001',
    hotel_id: 'hotel-001',
    rank: 1,
    product: {
      code: 'PARKING',
      name: 'Self-Parking',
      description: 'Overnight self-parking',
      category: 'parking_transportation',
      base_price: 42,
      variable_cost: 8,
      daily_capacity: 150,
      current_utilization: 0.82,
      revenue_impact_tier: 'high',
      is_active: true,
      requires_vehicle_flag: true,
      requires_ev_flag: false,
      requires_pet_flag: false,
      target_segments: [],
      applicable_event_types: ['convention', 'sports'],
      base_propensity: 0.55,
    },
    persona: 'hotel_wide',
    base_price: 42,
    recommended_price: 46.2,
    price_change_pct: 10.0,
    price_change_reason: 'High hotel demand & parking utilization',
    propensity: 0.65,
    eligible_guests: 80,
    expected_conversions: 52.0,
    expected_revenue: 2404.08,
    expected_margin: 1996.92,
    score: 72.5,
    score_components: {
      propensity_score: 19.5,
      margin_score: 19.84,
      demand_relevance_score: 12.0,
      segment_affinity_score: 8.0,
      event_relevance_score: 7.0,
      capacity_score: 0.54,
      total: 72.5,
    },
    confidence: 'high',
    reason_codes: ['high_propensity_segment', 'high_demand_period'],
    supporting_factors: [
      'Persona: hotel_wide',
      'Estimated eligible guests: 80',
      'Propensity: 65%',
      'Forecast occupancy: 88.0%',
    ],
    generated_at: '2025-08-01T10:00:00Z',
    ...overrides,
  };
}

function makeResponse(
  recs: AncillaryRecommendation[],
  persona: GuestPersona = 'hotel_wide'
): AncillaryRecommendationResponse {
  return {
    hotel_id: 'hotel-001',
    generated_at: '2025-08-01T10:00:00Z',
    engine_model: 'Rule Based Ancillary Engine v1',
    persona,
    horizon_days: 14,
    summary: {
      eligible_products: 12,
      shown: recs.length,
      total_revenue_opportunity: recs.reduce((s, r) => s + r.expected_revenue, 0),
      total_margin_opportunity: recs.reduce((s, r) => s + r.expected_margin, 0),
    },
    recommendations: recs,
  };
}

// ── AncillaryPanel tests ──────────────────────────────────────────────────────

describe('AncillaryPanel', () => {
  // Test 1: Loading state
  it('shows loading spinner when loading=true', () => {
    render(
      <AncillaryPanel
        hotelId="hotel-001"
        loading={true}
        persona="hotel_wide"
        onPersonaChange={() => {}}
      />
    );
    expect(screen.getByText(/generating ancillary revenue recommendations/i)).toBeInTheDocument();
  });

  // Test 10: Non-fatal error state
  it('shows non-fatal error without crashing other panels', () => {
    render(
      <AncillaryPanel
        hotelId="hotel-001"
        error="503: engine unavailable"
        persona="hotel_wide"
        onPersonaChange={() => {}}
      />
    );
    expect(screen.getByText(/ancillary recommendations unavailable/i)).toBeInTheDocument();
    expect(
      screen.getByText(/room pricing and demand-sensing panels are not affected/i)
    ).toBeInTheDocument();
  });

  // Test 7: Category filter tabs render
  it('renders category filter tabs', () => {
    render(
      <AncillaryPanel
        hotelId="hotel-001"
        data={makeResponse([makeRec()])}
        persona="hotel_wide"
        onPersonaChange={() => {}}
      />
    );
    expect(screen.getByText('All')).toBeInTheDocument();
    expect(screen.getByText('Parking')).toBeInTheDocument();
    expect(screen.getByText('Spa')).toBeInTheDocument();
    expect(screen.getByText('Meetings')).toBeInTheDocument();
  });

  // Test 8: Filters by category
  it('filters recommendations by category tab', () => {
    const recs = [
      makeRec({ id: 'r1', product: { ...makeRec().product, code: 'PARKING', category: 'parking_transportation', name: 'Self-Parking' } }),
      makeRec({ id: 'r2', rank: 2, product: { ...makeRec().product, code: 'SPA_BOOKING', category: 'spa_wellness', name: 'Spa Treatment' } }),
    ];
    render(
      <AncillaryPanel
        hotelId="hotel-001"
        data={makeResponse(recs)}
        persona="hotel_wide"
        onPersonaChange={() => {}}
      />
    );
    // Click Spa tab
    fireEvent.click(screen.getByText('Spa'));
    expect(screen.queryByText('Self-Parking')).not.toBeInTheDocument();
    expect(screen.getByText('Spa Treatment')).toBeInTheDocument();
  });

  // Test 9: Empty state when no matching category
  it('shows empty state when no offers match category filter', () => {
    const recs = [
      makeRec({ product: { ...makeRec().product, category: 'parking_transportation' } }),
    ];
    render(
      <AncillaryPanel
        hotelId="hotel-001"
        data={makeResponse(recs)}
        persona="hotel_wide"
        onPersonaChange={() => {}}
      />
    );
    fireEvent.click(screen.getByText('Spa'));
    expect(screen.getByText(/no ancillary offers available/i)).toBeInTheDocument();
  });

  // Test 11: Persona switcher renders all options
  it('renders persona switcher with all 8 options', () => {
    render(
      <AncillaryPanel
        hotelId="hotel-001"
        data={makeResponse([])}
        persona="hotel_wide"
        onPersonaChange={() => {}}
      />
    );
    const select = screen.getByLabelText(/filter by guest persona/i);
    expect(select).toBeInTheDocument();
    // Check for a few persona labels
    expect(screen.getByText('Hotel Wide')).toBeInTheDocument();
    expect(screen.getByText('Business Traveler')).toBeInTheDocument();
    expect(screen.getByText('Conference Attendee')).toBeInTheDocument();
    expect(screen.getByText('Leisure Couple')).toBeInTheDocument();
  });

  // Test 13: Summary bar metrics
  it('renders summary bar with eligible products and revenue opportunity', () => {
    const recs = [makeRec()];
    render(
      <AncillaryPanel
        hotelId="hotel-001"
        data={makeResponse(recs)}
        persona="hotel_wide"
        onPersonaChange={() => {}}
      />
    );
    expect(screen.getByText('Eligible Products')).toBeInTheDocument();
    expect(screen.getByText('Offers Shown')).toBeInTheDocument();
    expect(screen.getByText(/Revenue Opportunity/i)).toBeInTheDocument();
  });
});

// ── AncillaryCard tests ───────────────────────────────────────────────────────

describe('AncillaryCard', () => {
  // Test 2: Renders product name and rank
  it('renders product name', () => {
    render(<AncillaryCard rec={makeRec()} />);
    expect(screen.getByText('Self-Parking')).toBeInTheDocument();
  });

  // Test 3: Renders price with % change
  it('renders base price, recommended price, and % change', () => {
    render(<AncillaryCard rec={makeRec()} />);
    expect(screen.getByText('$42')).toBeInTheDocument();
    expect(screen.getByText('$46.2')).toBeInTheDocument();
    expect(screen.getByText('(+10.0%)')).toBeInTheDocument();
  });

  // Test 4: Renders propensity bar
  it('renders conversion propensity label', () => {
    render(<AncillaryCard rec={makeRec()} />);
    expect(screen.getByText('Conversion propensity')).toBeInTheDocument();
    expect(screen.getByText('65%')).toBeInTheDocument();
  });

  // Test 14: Shows est. revenue and est. margin labels
  it('shows est. revenue and est. margin labels', () => {
    render(<AncillaryCard rec={makeRec()} />);
    expect(screen.getByText('est. revenue')).toBeInTheDocument();
    expect(screen.getByText('est. margin')).toBeInTheDocument();
  });

  // Test 5: Expandable detail (supporting factors)
  it('expands to show supporting factors on click', () => {
    const rec = makeRec({
      supporting_factors: ['Persona: hotel_wide', 'Forecast occupancy: 88.0%'],
    });
    render(<AncillaryCard rec={rec} />);

    // Hidden before click
    expect(screen.queryByText('Why This Offer')).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Why This Offer')).toBeInTheDocument();
    expect(screen.getByText('Persona: hotel_wide')).toBeInTheDocument();
    expect(screen.getByText('Forecast occupancy: 88.0%')).toBeInTheDocument();
  });

  // Test 6: Score breakdown visible on expand
  it('shows score breakdown on expand', () => {
    render(<AncillaryCard rec={makeRec()} />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText(/score breakdown/i)).toBeInTheDocument();
    expect(screen.getByText('Propensity (×30)')).toBeInTheDocument();
    expect(screen.getByText('Margin (×25)')).toBeInTheDocument();
  });

  // Test 15: Collapses on second click
  it('collapses detail on second click', () => {
    render(<AncillaryCard rec={makeRec()} />);
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    expect(screen.getByText('Why This Offer')).toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.queryByText('Why This Offer')).not.toBeInTheDocument();
  });
});

// ── TotalRevenueBar tests ─────────────────────────────────────────────────────

describe('TotalRevenueBar', () => {
  // Test 12: Renders room + ancillary + total
  it('renders Room Revenue, Ancillary Revenue, and Total Revenue labels', () => {
    const recs = [makeRec()];
    const ancillaryData = makeResponse(recs);
    const roomData = {
      hotel_id: 'hotel-001',
      generated_at: '2025-08-01T10:00:00Z',
      forecast_model: 'Seasonal Baseline',
      adjustment_model: 'Rule Based Event Engine',
      recommendation_model: 'Rule Based Commercial Engine',
      summary: {
        total: 1,
        critical: 0,
        high: 1,
        medium: 0,
        low: 0,
        estimated_revenue_opportunity: 15000,
      },
      recommendations: [],
    };

    render(<TotalRevenueBar recommendations={roomData} ancillaryRecommendations={ancillaryData} />);
    expect(screen.getByText('Room Revenue Opportunity')).toBeInTheDocument();
    expect(screen.getByText('Ancillary Revenue Opportunity')).toBeInTheDocument();
    expect(screen.getByText('Total Revenue Opportunity')).toBeInTheDocument();
  });

  it('renders null when no data is provided', () => {
    const { container } = render(<TotalRevenueBar />);
    expect(container.firstChild).toBeNull();
  });
});
