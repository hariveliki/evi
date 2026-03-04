import { useMutation } from "@tanstack/react-query";
import api from "../api/client";
import type { BacktestResponse, ConfigOverrides } from "../api/types";

interface BacktestParams {
  start_date?: string;
  end_date?: string;
  frequency?: string;
  config_overrides?: ConfigOverrides;
  source?: string;
}

export function useBacktest() {
  return useMutation({
    mutationFn: async (params: BacktestParams) => {
      const { data } = await api.post<BacktestResponse>("/backtest", params);
      return data;
    },
  });
}
