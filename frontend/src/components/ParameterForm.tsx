import { useState } from "react";
import type { ConfigOverrides } from "../api/types";

interface Props {
  onSubmit: (overrides: ConfigOverrides) => void;
  loading?: boolean;
}

interface SliderDef {
  key: keyof ConfigOverrides;
  label: string;
  min: number;
  max: number;
  step: number;
  defaultVal: number;
}

const sliders: SliderDef[] = [
  { key: "strength_k", label: "Strength (k)", min: 0, max: 2, step: 0.1, defaultVal: 0.8 },
  { key: "shrinkage_lambda", label: "Shrinkage (λ)", min: 0, max: 1, step: 0.05, defaultVal: 0.2 },
  { key: "pe_weight", label: "P/E Weight", min: 0, max: 1, step: 0.05, defaultVal: 0.6 },
  { key: "weight_floor", label: "Weight Floor", min: 0, max: 0.2, step: 0.01, defaultVal: 0.02 },
  { key: "weight_ceiling", label: "Weight Ceiling", min: 0.3, max: 1, step: 0.05, defaultVal: 0.6 },
  { key: "max_overweight_pp", label: "Max Overweight (pp)", min: 1, max: 20, step: 0.5, defaultVal: 7.5 },
  { key: "lookback_years", label: "Lookback Years", min: 5, max: 20, step: 1, defaultVal: 10 },
];

export default function ParameterForm({ onSubmit, loading }: Props) {
  const [values, setValues] = useState<Record<string, number>>(
    Object.fromEntries(sliders.map((s) => [s.key, s.defaultVal])),
  );

  const handleChange = (key: string, val: number) => {
    setValues((prev) => ({ ...prev, [key]: val }));
  };

  const handleSubmit = () => {
    const overrides: ConfigOverrides = {};
    for (const s of sliders) {
      if (values[s.key] !== s.defaultVal) {
        (overrides as Record<string, number>)[s.key] = values[s.key];
      }
    }
    onSubmit(overrides);
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
        Parameters
      </h3>
      {sliders.map((s) => (
        <div key={s.key}>
          <div className="flex justify-between text-sm">
            <span>{s.label}</span>
            <span className="font-mono text-gray-600">{values[s.key]}</span>
          </div>
          <input
            type="range"
            min={s.min}
            max={s.max}
            step={s.step}
            value={values[s.key]}
            onChange={(e) => handleChange(s.key, parseFloat(e.target.value))}
            className="w-full accent-blue-600"
          />
        </div>
      ))}
      <button
        onClick={handleSubmit}
        disabled={loading}
        className="w-full bg-blue-600 text-white py-2 px-4 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? "Calculating..." : "Recalculate"}
      </button>
    </div>
  );
}
