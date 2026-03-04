import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { ScenarioVariantResult } from "../api/types";

interface Props {
  variants: ScenarioVariantResult[];
}

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"];

export default function ScenarioComparisonChart({ variants }: Props) {
  if (variants.length === 0) return null;

  // Build data: one bar group per region, one bar per variant
  const regionNames = variants[0].regions.map((r) => r.region_name);
  const data = regionNames.map((name) => {
    const row: Record<string, string | number> = { region: name };
    for (const v of variants) {
      const r = v.regions.find((r) => r.region_name === name);
      row[v.label] = r ? +(r.final_weight * 100).toFixed(2) : 0;
    }
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="region" tick={{ fontSize: 11 }} />
        <YAxis unit="%" />
        <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
        <Legend />
        {variants.map((v, i) => (
          <Bar key={v.label} dataKey={v.label} fill={COLORS[i % COLORS.length]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
