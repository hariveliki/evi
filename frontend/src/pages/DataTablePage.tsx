import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import api from "../api/client";
import DataTable from "../components/DataTable";
import ExportButton from "../components/ExportButton";
import type { RunSummary } from "../api/types";

const col = createColumnHelper<RunSummary>();
const runColumns = [
  col.accessor("id", { header: "ID" }),
  col.accessor("as_of_date", { header: "As-Of Date" }),
  col.accessor("scenario_name", {
    header: "Scenario",
    cell: (i) => i.getValue() ?? "—",
  }),
  col.accessor("triggered_by", { header: "Source" }),
  col.accessor("region_count", { header: "Regions" }),
  col.accessor("created_at", {
    header: "Created",
    cell: (i) => new Date(i.getValue()).toLocaleString(),
  }),
];

export default function DataTablePage() {
  const [tab, setTab] = useState<"runs">("runs");

  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: async () => {
      const { data } = await api.get<RunSummary[]>("/runs");
      return data;
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Data Explorer</h1>

      <div className="flex gap-2 border-b">
        <button
          onClick={() => setTab("runs")}
          className={`px-4 py-2 text-sm font-medium border-b-2 ${
            tab === "runs"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Calculation Runs
        </button>
      </div>

      {tab === "runs" && runs.data && (
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">
              Runs ({runs.data.length})
            </h2>
            {runs.data.length > 0 && (
              <div className="flex gap-2">
                <ExportButton runId={runs.data[0].id} format="csv" />
                <ExportButton runId={runs.data[0].id} format="json" />
              </div>
            )}
          </div>
          <DataTable data={runs.data} columns={runColumns} />
        </div>
      )}

      {runs.isLoading && (
        <div className="text-center py-20 text-gray-400">Loading...</div>
      )}
      {runs.data?.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          No runs yet. Run a calculation from the Dashboard first.
        </div>
      )}
    </div>
  );
}
