/**
 * AncillaryCard
 *
 * Displays a single ranked ancillary recommendation.
 * Features:
 *   - Rank badge (#1, #2, etc.)
 *   - Product name + category icon
 *   - Base price → Recommended price (with % change if different)
 *   - Propensity percentage bar
 *   - Expected revenue + margin (labelled as estimates)
 *   - Confidence badge
 *   - Expandable detail: WHY THIS OFFER, PRICE section, EXPECTED VALUE section,
 *     Score breakdown (mini bars)
 */
import { useState } from 'react';
import type { AncillaryRecommendation, AncillaryCategory } from '@/types/api';

// ── Category icons (emoji-free, text only) ────────────────────────────────────

const CATEGORY_ICONS: Record<AncillaryCategory, string> = {
  parking_transportation: 'P',
  food_beverage: 'F&B',
  meetings_events: 'MTG',
  spa_wellness: 'SPA',
  experiences: 'EXP',
  workspace: 'WRK',
  guest_commerce: 'COM',
  pet: 'PET',
  room_inventory: 'RM',
};

const CATEGORY_COLORS: Record<AncillaryCategory, string> = {
  parking_transportation: '#3b82d4',
  food_beverage: '#f59e0b',
  meetings_events: '#7c5cd8',
  spa_wellness: '#10b981',
  experiences: '#ef4444',
  workspace: '#0ea5e9',
  guest_commerce: '#8b5cf6',
  pet: '#f97316',
  room_inventory: '#6366f1',
};

const CATEGORY_LABELS: Record<AncillaryCategory, string> = {
  parking_transportation: 'Parking & Transport',
  food_beverage: 'Food & Beverage',
  meetings_events: 'Meetings & Events',
  spa_wellness: 'Spa & Wellness',
  experiences: 'Experiences',
  workspace: 'Workspace',
  guest_commerce: 'Guest Commerce',
  pet: 'Pet Program',
  room_inventory: 'Room Inventory',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n);
}

function pct(n: number): string {
  return `${(n * 100).toFixed(0)}%`;
}

function confidenceColor(c: string): string {
  if (c === 'high') return '#16a34a';
  if (c === 'medium') return '#d97706';
  return '#6b7280';
}

function confidenceBg(c: string): string {
  if (c === 'high') return '#dcfce7';
  if (c === 'medium') return '#fef3c7';
  return '#f3f4f6';
}

// ── Mini score bar ─────────────────────────────────────────────────────────────

interface MiniBarProps {
  label: string;
  value: number;
  max: number;
  color: string;
}

