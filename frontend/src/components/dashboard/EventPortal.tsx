/**
 * EventPortal
 *
 * Full-screen modal for adding and deleting demand events for the selected hotel.
 *
 * Features:
 *  - All 8 event types with icons
 *  - All DemandEvent fields (name, type, dates, distance, attendance, impact, confidence, status)
 *  - Inline validation (end_date ≥ start_date, required fields)
 *  - Slider for impact_strength and confidence with live labels
 *  - Submits POST /hotels/{id}/events, then calls onSaved() to trigger refetch
 *  - List of existing events with delete (×) button per row
 *  - Non-fatal: submit errors shown inline, modal stays open for correction
 */
import { useState, useCallback } from 'react';
import { format, parseISO } from 'date-fns';
import { eventsApi, type CreateEventPayload } from '@/services/api';
import type { DemandEvent } from '@/types/api';

// ── Constants ─────────────────────────────────────────────────────────────────

const EVENT_TYPES = [
  { value: 'convention',         label: 'Convention',         icon: '🏛' },
  { value: 'concert',            label: 'Concert',            icon: '🎵' },
  { value: 'sports',             label: 'Sports',             icon: '🏟' },
  { value: 'local_festival',     label: 'Local Festival',     icon: '🎪' },
  { value: 'holiday',            label: 'Holiday',            icon: '🎉' },
  { value: 'cruise_arrival',     label: 'Cruise Arrival',     icon: '🚢' },
  { value: 'weather_disruption', label: 'Weather Disruption', icon: '🌩' },
  { value: 'flight_disruption',  label: 'Flight Disruption',  icon: '✈' },
];

const today = new Date().toISOString().slice(0, 10);

function defaultForm(): CreateEventPayload {
  const start = today;
  const end = today;
  return {
    name: '',
    event_type: 'convention',
    start_date: start,
    end_date: end,
    distance_miles: 2.0,
    expected_attendance: 10000,
    impact_strength: 0.7,
    confidence: 0.8,
    status: 'active',
  };
}

// ── Shared form field styles ──────────────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '7px 10px',
  fontSize: 13,
  border: '1px solid #d1d5db',
  borderRadius: 6,
  background: '#fff',
  color: '#1f2328',
  boxSizing: 'border-box',
};

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  color: '#57606a',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  display: 'block',
  marginBottom: 4,
};

function FieldRow({ label, children, error }: { label: string; children: React.ReactNode; error?: string }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={labelStyle}>{label}</label>
      {children}
      {error && <div style={{ fontSize: 11, color: '#dc2626', marginTop: 3 }}>{error}</div>}
    </div>
  );
}

// ── Slider field ──────────────────────────────────────────────────────────────

