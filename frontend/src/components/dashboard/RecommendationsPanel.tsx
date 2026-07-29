/**
 * RecommendationsPanel
 *
 * Displays the Commercial Recommendation Engine output.
 * Features:
 *   - Summary metrics bar (total, high-priority, revenue opportunity)
 *   - Category filter tabs (All + 7 categories)
 *   - Priority filter dropdown
 *   - Ranked recommendation cards (expandable)
 *   - Loading, empty, and error states
 *   - Non-fatal: failures show an inline error, other dashboard panels continue
 *
 * Filtering is done client-side — the full 14-day list is loaded once.
 */
import { useState } from 'react';
import type {
  RecommendationResponse,
  RecommendationCategory,
  RecommendationPriority,
  Recommendation,
} from '@/types/api';
import { RecommendationCard } from '@/components/dashboard/RecommendationCard';
import { Spinner } from '@/components/ui/Spinner';

// ── Types & helpers ───────────────────────────────────────────────────────────

type CategoryFilter = 'all' | RecommendationCategory;
type PriorityFilter = 'all' | RecommendationPriority;

const CATEGORY_LABELS: Record<CategoryFilter, string> = {
  all:          'All',
  pricing:      'Pricing',
  inventory:    'Inventory',
  restrictions: 'Restrictions',
  upgrade:      'Upgrade',
  package:      'Package',
  ancillary:    'Ancillary',
  operational:  'Operational',
};

function fmt(n: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n);
}

// ── Summary bar ───────────────────────────────────────────────────────────────

interface SummaryBarProps {
  data: RecommendationResponse;
}

function SummaryBar({ data }: SummaryBarProps) {
  const s = data.summary;
  const demandDriven = data.recommendations.filter((r) =>
    r.reason_codes.includes('event_demand')
  ).length;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 10,
        marginBottom: 16,
      }}
    >
      {[
        { label: 'Proposed Actions', value: String(s.total), sub: 'recommendations' },
        {
          label: 'High Priority',
          value: String(s.critical + s.high),
          sub: `${s.critical} critical · ${s.high} high`,
        },
        {
          label: 'Est. Revenue Opportunity',
          value: fmt(s.estimated_revenue_opportunity),
          sub: '* estimate only',
        },
        { label: 'Demand-Driven', value: String(demandDriven), sub: 'event-triggered' },
      ].map(({ label, value, sub }) => (
        <div
          key={label}
          style={{
            background: '#f7f8fa',
            border: '1px solid #e5e7eb',
            borderRadius: 8,
            padding: '10px 14px',
          }}
        >
          <div style={{ fontSize: 11, color: '#57606a', marginBottom: 2, fontWeight: 600 }}>
            {label}
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#1f2328' }}>{value}</div>
          <div style={{ fontSize: 10, color: '#8b949e', marginTop: 2 }}>{sub}</div>
        </div>
      ))}
    </div>
  );
}

// ── Category filter tabs ──────────────────────────────────────────────────────

interface CategoryTabsProps {
  active: CategoryFilter;
  onChange: (c: CategoryFilter) => void;
  counts: Partial<Record<CategoryFilter, number>>;
}

