import { differenceInDays, format, parseISO } from 'date-fns';
import type { AdjustedForecastDay, DemandEvent } from '@/types/api';

// ── Props ─────────────────────────────────────────────────────────────────────

interface ExplainabilityPanelProps {
  adjustedDays: AdjustedForecastDay[];
  events: DemandEvent[];
  adjustmentModel?: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function confidenceLabel(c: number): string {
  if (c >= 0.85) return 'High';
  if (c >= 0.55) return 'Medium';
  return 'Low';
}

function confidenceColor(c: number): string {
  if (c >= 0.85) return '#166534';
  if (c >= 0.55) return '#92400e';
  return '#991b1b';
}

/** Build a natural-language sentence from an event and how it affects the hotel. */
function buildSentence(event: DemandEvent, daysUntil: number, upliftPts: number): string {
  const timing =
    daysUntil < 0
      ? 'currently ongoing'
      : daysUntil === 0
      ? 'starting today'
      : `begins in ${daysUntil} day${daysUntil !== 1 ? 's' : ''}`;

  const distText =
    event.distance_miles < 0.5
      ? 'on-site'
      : `${event.distance_miles.toFixed(1)} miles away`;

  const attendanceText =
    event.expected_attendance > 0
      ? ` Expected ${event.expected_attendance >= 1_000 ? `${Math.round(event.expected_attendance / 1_000)}k` : event.expected_attendance} attendees.`
      : '';

  const sign = upliftPts >= 0 ? '+' : '−';
  const direction = upliftPts >= 0 ? 'increase' : 'decrease';

  return (
    `${event.name} ${timing}. Located ${distText}.${attendanceText} ` +
    `Estimated occupancy ${direction} ${sign}${Math.abs(upliftPts).toFixed(1)}%.`
  );
}

// ── Single explanation row ────────────────────────────────────────────────────

interface ExplainRowProps {
  event: DemandEvent;
  daysUntil: number;
  maxUplift: number;
  netUplift: number;
}

function ExplainRow({ event, daysUntil, maxUplift, netUplift }: ExplainRowProps) {
  const isNegative = netUplift < 0;
  const barColor = isNegative ? '#ef4444' : '#3b82d4';
  const barPct = maxUplift > 0 ? Math.min(100, (Math.abs(netUplift) / Math.abs(maxUplift)) * 100) : 0;
  const conf = event.confidence;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        padding: '10px 12px',
        background: '#f7f8fa',
        borderRadius: 6,
        borderLeft: `3px solid ${isNegative ? '#ef4444' : '#3b82d4'}`,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#1f2328' }}>{event.name}</span>
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: isNegative ? '#991b1b' : '#166534',
            background: isNegative ? '#fee2e2' : '#dcfce7',
            padding: '1px 6px',
            borderRadius: 999,
            whiteSpace: 'nowrap',
          }}
        >
          {netUplift >= 0 ? '+' : '−'}{Math.abs(netUplift).toFixed(1)} occ pts
        </span>
      </div>

      {/* Natural-language sentence */}
      <p style={{ margin: 0, fontSize: 11, color: '#57606a', lineHeight: 1.5 }}>
        {buildSentence(event, daysUntil, netUplift)}
      </p>

      {/* Impact bar + confidence */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1, height: 3, background: '#e5e7eb', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ width: `${barPct}%`, height: '100%', background: barColor, borderRadius: 2 }} />
        </div>
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            color: confidenceColor(conf),
            whiteSpace: 'nowrap',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {confidenceLabel(conf)} confidence
        </span>
      </div>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export function ExplainabilityPanel({
  adjustedDays,
  events,
  adjustmentModel,
}: ExplainabilityPanelProps) {
  // Find the earliest date where any event affects the forecast
  const affectedDays = adjustedDays.filter((d) => d.influences.length > 0);

  if (affectedDays.length === 0) {
    return (
      <div
        style={{
          padding: '14px 16px',
          background: '#f7f8fa',
          borderRadius: 6,
          fontSize: 12,
          color: '#57606a',
        }}
      >
        No event-driven adjustments in the current forecast window.
      </div>
    );
  }

  // Build a deduplicated map: event_id → { event, maxUplift on any day }
  const eventMap = new Map<string, { event: DemandEvent; maxUplift: number }>();
  const eventById = new Map(events.map((e) => [e.id, e]));

  for (const day of affectedDays) {
    for (const inf of day.influences) {
      const event = eventById.get(inf.event_id);
      if (!event) continue;
      const existing = eventMap.get(inf.event_id);
      if (!existing || Math.abs(inf.uplift_points) > Math.abs(existing.maxUplift)) {
        eventMap.set(inf.event_id, { event, maxUplift: inf.uplift_points });
      }
    }
  }

  const rows = [...eventMap.values()];
  const absMax = Math.max(...rows.map((r) => Math.abs(r.maxUplift)), 1);
  const today = new Date();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#1f2328' }}>
          AI Adjustment Rationale
        </span>
        {adjustmentModel && (
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: '#3b5998',
              background: '#eef2ff',
              border: '1px solid #c7d2fe',
              padding: '1px 7px',
              borderRadius: 999,
            }}
          >
            {adjustmentModel}
          </span>
        )}
        <span style={{ fontSize: 10, color: '#57606a', marginLeft: 'auto' }}>
          {affectedDays.length} date{affectedDays.length !== 1 ? 's' : ''} affected
        </span>
      </div>

      {/* Per-event explanation rows, sorted: negative last */}
      {rows
        .sort((a, b) => b.maxUplift - a.maxUplift)
        .map(({ event, maxUplift }) => (
          <ExplainRow
            key={event.id}
            event={event}
            daysUntil={differenceInDays(parseISO(event.start_date), today)}
            maxUplift={absMax}
            netUplift={maxUplift}
          />
        ))}

      {/* Summary row */}
      <div
        style={{
          fontSize: 11,
          color: '#57606a',
          padding: '8px 12px',
          background: '#f0f4ff',
          borderRadius: 6,
          borderLeft: '3px solid #6366f1',
        }}
      >
        <strong>Summary:</strong>{' '}
        {rows.length} demand signal{rows.length !== 1 ? 's' : ''} are adjusting{' '}
        {affectedDays.length} forecast date{affectedDays.length !== 1 ? 's' : ''}. Dates shown are{' '}
        {format(parseISO(affectedDays[0].date), 'MMM d')}
        {affectedDays.length > 1 &&
          ` – ${format(parseISO(affectedDays[affectedDays.length - 1].date), 'MMM d')}`}
        .
      </div>
    </div>
  );
}