function MiniBar({ label, value, max, color }: MiniBarProps) {
  const pctFill = Math.round((value / max) * 100);
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
        <span style={{ fontSize: 11, color: '#57606a' }}>{label}</span>
        <span style={{ fontSize: 11, fontWeight: 600, color: '#1f2328' }}>
          {value.toFixed(1)}
        </span>
      </div>
      <div
        style={{
          height: 4,
          background: '#e5e7eb',
          borderRadius: 2,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${pctFill}%`,
            background: color,
            borderRadius: 2,
          }}
        />
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface AncillaryCardProps {
  rec: AncillaryRecommendation;
}

export function AncillaryCard({ rec }: AncillaryCardProps) {
  const [expanded, setExpanded] = useState(false);
  const cat = rec.product.category;
  const catColor = CATEGORY_COLORS[cat];
  const hasPriceChange = rec.price_change_pct !== 0;
  const sc = rec.score_components;

  return (
    <button
      onClick={() => setExpanded((v) => !v)}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        background: '#fff',
        border: `1px solid ${expanded ? catColor : '#e5e7eb'}`,
        borderRadius: 8,
        padding: 0,
        cursor: 'pointer',
        transition: 'border-color 0.15s',
      }}
      aria-label={`Ancillary offer: ${rec.product.name}`}
    >
      {/* ── Card header ──────────────────────────────────────────────────── */}
      <div style={{ padding: '14px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          {/* Rank badge */}
          <div
            style={{
              minWidth: 28,
              height: 28,
              borderRadius: '50%',
              background: catColor,
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 12,
              fontWeight: 700,
              flexShrink: 0,
            }}
          >
            {rec.rank}
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Category icon + name row */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 4,
                flexWrap: 'wrap',
              }}
            >
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  background: `${catColor}22`,
                  color: catColor,
                  padding: '2px 6px',
                  borderRadius: 4,
                  letterSpacing: '0.04em',
                }}
              >
                {CATEGORY_ICONS[cat]}
              </span>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#1f2328',
                  lineHeight: 1.3,
                }}
              >
                {rec.product.name}
              </span>
              {/* Confidence badge */}
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: confidenceColor(rec.confidence),
                  background: confidenceBg(rec.confidence),
                  padding: '2px 6px',
                  borderRadius: 4,
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                  marginLeft: 'auto',
                }}
              >
                {rec.confidence}
              </span>
            </div>

            {/* Category label */}
            <div style={{ fontSize: 11, color: '#57606a', marginBottom: 8 }}>
              {CATEGORY_LABELS[cat]}
            </div>

            {/* Price row */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 8,
                flexWrap: 'wrap',
              }}
            >
              {hasPriceChange ? (
                <>
                  <span
                    style={{
                      fontSize: 12,
                      color: '#57606a',
                      textDecoration: 'line-through',
                    }}
                  >
                    ${rec.base_price}
                  </span>
                  <span style={{ fontSize: 12, color: '#57606a' }}>→</span>
                  <span
                    style={{
                      fontSize: 15,
                      fontWeight: 700,
                      color: rec.price_change_pct > 0 ? '#16a34a' : '#d97706',
                    }}
                  >
                    ${rec.recommended_price}
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      color: rec.price_change_pct > 0 ? '#16a34a' : '#d97706',
                      fontWeight: 600,
                    }}
                  >
                    ({rec.price_change_pct > 0 ? '+' : ''}
                    {rec.price_change_pct.toFixed(1)}%)
                  </span>
                </>
              ) : (
                <span style={{ fontSize: 15, fontWeight: 700, color: '#1f2328' }}>
                  ${rec.recommended_price}
                </span>
              )}
            </div>

            {/* Propensity bar */}
            <div style={{ marginBottom: 8 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: 3,
                }}
              >
                <span style={{ fontSize: 11, color: '#57606a' }}>Conversion propensity</span>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#1f2328' }}>
                  {pct(rec.propensity)}
                </span>
              </div>
              <div
                style={{
                  height: 5,
                  background: '#e5e7eb',
                  borderRadius: 3,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${Math.round(rec.propensity * 100)}%`,
                    background: catColor,
                    borderRadius: 3,
                  }}
                />
              </div>
            </div>

            {/* Revenue + Margin estimates */}
            <div
              style={{
                display: 'flex',
                gap: 16,
                flexWrap: 'wrap',
              }}
            >
              <div>
                <div style={{ fontSize: 11, color: '#57606a' }}>est. revenue</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#1f2328' }}>
                  {fmt(rec.expected_revenue)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#57606a' }}>est. margin</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#16a34a' }}>
                  {fmt(rec.expected_margin)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Expanded detail ──────────────────────────────────────────────── */}
      {expanded && (
        <div
          style={{
            borderTop: `1px solid #e5e7eb`,
            padding: '14px 16px',
            background: '#f7f8fa',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* WHY THIS OFFER */}
          {rec.supporting_factors.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: '#57606a',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  marginBottom: 6,
                }}
              >
                Why This Offer
              </div>
              <ul style={{ paddingLeft: 0, listStyle: 'none', margin: 0 }}>
                {rec.supporting_factors.map((f, i) => (
                  <li
                    key={i}
                    style={{
                      fontSize: 12,
                      color: '#1f2328',
                      padding: '2px 0',
                      paddingLeft: 10,
                      borderLeft: `2px solid ${catColor}`,
                      marginBottom: 3,
                    }}
                  >
                    {f}
                  </li>
                ))}
              </ul>
              {rec.reason_codes.length > 0 && (
                <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {rec.reason_codes.map((rc) => (
                    <span
                      key={rc}
                      style={{
                        fontSize: 10,
                        color: '#57606a',
                        background: '#e5e7eb',
                        padding: '2px 6px',
                        borderRadius: 4,
                      }}
                    >
                      {rc}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* PRICE */}
          {hasPriceChange && (
            <div style={{ marginBottom: 14 }}>
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: '#57606a',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  marginBottom: 6,
                }}
              >
                Pricing
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 8,
                  marginBottom: 6,
                }}
              >
                {[
                  { label: 'Base', value: `$${rec.base_price}` },
                  {
                    label: 'Recommended',
                    value: `$${rec.recommended_price}`,
                  },
                  {
                    label: 'Change',
                    value: `${rec.price_change_pct > 0 ? '+' : ''}${rec.price_change_pct.toFixed(1)}%`,
                  },
                ].map(({ label, value }) => (
                  <div
                    key={label}
                    style={{
                      background: '#fff',
                      border: '1px solid #e5e7eb',
                      borderRadius: 6,
                      padding: '6px 10px',
                    }}
                  >
                    <div style={{ fontSize: 10, color: '#57606a', marginBottom: 2 }}>
                      {label}
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#1f2328' }}>
                      {value}
                    </div>
                  </div>
                ))}
              </div>
              {rec.price_change_reason && (
                <div style={{ fontSize: 11, color: '#57606a', fontStyle: 'italic' }}>
                  {rec.price_change_reason}
                </div>
              )}
            </div>
          )}

          {/* EXPECTED VALUE */}
          <div style={{ marginBottom: 14 }}>
            <div
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: '#57606a',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: 6,
              }}
            >
              Expected Value (Estimate)
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: 8,
                marginBottom: 6,
              }}
            >
              {[
                { label: 'Eligible Guests', value: String(rec.eligible_guests) },
                {
                  label: 'Est. Conversions',
                  value: rec.expected_conversions.toFixed(1),
                },
                { label: 'Est. Revenue', value: fmt(rec.expected_revenue) },
                { label: 'Est. Margin', value: fmt(rec.expected_margin) },
              ].map(({ label, value }) => (
                <div
                  key={label}
                  style={{
                    background: '#fff',
                    border: '1px solid #e5e7eb',
                    borderRadius: 6,
                    padding: '6px 10px',
                  }}
                >
                  <div style={{ fontSize: 10, color: '#57606a', marginBottom: 2 }}>
                    {label}
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#1f2328' }}>
                    {value}
                  </div>
                </div>
              ))}
            </div>
            <div
              style={{
                fontSize: 10,
                color: '#8b949e',
                fontStyle: 'italic',
              }}
            >
              Impact figures are model estimates based on propensity scoring and demand signals.
              Not causal claims.
            </div>
          </div>

          {/* SCORE BREAKDOWN */}
          <div>
            <div
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: '#57606a',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: 8,
              }}
            >
              Score Breakdown (total: {rec.score.toFixed(1)} / 100)
            </div>
            <MiniBar label="Propensity (×30)" value={sc.propensity_score} max={30} color={catColor} />
            <MiniBar label="Margin (×25)" value={sc.margin_score} max={25} color="#7c5cd8" />
            <MiniBar label="Demand (×20)" value={sc.demand_relevance_score} max={20} color="#f59e0b" />
            <MiniBar label="Segment (×15)" value={sc.segment_affinity_score} max={15} color="#10b981" />
            <MiniBar label="Event (×7)" value={sc.event_relevance_score} max={7} color="#ef4444" />
            <MiniBar label="Capacity (×3)" value={sc.capacity_score} max={3} color="#6b7280" />
          </div>
        </div>
      )}
    </button>
  );
}
