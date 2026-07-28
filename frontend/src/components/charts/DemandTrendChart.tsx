import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  type TooltipProps,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import type { AdjustedForecastDay, DemandPoint, ForecastPoint } from '@/types/api';

// ── Props ─────────────────────────────────────────────────────────────────────

export type ForecastMode = 'baseline' | 'adjusted';

interface DemandTrendChartProps {
  /** Historical demand/occupancy (last 30 days). */
  data: DemandPoint[];
  /** Baseline forecast (used when mode === 'baseline'). */
  forecast?: ForecastPoint[];
  /** Adjusted forecast (used when mode === 'adjusted'). */
  adjustedForecast?: AdjustedForecastDay[];
  /** Which forecast series to render in the forecast region. */
  forecastMode?: ForecastMode;
  /** Model name shown in the pill above the chart. */
  modelName?: string;
  /** Name of the event engine shown as secondary pill when adjusted. */
  adjustmentModel?: string;
  forecastLoading?: boolean;
}

// ── Unified chart row ─────────────────────────────────────────────────────────

interface ChartRow {
  date: string;
  isForecast: boolean;
  isEventAffected: boolean;

  // Historical
  demandIndex: number | null;
  occupancyPct: number | null;
  adr: number | null;

  // Active forecast series (baseline or adjusted)
  forecastOcc: number | null;
  forecastLower: number | null;
  forecastUpper: number | null;
  confidenceBase: number | null;
  confidenceBand: number | null;

  // Tooltip-only: richer event data for adjusted dates
  eventExplanations: string[];
  eventNames: string[];
  eventUplifts: number[];
  eventConfidences: number[];
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as ChartRow | undefined;
  if (!row) return null;

  const isAdjustedAndAffected = row.isForecast && row.isEventAffected;

