/**
 * ForecastPlatformPanel
 * =====================
 * Enterprise Forecasting Platform dashboard panel.
 *
 * Sections:
 *   1. Forecast Health Banner
 *   2. Model Performance Cards
 *   3. Model Comparison Chart (SVG)
 *   4. Backtest Visualization (actuals vs predicted + residual bars)
 *   5. Model Selector (display current FORECAST_PROVIDER config)
 */
import { useState } from 'react';
import { format, parseISO } from 'date-fns';
import { SectionCard } from '@/components/ui/SectionCard';
import {
  useForecastHealth,
  useForecastModels,
  useForecastComparison,
  useForecastBacktest,
} from '@/hooks/useForecastPlatform';
import type {
  BacktestPoint,
  EvaluationMetrics,
  ForecastHealthStatusLevel,
  ForecastModelInfo,
} from '@/types/api';

interface ForecastPlatformPanelProps {
  hotelId: string;
}

// ── colour helpers ────────────────────────────────────────────────────────────

function healthColor(status: ForecastHealthStatusLevel): string {
  if (status === 'healthy') return '#16a34a';
  if (status === 'warning') return '#d97706';
  return '#dc2626';
}

function statusDot(status: ForecastHealthStatusLevel) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: 10,
        height: 10,
        borderRadius: '50%',
        background: healthColor(status),
        marginRight: 6,
        flexShrink: 0,
      }}
    />
  );
}

function modelStatusColor(s: string) {
  if (s === 'active') return '#16a34a';
  if (s === 'degraded') return '#d97706';
  return '#6b7280';
}

// ── Section 1: Health Banner ──────────────────────────────────────────────────

function HealthBanner({ hotelId }: { hotelId: string }) {
  const { data, loading, error } = useForecastHealth(hotelId);

  if (loading) return <div style={{ fontSize: 13, color: '#57606a' }}>Loading health…</div>;
  if (error || !data) return <div style={{ fontSize: 12, color: '#dc2626' }}>Health unavailable</div>;

  const color = healthColor(data.status);
  const label = data.status.charAt(0).toUpperCase() + data.status.slice(1);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 20,
        flexWrap: 'wrap',
        padding: '10px 16px',
        background: data.status === 'healthy' ? '#f0fdf4' : data.status === 'warning' ? '#fffbeb' : '#fef2f2',
        border: `1px solid ${data.status === 'healthy' ? '#bbf7d0' : data.status === 'warning' ? '#fde68a' : '#fecaca'}`,
        borderRadius: 8,
        fontSize: 13,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center' }}>
        {statusDot(data.status)}
        <span style={{ fontWeight: 700, color }}>
          {label}
        </span>
      </div>
      <div>
        <span style={{ color: '#57606a' }}>Active model: </span>
        <strong>{data.active_model}</strong>
        <span style={{ color: '#57606a', marginLeft: 4 }}>v{data.active_model_version}</span>
      </div>
      {data.fallback_active && (
        <div
          style={{
            background: '#fef3c7',
            border: '1px solid #fde68a',
            borderRadius: 4,
            padding: '2px 8px',
            fontSize: 11,
            fontWeight: 600,
            color: '#92400e',
          }}
        >
          Fallback active
        </div>
      )}
      <div style={{ marginLeft: 'auto', fontSize: 11, color: '#57606a' }}>
        Last validated: {format(parseISO(data.last_validation), 'MMM d, HH:mm')}
      </div>
    </div>
  );
}

// ── Section 2: Model Performance Cards ───────────────────────────────────────

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: 12,
        padding: '3px 0',
        borderBottom: '1px solid #f3f4f6',
      }}
    >
      <span style={{ color: '#57606a' }}>{label}</span>
      <strong style={{ color: '#1f2328' }}>{value}</strong>
    </div>
  );
}

