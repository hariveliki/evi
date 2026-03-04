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
import type { RegionResult } from "../api/types";

interface Props {
  regions: RegionResult[];
}

export default function WeightsBarChart({ regions }: Props) {
  const data = regions.map((r) => ({
    name: r.region_name,
    "MCAP Weight": +(r.mcap_weight * 100).toFixed(2),
    "EVI Weight": +(r.final_weight * 100).toFixed(2),
  }));

  return (
    <ResponsiveContainer width="100%" height={350}>
      <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" domain={[0, "auto"]} unit="%" />
        <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 12 }} />
        <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
        <Legend />
        <Bar dataKey="MCAP Weight" fill="#94a3b8" />
        <Bar dataKey="EVI Weight" fill="#3b82f6" />
      </BarChart>
    </ResponsiveContainer>
  );
}
