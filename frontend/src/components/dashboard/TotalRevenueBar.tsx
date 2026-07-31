/**
 * TotalRevenueBar
 *
 * Displays three financial metrics side by side:
 *   - Room Revenue Opportunity (from recommendations summary)
 *   - Ancillary Revenue Opportunity (from ancillary summary)
 *   - Total Revenue Opportunity (sum)
 *
 * All clearly labelled as estimates.
 * Premium look for exec demo.
 */
import type { AncillaryRecommendationResponse, RecommendationResponse } from '@/types/api';

interface TotalRevenueBarProps {
  recommendations?: RecommendationResponse;
  ancillaryRecommendations?: AncillaryRecommendationResponse;
}

function fmt(n: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n);
}

export function TotalRevenueBar({
  recommendations,
  ancillaryRecommendations,
}: TotalRevenueBarProps) {
  if (!recommendations && !ancillaryRecommendations) return null;

  const roomRevenue = recommendations?.summary.estimated_revenue_opportunity ?? 0;
  const ancillaryRevenue =
    ancillaryRecommendations?.summary.total_revenue_opportunity ?? 0;
  const totalRevenue = roomRevenue + ancillaryRevenue;

  const metrics: { label: string; value: string; sub: string; color: string }[] = [
    {
      label: 'Room Revenue Opportunity',
      value: fmt(roomRevenue),
      sub: 'Rate + Inventory actions',
      color: '#3b82d4',
    },
    {
      label: 'Ancillary Revenue Opportunity',
      value: fmt(ancillaryRevenue),
      sub: 'Non-room upsell & ancillaries',
      color: '#7c5cd8',
    },
    {
      label: 'Total Revenue Opportunity',
      value: fmt(totalRevenue),
      sub: 'Combined estimate',
      color: '#0f172a',
    },
  ];

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%)',
        borderRadius: 10,
        padding: '16px 24px',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 0,
      }}
    >
      {metrics.map(({ label, value, sub, color }, idx) => (
        <div
          key={label}
          style={{
            padding: '8px 16px',
            borderLeft: idx > 0 ? '1px solid rgba(255,255,255,0.12)' : undefined,
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: 'rgba(255,255,255,0.55)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              marginBottom: 4,
            }}
          >
            {label}
            <span
              style={{
                marginLeft: 4,
                fontSize: 9,
                color: 'rgba(255,255,255,0.35)',
              }}
            >
              (est.)
            </span>
          </div>
          <div
            style={{
              fontSize: idx === 2 ? 22 : 20,
              fontWeight: 700,
              color: idx === 2 ? '#fff' : color === '#3b82d4' ? '#93c5fd' : '#c4b5fd',
              letterSpacing: '-0.02em',
              marginBottom: 2,
            }}
          >
            {value}
          </div>
          <div
            style={{
              fontSize: 11,
              color: 'rgba(255,255,255,0.40)',
            }}
          >
            {sub}
          </div>
        </div>
      ))}
    </div>
  );
}
