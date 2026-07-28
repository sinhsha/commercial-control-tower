import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  type TooltipProps,
} from 'recharts';
import type { DemandPoint } from '@/types/api';
import { format, parseISO } from 'date-fns';

interface OccupancyBarChartProps {
  data: DemandPoint[];
}

function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const occ = payload[0]?.value ?? 0;
  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid #e5e7eb',
        borderRadius: 6,
        padding: '8px 12px',
        fontSize: 12,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      <div style={{ color: '#3b82d4' }}>Occupancy: <strong>{occ}%</strong></div>
    </div>
  );
}

function getBarColor(occ: number): string {
  if (occ >= 85) return '#16a34a';
  if (occ >= 65) return '#3b82d4';
  if (occ >= 45) return '#f59e0b';
  return '#dc2626';
}

export function OccupancyBarChart({ data }: OccupancyBarChartProps) {
  const chartData = data.map((d) => ({
    date: format(parseISO(d.date), 'MMM d'),
    occupancy: +d.occupancy_pct.toFixed(1),
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: '#57606a' }}
          tickLine={false}
          axisLine={false}
          interval={4}
        />
        <YAxis
          tick={{ fontSize: 10, fill: '#57606a' }}
          tickLine={false}
          axisLine={false}
          domain={[0, 100]}
          tickFormatter={(v) => `${v}%`}
        />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="occupancy" radius={[3, 3, 0, 0]}>
          {chartData.map((entry, index) => (
            <Cell key={index} fill={getBarColor(entry.occupancy)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
