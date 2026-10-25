"use client";

import ReplayIcon from "@mui/icons-material/Replay";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Skeleton from "@mui/material/Skeleton";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { DialogShell } from "@/components/DialogShell";
import { useNotifications } from "@/components/Notifications";
import { StatusChip } from "@/components/StatusChip";
import { useBatch } from "@/hooks/data";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { BatchMessage } from "@/lib/api/types";
import { channelLabel } from "@/lib/channels";
import { formatDateTime, plural } from "@/lib/format";

function SummaryTile({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <Box sx={{ flex: "1 1 100px", border: "1px solid #EEEEEE", borderRadius: 1, px: 1.5, py: 1 }}>
      <Typography sx={{ fontSize: 22, fontWeight: 700, color }}>{value}</Typography>
      <Typography variant="caption">{label}</Typography>
    </Box>
  );
}

export function BatchResultsDialog({ batchId, onClose, onChanged }: { batchId: string | null; onClose: () => void; onChanged: () => void }) {
  const { data: batch, error, mutate } = useBatch(batchId, { live: true });
  const { notify } = useNotifications();
  const [retrying, setRetrying] = useState<Set<string>>(new Set());

  const retryable = batch?.messages.filter((m) => m.can_retry) ?? [];

  async function retry(messages: BatchMessage[]) {
    setRetrying((s) => new Set([...s, ...messages.map((m) => m.id)]));
    const results = await Promise.allSettled(messages.map((m) => api.retryMessage(m.id)));
    const failed = results.filter((r) => r.status === "rejected") as PromiseRejectedResult[];
    if (failed.length) notify({ severity: "error", message: errorMessage(failed[0].reason) });
    else notify({ severity: "info", message: `Retrying ${plural(messages.length, "message")}…` });
    setRetrying(new Set());
    await mutate();
    onChanged();
  }

  const s = batch?.summary;
  return (
    <DialogShell
      open={batchId !== null}
      title="Delivery results"
      onClose={onClose}
      width={720}
      footer={
        <>
          {retryable.length > 1 && (
            <Button variant="outlined" color="error" startIcon={<ReplayIcon />} onClick={() => retry(retryable)} disabled={retrying.size > 0}>
              Retry {retryable.length} failed
            </Button>
          )}
          <Button variant="contained" onClick={onClose}>
            Done
          </Button>
        </>
      }
    >
      {error && !batch && <Alert severity="error">{errorMessage(error)}</Alert>}
      {!batch && !error && <Skeleton variant="rectangular" height={160} />}
      {batch && s && (
        <>
          <Typography variant="caption" component="p">
            Sent {formatDateTime(batch.created_at)} via {channelLabel(batch.channel)} · {plural(batch.recipient_count, "recipient")} ·
            each tracked separately
          </Typography>
          <Box sx={{ mt: 1, p: 1.5, bgcolor: "#F6F6F6", borderRadius: 1, fontSize: 14, whiteSpace: "pre-wrap", maxHeight: 90, overflow: "auto" }}>
            {batch.body}
          </Box>
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mt: 2 }}>
            <SummaryTile label="Total" value={s.total} />
            <SummaryTile label="Sent" value={s.submitted} color="#1565C0" />
            <SummaryTile label="Delivered" value={s.delivered} color="#00695C" />
            <SummaryTile label="Failed" value={s.failed} color="#C62828" />
            <SummaryTile label={s.scheduled ? "Scheduled" : "In progress"} value={s.scheduled || s.processing} />
          </Box>

          <Box component="ul" sx={{ listStyle: "none", p: 0, m: 0, mt: 2, maxHeight: 340, overflowY: "auto" }} aria-label="Recipients">
            {batch.messages.map((m) => (
              <Box component="li" key={m.id} sx={{ py: 1.5, borderBottom: "1px solid #EEEEEE" }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography sx={{ fontWeight: 700, fontSize: 14 }}>{m.candidate.full_name}</Typography>
                    <Typography variant="caption">
                      {m.candidate.phone_display} · {m.candidate.candidate_code}
                    </Typography>
                  </Box>
                  <StatusChip status={m.status} retrying={m.retry_scheduled} />
                  {m.can_retry && (
                    <Button
                      size="small"
                      color="error"
                      onClick={() => retry([m])}
                      disabled={retrying.size > 0}
                      startIcon={retrying.has(m.id) ? <CircularProgress size={14} color="inherit" /> : <ReplayIcon />}
                      aria-label={`Retry message to ${m.candidate.full_name}`}
                    >
                      Retry
                    </Button>
                  )}
                </Box>
                {m.error && (m.status === "failed" || m.retry_scheduled) && (
                  <Typography sx={{ fontSize: 13, mt: 0.5, color: m.status === "failed" ? "#C62828" : "#E65100" }}>
                    <b>{m.error.title}:</b> {m.error.explanation}
                    {m.status === "failed" && !m.can_retry && m.retry_block_reason ? ` ${m.retry_block_reason}` : ""}
                  </Typography>
                )}
              </Box>
            ))}
          </Box>
        </>
      )}
    </DialogShell>
  );
}