function CategoryTabs({ active, onChange, counts }: CategoryTabsProps) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 4,
        flexWrap: 'wrap',
        marginBottom: 10,
      }}
    >
      {(Object.keys(CATEGORY_LABELS) as CategoryFilter[]).map((cat) => {
        const count = counts[cat] ?? 0;
        if (cat !== 'all' && count === 0) return null;
        return (
          <button
            key={cat}
            onClick={() => onChange(cat)}
            style={{
              padding: '4px 10px',
              fontSize: 12,
              fontWeight: 600,
              borderRadius: 5,
              border: active === cat ? '1.5px solid #3b82d4' : '1px solid #d1d5db',
              background: active === cat ? '#eff6ff' : '#fff',
              color: active === cat ? '#1d4ed8' : '#57606a',
              cursor: 'pointer',
            }}
          >
            {CATEGORY_LABELS[cat]}
            {count > 0 && cat !== 'all' && (
              <span
                style={{
                  marginLeft: 5,
                  fontSize: 10,
                  background: active === cat ? '#bfdbfe' : '#e5e7eb',
                  borderRadius: 10,
                  padding: '1px 5px',
                }}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

interface RecommendationsPanelProps {
  hotelId: string | null;
  loading?: boolean;
  error?: string;
  data?: RecommendationResponse;
}

export function RecommendationsPanel({
  hotelId,
  loading = false,
  error,
  data,
}: RecommendationsPanelProps) {
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all');
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all');

  // ── Loading state ─────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '24px 0',
          color: '#57606a',
          fontSize: 13,
        }}
      >
        <Spinner size={18} />
        Generating commercial recommendations…
      </div>
    );
  }

  // ── Non-fatal error ───────────────────────────────────────────────────────
  if (error) {
    return (
      <div
        style={{
          background: '#fff7ed',
          border: '1px solid #fed7aa',
          borderRadius: 8,
          padding: '12px 16px',
          fontSize: 13,
          color: '#92400e',
        }}
      >
        <strong>Recommendations unavailable:</strong> {error}
        <div style={{ fontSize: 11, color: '#b45309', marginTop: 4 }}>
          Forecast and demand-sensing panels are not affected.
        </div>
      </div>
    );
  }

  // ── No data yet ───────────────────────────────────────────────────────────
  if (!data || !hotelId) {
    return (
      <div style={{ padding: '24px 0', color: '#57606a', fontSize: 13, textAlign: 'center' }}>
        Select a hotel to view commercial recommendations.
      </div>
    );
  }

  // ── Client-side filtering ─────────────────────────────────────────────────
  const all = data.recommendations;

  // Count per category for tab badges
  const categoryCounts = all.reduce<Partial<Record<CategoryFilter, number>>>(
    (acc, r) => {
      acc[r.category] = (acc[r.category] ?? 0) + 1;
      acc['all'] = (acc['all'] ?? 0) + 1;
      return acc;
    },
    {}
  );

  const filtered: Recommendation[] = all.filter((r) => {
    if (categoryFilter !== 'all' && r.category !== categoryFilter) return false;
    if (priorityFilter !== 'all' && r.priority !== priorityFilter) return false;
    return true;
  });

  // ── Empty state ───────────────────────────────────────────────────────────
  if (all.length === 0) {
    return (
      <div>
        <SummaryBar data={data} />
        <div
          style={{
            padding: '20px',
            textAlign: 'center',
            color: '#57606a',
            fontSize: 13,
            background: '#f7f8fa',
            borderRadius: 8,
            border: '1px solid #e5e7eb',
          }}
        >
          No commercial actions recommended for the current forecast period.
          <div style={{ fontSize: 11, color: '#8b949e', marginTop: 4 }}>
            All occupancy and rate indicators are within normal thresholds.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* ── Summary metrics bar ────────────────────────────────── */}
      <SummaryBar data={data} />

      {/* ── Filters row ────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 8,
          marginBottom: 8,
        }}
      >
        <CategoryTabs
          active={categoryFilter}
          onChange={setCategoryFilter}
          counts={categoryCounts}
        />

        {/* Priority filter */}
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value as PriorityFilter)}
          style={{
            fontSize: 12,
            padding: '4px 8px',
            borderRadius: 5,
            border: '1px solid #d1d5db',
            background: '#fff',
            color: '#1f2328',
            cursor: 'pointer',
          }}
          aria-label="Filter by priority"
        >
          <option value="all">All priorities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* ── Recommendation list ─────────────────────────────────── */}
      {filtered.length === 0 ? (
        <div style={{ fontSize: 13, color: '#57606a', padding: '16px 0', textAlign: 'center' }}>
          No recommendations match the selected filters.
        </div>
      ) : (
        filtered.map((rec) => <RecommendationCard key={rec.id} rec={rec} />)
      )}

      {/* ── Footer ─────────────────────────────────────────────── */}
      <div
        style={{
          fontSize: 11,
          color: '#8b949e',
          marginTop: 8,
          borderTop: '1px solid #e5e7eb',
          paddingTop: 8,
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        <span>Engine: {data.recommendation_model}</span>
        <span>* Revenue figures are estimates, not guarantees</span>
      </div>
    </div>
  );
}
