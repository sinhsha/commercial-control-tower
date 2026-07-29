/**
 * RecommendationCard
 *
 * Renders a single commercial recommendation as an expandable card.
 * Collapsed: priority badge, category, title, dates, current/recommended value, revenue impact.
 * Expanded: full detail — supporting factors, reason codes, risk flags, impact calculation.
 *
 * All financial figures are labelled "(estimate)" per spec.
 * No event handlers that modify state are attached except the expand toggle.
 */
import { useState } from 'react';
import { format, parseISO } from 'date-fns';
import type {
  Recommendation,
  RecommendationCategory,
  RecommendationPriority,
  RecommendationConfidence,
} from '@/types/api';
import { Badge } from '@/components/ui/Badge';

// ── Style helpers ─────────────────────────────────────────────────────────────

const PRIORITY_COLORS: Record<RecommendationPriority, { bg: string; text: string; border: string }> = {
  critical: { bg: '#fef2f2', text: '#991b1b', border: '#fca5a5' },
  high:     { bg: '#fff7ed', text: '#92400e', border: '#fed7aa' },
  medium:   { bg: '#fffbeb', text: '#78350f', border: '#fde68a' },
  low:      { bg: '#f0fdf4', text: '#166534', border: '#bbf7d0' },
};

const PRIORITY_BADGE_VARIANT: Record<RecommendationPriority, 'red' | 'yellow' | 'blue' | 'green' | 'purple'> = {
  critical: 'red',
  high:     'yellow',
  medium:   'blue',
  low:      'green',
};

const CATEGORY_ICONS: Record<RecommendationCategory, string> = {
  pricing:      '💰',
  inventory:    '🏨',
  restrictions: '🔒',
  upgrade:      '⬆',
  package:      '📦',
  ancillary:    '✨',
  operational:  '🔔',
};

const CONFIDENCE_LABEL: Record<RecommendationConfidence, string> = {
  high:   'High confidence',
  medium: 'Medium confidence',
  low:    'Low confidence',
};

function fmt(n: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n);
}

function fmtDate(d: string): string {
  try { return format(parseISO(d), 'MMM d'); } catch { return d; }
}

// ── Component ─────────────────────────────────────────────────────────────────

interface RecommendationCardProps {
  rec: Recommendation;
}

