import { apiFetch } from "./client";
import type {
  Batch,
  Candidate,
  MessageDetail,
  NewCandidate,
  Paginated,
  ProviderHealth,
  SendPayload,
  Template,
  TemplateVariable,
} from "./types";

export interface CandidateQuery {
  search?: string;
  page?: number;
  pageSize?: number;
  ordering?: string;
  status?: string[];
}

export function candidatesPath(query: CandidateQuery): string {
  const params = new URLSearchParams();
  if (query.search?.trim()) params.set("search", query.search.trim());
  if (query.page && query.page > 1) params.set("page", String(query.page));
  if (query.pageSize) params.set("page_size", String(query.pageSize));
  if (query.ordering) params.set("ordering", query.ordering);
  if (query.status?.length) params.set("status", query.status.join(","));
  const qs = params.toString();
  return `/candidates${qs ? `?${qs}` : ""}`;
}

export const api = {
  listCandidates: (path: string) => apiFetch<Paginated<Candidate>>(path),
  createCandidate: (data: NewCandidate) => apiFetch<Candidate>("/candidates", { method: "POST", json: data }),
  deleteCandidate: (id: number) => apiFetch<void>(`/candidates/${id}`, { method: "DELETE" }),
  bulkDeleteCandidates: (ids: number[]) =>
    apiFetch<{ deleted: number; not_found: number[] }>("/candidates/bulk-delete", { method: "POST", json: { ids } }),

  history: (candidateId: number) => apiFetch<Paginated<MessageDetail>>(`/candidates/${candidateId}/messages`),
  sendToCandidate: (candidateId: number, payload: SendPayload) =>
    apiFetch<MessageDetail>(`/candidates/${candidateId}/messages`, { method: "POST", json: payload }),
  sendBatch: (candidateIds: number[], payload: SendPayload) =>
    apiFetch<Batch>("/message-batches", { method: "POST", json: { candidate_ids: candidateIds, ...payload } }),
  batch: (id: string) => apiFetch<Batch>(`/message-batches/${id}`),
  retryMessage: (id: string) => apiFetch<MessageDetail>(`/messages/${id}/retry`, { method: "POST" }),
  cancelMessage: (id: string) => apiFetch<MessageDetail>(`/messages/${id}/cancel`, { method: "POST" }),

  templates: () => apiFetch<Template[]>("/templates"),
  createTemplate: (data: { name: string; body: string }) =>
    apiFetch<Template>("/templates", { method: "POST", json: data }),
  deleteTemplate: (id: number) => apiFetch<void>(`/templates/${id}`, { method: "DELETE" }),
  templateVariables: () => apiFetch<TemplateVariable[]>("/template-variables"),

  providerHealth: () => apiFetch<ProviderHealth>("/provider/health"),
  setSimulatorOutage: (enabled: boolean) =>
    apiFetch<{ outage: boolean }>("/provider/simulator/outage", { method: "POST", json: { enabled } }),
};