  return (
    <div
      style={{
        background: '#fff',
        border: `1px solid ${isAdjustedAndAffected ? '#f59e0b' : row.isForecast ? '#6366f1' : '#e5e7eb'}`,
        borderRadius: 6,
        padding: '10px 14px',
        fontSize: 12,
        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        minWidth: 200,
        maxWidth: 300,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 6, color: '#1f2328', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {label}
        {row.isForecast && (
          <span style={{ fontSize: 10, fontWeight: 600, color: '#6366f1', background: '#eef2ff', padding: '1px 5px', borderRadius: 3 }}>
            FORECAST
          </span>
        )}
        {isAdjustedAndAffected && (
          <span style={{ fontSize: 10, fontWeight: 600, color: '#92400e', background: '#fef3c7', padding: '1px 5px', borderRadius: 3 }}>
            AI ADJUSTED
          </span>
        )}
      </div>

      {payload.map((entry) => {
        if (entry.value == null) return null;
        if (entry.name === '_confBase') return null;
        const displayName = entry.name === '_confBand' ? 'Confidence Band' : (legendLabels[entry.name ?? ''] ?? entry.name);
        const displayVal =
          entry.name === '_confBand'
            ? `${row.forecastLower?.toFixed(1)}% – ${row.forecastUpper?.toFixed(1)}%`
            : `${(entry.value as number).toFixed(1)}${(entry.name ?? '').includes('adr') ? '' : '%'}`;
        return (
          <div key={entry.name} style={{ color: entry.color ?? '#57606a', marginBottom: 2 }}>
            {displayName}: <strong>{displayVal}</strong>
          </div>
        );
      })}

      {/* Richer event breakdown: name + uplift + confidence */}
      {row.eventNames.length > 0 && (
        <div
          style={{
            marginTop: 8,
            paddingTop: 8,
            borderTop: '1px solid #e5e7eb',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          <div style={{ fontSize: 10, fontWeight: 700, color: '#57606a', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
            Event Signals
          </div>
          {row.eventNames.map((name, i) => {
            const uplift = row.eventUplifts[i];
            const conf = row.eventConfidences[i];
            const confLabel = conf >= 0.85 ? 'High' : conf >= 0.55 ? 'Med' : 'Low';
            const confColor = conf >= 0.85 ? '#166534' : conf >= 0.55 ? '#92400e' : '#991b1b';
            const isNeg = uplift < 0;
            return (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, color: '#1f2328', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {name}
                </span>
                <span style={{ fontSize: 10, fontWeight: 700, color: isNeg ? '#991b1b' : '#166534', whiteSpace: 'nowrap' }}>
                  {uplift >= 0 ? '+' : ''}{uplift.toFixed(1)}%
                </span>
                <span style={{ fontSize: 9, fontWeight: 700, color: confColor, background: conf >= 0.85 ? '#dcfce7' : conf >= 0.55 ? '#fef3c7' : '#fee2e2', padding: '1px 4px', borderRadius: 3 }}>
                  {confLabel}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Legend labels ─────────────────────────────────────────────────────────────

const legendLabels: Record<string, string> = {
  demandIndex: 'Demand Index',
  occupancyPct: 'Occupancy %',
  adr: 'ADR ($)',
  forecastOcc: 'Forecast Occ %',
  _confBand: 'Confidence Band',
  _confBase: '',
};

function legendFormatter(value: string) {
  return legendLabels[value] ?? value;
}

// ── Main component ────────────────────────────────────────────────────────────

export function DemandTrendChart({
  data,
  forecast,
  adjustedForecast,
  forecastMode = 'baseline',
  modelName,
  adjustmentModel,
  forecastLoading = false,
}: DemandTrendChartProps) {

  // ── Build historical rows ───────────────────────────────────────────────────
  const historicalRows: ChartRow[] = data.map((d) => ({
    date: format(parseISO(d.date), 'MMM d'),
    isForecast: false,
    isEventAffected: false,
    demandIndex: +d.demand_index.toFixed(1),
    occupancyPct: +d.occupancy_pct.toFixed(1),
    adr: +d.adr.toFixed(0),
    forecastOcc: null,
    forecastLower: null,
    forecastUpper: null,
    confidenceBase: null,
    confidenceBand: null,
    eventExplanations: [],
    eventNames: [],
    eventUplifts: [],
    eventConfidences: [],
  }));

  // ── Build forecast rows depending on mode ──────────────────────────────────
  let forecastRows: ChartRow[] = [];

  if (forecastMode === 'adjusted' && adjustedForecast && adjustedForecast.length > 0) {
    forecastRows = adjustedForecast.map((f) => {
      const isAffected = f.influences.length > 0;
      const occ = +f.adjusted.toFixed(1);
      const lo = +f.confidence_low.toFixed(1);
      const hi = +f.confidence_high.toFixed(1);
      return {
        date: format(parseISO(f.date), 'MMM d'),
        isForecast: true,
        isEventAffected: isAffected,
        demandIndex: null,
        occupancyPct: null,
        adr: null,
        forecastOcc: occ,
        forecastLower: lo,
        forecastUpper: hi,
        confidenceBase: lo,
        confidenceBand: +(hi - lo).toFixed(1),
        eventExplanations: f.influences.map((inf) => inf.explanation),
        eventNames: f.influences.map((inf) => inf.event_name),
        eventUplifts: f.influences.map((inf) => inf.uplift_points),
        eventConfidences: f.influences.map((inf) => inf.confidence),
      };
    });
  } else if (forecast && forecast.length > 0) {
    forecastRows = forecast.map((f) => ({
      date: format(parseISO(f.forecast_date), 'MMM d'),
      isForecast: true,
      isEventAffected: false,
      demandIndex: null,
      occupancyPct: null,
      adr: null,
      forecastOcc: +f.occupancy_pct.toFixed(1),
      forecastLower: +f.lower_bound.toFixed(1),
      forecastUpper: +f.upper_bound.toFixed(1),
      confidenceBase: +f.lower_bound.toFixed(1),
      confidenceBand: +(f.upper_bound - f.lower_bound).toFixed(1),
      eventExplanations: [],
      eventNames: [],
      eventUplifts: [],
      eventConfidences: [],
    }));
  }

  const chartData = [...historicalRows, ...forecastRows];
  const dividerLabel = forecastRows.length > 0 ? forecastRows[0].date : null;
  const hasForecast = forecastRows.length > 0;
  const isAdjustedMode = forecastMode === 'adjusted';

  // Dates with event influence: mark with reference lines
  const eventAffectedDates = forecastRows
    .filter((r) => r.isEventAffected)
    .map((r) => r.date);

  // Forecast line colour: amber when adjusted mode, indigo for baseline
  const forecastColor = isAdjustedMode ? '#d97706' : '#6366f1';
  const confGradId = isAdjustedMode ? 'confGradAdj' : 'confGrad';

  return (
    <div>
      {/* Model pill + mode indicator */}
      {hasForecast && modelName && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: 11, fontWeight: 600,
              color: '#6366f1', background: '#eef2ff',
              border: '1px solid #c7d2fe', padding: '2px 8px', borderRadius: 999,
            }}
          >
            {modelName}
          </span>
          {isAdjustedMode ? (
            <>
              <span
                style={{
                  fontSize: 11, fontWeight: 700,
                  color: '#fff', background: '#7c5cd8',
                  border: '1px solid #6d3fc7', padding: '2px 8px', borderRadius: 999,
                }}
              >
                ✦ AI Adjusted
              </span>
              <span
                style={{
                  fontSize: 11, fontWeight: 600,
                  color: '#92400e', background: '#fef3c7',
                  border: '1px solid #fbbf24', padding: '2px 8px', borderRadius: 999,
                }}
              >
                {eventAffectedDates.length} date{eventAffectedDates.length !== 1 ? 's' : ''} affected
              </span>
              {adjustmentModel && (
                <span style={{ fontSize: 11, color: '#57606a' }}>via {adjustmentModel}</span>
              )}
            </>
          ) : (
            <span style={{ fontSize: 11, color: '#57606a' }}>
              14-day forecast · 80% confidence band
            </span>
          )}
        </div>
      )}
      {forecastLoading && (
        <div style={{ fontSize: 11, color: '#57606a', marginBottom: 8 }}>Loading forecast…</div>
      )}

      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="demandGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82d4" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#3b82d4" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="occGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#7c5cd8" stopOpacity={0.12} />
              <stop offset="95%" stopColor="#7c5cd8" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="confGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.20} />
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0.05} />
            </linearGradient>
            <linearGradient id="confGradAdj" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#d97706" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#d97706" stopOpacity={0.05} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />

          <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#57606a' }} tickLine={false} axisLine={false} interval={4} />
          <YAxis
            yAxisId="left" tick={{ fontSize: 11, fill: '#57606a' }} tickLine={false} axisLine={false} domain={[0, 100]}
            label={{ value: 'Index / %', angle: -90, position: 'insideLeft', offset: 10, style: { fontSize: 10, fill: '#57606a' } }}
          />
          <YAxis
            yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: '#57606a' }} tickLine={false} axisLine={false}
            label={{ value: 'ADR ($)', angle: 90, position: 'insideRight', offset: 10, style: { fontSize: 10, fill: '#57606a' } }}
          />

          {/* Historical/forecast boundary */}
          {dividerLabel && (
            <ReferenceLine
              yAxisId="left" x={dividerLabel}
              stroke="#6366f1" strokeDasharray="4 3" strokeWidth={1.5}
              label={{ value: 'Today', position: 'insideTopLeft', fontSize: 10, fill: '#6366f1', fontWeight: 600 }}
            />
          )}

          {/* Highlight event-affected dates with a subtle amber reference line */}
          {isAdjustedMode && eventAffectedDates.map((d) => (
            <ReferenceLine
              key={d}
              yAxisId="left"
              x={d}
              stroke="#f59e0b"
              strokeWidth={8}
              strokeOpacity={0.15}
            />
          ))}

          <Tooltip content={<CustomTooltip />} />
          <Legend formatter={legendFormatter} wrapperStyle={{ fontSize: 12, paddingTop: 8 }} iconType="circle" iconSize={8} />

          {/* ── Historical series ──────────────────────────────────────── */}
          <Area yAxisId="left" type="monotone" dataKey="demandIndex" name="demandIndex"
            stroke="#3b82d4" strokeWidth={2} fill="url(#demandGrad)" dot={false} activeDot={{ r: 4 }} connectNulls={false} />
          <Area yAxisId="left" type="monotone" dataKey="occupancyPct" name="occupancyPct"
            stroke="#7c5cd8" strokeWidth={2} fill="url(#occGrad)" dot={false} activeDot={{ r: 4 }} connectNulls={false} />
          <Line yAxisId="right" type="monotone" dataKey="adr" name="adr"
            stroke="#f59e0b" strokeWidth={1.5} dot={false} activeDot={{ r: 4 }} strokeDasharray="4 2" connectNulls={false} />

          {/* ── Forecast: confidence band (stacked) ────────────────────── */}
          {hasForecast && (
            <>
              <Area yAxisId="left" type="monotone" dataKey="confidenceBase" name="_confBase"
                stroke="none" fill="none" legendType="none" dot={false} activeDot={false}
                connectNulls={false} stackId="conf" />
              <Area yAxisId="left" type="monotone" dataKey="confidenceBand" name="_confBand"
                stroke={forecastColor} strokeWidth={0.5} strokeDasharray="2 2"
                fill={`url(#${confGradId})`} dot={false} activeDot={false}
                connectNulls={false} stackId="conf" />
            </>
          )}

          {/* ── Forecast: point forecast line ──────────────────────────── */}
          {hasForecast && (
            <Line yAxisId="left" type="monotone" dataKey="forecastOcc" name="forecastOcc"
              stroke={forecastColor} strokeWidth={2} strokeDasharray="6 3"
              dot={{ fill: forecastColor, r: 2, strokeWidth: 0 }}
              activeDot={{ r: 4, stroke: forecastColor, strokeWidth: 2 }}
              connectNulls={false} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
