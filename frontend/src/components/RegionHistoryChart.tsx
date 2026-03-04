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
import type { Snapshot } from "../api/types";

interface Props {
  snapshots: Snapshot[];
}

export default function RegionHistoryChart({ snapshots }: Props) {
  const data = snapshots.map((s) => ({
    date: s.date,
    "P/E": s.pe_ratio,
    "P/B": s.pb_ratio,
  }));

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis yAxisId="pe" orientation="left" label={{ value: "P/E", angle: -90, position: "insideLeft" }} />
        <YAxis yAxisId="pb" orientation="right" label={{ value: "P/B", angle: 90, position: "insideRight" }} />
        <Tooltip />
        <Legend />
        <Line yAxisId="pe" type="monotone" dataKey="P/E" stroke="#3b82f6" dot={false} />
        <Line yAxisId="pb" type="monotone" dataKey="P/B" stroke="#10b981" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
