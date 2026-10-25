"use client";

import Box from "@mui/material/Box";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSWRConfig } from "swr";
import { AddCandidateDialog } from "@/components/candidates/AddCandidateDialog";
import { CandidateTable } from "@/components/candidates/CandidateTable";
import { DeleteCandidatesDialog, type DeleteResult } from "@/components/candidates/DeleteCandidatesDialog";
import { CommunicationHistoryDrawer } from "@/components/history/CommunicationHistoryDrawer";
import { BatchResultsDialog } from "@/components/messaging/BatchResultsDialog";
import { BatchWatcher, type TrackedBatch } from "@/components/messaging/BatchWatcher";
import { SendMessageDrawer, type SendResult } from "@/components/messaging/SendMessageDrawer";
import { useNotifications } from "@/components/Notifications";
import { PageHeader } from "@/components/PageHeader";
import { useCandidates, useDebouncedValue } from "@/hooks/data";
import { errorMessage } from "@/lib/api/client";
import { candidatesPath } from "@/lib/api/endpoints";
import type { Candidate } from "@/lib/api/types";
import { formatDateTime, plural } from "@/lib/format";

export function CandidateCommunicationPage() {
  const { notify } = useNotifications();
  const { mutate: globalMutate } = useSWRConfig();

  // List state
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 300);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [ordering, setOrdering] = useState("");
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  // Selection survives paging and searching; candidates are kept for recipient chips.
  const [selected, setSelected] = useState<Map<number, Candidate>>(new Map());

  // Overlays
  const [adding, setAdding] = useState(false);
  const [deleteTargets, setDeleteTargets] = useState<Candidate[] | null>(null);
  const [sendTargets, setSendTargets] = useState<Candidate[] | null>(null);
  const [historyCandidate, setHistoryCandidate] = useState<Candidate | null>(null);
  const [resultsBatchId, setResultsBatchId] = useState<string | null>(null);
  const [tracked, setTracked] = useState<TrackedBatch[]>([]);

  const path = candidatesPath({ search: debouncedSearch, page: page + 1, pageSize: rowsPerPage, ordering, status: statusFilter });
  const { data, error, isLoading, mutate } = useCandidates(path);
  const rows = useMemo(() => data?.results ?? [], [data]);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    if (data) setLastUpdated(new Date().toISOString());
  }, [data]);

  // Back to the first page whenever the result set changes shape.
  useEffect(() => setPage(0), [debouncedSearch, ordering, statusFilter, rowsPerPage]);

  // If a page empties (e.g. after deleting), step back.
  useEffect(() => {
    if (data && rows.length === 0 && page > 0) setPage((p) => p - 1);
  }, [data, rows.length, page]);

  // Keep selected candidates' details fresh (e.g. latest status) when visible.
  useEffect(() => {
    setSelected((current) => {
      if (!rows.some((r) => current.has(r.id))) return current;
      const next = new Map(current);
      rows.forEach((r) => next.has(r.id) && next.set(r.id, r));
      return next;
    });
  }, [rows]);

  const refreshAll = useCallback(() => {
    void globalMutate((key) => Array.isArray(key) && (key[0] === "candidates" || key[0] === "history"));
    void globalMutate("provider-health");
  }, [globalMutate]);

  function toggle(candidate: Candidate) {
    setSelected((current) => {
      const next = new Map(current);
      if (next.has(candidate.id)) next.delete(candidate.id);
      else next.set(candidate.id, candidate);
      return next;
    });
  }

  function toggleAll(checked: boolean) {
    setSelected((current) => {
      const next = new Map(current);
      rows.forEach((r) => (checked ? next.set(r.id, r) : next.delete(r.id)));
      return next;
    });
  }

  function clearFilters() {
    setSearch("");
    setStatusFilter([]);
    setOrdering("");
  }

  function handleCreated(candidate: Candidate) {
    setAdding(false);
    notify({ severity: "success", message: `${candidate.full_name} added successfully` });
    clearFilters();
    setPage(0);
    void mutate();
  }

  function handleDeleted(result: DeleteResult) {
    setDeleteTargets(null);
    setSelected((current) => {
      const next = new Map(current);
      result.deletedIds.forEach((id) => next.delete(id));
      return next;
    });
    if (historyCandidate && result.deletedIds.includes(historyCandidate.id)) setHistoryCandidate(null);
    const message =
      result.deletedIds.length === 1
        ? "Candidate deleted successfully"
        : result.alreadyGone > 0
          ? `${plural(result.deleted, "candidate")} deleted. ${result.alreadyGone} had already been removed.`
          : `${result.deleted} Candidates deleted successfully`;
    notify({ severity: "success", message });
    refreshAll();
  }

  const handleTrackedDone = useCallback(
    (batchId: string) => {
      setTracked((all) => all.filter((t) => t.batchId !== batchId));
      refreshAll();
    },
    [refreshAll],
  );

  function handleSent(result: SendResult) {
    setSendTargets(null);
    setSelected(new Map());
    refreshAll();
    const who = result.recipientName ?? plural(result.recipientCount, "candidate");
    if (result.scheduledAt) {
      notify({
        severity: "success",
        message: `Message scheduled for ${who} on ${formatDateTime(result.scheduledAt)}`,
        action: result.batchId ? { label: "Details", onClick: () => setResultsBatchId(result.batchId) } : undefined,
      });
      return;
    }
    const toastId = notify({ severity: "info", message: `Sending to ${who}…`, progress: true, autoHideMs: null });
    if (result.batchId) setTracked((all) => [...all, { batchId: result.batchId, toastId, recipientName: result.recipientName }]);
  }

  function openSendFromHistory(candidate: Candidate) {
    setHistoryCandidate(null);
    setSendTargets([candidate]);
  }

  const selectedList = useMemo(() => Array.from(selected.values()), [selected]);
  const isFiltered = Boolean(debouncedSearch.trim() || statusFilter.length);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100dvh", minHeight: 560 }}>
      <PageHeader
        search={search}
        onSearchChange={setSearch}
        selectedCount={selected.size}
        onAdd={() => setAdding(true)}
        onDelete={() => setDeleteTargets(selectedList)}
        onSend={() => setSendTargets(selectedList)}
      />
      <Box component="main" sx={{ flex: 1, minHeight: 0, p: 1 }}>
        <Box sx={{ bgcolor: "#fff", borderRadius: 1, height: "100%", p: 1, display: "flex", flexDirection: "column" }}>
          <CandidateTable
            rows={rows}
            totalCount={data?.count ?? 0}
            loading={isLoading}
            error={error && !data ? errorMessage(error) : null}
            refreshError={Boolean(error && data)}
            lastUpdated={lastUpdated}
            isFiltered={isFiltered}
            page={page}
            rowsPerPage={rowsPerPage}
            onPageChange={setPage}
            onRowsPerPageChange={setRowsPerPage}
            ordering={ordering}
            onOrderingChange={setOrdering}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            selectedIds={new Set(selected.keys())}
            onToggle={toggle}
            onToggleAll={toggleAll}
            onOpenHistory={setHistoryCandidate}
            onRetryLoad={() => void mutate()}
            onClearFilters={clearFilters}
          />
        </Box>
      </Box>

      <AddCandidateDialog open={adding} onClose={() => setAdding(false)} onCreated={handleCreated} />
      <DeleteCandidatesDialog candidates={deleteTargets} onClose={() => setDeleteTargets(null)} onDeleted={handleDeleted} />
      <SendMessageDrawer recipients={sendTargets} onClose={() => setSendTargets(null)} onSent={handleSent} />
      <CommunicationHistoryDrawer
        candidate={historyCandidate}
        onClose={() => setHistoryCandidate(null)}
        onSendMessage={openSendFromHistory}
        onChanged={refreshAll}
      />
      <BatchResultsDialog batchId={resultsBatchId} onClose={() => setResultsBatchId(null)} onChanged={refreshAll} />
      {tracked.map((t) => (
        <BatchWatcher key={t.batchId} tracked={t} onDone={handleTrackedDone} onViewDetails={setResultsBatchId} />
      ))}
    </Box>
  );
}