function ModelCard({
  metrics,
  isRecommended,
  modelInfo,
}: {
  metrics: EvaluationMetrics;
  isRecommended: boolean;
  modelInfo?: ForecastModelInfo;
}) {
  return (
    <div
      style={{
        flex: '1 1 220px',
        border: isRecommended ? '2px solid #3b82d4' : '1px solid #e5e7eb',
        borderRadius: 8,
        padding: '12px 16px',
        background: isRecommended ? '#eff6ff' : '#fff',
        position: 'relative',
      }}
    >
      {isRecommended && (
        <span
          style={{
            position: 'absolute',
            top: -9,
            right: 12,
            fontSize: 9,
            fontWeight: 700,
            background: '#3b82d4',
            color: '#fff',
            padding: '2px 7px',
            borderRadius: 999,
            letterSpacing: '0.04em',
          }}
        >
          RECOMMENDED
        </span>
      )}
      <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 2, color: '#1f2328' }}>
        {metrics.model_name}
      </div>
      {modelInfo && (
        <div
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: modelStatusColor(modelInfo.status),
            marginBottom: 8,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          {modelInfo.status}
        </div>
      )}
      <MetricRow label="WAPE" value={`${metrics.wape.toFixed(2)}%`} />
      <MetricRow label="MAE" value={`${metrics.mae.toFixed(2)}pp`} />
      <MetricRow label="RMSE" value={`${metrics.rmse.toFixed(2)}pp`} />
      <MetricRow label="Bias" value={`${metrics.bias >= 0 ? '+' : ''}${metrics.bias.toFixed(2)}pp`} />
      <MetricRow label="Coverage" value={`${metrics.coverage.toFixed(1)}%`} />
      <MetricRow label="Inference" value={`${metrics.runtime_ms.toFixed(0)}ms`} />
    </div>
  );
}

function ModelPerformanceCards({ hotelId }: { hotelId: string }) {
  const { data: comparison, loading, error } = useForecastComparison(hotelId, 30);
  const { data: modelsData } = useForecastModels();

  if (loading) return <div style={{ fontSize: 13, color: '#57606a' }}>Evaluating models…</div>;
  if (error || !comparison)
    return <div style={{ fontSize: 12, color: '#dc2626' }}>Evaluation unavailable</div>;

  const modelInfoMap = new Map<string, ForecastModelInfo>(
    modelsData?.models.map((m) => [m.model_id, m]) ?? [],
  );

  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      {comparison.models.map((m) => (
        <ModelCard
          key={m.model_id}
          metrics={m}
          isRecommended={m.model_id === comparison.recommended_model_id}
          modelInfo={modelInfoMap.get(m.model_id)}
        />
      ))}
    </div>
  );
}

// ── Section 3: Model Comparison SVG Chart ─────────────────────────────────────

// Per-model colours for the comparison chart
const MODEL_COLOURS: Record<string, string> = {
  seasonal_baseline: '#6366f1',
  timesfm: '#f59e0b',
};
const MODEL_DASH: Record<string, string> = {
  seasonal_baseline: '5 3',
  timesfm: '8 2',
};

