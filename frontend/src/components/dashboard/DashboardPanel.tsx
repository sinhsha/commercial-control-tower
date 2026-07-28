import { useState } from 'react';
import { format, parseISO } from 'date-fns';
import type { AdjustedForecastResponse, DashboardSummary, DemandEvent, ForecastResponse } from '@/types/api';
import { KpiCard } from '@/components/ui/KpiCard';
import { SectionCard } from '@/components/ui/SectionCard';
import { Badge } from '@/components/ui/Badge';
import { DemandTrendChart, type ForecastMode } from '@/components/charts/DemandTrendChart';
import { OccupancyBarChart } from '@/components/charts/OccupancyBarChart';
import { DemandSignalsPanel } from '@/components/dashboard/DemandSignalsPanel';
import { ExplainabilityPanel } from '@/components/dashboard/ExplainabilityPanel';

interface DashboardPanelProps {
  data: DashboardSummary;
  forecast?: ForecastResponse;
  forecastLoading?: boolean;
  adjustedForecast?: AdjustedForecastResponse;
  adjustedForecastLoading?: boolean;
  events?: DemandEvent[];
  eventsLoading?: boolean;
}

function occupancyBadge(pct: number): { label: string; variant: 'green' | 'yellow' | 'red' } {
  if (pct >= 85) return { label: 'High Occupancy', variant: 'green' };
  if (pct >= 60) return { label: 'Moderate', variant: 'yellow' };
  return { label: 'Low Occupancy', variant: 'red' };
}

function demandBadge(idx: number): { label: string; variant: 'green' | 'blue' | 'yellow' | 'red' } {
  if (idx >= 75) return { label: 'High Demand', variant: 'green' };
  if (idx >= 50) return { label: 'Normal Demand', variant: 'blue' };
  if (idx >= 30) return { label: 'Soft Demand', variant: 'yellow' };
  return { label: 'Weak Demand', variant: 'red' };
}

// ── Forecast mode toggle ──────────────────────────────────────────────────────

interface ForecastToggleProps {
  mode: ForecastMode;
  onChange: (mode: ForecastMode) => void;
  disabled?: boolean;
}

