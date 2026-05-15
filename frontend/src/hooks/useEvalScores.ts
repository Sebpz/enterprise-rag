"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchEvalRuns } from "../lib/api";

export function useEvalScores() {
  return useQuery({
    queryKey: ["evals"],
    queryFn: fetchEvalRuns,
    staleTime: 60_000,
    retry: false,
  });
}