function ComparisonChart({ hotelId }: { hotelId: string }) {
  const [selectedModels, setSelectedModels] = useState<Set<string>>(
    new Set(['seasonal_baseline', 'timesfm'])
  );
  const { data: comparison, loading: compLoading } = useForecastComparison(hotelId, 30);
  const { data: baselineBacktest, loading: btLoading } = useForecastBacktest(hotelId, 'last_30', 'baseline');
  const { data: timesfmBacktest } = useForecastBacktest(hotelId, 'last_30', 'timesfm');

  if (compLoading || btLoading) {
    return <div style={{ fontSize: 13, color: '#57606a', padding: '12px 0' }}>Loading comparison…</div>;
  }
  if (!baselineBacktest || !comparison) {
    return <div style={{ fontSize: 13, color: '#57606a' }}>No comparison data available</div>;
  }

  const points = baselineBacktest.points;
  if (points.length === 0) {
    return <div style={{ fontSize: 13, color: '#57606a' }}>No backtest data available</div>;
  }

  const toggleModel = (id: string) => {
    setSelectedModels((prev) => {
      const next = new Set(prev);
      if (next.has(id)) { if (next.size > 1) next.delete(id); }
      else { next.add(id); }
      return next;
    });
  };

  // Build per-model predicted series (keyed by model_id)
  const modelPredictions: Record<string, number[]> = {
    seasonal_baseline: points.map((p) => p.predicted),
  };
  if (timesfmBacktest && timesfmBacktest.points.length === points.length) {
    modelPredictions['timesfm'] = timesfmBacktest.points.map((p) => p.predicted);
  }

  // y-axis range: don't clamp at 100 — let data drive the scale
  const allOcc = [
    ...points.map((p) => p.actual),
    ...Object.values(modelPredictions).flat(),
  ];
  const minOcc = Math.max(0, Math.min(...allOcc) - 3);
  const maxOcc = Math.min(105, Math.max(...allOcc) + 3);  // allow up to 105 so 100% values aren't clipped

  const W = 600, H = 200, PAD = { top: 12, right: 16, bottom: 36, left: 40 };
  const chartW = W - PAD.left - PAD.right;
  const chartH = H - PAD.top - PAD.bottom;

  const xScale = (i: number) => PAD.left + (i / (points.length - 1)) * chartW;
  const yScale = (v: number) => PAD.top + chartH - ((v - minOcc) / (maxOcc - minOcc)) * chartH;
  const pathFor = (vals: number[]) =>
    vals.map((v, i) => `${i === 0 ? 'M' : 'L'}${xScale(i).toFixed(1)},${yScale(v).toFixed(1)}`).join(' ');

  const xTicks = points.filter((_, i) => i % 5 === 0 || i === points.length - 1);
  const yStep = Math.max(1, Math.ceil((maxOcc - minOcc) / 5));
  const yTicks: number[] = [];
  for (let v = Math.floor(minOcc); v <= maxOcc; v += yStep) yTicks.push(v);

  // Build toggle labels from comparison + what we actually have data for
  const modelLabels: Array<{ model_id: string; model_name: string }> = comparison.models.map((m) => ({
    model_id: m.model_id,
    model_name: m.model_name,
  }));

  return (
    <div>
      {/* Model toggles */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
        {modelLabels.map((m) => (
          <label key={m.model_id} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={selectedModels.has(m.model_id)}
              onChange={() => toggleModel(m.model_id)}
            />
            <span style={{ color: MODEL_COLOURS[m.model_id] ?? '#57606a', fontWeight: 500 }}>
              {m.model_name}
            </span>
          </label>
        ))}
        <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12 }}>
          <input type="checkbox" checked readOnly />
          <span style={{ color: '#57606a' }}>Historical Actuals</span>
        </label>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', height: 'auto', overflow: 'visible' }}
        aria-label="Model comparison chart"
      >
        {yTicks.map((v) => (
          <line key={v} x1={PAD.left} x2={W - PAD.right} y1={yScale(v)} y2={yScale(v)}
            stroke="#f0f0f0" strokeWidth={1} />
        ))}
        {yTicks.map((v) => (
          <text key={v} x={PAD.left - 4} y={yScale(v) + 4} textAnchor="end" fontSize={9} fill="#57606a">
            {v}%
          </text>
        ))}
        {xTicks.map((p) => {
          const i = points.indexOf(p);
          return (
            <text key={p.date} x={xScale(i)} y={H - PAD.bottom + 14}
              textAnchor="middle" fontSize={9} fill="#57606a">
              {format(parseISO(String(p.date)), 'MMM d')}
            </text>
          );
        })}

        {/* Actuals line */}
        <path d={pathFor(points.map((p) => p.actual))} fill="none" stroke="#3b82d4" strokeWidth={2} />

        {/* Per-model forecast lines */}
        {Object.entries(modelPredictions).map(([modelId, preds]) =>
          selectedModels.has(modelId) ? (
            <path
              key={modelId}
              d={pathFor(preds)}
              fill="none"
              stroke={MODEL_COLOURS[modelId] ?? '#999'}
              strokeWidth={1.5}
              strokeDasharray={MODEL_DASH[modelId] ?? '4 2'}
            />
          ) : null
        )}
      </svg>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, fontSize: 11, color: '#57606a', marginTop: 4, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <svg width={20} height={4}><line x1={0} y1={2} x2={20} y2={2} stroke="#3b82d4" strokeWidth={2} /></svg>
          Actuals
        </div>
        {modelLabels.map((m) =>
          selectedModels.has(m.model_id) ? (
            <div key={m.model_id} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <svg width={20} height={4}>
                <line x1={0} y1={2} x2={20} y2={2}
                  stroke={MODEL_COLOURS[m.model_id] ?? '#999'}
                  strokeWidth={1.5}
                  strokeDasharray={MODEL_DASH[m.model_id] ?? '4 2'} />
              </svg>
              {m.model_name}
            </div>
          ) : null
        )}
      </div>
    </div>
  );
}