function ForecastToggle({ mode, onChange, disabled = false }: ForecastToggleProps) {
  const btn = (id: ForecastMode, label: string) => (
    <button
      onClick={() => onChange(id)}
      disabled={disabled}
      style={{
        padding: '5px 14px',
        fontSize: 12,
        fontWeight: 600,
        borderRadius: 5,
        border: mode === id ? '1.5px solid #6366f1' : '1px solid #d1d5db',
        background: mode === id ? '#eef2ff' : '#fff',
        color: mode === id ? '#4338ca' : '#57606a',
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'all 0.15s',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {label}
    </button>
  );
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ fontSize: 11, color: '#57606a', marginRight: 4 }}>Forecast:</span>
      {btn('baseline', 'Baseline')}
      {btn('adjusted', 'Event-Adjusted')}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function DashboardPanel({
  data,
  forecast,
  forecastLoading = false,
  adjustedForecast,
  adjustedForecastLoading = false,
  events = [],
  eventsLoading = false,
}: DashboardPanelProps) {
  const [forecastMode, setForecastMode] = useState<ForecastMode>('baseline');

  const occ = occupancyBadge(data.occupancy_pct);
  const demand = demandBadge(data.demand_index);
  const hasCompset = data.compset_adr != null;
  const rateVsCompset = hasCompset ? data.adr - data.compset_adr! : null;

  const hasEvents = events.length > 0;
  const activeAdjusted = forecastMode === 'adjusted' && adjustedForecast != null;
  const chartLoading = forecastMode === 'adjusted' ? adjustedForecastLoading : forecastLoading;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Header strip ───────────────────────────────────────────── */}
      <div
        style={{
          background: '#1e3a5f',
          borderRadius: 8,
          padding: '16px 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#fff' }}>{data.hotel_name}</div>
          <div style={{ fontSize: 12, color: '#93c5fd', marginTop: 2 }}>
            As of {format(parseISO(data.as_of_date), 'EEEE, MMMM d yyyy')}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <Badge variant={occ.variant}>{occ.label}</Badge>
          <Badge variant={demand.variant}>{demand.label}</Badge>
          {forecast != null && (
            <Badge variant="purple">{forecast.model_name}</Badge>
          )}
          {activeAdjusted && (
            <Badge variant="purple">✦ AI Adjusted</Badge>
          )}
          {hasEvents && (
            <Badge variant="yellow">{`${events.length} Demand Signal${events.length !== 1 ? 's' : ''}`}</Badge>
          )}
        </div>
      </div>

      {/* ── Primary KPI row ─────────────────────────────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 12,
        }}
      >
        <KpiCard
          label="Occupancy"
          value={`${data.occupancy_pct.toFixed(1)}%`}
          subtext={`${data.occupied_rooms} / ${data.total_rooms} rooms`}
          trend={data.occupancy_pct >= 70 ? 'up' : data.occupancy_pct >= 50 ? 'neutral' : 'down'}
          accent
        />
        <KpiCard
          label="ADR"
          value={`$${data.adr.toFixed(0)}`}
          subtext={
            rateVsCompset != null
              ? `${rateVsCompset >= 0 ? '+' : ''}$${rateVsCompset.toFixed(0)} vs compset`
              : 'Average Daily Rate'
          }
          trend={rateVsCompset != null ? (rateVsCompset >= 0 ? 'up' : 'down') : 'neutral'}
        />
        <KpiCard
          label="RevPAR"
          value={`$${data.revpar.toFixed(0)}`}
          subtext="Revenue Per Avail. Room"
          trend={data.revpar > data.adr * 0.65 ? 'up' : 'neutral'}
        />
        <KpiCard
          label="Available Rooms"
          value={data.available_rooms.toLocaleString()}
          subtext={`${data.total_rooms - data.available_rooms} occupied`}
          trend={data.available_rooms < data.total_rooms * 0.2 ? 'down' : 'neutral'}
        />
        <KpiCard
          label="Demand Index"
          value={data.demand_index.toFixed(0)}
          subtext="/ 100 scale"
          trend={data.demand_index >= 60 ? 'up' : data.demand_index >= 40 ? 'neutral' : 'down'}
        />
      </div>

      {/* ── AI Extension banner ──────────────────────────────────────── */}
      {(data.recommended_rate != null || data.ai_insight != null) && (
        <div
          style={{
            background: '#fef3c7',
            border: '1px solid #fbbf24',
            borderRadius: 8,
            padding: '12px 20px',
            fontSize: 13,
            color: '#78350f',
          }}
        >
          {data.recommended_rate != null && (
            <span>
              <strong>AI Recommended Rate:</strong> ${data.recommended_rate.toFixed(0)} &nbsp;
            </span>
          )}
          {data.ai_insight && <span>{data.ai_insight}</span>}
        </div>
      )}

      {/* ── Charts + Demand Signals two-column layout ────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) 280px',
          gap: 16,
          alignItems: 'start',
        }}
      >
        {/* Left: forecast chart column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <SectionCard
            title="30-Day Demand & Occupancy Trend"
            action={
              <ForecastToggle
                mode={forecastMode}
                onChange={setForecastMode}
                disabled={adjustedForecast == null && forecastMode === 'baseline'}
              />
            }
          >
            <DemandTrendChart
              data={data.demand_trend}
              forecast={forecast?.forecast}
              adjustedForecast={adjustedForecast?.days}
              forecastMode={forecastMode}
              modelName={
                activeAdjusted
                  ? adjustedForecast!.model
                  : forecast?.model_name
              }
              adjustmentModel={activeAdjusted ? adjustedForecast!.adjustment_model : undefined}
              forecastLoading={chartLoading}
            />
          </SectionCard>

          <SectionCard title="Occupancy by Day">
            <OccupancyBarChart data={data.demand_trend} />
          </SectionCard>

          {/* Explainability panel – only rendered when Event-Adjusted mode is active */}
          {activeAdjusted && adjustedForecast!.days.length > 0 && (
            <SectionCard title="AI Adjustment Rationale">
              <ExplainabilityPanel
                adjustedDays={adjustedForecast!.days}
                events={events}
                adjustmentModel={adjustedForecast!.adjustment_model}
              />
            </SectionCard>
          )}
        </div>

        {/* Right: demand signals panel */}
        <SectionCard title={`Demand Signals${hasEvents ? ` (${events.length})` : ''}`}>
          <DemandSignalsPanel events={events} loading={eventsLoading} />
        </SectionCard>
      </div>

      {/* ── Compset table ────────────────────────────────────────────── */}
      {hasCompset && (
        <SectionCard title="Rate Positioning">
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {['Metric', 'Your Hotel', 'Compset Avg', 'Variance'].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: 'left',
                      padding: '6px 12px',
                      borderBottom: '1px solid #e5e7eb',
                      color: '#57606a',
                      fontWeight: 600,
                      fontSize: 11,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ padding: '8px 12px', color: '#1f2328' }}>ADR</td>
                <td style={{ padding: '8px 12px', fontWeight: 600 }}>${data.adr.toFixed(2)}</td>
                <td style={{ padding: '8px 12px' }}>${data.compset_adr!.toFixed(2)}</td>
                <td
                  style={{
                    padding: '8px 12px',
                    fontWeight: 600,
                    color: rateVsCompset! >= 0 ? '#16a34a' : '#dc2626',
                  }}
                >
                  {rateVsCompset! >= 0 ? '+' : ''}${rateVsCompset!.toFixed(2)}
                </td>
              </tr>
            </tbody>
          </table>
        </SectionCard>
      )}

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <div style={{ fontSize: 11, color: '#8b949e', textAlign: 'right', marginTop: -8 }}>
        Data refreshes on page load
        {forecast != null
          ? ` · Forecast: ${forecast.model_name} · ${forecast.horizon}-day horizon`
          : ' · Forecasting & optimisation engines not yet connected'}
        {adjustedForecast != null && forecastMode === 'adjusted'
          ? ` · AI Adjusted via ${adjustedForecast.adjustment_model} (${adjustedForecast.days.filter((p) => p.influences.length > 0).length} dates)`
          : ''}
      </div>
    </div>
  );
}
