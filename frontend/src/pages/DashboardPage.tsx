import { useState } from "react";
import { useCalculation } from "../hooks/useCalculation";
import WeightsBarChart from "../components/WeightsBarChart";
import WeightsPieChart from "../components/WeightsPieChart";
import ParameterForm from "../components/ParameterForm";
import DataTable from "../components/DataTable";
import ExportButton from "../components/ExportButton";
import type { ConfigOverrides, RegionResult } from "../api/types";
import { createColumnHelper } from "@tanstack/react-table";

const col = createColumnHelper<RegionResult>();
const columns = [
  col.accessor("region_name", { header: "Region" }),
  col.accessor("mcap_weight", {
    header: "MCAP %",
    cell: (i) => (i.getValue() * 100).toFixed(2),
  }),
  col.accessor("final_weight", {
    header: "EVI %",
    cell: (i) => (i.getValue() * 100).toFixed(2),
  }),
  col.accessor("composite_score", {
    header: "Score",
    cell: (i) => i.getValue().toFixed(3),
  }),
  col.accessor("adjustment_factor", {
    header: "Adj. Factor",
    cell: (i) => i.getValue().toFixed(3),
  }),
];

export default function DashboardPage() {
  const calc = useCalculation();
  const [source, setSource] = useState("sample");

  const handleCalculate = (overrides: ConfigOverrides) => {
    const hasOverrides = Object.keys(overrides).length > 0;
    calc.mutate({
      source,
      config_overrides: hasOverrides ? overrides : undefined,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-3">
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value="sample">Sample Data</option>
            <option value="live">Live (yfinance)</option>
          </select>
          <button
            onClick={() => calc.mutate({ source })}
            disabled={calc.isPending}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {calc.isPending ? "Calculating..." : "Calculate"}
          </button>
        </div>
      </div>

      {calc.data && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-white rounded-lg shadow p-4">
                <h2 className="text-lg font-semibold mb-4">
                  MCAP vs EVI Weights
                </h2>
                <WeightsBarChart regions={calc.data.regions} />
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                <h2 className="text-lg font-semibold mb-4">
                  Final Allocation
                </h2>
                <WeightsPieChart regions={calc.data.regions} />
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <ParameterForm
                onSubmit={handleCalculate}
                loading={calc.isPending}
              />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Results</h2>
              <div className="flex gap-2">
                <ExportButton runId={calc.data.run_id} format="csv" />
                <ExportButton runId={calc.data.run_id} format="json" />
              </div>
            </div>
            <DataTable data={calc.data.regions} columns={columns} />
          </div>
        </>
      )}

      {!calc.data && !calc.isPending && (
        <div className="text-center py-20 text-gray-400">
          Click "Calculate" to run the EVI pipeline
        </div>
      )}
    </div>
  );
}
