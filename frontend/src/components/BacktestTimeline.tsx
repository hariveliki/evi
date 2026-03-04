import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { BacktestPoint } from "../api/types";

interface Props {
  points: BacktestPoint[];
}

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

export default function BacktestTimeline({ points }: Props) {
  if (points.length === 0) return null;

  const regionNames = points[0].regions.map((r) => r.name);
  const data = points.map((pt) => {
    const row: Record<string, string | number> = { date: pt.as_of_date };
    for (const r of pt.regions) {
      row[r.name] = +(r.evi_weight * 100).toFixed(2);
    }
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={450}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis unit="%" />
        <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
        <Legend />
        {regionNames.map((name, i) => (
          <Line
            key={name}
            type="monotone"
            dataKey={name}
            stroke={COLORS[i % COLORS.length]}
            dot={false}
            strokeWidth={2}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
