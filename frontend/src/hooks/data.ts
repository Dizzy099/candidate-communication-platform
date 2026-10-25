"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api/endpoints";
import type { Batch } from "@/lib/api/types";

// Status updates arrive at the backend by webhook; the browser learns about
// them by polling these endpoints (SWR pauses polling while the tab is hidden).
export const POLL = {
  candidates: 4000,
  history: 2500,
  batch: 1000,
  provider: 10000,
} as const;

export function useCandidates(path: string) {
  return useSWR(["candidates", path], ([, p]) => api.listCandidates(p), { refreshInterval: POLL.candidates });
}

export function useHistory(candidateId: number | null) {
  return useSWR(candidateId ? ["history", candidateId] : null, ([, id]) => api.history(id), {
    refreshInterval: POLL.history,
    keepPreviousData: false,
  });
}

/** ``live`` keeps polling after sending finishes (delivered/read updates keep coming). */
export function useBatch(batchId: string | null, { live = false } = {}) {
  return useSWR(batchId ? ["batch", batchId] : null, ([, id]) => api.batch(id), {
    keepPreviousData: false,
    refreshInterval: (latest?: Batch) => (live || !latest?.summary.complete ? POLL.batch : 0),
  });
}

export function useProviderHealth() {
  return useSWR("provider-health", api.providerHealth, { refreshInterval: POLL.provider });
}

export function useTemplates(enabled: boolean) {
  return useSWR(enabled ? "templates" : null, api.templates);
}

export function useTemplateVariables(enabled: boolean) {
  return useSWR(enabled ? "template-variables" : null, api.templateVariables, { revalidateOnFocus: false });
}

export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}
