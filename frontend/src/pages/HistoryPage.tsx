import { useState } from "react";
import { useRegions, useRegionHistory } from "../hooks/useRegions";
import RegionHistoryChart from "../components/RegionHistoryChart";
import DataTable from "../components/DataTable";
import type { Snapshot } from "../api/types";
import { createColumnHelper } from "@tanstack/react-table";

const col = createColumnHelper<Snapshot>();
const columns = [
  col.accessor("date", { header: "Date" }),
  col.accessor("pe_ratio", {
    header: "P/E",
    cell: (i) => i.getValue()?.toFixed(2) ?? "—",
  }),
  col.accessor("pb_ratio", {
    header: "P/B",
    cell: (i) => i.getValue()?.toFixed(2) ?? "—",
  }),
];

export default function HistoryPage() {
  const regions = useRegions();
  const [selected, setSelected] = useState("North America");
  const history = useRegionHistory(selected, !!regions.data);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold">Region History</h1>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="border rounded px-2 py-1 text-sm"
        >
          {regions.data?.map((r) => (
            <option key={r.name} value={r.name}>
              {r.name}
            </option>
          )) ?? <option>Loading...</option>}
        </select>
      </div>

      {history.data && history.data.snapshots.length > 0 ? (
        <>
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">
              {selected} — P/E & P/B Over Time
            </h2>
            <RegionHistoryChart snapshots={history.data.snapshots} />
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">Raw Data</h2>
            <DataTable data={history.data.snapshots} columns={columns} />
          </div>
        </>
      ) : history.isLoading ? (
        <div className="text-center py-20 text-gray-400">Loading...</div>
      ) : (
        <div className="text-center py-20 text-gray-400">
          No history data. Run a calculation first to populate the database.
        </div>
      )}
    </div>
  );
}
