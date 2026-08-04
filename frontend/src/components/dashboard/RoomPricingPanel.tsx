import { useState, useCallback } from 'react';
import type {
  RoomPricingResponse,
  RoomCalendarResponse,
  InventoryResponse,
  RoomTypePricingRecommendation,
} from '@/types/api';
import { SectionCard } from '@/components/ui/SectionCard';
import { useRoomPricing, useRoomCalendar, useRoomInventory } from '@/hooks/useRoomPricing';

interface RoomPricingPanelProps {
  hotelId: string;
}

// ── Colour helpers ────────────────────────────────────────────────────────────

function demandCellColor(occ: number): string {
  if (occ > 92) return '#fff1f0'; // hot – red tint
  if (occ > 85) return '#fff7e6'; // warm – amber tint
  if (occ > 75) return '#f6ffed'; // good – green tint
  if (occ > 65) return '#f0f5ff'; // neutral – blue tint
  return '#fafafa';               // cool
}

function confidenceDot(confidence: string): string {
  switch (confidence) {
    case 'high': return '#16a34a';
    case 'medium': return '#d97706';
    default: return '#dc2626';
  }
}

function protectionBadge(status: string): { bg: string; color: string } {
  switch (status) {
    case 'protected': return { bg: '#fff1f0', color: '#cf1322' };
    case 'hold': return { bg: '#fff7e6', color: '#d46b08' };
    default: return { bg: '#f6ffed', color: '#389e0d' };
  }
}

function occupancyBarColor(pct: number): string {
  if (pct > 85) return '#f5222d';
  if (pct > 70) return '#fa8c16';
  return '#52c41a';
}

