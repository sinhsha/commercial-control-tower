import { useState } from 'react';
import type {
  RoomPricingResponse,
  RoomCalendarResponse,
  InventoryResponse,
  RoomTypePricingRecommendation,
} from '@/types/api';
import { KpiCard } from '@/components/ui/KpiCard';
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

// ── Section 1: Projected KPI Strip ───────────────────────────────────────────

function ProjectedKpiStrip({ data }: { data: RoomPricingResponse }) {
  const currentAdr =
    data.recommendations.length > 0
      ? data.recommendations.reduce((s, r) => s + r.current_price, 0) /
        data.recommendations.length
      : data.competitor_adr;

  const adrDelta = data.projected_adr - currentAdr;
  const currentRevpar = currentAdr * data.projected_occupancy_pct / 100;
  const revparDelta = data.projected_revpar - currentRevpar;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: 12,
      }}
    >
      <KpiCard
        label="Projected ADR"
        value={`$${data.projected_adr.toFixed(0)}`}
        subtext={`${adrDelta >= 0 ? '+' : ''}$${adrDelta.toFixed(0)} vs current`}
        trend={adrDelta >= 0 ? 'up' : 'down'}
      />
      <KpiCard
        label="Projected RevPAR"
        value={`$${data.projected_revpar.toFixed(0)}`}
        subtext={`${revparDelta >= 0 ? '+' : ''}$${revparDelta.toFixed(0)} vs current`}
        trend={revparDelta >= 0 ? 'up' : 'down'}
      />
      <KpiCard
        label="Projected Revenue"
        value={fmtMoney(data.projected_room_revenue)}
        subtext="room revenue"
        trend="neutral"
      />
      <KpiCard
        label="Projected Occupancy"
        value={`${data.projected_occupancy_pct.toFixed(1)}%`}
        subtext={`Forecast: ${data.forecast_occupancy_pct.toFixed(1)}%`}
        trend={data.projected_occupancy_pct >= 70 ? 'up' : 'neutral'}
      />
      <KpiCard
        label="Revenue Opportunity"
        value={fmtMoney(data.projected_revenue_opportunity)}
        subtext="vs current pricing"
        trend={data.projected_revenue_opportunity >= 0 ? 'up' : 'down'}
        accent
      />
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
