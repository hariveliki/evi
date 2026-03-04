import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import api from "../api/client";
import ScenarioComparisonChart from "../components/ScenarioComparisonChart";
import type { ScenarioCompareResponse } from "../api/types";

interface Variant {
  label: string;
  strength_k: number;
}

export default function ScenariosPage() {
  const [variants, setVariants] = useState<Variant[]>([
    { label: "k=0.3", strength_k: 0.3 },
    { label: "k=0.8", strength_k: 0.8 },
    { label: "k=1.5", strength_k: 1.5 },
  ]);

  const mutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<ScenarioCompareResponse>(
        "/scenarios/compare",
        {
          name: "Parameter comparison",
          source: "sample",
          variants: variants.map((v) => ({
            label: v.label,
            config_overrides: { strength_k: v.strength_k },
          })),
        },
      );
      return data;
    },
  });

  const addVariant = () => {
    setVariants((prev) => [
      ...prev,
      { label: `k=${(prev.length * 0.5 + 0.3).toFixed(1)}`, strength_k: prev.length * 0.5 + 0.3 },
    ]);
  };

  const removeVariant = (i: number) => {
    setVariants((prev) => prev.filter((_, idx) => idx !== i));
  };

  const updateVariant = (i: number, field: keyof Variant, val: string) => {
    setVariants((prev) =>
      prev.map((v, idx) =>
        idx === i
          ? { ...v, [field]: field === "strength_k" ? parseFloat(val) : val }
          : v,
      ),
    );
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Scenario Comparison</h1>

      <div className="bg-white rounded-lg shadow p-4 space-y-3">
        <h2 className="text-lg font-semibold">Variants</h2>
        {variants.map((v, i) => (
          <div key={i} className="flex items-center gap-3">
            <input
              value={v.label}
              onChange={(e) => updateVariant(i, "label", e.target.value)}
              className="border rounded px-2 py-1 text-sm w-32"
              placeholder="Label"
            />
            <label className="text-sm text-gray-600">k =</label>
            <input
              type="number"
              step="0.1"
              value={v.strength_k}
              onChange={(e) => updateVariant(i, "strength_k", e.target.value)}
              className="border rounded px-2 py-1 text-sm w-20"
            />
            {variants.length > 2 && (
              <button
                onClick={() => removeVariant(i)}
                className="text-red-500 text-sm hover:underline"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <div className="flex gap-3">
          {variants.length < 4 && (
            <button
              onClick={addVariant}
              className="text-sm text-blue-600 hover:underline"
            >
              + Add Variant
            </button>
          )}
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? "Running..." : "Run Comparison"}
          </button>
        </div>
      </div>

      {mutation.data && (
        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-semibold mb-4">Results</h2>
          <ScenarioComparisonChart variants={mutation.data.variants} />
        </div>
      )}
    </div>
  );
}
