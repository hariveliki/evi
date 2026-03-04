export interface RegionResult {
  region_name: string;
  mcap_weight: number;
  current_pe: number | null;
  current_pb: number | null;
  baseline_pe: number | null;
  baseline_pb: number | null;
  pe_score: number | null;
  pb_score: number | null;
  composite_score: number;
  adjustment_factor: number;
  raw_evi_weight: number;
  normalized_weight: number;
  shrunk_weight: number;
  final_weight: number;
}

export interface CalculateResponse {
  run_id: number;
  as_of_date: string;
  effective_date: string;
  total_weight: number;
  regions: RegionResult[];
  config_used: Record<string, unknown>;
}

export interface ConfigOverrides {
  strength_k?: number;
  shrinkage_lambda?: number;
  pe_weight?: number;
  pb_weight?: number;
  weight_floor?: number;
  weight_ceiling?: number;
  max_overweight_pp?: number;
  max_underweight_pp?: number;
  lookback_years?: number;
}

export interface RunSummary {
  id: number;
  as_of_date: string;
  effective_date: string;
  scenario_name: string | null;
  triggered_by: string;
  created_at: string;
  region_count: number;
}

export interface RunDetail {
  id: number;
  as_of_date: string;
  effective_date: string;
  scenario_name: string | null;
  triggered_by: string;
  created_at: string;
  config: Record<string, unknown>;
  regions: RegionResult[];
}

export interface RegionInfo {
  name: string;
  latest_date: string | null;
  snapshot_count: number;
}

export interface Snapshot {
  date: string;
  pe_ratio: number | null;
  pb_ratio: number | null;
  earnings_growth: number | null;
}

export interface RegionHistory {
  region_name: string;
  snapshots: Snapshot[];
}

export interface BacktestPoint {
  as_of_date: string;
  run_id: number;
  regions: { name: string; mcap_weight: number; evi_weight: number; composite_score: number }[];
}

export interface BacktestResponse {
  points: BacktestPoint[];
}

export interface ScenarioVariantResult {
  label: string;
  run_id: number;
  config_overrides: Record<string, unknown>;
  regions: { region_name: string; mcap_weight: number; final_weight: number; composite_score: number; adjustment_factor: number }[];
}

export interface ScenarioCompareResponse {
  scenario_id: number;
  name: string;
  variants: ScenarioVariantResult[];
}
