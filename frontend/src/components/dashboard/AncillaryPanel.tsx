/**
 * AncillaryPanel
 *
 * Displays the Ancillary Revenue Optimization Engine output.
 * Features:
 *   - Summary bar: eligible products, shown, revenue opportunity
 *   - PersonaSwitcher dropdown (8 personas) – triggers reload
 *   - Category filter tabs: All, Parking, F&B, Meetings, Spa, Experiences, Workspace, Other
 *   - List of AncillaryCard components
 *   - Loading, error, empty states (non-fatal)
 *   - Footer: engine model name, estimate disclaimer
 */
import { useState } from 'react';
import type {
  AncillaryRecommendationResponse,
  AncillaryCategory,
  GuestPersona,
} from '@/types/api';
import { AncillaryCard } from '@/components/dashboard/AncillaryCard';
import { Spinner } from '@/components/ui/Spinner';

// ── Types ─────────────────────────────────────────────────────────────────────

type CategoryFilter = 'all' | AncillaryCategory;

const PERSONA_LABELS: Record<GuestPersona, string> = {
  hotel_wide: 'Hotel Wide',
  business_traveler: 'Business Traveler',
  conference_attendee: 'Conference Attendee',
  leisure_couple: 'Leisure Couple',
  family: 'Family',
  resort_guest: 'Resort Guest',
  ev_traveler: 'EV Traveler',
  pet_traveler: 'Pet Traveler',
};

const CATEGORY_TABS: { key: CategoryFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'parking_transportation', label: 'Parking' },
  { key: 'food_beverage', label: 'F&B' },
  { key: 'meetings_events', label: 'Meetings' },
  { key: 'spa_wellness', label: 'Spa' },
  { key: 'experiences', label: 'Experiences' },
  { key: 'workspace', label: 'Workspace' },
  { key: 'guest_commerce', label: 'Other' },
];

function fmt(n: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n);
}

// ── Summary bar ────────────────────────────────────────────────────────────────

function SummaryBar({ data }: { data: AncillaryRecommendationResponse }) {
  const s = data.summary;
  return (
    <div
      style={{
        display: 'flex',
        gap: 20,
        flexWrap: 'wrap',
        padding: '10px 0',
        marginBottom: 12,
        borderBottom: '1px solid #e5e7eb',
      }}
    >
      {[
        { label: 'Eligible Products', value: String(s.eligible_products) },
        { label: 'Offers Shown', value: String(s.shown) },
        { label: 'Revenue Opportunity (est.)', value: fmt(s.total_revenue_opportunity) },
        { label: 'Margin Opportunity (est.)', value: fmt(s.total_margin_opportunity) },
      ].map(({ label, value }) => (
        <div key={label}>
          <div style={{ fontSize: 10, color: '#57606a', marginBottom: 2 }}>{label}</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#1f2328' }}>{value}</div>
        </div>
      ))}
    </div>
  );
}

// ── Persona switcher ──────────────────────────────────────────────────────────

interface PersonaSwitcherProps {
  value: GuestPersona;
  onChange: (p: GuestPersona) => void;
}

function PersonaSwitcher({ value, onChange }: PersonaSwitcherProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
      <label
        htmlFor="ancillary-persona-select"
        style={{ fontSize: 12, color: '#57606a', whiteSpace: 'nowrap' }}
      >
        Guest Persona:
      </label>
      <select
        id="ancillary-persona-select"
        value={value}
        onChange={(e) => onChange(e.target.value as GuestPersona)}
        aria-label="Filter by guest persona"
        style={{
          fontSize: 12,
          padding: '4px 8px',
          border: '1px solid #d1d5db',
          borderRadius: 5,
          background: '#fff',
          cursor: 'pointer',
          color: '#1f2328',
        }}
      >
        {(Object.keys(PERSONA_LABELS) as GuestPersona[]).map((p) => (
          <option key={p} value={p}>
            {PERSONA_LABELS[p]}
          </option>
        ))}
      </select>
    </div>
  );
}

// ── Category tabs ─────────────────────────────────────────────────────────────

interface CategoryTabsProps {
  active: CategoryFilter;
  onChange: (c: CategoryFilter) => void;
}

function CategoryTabs({ active, onChange }: CategoryTabsProps) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 4,
        flexWrap: 'wrap',
        marginBottom: 14,
      }}
    >
      {CATEGORY_TABS.map(({ key, label }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          style={{
            padding: '4px 12px',
            fontSize: 11,
            fontWeight: 600,
            borderRadius: 5,
            border: active === key ? '1.5px solid #3b82d4' : '1px solid #d1d5db',
            background: active === key ? '#eff6ff' : '#fff',
            color: active === key ? '#1d4ed8' : '#57606a',
            cursor: 'pointer',
            transition: 'all 0.12s',
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface AncillaryPanelProps {
  hotelId: string;
  loading?: boolean;
  error?: string;
  data?: AncillaryRecommendationResponse;
  persona: GuestPersona;
  onPersonaChange: (p: GuestPersona) => void;
}

export function AncillaryPanel({
  hotelId: _hotelId,
  loading = false,
  error,
  data,
  persona,
  onPersonaChange,
}: AncillaryPanelProps) {
  const [catFilter, setCatFilter] = useState<CategoryFilter>('all');

  // Loading state
  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '20px 0',
          color: '#57606a',
          fontSize: 13,
        }}
      >
        <Spinner size={18} />
        Generating ancillary revenue recommendations…
      </div>
    );
  }

  // Error state (non-fatal)
  if (error) {
    return (
      <div
        style={{
          background: '#fef2f2',
          border: '1px solid #fecaca',
          borderRadius: 6,
          padding: '12px 16px',
          fontSize: 13,
          color: '#991b1b',
        }}
      >
        <strong>Ancillary recommendations unavailable.</strong>{' '}
        Room pricing and demand-sensing panels are not affected.
        <div style={{ fontSize: 11, color: '#b91c1c', marginTop: 4 }}>{error}</div>
      </div>
    );
  }

  return (
    <div>
      {/* Controls row */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 8,
          marginBottom: 4,
        }}
      >
        <PersonaSwitcher value={persona} onChange={onPersonaChange} />
      </div>

      {/* Category filter tabs */}
      <CategoryTabs active={catFilter} onChange={setCatFilter} />

      {/* No data yet (before first load) */}
      {!data && (
        <div
          style={{
            textAlign: 'center',
            padding: '30px 0',
            color: '#57606a',
            fontSize: 13,
          }}
        >
          Select a property to view ancillary recommendations.
        </div>
      )}

      {data && (
        <>
          <SummaryBar data={data} />

          {/* Filtered recommendations */}
          {(() => {
            const recs =
              catFilter === 'all'
                ? data.recommendations
                : data.recommendations.filter((r) => r.product.category === catFilter);

            if (recs.length === 0) {
              return (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '24px 0',
                    color: '#57606a',
                    fontSize: 13,
                  }}
                >
                  No ancillary offers available for the selected filter.
                </div>
              );
            }

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {recs.map((rec) => (
                  <AncillaryCard key={rec.id} rec={rec} />
                ))}
              </div>
            );
          })()}

          {/* Footer */}
          <div
            style={{
              marginTop: 12,
              fontSize: 10,
              color: '#8b949e',
              display: 'flex',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 4,
            }}
          >
            <span>Engine: {data.engine_model}</span>
            <span>
              All revenue & margin figures are model estimates. Not causal claims.
            </span>
          </div>
        </>
      )}
    </div>
  );
}
