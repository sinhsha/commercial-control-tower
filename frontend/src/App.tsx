import { useState, useEffect } from 'react';
import { useHotels } from '@/hooks/useHotels';
import { useDashboard } from '@/hooks/useDashboard';
import { useForecast } from '@/hooks/useForecast';
import { useAdjustedForecast } from '@/hooks/useAdjustedForecast';
import { useEvents } from '@/hooks/useEvents';
import { HotelSelector } from '@/components/dashboard/HotelSelector';
import { DashboardPanel } from '@/components/dashboard/DashboardPanel';
import { Spinner } from '@/components/ui/Spinner';

export default function App() {
  const hotelsState = useHotels();
  const { hotels, status: hotelsStatus } = hotelsState;
  const hotelsError = hotelsState.status === 'error' ? hotelsState.error : undefined;
  const [selectedHotelId, setSelectedHotelId] = useState<string | null>(null);

  // Auto-select first hotel once list loads
  useEffect(() => {
    if (hotels.length > 0 && selectedHotelId === null) {
      setSelectedHotelId(hotels[0].id);
    }
  }, [hotels, selectedHotelId]);

  const dashboardState = useDashboard(selectedHotelId);
  const { refetch: refetchDashboard } = dashboardState;

  // Baseline forecast – always runs (non-fatal on error)
  const forecastState = useForecast(selectedHotelId, 14);
  const forecastData = forecastState.status === 'success' ? forecastState.data : undefined;
  const forecastLoading = forecastState.status === 'loading';

  // Adjusted forecast – always runs in parallel (non-fatal on error)
  const adjustedForecastState = useAdjustedForecast(selectedHotelId, true, 14);
  const adjustedForecastData =
    adjustedForecastState.status === 'success' ? adjustedForecastState.data : undefined;
  const adjustedForecastLoading = adjustedForecastState.status === 'loading';

  // Demand events (non-fatal on error)
  const eventsState = useEvents(selectedHotelId);
  const eventsData = eventsState.status === 'success' ? eventsState.data.items : [];
  const eventsLoading = eventsState.status === 'loading';

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#f0f2f5',
        fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif',
      }}
    >
      {/* ── Global keyframes ─────────────────────────────────────────── */}
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #f0f2f5; }
      `}</style>

      {/* ── Top navbar ───────────────────────────────────────────────── */}
      <nav
        style={{
          background: '#0f172a',
          borderBottom: '1px solid #1e293b',
          padding: '0 24px',
          height: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <rect x="2" y="3" width="20" height="18" rx="2" stroke="#3b82d4" strokeWidth="2" />
            <path d="M8 10h8M8 14h5" stroke="#3b82d4" strokeWidth="2" strokeLinecap="round" />
            <path d="M2 7h20" stroke="#3b82d4" strokeWidth="2" />
          </svg>
          <span
            style={{
              fontSize: 15,
              fontWeight: 700,
              color: '#f1f5f9',
              letterSpacing: '-0.01em',
            }}
          >
            Hotel Control Tower
          </span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: '#3b82d4',
              background: '#1e293b',
              padding: '2px 6px',
              borderRadius: 4,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
            }}
          >
            PoC
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <HotelSelector
            hotels={hotels}
            selectedId={selectedHotelId}
            onChange={setSelectedHotelId}
            loading={hotelsStatus === 'loading'}
          />
          <button
            onClick={refetchDashboard}
            title="Refresh dashboard"
            style={{
              background: 'none',
              border: '1px solid #334155',
              color: '#94a3b8',
              borderRadius: 6,
              padding: '5px 10px',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            ↻
          </button>
        </div>
      </nav>

      {/* ── Main content ─────────────────────────────────────────────── */}
      <main
        style={{
          maxWidth: 1400,
          margin: '0 auto',
          padding: '24px 24px 48px',
        }}
      >
        {hotelsStatus === 'error' && (
          <ErrorBanner message={`Failed to load hotels: ${hotelsError}`} />
        )}

        {!selectedHotelId && hotelsStatus !== 'loading' && (
          <EmptyState message="Select a property above to view the commercial dashboard." />
        )}

        {selectedHotelId && dashboardState.status === 'loading' && (
          <LoadingState />
        )}

        {selectedHotelId && dashboardState.status === 'error' && (
          <ErrorBanner message={`Dashboard error: ${dashboardState.status === 'error' ? dashboardState.error : ''}`} />
        )}

        {dashboardState.status === 'success' && (
          <DashboardPanel
            data={dashboardState.data}
            forecast={forecastData}
            forecastLoading={forecastLoading}
            adjustedForecast={adjustedForecastData}
            adjustedForecastLoading={adjustedForecastLoading}
            events={eventsData}
            eventsLoading={eventsLoading}
          />
        )}
      </main>
    </div>
  );
}

function LoadingState() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        padding: '80px 0',
      }}
    >
      <Spinner size={40} />
      <span style={{ color: '#57606a', fontSize: 14 }}>Loading dashboard…</span>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      style={{
        background: '#fee2e2',
        border: '1px solid #fca5a5',
        borderRadius: 8,
        padding: '14px 18px',
        color: '#991b1b',
        fontSize: 14,
        marginBottom: 16,
      }}
    >
      <strong>Error:</strong> {message}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div
      style={{
        textAlign: 'center',
        padding: '80px 24px',
        color: '#57606a',
        fontSize: 14,
      }}
    >
      {message}
    </div>
  );
}
