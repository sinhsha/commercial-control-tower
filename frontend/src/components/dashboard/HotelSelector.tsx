import { type ChangeEvent } from 'react';
import type { Hotel } from '@/types/api';

interface HotelSelectorProps {
  hotels: Hotel[];
  selectedId: string | null;
  onChange: (id: string) => void;
  loading: boolean;
}

export function HotelSelector({ hotels, selectedId, onChange, loading }: HotelSelectorProps) {
  const handleChange = (e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <label
        htmlFor="hotel-select"
        style={{ fontSize: 13, fontWeight: 500, color: '#57606a', whiteSpace: 'nowrap' }}
      >
        Property
      </label>
      <select
        id="hotel-select"
        value={selectedId ?? ''}
        onChange={handleChange}
        disabled={loading}
        style={{
          fontSize: 14,
          fontWeight: 500,
          color: '#1f2328',
          background: '#f7f8fa',
          border: '1px solid #d0d7de',
          borderRadius: 6,
          padding: '6px 32px 6px 10px',
          outline: 'none',
          cursor: loading ? 'not-allowed' : 'pointer',
          minWidth: 260,
          appearance: 'auto',
        }}
      >
        {hotels.length === 0 && (
          <option value="">Loading properties…</option>
        )}
        {hotels.map((h) => (
          <option key={h.id} value={h.id}>
            {h.name} — {h.city}
          </option>
        ))}
      </select>
    </div>
  );
}
