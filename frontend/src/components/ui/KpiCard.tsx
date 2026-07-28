import { type ReactNode } from 'react';

interface KpiCardProps {
  label: string;
  value: string;
  subtext?: string;
  trend?: 'up' | 'down' | 'neutral';
  accent?: boolean;
  icon?: ReactNode;
}

const trendArrow = {
  up: '↑',
  down: '↓',
  neutral: '→',
} as const;

const trendColor = {
  up: '#16a34a',
  down: '#dc2626',
  neutral: '#6b7280',
} as const;

export function KpiCard({ label, value, subtext, trend, accent = false, icon }: KpiCardProps) {
  return (
    <div
      style={{
        background: accent ? '#1e3a5f' : '#ffffff',
        border: `1px solid ${accent ? '#2d5a8e' : '#e5e7eb'}`,
        borderRadius: 8,
        padding: '20px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        minWidth: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {icon && (
          <span style={{ fontSize: 18, opacity: 0.7 }}>{icon}</span>
        )}
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: accent ? '#93c5fd' : '#57606a',
          }}
        >
          {label}
        </span>
      </div>
      <div
        style={{
          fontSize: 32,
          fontWeight: 700,
          lineHeight: 1.1,
          color: accent ? '#ffffff' : '#1f2328',
          letterSpacing: '-0.02em',
        }}
      >
        {value}
      </div>
      {(subtext || trend) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
          {trend && (
            <span style={{ color: trendColor[trend], fontSize: 13, fontWeight: 600 }}>
              {trendArrow[trend]}
            </span>
          )}
          {subtext && (
            <span style={{ fontSize: 12, color: accent ? '#93c5fd' : '#57606a' }}>
              {subtext}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