// ── Section 4: Backtest Visualization ────────────────────────────────────────

function BacktestChart({ hotelId }: { hotelId: string }) {
  const [backtestWindow, setBacktestWindow] = useState<string>('last_30');
  const { data, loading, error } = useForecastBacktest(hotelId, backtestWindow, 'baseline');

  if (loading) return <div style={{ fontSize: 13, color: '#57606a' }}>Running backtest…</div>;
  if (error || !data) return <div style={{ fontSize: 12, color: '#dc2626' }}>Backtest unavailable</div>;

  const points: BacktestPoint[] = data.points;
  if (points.length === 0)
    return <div style={{ fontSize: 13, color: '#57606a' }}>Insufficient data for backtest</div>;

  const W = 600, H_TOP = 140, H_RES = 60, PAD = { top: 10, right: 16, bottom: 20, left: 40 };
  const chartW = W - PAD.left - PAD.right;
  const chartH = H_TOP - PAD.top - PAD.bottom;

  const allOcc = points.flatMap((p) => [p.actual, p.predicted]);
  const minOcc = Math.max(0, Math.min(...allOcc) - 5);
  const maxOcc = Math.min(100, Math.max(...allOcc) + 5);

  const xScale = (i: number) => PAD.left + (i / (points.length - 1)) * chartW;
  const yScale = (v: number) => PAD.top + chartH - ((v - minOcc) / (maxOcc - minOcc)) * chartH;

  const pathFor = (vals: number[]) =>
    vals.map((v, i) => `${i === 0 ? 'M' : 'L'}${xScale(i).toFixed(1)},${yScale(v).toFixed(1)}`).join(' ');

  // Residual bars
  const residuals = points.map((p) => p.residual);
  const maxResAbs = Math.max(1, Math.max(...residuals.map(Math.abs)));
  const resScale = (v: number) => (H_RES / 2) + ((v / maxResAbs) * (H_RES / 2 - 4)) * -1;
  const barW = Math.max(2, (chartW / points.length) * 0.7);

  // x-axis ticks
  const step = Math.max(1, Math.floor(points.length / 6));
  const xTicks = points.filter((_, i) => i % step === 0 || i === points.length - 1);

  return (
    <div>
      {/* Window selector */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: '#57606a' }}>Window:</span>
        {(['last_30', 'last_60', 'last_90'] as const).map((w) => (
          <button
            key={w}
            onClick={() => setBacktestWindow(w)}
            style={{
              padding: '3px 10px',
              fontSize: 11,
              borderRadius: 4,
              border: backtestWindow === w ? '1.5px solid #6366f1' : '1px solid #d1d5db',
              background: backtestWindow === w ? '#eef2ff' : '#fff',
              color: backtestWindow === w ? '#4338ca' : '#57606a',
              cursor: 'pointer',
            }}
          >
            {w.replace('last_', 'Last ')}
          </button>
        ))}
      </div>

      {/* Error distribution summary */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 10, flexWrap: 'wrap' }}>
        {[
          { label: 'MAE', value: `${data.mae.toFixed(2)}pp`, color: '#3b82d4' },
          { label: 'RMSE', value: `${data.rmse.toFixed(2)}pp`, color: '#6366f1' },
          { label: 'Bias', value: `${data.bias >= 0 ? '+' : ''}${data.bias.toFixed(2)}pp`, color: data.bias > 0 ? '#d97706' : '#16a34a' },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            style={{
              background: '#f7f8fa',
              border: '1px solid #e5e7eb',
              borderRadius: 6,
              padding: '4px 12px',
              fontSize: 12,
            }}
          >
            <span style={{ color: '#57606a' }}>{label}: </span>
            <strong style={{ color }}>{value}</strong>
          </div>
        ))}
      </div>

      <svg
        viewBox={`0 0 ${W} ${H_TOP + H_RES}`}
        style={{ width: '100%', height: 'auto', overflow: 'visible' }}
        aria-label="Backtest chart"
      >
        {/* Top: actuals vs predicted */}
        <path d={pathFor(points.map((p) => p.actual))} fill="none" stroke="#3b82d4" strokeWidth={2} />
        <path d={pathFor(points.map((p) => p.predicted))} fill="none" stroke="#6366f1" strokeWidth={1.5} strokeDasharray="6 3" />

        {/* x-axis labels */}
        {xTicks.map((p) => {
          const i = points.indexOf(p);
          return (
            <text key={p.date} x={xScale(i)} y={H_TOP - 2} textAnchor="middle" fontSize={8} fill="#57606a">
              {format(parseISO(p.date), 'MMM d')}
            </text>
          );
        })}

        {/* Bottom: residual bars */}
        {points.map((p, i) => {
          const x = xScale(i) - barW / 2;
          const zeroY = H_TOP + H_RES / 2;
          const barH = Math.abs(resScale(p.residual) - H_RES / 2);
          const y = p.residual >= 0 ? zeroY - barH : zeroY;
          return (
            <rect
              key={p.date}
              x={x}
              y={H_TOP + y}
              width={barW}
              height={barH}
              fill={p.residual >= 0 ? '#fbbf24' : '#86efac'}
              opacity={0.8}
            />
          );
        })}

        {/* Zero line for residuals */}
        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={H_TOP + H_RES / 2}
          y2={H_TOP + H_RES / 2}
          stroke="#d1d5db"
          strokeWidth={1}
        />
      </svg>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, fontSize: 11, color: '#57606a', marginTop: 4, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <svg width={20} height={4}><line x1={0} y1={2} x2={20} y2={2} stroke="#3b82d4" strokeWidth={2} /></svg>
          Actuals
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <svg width={20} height={4}><line x1={0} y1={2} x2={20} y2={2} stroke="#6366f1" strokeWidth={1.5} strokeDasharray="5 3" /></svg>
          Predicted
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <svg width={10} height={10}><rect width={10} height={10} fill="#fbbf24" /></svg>
          Over-predicted
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <svg width={10} height={10}><rect width={10} height={10} fill="#86efac" /></svg>
          Under-predicted
        </div>
      </div>
    </div>
  );
}

