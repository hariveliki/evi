import { useState } from "react";
import { useBacktest } from "../hooks/useBacktest";
import BacktestTimeline from "../components/BacktestTimeline";

export default function BacktestPage() {
  const backtest = useBacktest();
  const [startDate, setStartDate] = useState("2016-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold">Backtest</h1>
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="border rounded px-2 py-1 text-sm"
        />
        <span className="text-gray-400">to</span>
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="border rounded px-2 py-1 text-sm"
        />
        <button
          onClick={() =>
            backtest.mutate({
              start_date: startDate,
              end_date: endDate,
              source: "sample",
            })
          }
          disabled={backtest.isPending}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {backtest.isPending ? "Running..." : "Run Backtest"}
        </button>
      </div>

      {backtest.data && (
        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-semibold mb-4">
            Weight Evolution ({backtest.data.points.length} quarters)
          </h2>
          <BacktestTimeline points={backtest.data.points} />
        </div>
      )}

      {!backtest.data && !backtest.isPending && (
        <div className="text-center py-20 text-gray-400">
          Select a date range and click "Run Backtest"
        </div>
      )}
    </div>
  );
}
