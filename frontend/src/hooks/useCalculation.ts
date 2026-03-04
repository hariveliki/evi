import { useMutation } from "@tanstack/react-query";
import api from "../api/client";
import type { CalculateResponse, ConfigOverrides } from "../api/types";

interface CalculateParams {
  source?: string;
  config_overrides?: ConfigOverrides;
  scenario_name?: string;
}

export function useCalculation() {
  return useMutation({
    mutationFn: async (params: CalculateParams) => {
      const { data } = await api.post<CalculateResponse>("/calculate", params);
      return data;
    },
  });
}