// ── Section 5: Model Selector ─────────────────────────────────────────────────

function ModelSelector({
  timesfmStatus,
  activeModel,
}: {
  timesfmStatus: string | undefined;
  activeModel: string | undefined;
}) {
  const [selected, setSelected] = useState<'baseline' | 'timesfm' | 'auto'>('baseline');
  const timesfmAvailable = timesfmStatus === 'active';
  const timesfmIsRunning = activeModel === 'timesfm';

  return (
    <div>
      <div style={{ fontSize: 12, color: '#57606a', marginBottom: 8 }}>
        Current FORECAST_PROVIDER configuration (changing requires server restart):
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
        {(['baseline', 'timesfm', 'auto'] as const).map((opt) => (
          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
            <input
              type="radio"
              name="forecast-provider"
              value={opt}
              checked={selected === opt}
              onChange={() => setSelected(opt)}
            />
            <span style={{ fontWeight: selected === opt ? 600 : 400, color: '#1f2328', textTransform: 'capitalize' }}>
              {opt === 'auto' ? 'Auto (Eval-Based)' : opt === 'timesfm' ? 'TimesFM' : 'Seasonal Baseline'}
              {opt === 'timesfm' && timesfmStatus !== undefined && (
                <span style={{
                  marginLeft: 6,
                  fontSize: 10,
                  fontWeight: 700,
                  padding: '1px 6px',
                  borderRadius: 4,
                  background: timesfmAvailable ? '#dcfce7' : '#fef9c3',
                  color: timesfmAvailable ? '#166534' : '#854d0e',
                }}>
                  {timesfmAvailable ? '● active' : '● degraded'}
                </span>
              )}
            </span>
          </label>
        ))}
      </div>
      <div
        style={{
          background: '#f7f8fa',
          border: '1px solid #e5e7eb',
          borderRadius: 6,
          padding: '8px 14px',
          fontSize: 12,
          color: '#57606a',
        }}
      >
        <strong>Selected:</strong> {selected.toUpperCase()} &nbsp;·&nbsp;
        Set <code style={{ background: '#e5e7eb', padding: '1px 4px', borderRadius: 3 }}>FORECAST_PROVIDER={selected}</code> in
        your <code style={{ background: '#e5e7eb', padding: '1px 4px', borderRadius: 3 }}>.env</code> file and restart the backend to apply.
        {selected === 'timesfm' && !timesfmAvailable && timesfmStatus !== undefined && (
          <span style={{ color: '#d97706', marginLeft: 8 }}>
            ⚠ TimesFM not yet available — will fall back to Seasonal Baseline.
          </span>
        )}
        {selected === 'timesfm' && timesfmAvailable && timesfmIsRunning && (
          <span style={{ color: '#166534', marginLeft: 8 }}>
            ✓ TimesFM 2.5 is active and running.
          </span>
        )}
        {selected === 'timesfm' && timesfmAvailable && !timesfmIsRunning && (
          <span style={{ color: '#d97706', marginLeft: 8 }}>
            ⚠ TimesFM is installed but backend is currently running{' '}
            {activeModel ?? 'another model'}. Set FORECAST_PROVIDER=timesfm and restart.
          </span>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ForecastPlatformPanel({ hotelId }: ForecastPlatformPanelProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Section 1: Health Banner */}
      <SectionCard
        title="Forecast Health"
        action={
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: '#3b82d4',
              background: '#eff6ff',
              padding: '2px 8px',
              borderRadius: 4,
              letterSpacing: '0.04em',
            }}
          >
            Enterprise Platform
          </span>
        }
      >
        <HealthBanner hotelId={hotelId} />
      </SectionCard>

      {/* Section 2: Model Performance */}
      <SectionCard title="Model Performance Metrics">
        <ModelPerformanceCards hotelId={hotelId} />
      </SectionCard>

      {/* Section 3: Comparison Chart */}
      <SectionCard title="Model Comparison — Backtest">
        <ComparisonChart hotelId={hotelId} />
      </SectionCard>

      {/* Section 4: Backtest Visualization */}
      <SectionCard title="Backtest Visualization">
        <BacktestChart hotelId={hotelId} />
      </SectionCard>

      {/* Section 5: Model Selector */}
      <SectionCard title="Model Selector">
        <ModelSelectorWithRegistry hotelId={hotelId} />
      </SectionCard>

    </div>
  );
}

function ModelSelectorWithRegistry({ hotelId }: { hotelId: string }) {
  const { data: modelsData } = useForecastModels();
  const { data: healthData } = useForecastHealth(hotelId);
  const timesfmEntry = modelsData?.models.find(
    (m: import('@/types/api').ForecastModelInfo) => m.model_id === 'timesfm'
  );
  return (
    <ModelSelector
      timesfmStatus={timesfmEntry?.status}
      activeModel={healthData?.active_model}
    />
  );
}
