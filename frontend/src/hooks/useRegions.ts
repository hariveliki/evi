import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import type { RegionHistory, RegionInfo } from "../api/types";

export function useRegions() {
  return useQuery({
    queryKey: ["regions"],
    queryFn: async () => {
      const { data } = await api.get<RegionInfo[]>("/regions");
      return data;
    },
  });
}

export function useRegionHistory(name: string, enabled = true) {
  return useQuery({
    queryKey: ["region-history", name],
    queryFn: async () => {
      const { data } = await api.get<RegionHistory>(
        `/regions/${encodeURIComponent(name)}/history`,
      );
      return data;
    },
    enabled,
  });
}