function fmtPct(n: number): string {
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(1)}%`;
}

function fmtMoney(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

// ── Section 1: Projected KPI Strip (clickable drill-down) ────────────────────

type DrillDownKey = 'adr' | 'revpar' | 'revenue' | 'occupancy' | 'opportunity' | null;

function ClickableKpiCard({
  label,
  value,
  subtext,
  trend,
  accent,
  active,
  onClick,
}: {
  label: string;
  value: string;
  subtext?: string;
  trend?: 'up' | 'down' | 'neutral';
  accent?: boolean;
  active: boolean;
  onClick: () => void;
}) {
  const trendArrow = { up: '↑', down: '↓', neutral: '→' } as const;
  const trendColor = { up: '#16a34a', down: '#dc2626', neutral: '#6b7280' } as const;

  return (
    <div
      onClick={onClick}
      style={{
        background: accent ? '#1e3a5f' : '#ffffff',
        border: active
          ? `2px solid ${accent ? '#60a5fa' : '#3b82d4'}`
          : `1px solid ${accent ? '#2d5a8e' : '#e5e7eb'}`,
        borderRadius: 8,
        padding: active ? '19px 23px' : '20px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        minWidth: 0,
        cursor: 'pointer',
        transition: 'box-shadow 0.15s, border 0.15s',
        boxShadow: active ? '0 0 0 3px rgba(59,130,212,0.15)' : 'none',
        position: 'relative',
      }}
    >
      {/* Active indicator dot */}
      {active && (
        <div style={{
          position: 'absolute', top: 8, right: 10,
          width: 6, height: 6, borderRadius: '50%',
          background: accent ? '#60a5fa' : '#3b82d4',
        }} />
      )}
      <span style={{
        fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
        textTransform: 'uppercase' as const,
        color: accent ? '#93c5fd' : '#57606a',
      }}>
        {label}
      </span>
      <div style={{
        fontSize: 32, fontWeight: 700, lineHeight: 1.1,
        color: accent ? '#ffffff' : '#1f2328', letterSpacing: '-0.02em',
      }}>
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
      {/* Click hint */}
      <span style={{ fontSize: 10, color: accent ? '#7dd3fc' : '#9ca3af', marginTop: 2 }}>
        {active ? '▲ hide breakdown' : '▼ see breakdown'}
      </span>
    </div>
  );
}

// ── Drill-down drawer ─────────────────────────────────────────────────────────

function DrillDownDrawer({
  metric,
  data,
}: {
  metric: DrillDownKey;
  data: RoomPricingResponse;
}) {
  if (!metric || data.recommendations.length === 0) return null;

  const recs = [...data.recommendations].sort((a, b) => a.room_rank - b.room_rank);
  const soldEstimate = (r: RoomTypePricingRecommendation) =>
    r.inventory_count - r.current_available;

  // Build per-room rows depending on which metric was clicked
  const rows = recs.map((r) => {
    const sold = soldEstimate(r);

    switch (metric) {
      case 'adr': return {
        label: r.display_name,
        current: `$${r.current_price.toFixed(0)}`,
        projected: `$${r.recommended_price.toFixed(0)}`,
        delta: r.price_change_pct,
        bar: r.recommended_price / (data.projected_adr * 2),
        note: r.reason_codes.slice(0, 1).join(', ') || '—',
      };
      case 'revpar': {
        const occ = r.inventory_count > 0 ? sold / r.inventory_count : 0;
        const revpar = r.recommended_price * occ;
        const curRevpar = r.current_price * occ;
        return {
          label: r.display_name,
          current: `$${curRevpar.toFixed(0)}`,
          projected: `$${revpar.toFixed(0)}`,
          delta: curRevpar > 0 ? ((revpar - curRevpar) / curRevpar) * 100 : 0,
          bar: revpar / (data.projected_revpar * 2),
          note: `${(occ * 100).toFixed(0)}% occ · ${r.inventory_count} rooms`,
        };
      }
      case 'revenue': {
        const rev = r.recommended_price * sold;
        const curRev = r.current_price * sold;
        return {
          label: r.display_name,
          current: fmtMoney(curRev),
          projected: fmtMoney(rev),
          delta: curRev > 0 ? ((rev - curRev) / curRev) * 100 : 0,
          bar: rev / (data.projected_room_revenue * 0.6 + 1),
          note: `${sold} rooms sold est.`,
        };
      }
      case 'occupancy': {
        const occ = r.inventory_count > 0 ? sold / r.inventory_count : 0;
        return {
          label: r.display_name,
          current: `${(occ * 100).toFixed(0)}%`,
          projected: `${(occ * 100).toFixed(0)}%`,
          delta: 0,
          bar: occ,
          note: `${sold} / ${r.inventory_count} rooms`,
        };
      }
      case 'opportunity': {
        const opp = (r.recommended_price - r.current_price) * sold;
        return {
          label: r.display_name,
          current: fmtMoney(r.current_price * sold),
          projected: fmtMoney(r.recommended_price * sold),
          delta: r.price_change_pct,
          bar: Math.max(0, opp) / (data.projected_revenue_opportunity * 0.6 + 1),
          note: opp >= 0 ? `+${fmtMoney(opp)} opportunity` : `${fmtMoney(opp)} risk`,
        };
      }
      default: return {
        label: r.display_name, current: '—', projected: '—', delta: 0, bar: 0, note: '',
      };
    }
  });

  const metricLabels: Record<NonNullable<DrillDownKey>, string> = {
    adr: 'ADR by Room Type',
    revpar: 'RevPAR by Room Type',
    revenue: 'Revenue by Room Type',
    occupancy: 'Occupancy by Room Type',
    opportunity: 'Revenue Opportunity by Room Type',
  };

  return (
    <div style={{
      border: '1px solid #e5e7eb',
      borderRadius: 8,
      background: '#f7f8fa',
      padding: '16px 20px',
      marginTop: -8,
    }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#1f2328', marginBottom: 12,
        textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {metricLabels[metric]}
      </div>

      {/* Header */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px 80px 60px 1fr 100px',
        gap: 8, fontSize: 10, fontWeight: 600, color: '#57606a',
        textTransform: 'uppercase', letterSpacing: '0.04em',
        borderBottom: '1px solid #e5e7eb', paddingBottom: 6, marginBottom: 8 }}>
        <span>Room Type</span>
        <span style={{ textAlign: 'right' }}>Current</span>
        <span style={{ textAlign: 'right' }}>Projected</span>
        <span style={{ textAlign: 'right' }}>Δ</span>
        <span style={{ paddingLeft: 8 }}>Contribution</span>
        <span>Note</span>
      </div>

      {/* Rows */}
      {rows.map((row, i) => (
        <div key={i} style={{ display: 'grid',
          gridTemplateColumns: '1fr 80px 80px 60px 1fr 100px',
          gap: 8, alignItems: 'center', padding: '5px 0',
          borderBottom: i < rows.length - 1 ? '1px solid #f0f0f0' : 'none' }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: '#1f2328' }}>{row.label}</span>
          <span style={{ fontSize: 12, color: '#57606a', textAlign: 'right' }}>{row.current}</span>
          <span style={{ fontSize: 12, fontWeight: 600, color: '#1f2328', textAlign: 'right' }}>
            {row.projected}
          </span>
          <span style={{ fontSize: 11, fontWeight: 600, textAlign: 'right',
            color: row.delta > 0 ? '#16a34a' : row.delta < 0 ? '#dc2626' : '#6b7280' }}>
            {row.delta !== 0 ? `${row.delta > 0 ? '+' : ''}${row.delta.toFixed(1)}%` : '—'}
          </span>
          {/* Mini bar */}
          <div style={{ paddingLeft: 8 }}>
            <div style={{ height: 6, borderRadius: 3, background: '#e5e7eb', overflow: 'hidden' }}>
              <div style={{
                height: '100%', borderRadius: 3,
                background: '#3b82d4',
                width: `${Math.min(100, Math.max(0, row.bar * 100)).toFixed(1)}%`,
                transition: 'width 0.3s',
              }} />
            </div>
          </div>
          <span style={{ fontSize: 10, color: '#6b7280' }}>{row.note}</span>
        </div>
      ))}
    </div>
  );
}

function ProjectedKpiStrip({ data }: { data: RoomPricingResponse }) {
  const [active, setActive] = useState<DrillDownKey>(null);

  const toggle = useCallback((key: DrillDownKey) => {
    setActive((prev) => (prev === key ? null : key));
  }, []);

  const currentAdr =
    data.recommendations.length > 0
      ? data.recommendations.reduce((s, r) => s + r.current_price, 0) /
        data.recommendations.length
      : data.competitor_adr;

  const adrDelta = data.projected_adr - currentAdr;
  const currentRevpar = currentAdr * data.projected_occupancy_pct / 100;
  const revparDelta = data.projected_revpar - currentRevpar;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
        <ClickableKpiCard
          label="Projected ADR"
          value={`$${data.projected_adr.toFixed(0)}`}
          subtext={`${adrDelta >= 0 ? '+' : ''}$${adrDelta.toFixed(0)} vs current`}
          trend={adrDelta >= 0 ? 'up' : 'down'}
          active={active === 'adr'}
          onClick={() => toggle('adr')}
        />
        <ClickableKpiCard
          label="Projected RevPAR"
          value={`$${data.projected_revpar.toFixed(0)}`}
          subtext={`${revparDelta >= 0 ? '+' : ''}$${revparDelta.toFixed(0)} vs current`}
          trend={revparDelta >= 0 ? 'up' : 'down'}
          active={active === 'revpar'}
          onClick={() => toggle('revpar')}
        />
        <ClickableKpiCard
          label="Projected Revenue"
          value={fmtMoney(data.projected_room_revenue)}
          subtext="room revenue"
          trend="neutral"
          active={active === 'revenue'}
          onClick={() => toggle('revenue')}
        />
        <ClickableKpiCard
          label="Projected Occupancy"
          value={`${data.projected_occupancy_pct.toFixed(1)}%`}
          subtext={`Forecast: ${data.forecast_occupancy_pct.toFixed(1)}%`}
          trend={data.projected_occupancy_pct >= 70 ? 'up' : 'neutral'}
          active={active === 'occupancy'}
          onClick={() => toggle('occupancy')}
        />
        <ClickableKpiCard
          label="Revenue Opportunity"
          value={fmtMoney(data.projected_revenue_opportunity)}
          subtext="vs current pricing"
          trend={data.projected_revenue_opportunity >= 0 ? 'up' : 'down'}
          accent
          active={active === 'opportunity'}
          onClick={() => toggle('opportunity')}
        />
      </div>
      <DrillDownDrawer metric={active} data={data} />
    </div>
  );
}

// ── Section 2: Rate Calendar Grid ─────────────────────────────────────────────

function RateCalendarGrid({
  calendar,
  onCellClick,
  expandedCell,
  pricingData,
}: {
  calendar: RoomCalendarResponse;
  onCellClick: (rtCode: string, dateIdx: number) => void;
  expandedCell: { code: string; dayIdx: number } | null;
  pricingData: RoomPricingResponse;
}) {
  if (calendar.room_types.length === 0) {
    return <div style={{ color: '#57606a', fontSize: 13 }}>No calendar data available.</div>;
  }

  const sortedTypes = [...calendar.room_types].sort((a, b) => a.room_rank - b.room_rank);
  const dates = sortedTypes[0]?.days ?? [];
  const MAX_VISIBLE_COLS = 14;
  const visibleDates = dates.slice(0, MAX_VISIBLE_COLS);

  const findCurrentPrice = (code: string): number => {
    const rec = pricingData.recommendations.find(r => r.code === code);
    return rec?.current_price ?? 0;
  };

  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 12,
          minWidth: 600,
        }}
      >
        <thead>
          <tr style={{ background: '#f7f8fa' }}>
            <th
              style={{
                textAlign: 'left',
                padding: '8px 12px',
                borderBottom: '1px solid #e5e7eb',
                position: 'sticky',
                left: 0,
                background: '#f7f8fa',
                zIndex: 1,
                minWidth: 130,
                fontWeight: 600,
                color: '#57606a',
                fontSize: 11,
                textTransform: 'uppercase',
              }}
            >
              Room Type
            </th>
            {visibleDates.map((day) => {
              const d = new Date(day.date);
              const label = `${d.getMonth() + 1}/${d.getDate()}`;
              const dow = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'][d.getDay()];
              return (
                <th
                  key={day.date}
                  style={{
                    padding: '6px 8px',
                    textAlign: 'center',
                    borderBottom: '1px solid #e5e7eb',
                    fontWeight: 600,
                    color: '#57606a',
                    fontSize: 10,
                    minWidth: 72,
                  }}
                >
                  <div>{label}</div>
                  <div style={{ color: '#8b949e', fontWeight: 400 }}>{dow}</div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sortedTypes.map((rt) => (
            <>
              <tr key={rt.code}>
                <td
                  style={{
                    padding: '8px 12px',
                    borderBottom: '1px solid #e5e7eb',
                    position: 'sticky',
                    left: 0,
                    background: '#fff',
                    zIndex: 1,
                    fontWeight: 600,
                    color: '#1f2328',
                    fontSize: 12,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {rt.display_name}
                  <div style={{ fontSize: 10, color: '#8b949e', fontWeight: 400 }}>
                    floor ${findCurrentPrice(rt.code).toFixed(0)}
                  </div>
                </td>
                {rt.days.slice(0, MAX_VISIBLE_COLS).map((day, dayIdx) => {
                  const isExpanded =
                    expandedCell?.code === rt.code && expandedCell?.dayIdx === dayIdx;
                  const pctChange = day.price_change_pct;
                  return (
                    <td
                      key={day.date}
                      onClick={() => onCellClick(rt.code, dayIdx)}
                      style={{
                        padding: '6px 8px',
                        borderBottom: '1px solid #e5e7eb',
                        textAlign: 'center',
                        background: isExpanded
                          ? '#eff6ff'
                          : demandCellColor(day.forecast_occupancy_pct),
                        cursor: 'pointer',
                        outline: isExpanded ? '2px solid #3b82d4' : undefined,
                      }}
                    >
                      <div style={{ fontWeight: 700, fontSize: 13, color: '#1f2328' }}>
                        ${day.recommended_price.toFixed(0)}
                      </div>
                      <div
                        style={{
                          fontSize: 10,
                          color: pctChange >= 0 ? '#16a34a' : '#dc2626',
                          fontWeight: 600,
                        }}
                      >
                        {fmtPct(pctChange)}
                      </div>
                      <div
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          background: confidenceDot(day.confidence),
                          margin: '2px auto 0',
                        }}
                      />
                    </td>
                  );
                })}
              </tr>
              {expandedCell?.code === rt.code && (
                <tr key={`${rt.code}-expand`}>
                  <td
                    colSpan={MAX_VISIBLE_COLS + 1}
                    style={{
                      padding: '12px 16px',
                      background: '#eff6ff',
                      borderBottom: '1px solid #bfdbfe',
                    }}
                  >
                    {(() => {
                      const day = rt.days[expandedCell.dayIdx];
                      if (!day) return null;
                      return (
                        <div style={{ fontSize: 12, color: '#1f2328' }}>
                          <strong>{rt.display_name}</strong> — {day.date} &nbsp;·&nbsp;
                          Forecast occ: {day.forecast_occupancy_pct.toFixed(1)}% &nbsp;·&nbsp;
                          Recommended: <strong>${day.recommended_price.toFixed(0)}</strong> &nbsp;·&nbsp;
                          Current: ${day.current_price.toFixed(0)} &nbsp;·&nbsp;
                          Change: <span style={{ color: day.price_change_pct >= 0 ? '#16a34a' : '#dc2626', fontWeight: 600 }}>
                            {fmtPct(day.price_change_pct)}
                          </span> &nbsp;·&nbsp;
                          Status:{' '}
                          <span
                            style={{
                              padding: '1px 6px',
                              borderRadius: 3,
                              fontSize: 11,
                              fontWeight: 600,
                              ...protectionBadge(day.protection_status),
                            }}
                          >
                            {day.protection_status}
                          </span>
                        </div>
                      );
                    })()}
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Section 3: Inventory Heat Map ─────────────────────────────────────────────

function InventoryHeatMap({ inventory }: { inventory: InventoryResponse }) {
  const sorted = [...inventory.room_types].sort((a, b) => a.room_rank - b.room_rank);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {sorted.map((rt) => {
        const soldPct = (rt.sold / rt.inventory_count) * 100;
        const barColor = occupancyBarColor(soldPct);
        const badge = protectionBadge(rt.protection_status);
        return (
          <div
            key={rt.code}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '8px 12px',
              background: '#f7f8fa',
              borderRadius: 6,
              border: '1px solid #e5e7eb',
            }}
          >
            <div style={{ minWidth: 130, fontWeight: 600, fontSize: 12, color: '#1f2328' }}>
              {rt.display_name}
            </div>

            {/* Inventory bar */}
            <div style={{ flex: 1, minWidth: 80 }}>
              <div
                style={{
                  height: 8,
                  background: '#e5e7eb',
                  borderRadius: 4,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: `${soldPct}%`,
                    height: '100%',
                    background: barColor,
                    borderRadius: 4,
                    transition: 'width 0.3s',
                  }}
                />
              </div>
              <div style={{ fontSize: 10, color: '#57606a', marginTop: 2 }}>
                {rt.sold} sold / {rt.remaining} avail ({soldPct.toFixed(0)}%)
              </div>
            </div>

            {/* Protection badge */}
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                padding: '2px 7px',
                borderRadius: 4,
                ...badge,
                whiteSpace: 'nowrap',
              }}
            >
              {rt.protection_status}
            </span>

            {/* Upgrade badge */}
            {rt.upgrade_eligible && (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  padding: '2px 7px',
                  borderRadius: 4,
                  background: '#f0f0ff',
                  color: '#5145cd',
                  whiteSpace: 'nowrap',
                }}
              >
                ↑ upgrade
              </span>
            )}

            {/* Revenue at risk */}
            <div style={{ fontSize: 11, color: '#57606a', whiteSpace: 'nowrap', minWidth: 60, textAlign: 'right' }}>
              {fmtMoney(rt.revenue_at_risk)} at risk
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Section 4: Room Type Detail Accordion ─────────────────────────────────────

function RoomTypeDetailAccordion({
  recommendations,
}: {
  recommendations: RoomTypePricingRecommendation[];
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const sorted = [...recommendations].sort((a, b) => a.room_rank - b.room_rank);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {sorted.map((rec) => {
        const isOpen = expanded === rec.code;
        const priceBadge = protectionBadge(rec.protection_status);
        return (
          <div
            key={rec.code}
            style={{
              border: '1px solid #e5e7eb',
              borderRadius: 6,
              overflow: 'hidden',
            }}
          >
            <div
              onClick={() => setExpanded(isOpen ? null : rec.code)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '10px 14px',
                background: isOpen ? '#f0f7ff' : '#f7f8fa',
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              <span style={{ fontSize: 11, color: '#8b949e', minWidth: 20 }}>{rec.room_rank}</span>
              <span style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>{rec.display_name}</span>
              <span style={{ fontSize: 12, color: '#57606a' }}>
                ${rec.current_price.toFixed(0)} → <strong>${rec.recommended_price.toFixed(0)}</strong>
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: rec.price_change_pct >= 0 ? '#16a34a' : '#dc2626',
                }}
              >
                {fmtPct(rec.price_change_pct)}
              </span>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: confidenceDot(rec.confidence),
                }}
              />
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  padding: '1px 6px',
                  borderRadius: 3,
                  ...priceBadge,
                }}
              >
                {rec.protection_status}
              </span>
              <span style={{ fontSize: 12, color: '#8b949e' }}>{isOpen ? '▲' : '▼'}</span>
            </div>

            {isOpen && (
              <div style={{ padding: '14px 16px', background: '#fff', borderTop: '1px solid #e5e7eb' }}>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: 16,
                  }}
                >
                  {/* Multipliers */}
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: '#57606a', marginBottom: 6, textTransform: 'uppercase' }}>
                      Pricing Multipliers
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Demand</span>
                        <strong
                          style={{ color: rec.demand_multiplier > 1 ? '#16a34a' : rec.demand_multiplier < 1 ? '#dc2626' : '#6b7280' }}
                        >
                          ×{rec.demand_multiplier.toFixed(2)}
                        </strong>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Scarcity</span>
                        <strong
                          style={{ color: rec.scarcity_multiplier > 1 ? '#16a34a' : rec.scarcity_multiplier < 1 ? '#dc2626' : '#6b7280' }}
                        >
                          ×{rec.scarcity_multiplier.toFixed(2)}
                        </strong>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Competitor</span>
                        <strong
                          style={{ color: rec.competitor_multiplier > 1 ? '#16a34a' : rec.competitor_multiplier < 1 ? '#dc2626' : '#6b7280' }}
                        >
                          ×{rec.competitor_multiplier.toFixed(2)}
                        </strong>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Premium Factor</span>
                        <strong style={{ color: '#6b7280' }}>×{rec.premium_factor.toFixed(2)}</strong>
                      </div>
                    </div>
                  </div>

                  {/* Reason codes & factors */}
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: '#57606a', marginBottom: 6, textTransform: 'uppercase' }}>
                      Reason Codes
                    </div>
                    {rec.reason_codes.length > 0 ? (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {rec.reason_codes.map((rc) => (
                          <span
                            key={rc}
                            style={{
                              background: '#f0f5ff',
                              color: '#3b82d4',
                              padding: '2px 7px',
                              borderRadius: 4,
                              fontSize: 11,
                              fontWeight: 500,
                            }}
                          >
                            {rc.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span style={{ fontSize: 12, color: '#8b949e' }}>No active signals</span>
                    )}
                    {rec.supporting_factors.length > 0 && (
                      <ul style={{ margin: '6px 0 0', paddingLeft: 16, fontSize: 12, color: '#57606a' }}>
                        {rec.supporting_factors.map((f) => (
                          <li key={f}>{f}</li>
                        ))}
                      </ul>
                    )}
                  </div>

                  {/* Guardrails & LOS */}
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: '#57606a', marginBottom: 6, textTransform: 'uppercase' }}>
                      Controls Applied
                    </div>
                    {rec.guardrails_applied.length > 0 ? (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {rec.guardrails_applied.map((g) => (
                          <span
                            key={g}
                            style={{
                              background: '#fff7e6',
                              color: '#d46b08',
                              padding: '2px 7px',
                              borderRadius: 4,
                              fontSize: 11,
                              fontWeight: 500,
                            }}
                          >
                            {g.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span style={{ fontSize: 12, color: '#8b949e' }}>No guardrails triggered</span>
                    )}
                    {rec.los_recommendation && (
                      <div style={{ marginTop: 8 }}>
                        <span style={{ fontSize: 11, color: '#57606a' }}>LOS: </span>
                        <span
                          style={{
                            background: '#fff1f0',
                            color: '#cf1322',
                            padding: '2px 7px',
                            borderRadius: 4,
                            fontSize: 11,
                            fontWeight: 600,
                          }}
                        >
                          {rec.los_recommendation.replace(/_/g, ' ')}
                        </span>
                      </div>
                    )}
                    {rec.upgrade_recommendation && (
                      <div style={{ marginTop: 8, fontSize: 12, color: '#5145cd' }}>
                        ↑ {rec.upgrade_recommendation}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function RoomPricingPanel({ hotelId }: RoomPricingPanelProps) {
  const [expandedCell, setExpandedCell] = useState<{ code: string; dayIdx: number } | null>(null);

  const pricingState = useRoomPricing(hotelId, 14);
  const calendarState = useRoomCalendar(hotelId, 14);
  const inventoryState = useRoomInventory(hotelId);

  const handleCellClick = (code: string, dayIdx: number) => {
    setExpandedCell((prev) =>
      prev?.code === code && prev?.dayIdx === dayIdx ? null : { code, dayIdx }
    );
  };

  if (pricingState.status === 'loading') {
    return (
      <SectionCard title="Dynamic Room Pricing & Inventory">
        <div style={{ padding: '40px 0', textAlign: 'center', color: '#57606a', fontSize: 13 }}>
          Loading room pricing data…
        </div>
      </SectionCard>
    );
  }

  if (pricingState.status === 'error') {
    return (
      <SectionCard title="Dynamic Room Pricing & Inventory">
        <div style={{ padding: '20px 0', color: '#dc2626', fontSize: 13 }}>
          Room pricing unavailable: {pricingState.error}
        </div>
      </SectionCard>
    );
  }

  if (pricingState.status !== 'success') return null;

  const pricing = pricingState.data;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* ── Section 1: Projected KPI Strip ───────────────────────────── */}
      <SectionCard
        title="Room Revenue Projections"
        action={
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: '#16a34a',
              background: '#f0fdf4',
              padding: '2px 8px',
              borderRadius: 4,
              letterSpacing: '0.04em',
            }}
          >
            Rule-Based Engine
          </span>
        }
      >
        <ProjectedKpiStrip data={pricing} />
      </SectionCard>

      {/* ── Section 2: Rate Calendar Grid ────────────────────────────── */}
      <SectionCard
        title="14-Day Rate Calendar"
        action={
          <span style={{ fontSize: 11, color: '#57606a' }}>
            {pricing.forecast_occupancy_pct.toFixed(1)}% forecast occ · compset ${pricing.competitor_adr.toFixed(0)}
          </span>
        }
      >
        {calendarState.status === 'loading' && (
          <div style={{ padding: '20px 0', textAlign: 'center', color: '#57606a', fontSize: 13 }}>
            Loading calendar…
          </div>
        )}
        {calendarState.status === 'success' && (
          <RateCalendarGrid
            calendar={calendarState.data}
            onCellClick={handleCellClick}
            expandedCell={expandedCell}
            pricingData={pricing}
          />
        )}
        {calendarState.status === 'error' && (
          <div style={{ color: '#dc2626', fontSize: 13 }}>
            Calendar unavailable: {calendarState.error}
          </div>
        )}
      </SectionCard>

      {/* ── Section 3: Inventory Heat Map ────────────────────────────── */}
      <SectionCard title="Inventory Status">
        {inventoryState.status === 'loading' && (
          <div style={{ padding: '20px 0', textAlign: 'center', color: '#57606a', fontSize: 13 }}>
            Loading inventory…
          </div>
        )}
        {inventoryState.status === 'success' && (
          <>
            <div style={{ display: 'flex', gap: 20, marginBottom: 14, fontSize: 12, color: '#57606a' }}>
              <span>Total rooms: <strong style={{ color: '#1f2328' }}>{inventoryState.data.total_rooms}</strong></span>
              <span>Sold: <strong style={{ color: '#1f2328' }}>{inventoryState.data.total_sold}</strong></span>
              <span>Available: <strong style={{ color: '#1f2328' }}>{inventoryState.data.total_available}</strong></span>
              <span>Overall occ: <strong style={{ color: '#1f2328' }}>{inventoryState.data.overall_occupancy_pct.toFixed(1)}%</strong></span>
            </div>
            <InventoryHeatMap inventory={inventoryState.data} />
          </>
        )}
        {inventoryState.status === 'error' && (
          <div style={{ color: '#dc2626', fontSize: 13 }}>
            Inventory unavailable: {inventoryState.error}
          </div>
        )}
      </SectionCard>

      {/* ── Section 4: Room Type Detail Accordion ────────────────────── */}
      <SectionCard
        title="Room Type Pricing Detail"
        action={
          <span style={{ fontSize: 11, color: '#57606a' }}>
            Click a row to expand
          </span>
        }
      >
        <RoomTypeDetailAccordion recommendations={pricing.recommendations} />
      </SectionCard>
    </div>
  );
}