export function RecommendationCard({ rec }: RecommendationCardProps) {
  const [expanded, setExpanded] = useState(false);
  const colors = PRIORITY_COLORS[rec.priority];
  const icon = CATEGORY_ICONS[rec.category];
  const showValue =
    rec.current_value != null &&
    rec.recommended_value != null &&
    rec.unit !== 'alert' &&
    rec.unit !== 'policy' &&
    rec.unit !== 'rate plans' &&
    rec.unit !== 'package';

  return (
    <div
      style={{
        border: `1px solid ${colors.border}`,
        borderRadius: 8,
        background: colors.bg,
        marginBottom: 8,
        overflow: 'hidden',
      }}
    >
      {/* ── Collapsed row ───────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 12,
          padding: '12px 16px',
          cursor: 'pointer',
        }}
        onClick={() => setExpanded((v) => !v)}
        role="button"
        aria-expanded={expanded}
      >
        {/* Icon */}
        <span style={{ fontSize: 18, lineHeight: '22px', flexShrink: 0 }}>{icon}</span>

        {/* Main content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
            <Badge variant={PRIORITY_BADGE_VARIANT[rec.priority]}>
              {rec.priority.toUpperCase()}
            </Badge>
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: '#57606a',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              {rec.category}
            </span>
            <span style={{ fontSize: 10, color: '#8b949e' }}>
              {fmtDate(rec.effective_start_date)} – {fmtDate(rec.effective_end_date)}
            </span>
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2328', marginBottom: 3 }}>
            {rec.title}
          </div>
          <div style={{ fontSize: 12, color: '#57606a', lineHeight: 1.5 }}>{rec.summary}</div>

          {/* Value change + revenue row */}
          <div
            style={{
              display: 'flex',
              gap: 16,
              marginTop: 8,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            {showValue && (
              <span style={{ fontSize: 12, color: '#1f2328' }}>
                <span style={{ color: '#57606a' }}>Current: </span>
                <strong>
                  {rec.unit === 'USD' ? fmt(rec.current_value!) : rec.current_value}
                  {rec.unit !== 'USD' ? ` ${rec.unit}` : ''}
                </strong>
                <span style={{ color: '#57606a', margin: '0 4px' }}>→</span>
                <strong style={{ color: rec.action === 'reduce_rate' ? '#dc2626' : '#16a34a' }}>
                  {rec.unit === 'USD' ? fmt(rec.recommended_value!) : rec.recommended_value}
                  {rec.unit !== 'USD' ? ` ${rec.unit}` : ''}
                </strong>
              </span>
            )}
            {rec.expected_revenue_impact !== 0 && (
              <span style={{ fontSize: 12, color: rec.expected_revenue_impact > 0 ? '#16a34a' : '#dc2626' }}>
                {rec.expected_revenue_impact > 0 ? '+' : ''}
                {fmt(rec.expected_revenue_impact)}{' '}
                <span style={{ color: '#8b949e', fontWeight: 400 }}>est. revenue</span>
              </span>
            )}
            <span style={{ fontSize: 11, color: '#8b949e', marginLeft: 'auto' }}>
              {CONFIDENCE_LABEL[rec.confidence]}
            </span>
          </div>
        </div>

        {/* Expand chevron */}
        <span
          style={{
            color: '#8b949e',
            fontSize: 14,
            flexShrink: 0,
            transform: expanded ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.15s',
          }}
        >
          ▾
        </span>
      </div>

      {/* ── Expanded detail ──────────────────────────────────────── */}
      {expanded && (
        <div
          style={{
            borderTop: `1px solid ${colors.border}`,
            padding: '12px 16px 16px',
            background: '#fff',
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 16,
            }}
          >
            {/* Supporting factors */}
            {rec.supporting_factors.length > 0 && (
              <DetailSection title="Supporting Demand Signals">
                <ul style={{ paddingLeft: 16, margin: 0, listStyle: 'disc' }}>
                  {rec.supporting_factors.map((f, i) => (
                    <li key={i} style={{ fontSize: 12, color: '#1f2328', lineHeight: 1.6 }}>{f}</li>
                  ))}
                </ul>
              </DetailSection>
            )}

            {/* Reason codes */}
            {rec.reason_codes.length > 0 && (
              <DetailSection title="Why This Recommendation">
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {rec.reason_codes.map((code) => (
                    <span
                      key={code}
                      style={{
                        fontSize: 11,
                        background: '#e0e7ff',
                        color: '#3730a3',
                        borderRadius: 4,
                        padding: '2px 6px',
                      }}
                    >
                      {code.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </DetailSection>
            )}

            {/* Risk flags */}
            {rec.risk_flags.length > 0 && (
              <DetailSection title="Applied Guardrails & Risk Flags">
                {rec.risk_flags.map((flag, i) => (
                  <div
                    key={i}
                    style={{
                      fontSize: 12,
                      color: '#92400e',
                      background: '#fef3c7',
                      borderRadius: 4,
                      padding: '4px 8px',
                      marginBottom: 4,
                    }}
                  >
                    ⚠ {flag}
                  </div>
                ))}
              </DetailSection>
            )}

            {/* Impact calculation */}
            {rec.expected_revenue_impact !== 0 && (
              <DetailSection title="Estimated Impact">
                <div style={{ fontSize: 12, color: '#1f2328', lineHeight: 1.7 }}>
                  <div>
                    <strong>Revenue (estimate): </strong>
                    <span style={{ color: rec.expected_revenue_impact > 0 ? '#16a34a' : '#dc2626' }}>
                      {rec.expected_revenue_impact > 0 ? '+' : ''}{fmt(rec.expected_revenue_impact)}
                    </span>
                  </div>
                  {rec.expected_occupancy_impact !== 0 && (
                    <div>
                      <strong>Occupancy (estimate): </strong>
                      {rec.expected_occupancy_impact > 0 ? '+' : ''}
                      {rec.expected_occupancy_impact.toFixed(1)} pp
                    </div>
                  )}
                  <div style={{ fontSize: 11, color: '#8b949e', marginTop: 4 }}>
                    * Impact figures are model estimates, not causal guarantees.
                  </div>
                </div>
              </DetailSection>
            )}
          </div>

          {/* Action + confidence footer */}
          <div
            style={{
              marginTop: 12,
              paddingTop: 10,
              borderTop: '1px solid #e5e7eb',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: 11,
              color: '#8b949e',
            }}
          >
            <span>
              Action: <strong style={{ color: '#1f2328' }}>{rec.action.replace(/_/g, ' ')}</strong>
              {' · '}Score: <strong style={{ color: '#1f2328' }}>{rec.score.toFixed(0)}</strong>
            </span>
            <span>Status: {rec.status}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
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
        {title}
      </div>
      {children}
    </div>
  );
}
