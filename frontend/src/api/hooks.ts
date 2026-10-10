import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useDebounced } from "@/hooks/useDebounced";

import { api } from "./client";
import type { PlanRequest } from "./types";

export function usePlan(id: string | undefined) {
  return useQuery({
    queryKey: ["plan", id],
    queryFn: () => api.getPlan(id!),
    enabled: !!id,
    staleTime: Infinity, // plans are immutable snapshots
  });
}

export function useHeatmap(id: string | undefined) {
  return useQuery({
    queryKey: ["heatmap", id],
    queryFn: () => api.getHeatmap(id!),
    enabled: !!id,
    staleTime: Infinity,
    retry: 1,
  });
}

export function useCreatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PlanRequest) => api.createPlan(body),
    onSuccess: (plan) => qc.setQueryData(["plan", plan.id], plan),
  });
}

export function usePlaceSearch(query: string) {
  const q = useDebounced(query.trim(), 300);
  return useQuery({
    queryKey: ["geocode", q.toLowerCase()],
    queryFn: ({ signal }) => api.geocode(q, signal),
    enabled: q.length >= 3,
    staleTime: 60 * 60 * 1000,
    placeholderData: keepPreviousData,
  });
}
