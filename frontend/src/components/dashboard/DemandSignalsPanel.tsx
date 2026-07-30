import { format, parseISO, differenceInDays } from 'date-fns';
import type { DemandEvent } from '@/types/api';

// ── Type icons ────────────────────────────────────────────────────────────────

const EVENT_META: Record<string, { label: string; color: string; bg: string; icon: string }> = {
  convention:        { label: 'Convention',        color: '#1d4ed8', bg: '#dbeafe', icon: '🏛' },
  concert:           { label: 'Concert',           color: '#7c3aed', bg: '#ede9fe', icon: '🎵' },
  sports:            { label: 'Sports',            color: '#065f46', bg: '#d1fae5', icon: '🏟' },
  local_festival:    { label: 'Local Festival',    color: '#92400e', bg: '#fef3c7', icon: '🎪' },
  weather_disruption:{ label: 'Weather Disruption',color: '#9f1239', bg: '#ffe4e6', icon: '🌩' },
  flight_disruption: { label: 'Flight Disruption', color: '#7f1d1d', bg: '#fee2e2', icon: '✈' },
  holiday:           { label: 'Holiday',           color: '#0369a1', bg: '#e0f2fe', icon: '🎉' },
  cruise_arrival:    { label: 'Cruise Arrival',    color: '#0f766e', bg: '#ccfbf1', icon: '🚢' },
};

function meta(type: string) {
  return EVENT_META[type] ?? { label: type, color: '#4b5563', bg: '#f3f4f6', icon: '📌' };
}

// ── Confidence badge ──────────────────────────────────────────────────────────

function confidenceBadge(confidence: number) {
  const pct = confidence * 100;
  const { label, color, bg } =
    pct >= 85 ? { label: 'High',   color: '#166534', bg: '#dcfce7' } :
    pct >= 55 ? { label: 'Med',    color: '#92400e', bg: '#fef3c7' } :
               { label: 'Low',    color: '#991b1b', bg: '#fee2e2' };
  return (
    <span
      style={{
        fontSize: 9,
        fontWeight: 700,
        color,
        background: bg,
        padding: '1px 5px',
        borderRadius: 999,
        letterSpacing: '0.04em',
        textTransform: 'uppercase' as const,
      }}
    >
      {label} conf
    </span>
  );
}

// ── Uplift badge ──────────────────────────────────────────────────────────────

function impactBar({ impact_strength }: DemandEvent) {
  const pct = Math.round(impact_strength * 100);
  const color =
    pct >= 80 ? '#16a34a' :
    pct >= 50 ? '#d97706' :
    '#dc2626';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div
        style={{
          flex: 1,
          height: 4,
          background: '#e5e7eb',
          borderRadius: 2,
          overflow: 'hidden',
          minWidth: 60,
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: color,
            borderRadius: 2,
          }}
        />
      </div>
      <span style={{ fontSize: 11, color, fontWeight: 600, whiteSpace: 'nowrap' }}>
        {pct}%
      </span>
    </div>
  );
}

// ── Expected uplift chip ──────────────────────────────────────────────────────

function upliftChip(event: DemandEvent) {
  const isNegative = event.event_type === 'weather_disruption' || event.event_type === 'flight_disruption';
  // Rough display estimate based on impact_strength: strong → ~12pp, moderate → ~6pp
  const estPts = (event.impact_strength * 15 * event.confidence).toFixed(0);
  const sign = isNegative ? '−' : '+';
  const color = isNegative ? '#991b1b' : '#166534';
  const bg    = isNegative ? '#fee2e2' : '#dcfce7';
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        color,
        background: bg,
        padding: '2px 6px',
        borderRadius: 999,
      }}
    >
      {sign}{estPts} occ pts
    </span>
  );
}

// ── Single event card ─────────────────────────────────────────────────────────