function SliderField({
  label, value, min, max, step, onChange, format: fmt,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format: (v: number) => string;
}) {
  return (
    <FieldRow label={label}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{ flex: 1 }}
        />
        <span style={{
          fontSize: 13,
          fontWeight: 700,
          color: '#1d4ed8',
          minWidth: 38,
          textAlign: 'right',
        }}>
          {fmt(value)}
        </span>
      </div>
    </FieldRow>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface EventPortalProps {
  hotelId: string;
  hotelName: string;
  existingEvents: DemandEvent[];
  onClose: () => void;
  onSaved: () => void;
}

export function EventPortal({
  hotelId,
  hotelName,
  existingEvents,
  onClose,
  onSaved,
}: EventPortalProps) {
  const [form, setForm] = useState<CreateEventPayload>(defaultForm);
  const [errors, setErrors] = useState<Partial<Record<keyof CreateEventPayload, string>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'add' | 'manage'>('add');

  const set = useCallback(<K extends keyof CreateEventPayload>(
    key: K, value: CreateEventPayload[K]
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  }, []);

  // ── Validation ────────────────────────────────────────────────────────────

  function validate(): boolean {
    const errs: Partial<Record<keyof CreateEventPayload, string>> = {};
    if (!form.name.trim()) errs.name = 'Event name is required';
    if (!form.start_date) errs.start_date = 'Start date is required';
    if (!form.end_date) errs.end_date = 'End date is required';
    if (form.end_date < form.start_date) errs.end_date = 'End date must be on or after start date';
    if (form.distance_miles < 0) errs.distance_miles = 'Distance must be 0 or more';
    if (form.expected_attendance < 0) errs.expected_attendance = 'Attendance must be 0 or more';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true);
    setSubmitError(null);
    try {
      await eventsApi.create(hotelId, form);
      setForm(defaultForm());
      onSaved();
      setActiveTab('manage');
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to save event');
    } finally {
      setSaving(false);
    }
  }

  // ── Delete ────────────────────────────────────────────────────────────────

  async function handleDelete(eventId: string) {
    setDeletingId(eventId);
    try {
      await eventsApi.delete(hotelId, eventId);
      onSaved();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete event');
    } finally {
      setDeletingId(null);
    }
  }

  const selectedType = EVENT_TYPES.find((t) => t.value === form.event_type)!;

  return (
    /* ── Backdrop ─────────────────────────────────────────────────────────── */
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15,23,42,0.6)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* ── Modal panel ───────────────────────────────────────────────────── */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          width: '100%',
          maxWidth: 580,
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        }}
      >
        {/* Header */}
        <div
          style={{
            background: '#0f172a',
            padding: '16px 20px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexShrink: 0,
          }}
        >
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9' }}>
              Demand Event Portal
            </div>
            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{hotelName}</div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: '1px solid #334155',
              color: '#94a3b8',
              borderRadius: 6,
              width: 30,
              height: 30,
              cursor: 'pointer',
              fontSize: 16,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            ×
          </button>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid #e5e7eb', flexShrink: 0 }}>
          {(['add', 'manage'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                flex: 1,
                padding: '10px 0',
                fontSize: 13,
                fontWeight: 600,
                border: 'none',
                borderBottom: activeTab === tab ? '2px solid #3b82d4' : '2px solid transparent',
                background: activeTab === tab ? '#eff6ff' : '#fff',
                color: activeTab === tab ? '#1d4ed8' : '#57606a',
                cursor: 'pointer',
              }}
            >
              {tab === 'add' ? '+ Add New Event' : `Manage Events (${existingEvents.length})`}
            </button>
          ))}
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>

          {/* ── ADD TAB ──────────────────────────────────────────────── */}
          {activeTab === 'add' && (
            <form onSubmit={handleSubmit}>

              {/* Event Name */}
              <FieldRow label="Event Name *" error={errors.name}>
                <input
                  style={{ ...inputStyle, borderColor: errors.name ? '#dc2626' : '#d1d5db' }}
                  type="text"
                  placeholder="e.g. City Music Festival"
                  value={form.name}
                  onChange={(e) => set('name', e.target.value)}
                  maxLength={200}
                />
              </FieldRow>

              {/* Event Type */}
              <FieldRow label="Event Type *">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
                  {EVENT_TYPES.map((t) => (
                    <button
                      key={t.value}
                      type="button"
                      onClick={() => set('event_type', t.value)}
                      style={{
                        padding: '8px 4px',
                        fontSize: 11,
                        fontWeight: 600,
                        borderRadius: 6,
                        border: form.event_type === t.value
                          ? '2px solid #3b82d4'
                          : '1px solid #e5e7eb',
                        background: form.event_type === t.value ? '#eff6ff' : '#f7f8fa',
                        color: form.event_type === t.value ? '#1d4ed8' : '#57606a',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: 3,
                      }}
                    >
                      <span style={{ fontSize: 18 }}>{t.icon}</span>
                      <span>{t.label}</span>
                    </button>
                  ))}
                </div>
              </FieldRow>

              {/* Date range */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <FieldRow label="Start Date *" error={errors.start_date}>
                  <input
                    style={{ ...inputStyle, borderColor: errors.start_date ? '#dc2626' : '#d1d5db' }}
                    type="date"
                    value={form.start_date}
                    onChange={(e) => {
                      set('start_date', e.target.value);
                      if (form.end_date < e.target.value) set('end_date', e.target.value);
                    }}
                  />
                </FieldRow>
                <FieldRow label="End Date *" error={errors.end_date}>
                  <input
                    style={{ ...inputStyle, borderColor: errors.end_date ? '#dc2626' : '#d1d5db' }}
                    type="date"
                    value={form.end_date}
                    min={form.start_date}
                    onChange={(e) => set('end_date', e.target.value)}
                  />
                </FieldRow>
              </div>

              {/* Distance + Attendance */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <FieldRow label="Distance from Hotel (miles)" error={errors.distance_miles}>
                  <input
                    style={inputStyle}
                    type="number"
                    min={0}
                    max={500}
                    step={0.1}
                    value={form.distance_miles}
                    onChange={(e) => set('distance_miles', Number(e.target.value))}
                  />
                </FieldRow>
                <FieldRow label="Expected Attendance" error={errors.expected_attendance}>
                  <input
                    style={inputStyle}
                    type="number"
                    min={0}
                    step={100}
                    value={form.expected_attendance}
                    onChange={(e) => set('expected_attendance', Number(e.target.value))}
                  />
                </FieldRow>
              </div>

              {/* Impact strength slider */}
              <SliderField
                label={`Impact Strength — ${selectedType.icon} ${selectedType.label}`}
                value={form.impact_strength}
                min={0}
                max={1}
                step={0.05}
                onChange={(v) => set('impact_strength', v)}
                format={(v) => `${Math.round(v * 100)}%`}
              />

              {/* Confidence slider */}
              <SliderField
                label="Forecast Confidence"
                value={form.confidence}
                min={0}
                max={1}
                step={0.05}
                onChange={(v) => set('confidence', v)}
                format={(v) =>
                  v >= 0.85 ? `${Math.round(v * 100)}% (High)` :
                  v >= 0.55 ? `${Math.round(v * 100)}% (Med)` :
                              `${Math.round(v * 100)}% (Low)`}
              />

              {/* Status */}
              <FieldRow label="Status">
                <select
                  style={inputStyle}
                  value={form.status}
                  onChange={(e) => set('status', e.target.value)}
                >
                  <option value="active">Active</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="completed">Completed</option>
                </select>
              </FieldRow>

              {/* Submit error */}
              {submitError && (
                <div style={{
                  background: '#fee2e2',
                  border: '1px solid #fca5a5',
                  borderRadius: 6,
                  padding: '8px 12px',
                  fontSize: 13,
                  color: '#991b1b',
                  marginBottom: 14,
                }}>
                  {submitError}
                </div>
              )}

              {/* Submit button */}
              <button
                type="submit"
                disabled={saving}
                style={{
                  width: '100%',
                  padding: '10px 0',
                  fontSize: 14,
                  fontWeight: 700,
                  borderRadius: 7,
                  border: 'none',
                  background: saving ? '#93c5fd' : '#3b82d4',
                  color: '#fff',
                  cursor: saving ? 'not-allowed' : 'pointer',
                }}
              >
                {saving ? 'Saving…' : `${selectedType.icon} Add ${selectedType.label} Event`}
              </button>

              <div style={{ fontSize: 11, color: '#8b949e', textAlign: 'center', marginTop: 8 }}>
                Event will appear in Demand Signals and influence the adjusted forecast immediately.
              </div>
            </form>
          )}

          {/* ── MANAGE TAB ───────────────────────────────────────────── */}
          {activeTab === 'manage' && (
            <div>
              {existingEvents.length === 0 ? (
                <div style={{ textAlign: 'center', color: '#57606a', fontSize: 13, padding: '24px 0' }}>
                  No demand events yet. Add one using the "Add New Event" tab.
                </div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr>
                      {['Event', 'Type', 'Dates', 'Impact', 'Conf.', ''].map((h) => (
                        <th
                          key={h}
                          style={{
                            textAlign: 'left',
                            padding: '6px 8px',
                            borderBottom: '2px solid #e5e7eb',
                            fontSize: 10,
                            fontWeight: 700,
                            color: '#57606a',
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
                    {existingEvents.map((ev) => {
                      const meta = EVENT_TYPES.find((t) => t.value === ev.event_type);
                      const isDeleting = deletingId === ev.id;
                      const isNeg = ev.event_type === 'weather_disruption' || ev.event_type === 'flight_disruption';
                      return (
                        <tr
                          key={ev.id}
                          style={{
                            borderBottom: '1px solid #f0f1f3',
                            background: isNeg ? '#fff5f5' : '#fff',
                            opacity: isDeleting ? 0.4 : 1,
                          }}
                        >
                          <td style={{ padding: '8px', fontWeight: 600, color: '#1f2328', maxWidth: 160 }}>
                            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {ev.name}
                            </div>
                          </td>
                          <td style={{ padding: '8px', whiteSpace: 'nowrap' }}>
                            {meta?.icon} {meta?.label ?? ev.event_type}
                          </td>
                          <td style={{ padding: '8px', color: '#57606a', whiteSpace: 'nowrap', fontSize: 11 }}>
                            {format(parseISO(ev.start_date), 'MMM d')}
                            {ev.start_date !== ev.end_date && ` – ${format(parseISO(ev.end_date), 'MMM d')}`}
                          </td>
                          <td style={{ padding: '8px' }}>
                            <div style={{
                              width: 40, height: 5, background: '#e5e7eb', borderRadius: 3, overflow: 'hidden'
                            }}>
                              <div style={{
                                width: `${ev.impact_strength * 100}%`,
                                height: '100%',
                                background: isNeg ? '#dc2626' : '#16a34a',
                                borderRadius: 3,
                              }} />
                            </div>
                          </td>
                          <td style={{ padding: '8px', fontSize: 11, color: '#57606a' }}>
                            {Math.round(ev.confidence * 100)}%
                          </td>
                          <td style={{ padding: '8px', textAlign: 'right' }}>
                            <button
                              onClick={() => handleDelete(ev.id)}
                              disabled={isDeleting}
                              title="Delete event"
                              style={{
                                background: 'none',
                                border: '1px solid #fca5a5',
                                color: '#dc2626',
                                borderRadius: 5,
                                padding: '2px 7px',
                                cursor: isDeleting ? 'not-allowed' : 'pointer',
                                fontSize: 13,
                                fontWeight: 700,
                              }}
                            >
                              {isDeleting ? '…' : '×'}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