function EventCard({ event }: { event: DemandEvent }) {
  const m = meta(event.event_type);
  const today = new Date();
  const startDate = parseISO(event.start_date);
  const endDate = parseISO(event.end_date);
  const daysUntil = differenceInDays(startDate, today);
  const isNegative = event.event_type === 'weather_disruption' || event.event_type === 'flight_disruption';

  const statusLabel =
    daysUntil < 0
      ? 'Ongoing'
      : daysUntil === 0
      ? 'Today'
      : `In ${daysUntil}d`;

  const statusColor =
    daysUntil < 0 ? '#15803d' :
    daysUntil <= 3 ? '#dc2626' :
    daysUntil <= 7 ? '#d97706' :
    '#57606a';

  return (
    <div
      style={{
        border: `1px solid ${isNegative ? '#fca5a5' : '#e5e7eb'}`,
        borderLeft: `3px solid ${m.color}`,
        borderRadius: 6,
        padding: '10px 12px',
        background: isNegative ? '#fff5f5' : '#fff',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          <span style={{ fontSize: 14 }}>{m.icon}</span>
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: '#1f2328',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {event.name}
          </span>
        </div>
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: statusColor,
            whiteSpace: 'nowrap',
            paddingTop: 1,
          }}
        >
          {statusLabel}
        </span>
      </div>

      {/* Type chip + confidence badge + dates */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: m.color,
            background: m.bg,
            padding: '2px 6px',
            borderRadius: 999,
          }}
        >
          {m.label}
        </span>
        {confidenceBadge(event.confidence)}
        <span style={{ fontSize: 11, color: '#57606a' }}>
          {format(startDate, 'MMM d')}
          {event.start_date !== event.end_date && ` – ${format(endDate, 'MMM d')}`}
        </span>
      </div>

      {/* Stats row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '4px 12px',
          fontSize: 11,
          color: '#57606a',
        }}
      >
        {event.expected_attendance > 0 && (
          <span>👥 {event.expected_attendance.toLocaleString()} attendees</span>
        )}
        <span>📍 {event.distance_miles.toFixed(1)} mi away</span>
      </div>

      {/* Impact bar + expected uplift chip */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
          <span style={{ fontSize: 10, color: '#57606a' }}>
            {isNegative ? 'Disruption Severity' : 'Impact Strength'}
          </span>
          {upliftChip(event)}
        </div>
        {impactBar(event)}
      </div>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

interface DemandSignalsPanelProps {
  events: DemandEvent[];
  loading?: boolean;
  onAddEvent?: () => void;
}

export function DemandSignalsPanel({ events, loading = false, onAddEvent }: DemandSignalsPanelProps) {
  if (loading) {
    return (
      <div style={{ padding: '20px 0', color: '#57606a', fontSize: 13, textAlign: 'center' }}>
        Loading demand signals…
      </div>
    );
  }

  // Sort: ongoing first, then by days until start
  const sorted = [...events].sort((a, b) => {
    const da = differenceInDays(parseISO(a.start_date), new Date());
    const db = differenceInDays(parseISO(b.start_date), new Date());
    return da - db;
  });

  const positive = sorted.filter(
    (e) => e.event_type !== 'weather_disruption' && e.event_type !== 'flight_disruption',
  );
  const negative = sorted.filter(
    (e) => e.event_type === 'weather_disruption' || e.event_type === 'flight_disruption',
  );

  if (events.length === 0) {
    return (
      <div
        style={{
          padding: '16px',
          color: '#57606a',
          fontSize: 13,
          textAlign: 'center',
          background: '#f7f8fa',
          borderRadius: 6,
        }}
      >
        No active or upcoming demand events found.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {onAddEvent && (
        <button
          onClick={onAddEvent}
          style={{
            width: '100%',
            padding: '8px 0',
            fontSize: 12,
            fontWeight: 700,
            borderRadius: 6,
            border: '1.5px dashed #3b82d4',
            background: '#eff6ff',
            color: '#1d4ed8',
            cursor: 'pointer',
          }}
        >
          + Add Demand Event
        </button>
      )}
      {positive.length > 0 && (
        <>
          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: '#57606a',
              textTransform: 'uppercase',
              letterSpacing: '0.07em',
              paddingBottom: 2,
              borderBottom: '1px solid #e5e7eb',
            }}
          >
            Demand Drivers ({positive.length})
          </div>
          {positive.map((e) => <EventCard key={e.id} event={e} />)}
        </>
      )}
      {negative.length > 0 && (
        <>
          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: '#9f1239',
              textTransform: 'uppercase',
              letterSpacing: '0.07em',
              paddingBottom: 2,
              borderBottom: '1px solid #fca5a5',
              marginTop: positive.length > 0 ? 4 : 0,
            }}
          >
            Disruptions ({negative.length})
          </div>
          {negative.map((e) => <EventCard key={e.id} event={e} />)}
        </>
      )}
    </div>
  );
}
