"use client";

import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ReplayIcon from "@mui/icons-material/Replay";
import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Collapse from "@mui/material/Collapse";
import Typography from "@mui/material/Typography";
import { useState, type ReactNode } from "react";
import { StatusChip } from "@/components/StatusChip";
import type { MessageDetail } from "@/lib/api/types";
import { channelLabel } from "@/lib/channels";
import { formatDate, formatDateTime, formatTime, formatTimeWithSeconds } from "@/lib/format";

const TRIGGER_LABEL = { initial: "First send", auto_retry: "Automatic retry", manual_retry: "Manual retry" } as const;

function Caption({ children }: { children: ReactNode }) {
  return (
    <Typography variant="caption" component="span">
      {children}
    </Typography>
  );
}

export function MessageHistoryItem({
  message,
  onRetry,
  onCancel,
}: {
  message: MessageDetail;
  onRetry: (message: MessageDetail) => Promise<void>;
  onCancel: (message: MessageDetail) => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState<"retry" | "cancel" | null>(null);
  const when = message.sent_at ?? message.created_at;

  async function run(kind: "retry" | "cancel") {
    setBusy(kind);
    try {
      await (kind === "retry" ? onRetry(message) : onCancel(message));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Box component="article" sx={{ py: 3, borderBottom: "1px solid #E0E0E0" }} aria-label={`Message from ${formatDateTime(when)}`}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
          <Caption>{formatDate(when)}</Caption>
          <Caption>|</Caption>
          <Caption>{formatTime(when)}</Caption>
          <Caption>|</Caption>
          <Caption>{channelLabel(message.channel)}</Caption>
        </Box>
        <StatusChip status={message.status} retrying={message.retry_scheduled} />
      </Box>

      <Typography sx={{ mt: 1.5, fontSize: 16, lineHeight: 1.2, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
        {message.body}
      </Typography>

      {message.status === "failed" && message.error && (
        <Alert
          severity="error"
          variant="outlined"
          sx={{ mt: 2, "& .MuiAlert-message": { fontSize: 14, fontWeight: 400, lineHeight: 1.5, width: "100%" } }}
          action={
            message.can_retry ? (
              <Button
                color="error"
                size="small"
                onClick={() => run("retry")}
                disabled={busy !== null}
                startIcon={busy === "retry" ? <CircularProgress size={14} color="inherit" /> : <ReplayIcon />}
              >
                Retry
              </Button>
            ) : undefined
          }
        >
          <AlertTitle sx={{ fontWeight: 700, fontSize: 14, mb: 0.25 }}>{message.error.title}</AlertTitle>
          {message.error.explanation}
          {!message.can_retry && message.retry_block_reason && (
            <Typography sx={{ fontSize: 13, mt: 0.75, fontWeight: 700 }}>{message.retry_block_reason}</Typography>
          )}
        </Alert>
      )}

      {message.retry_scheduled && message.error && (
        <Alert severity="warning" sx={{ mt: 2, "& .MuiAlert-message": { fontSize: 14, fontWeight: 400, lineHeight: 1.5 } }}>
          <b>{message.error.title}.</b> Retrying automatically
          {message.next_attempt_at ? ` at ${formatTimeWithSeconds(message.next_attempt_at)}` : ""} (attempt{" "}
          {message.attempt_count + 1} of {message.max_attempts}).
        </Alert>
      )}

      {message.status === "scheduled" && message.scheduled_at && (
        <Alert
          severity="info"
          sx={{ mt: 2, "& .MuiAlert-message": { fontSize: 14, fontWeight: 400, lineHeight: 1.5 } }}
          action={
            <Button color="inherit" size="small" onClick={() => run("cancel")} disabled={busy !== null}>
              {busy === "cancel" ? <CircularProgress size={14} color="inherit" /> : "Cancel"}
            </Button>
          }
        >
          Scheduled for {formatDateTime(message.scheduled_at)}.
        </Alert>
      )}

      <Button
        size="small"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        endIcon={<ExpandMoreIcon sx={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform .2s" }} />}
        sx={{ mt: 1, ml: -1, textTransform: "none", fontWeight: 400, color: "rgba(0,0,0,0.6)" }}
      >
        {expanded ? "Hide details" : "Details"}
      </Button>
      <Collapse in={expanded} unmountOnExit>
        <Box sx={{ mt: 1, p: 2, bgcolor: "#FAFAFA", borderRadius: 1, fontSize: 13 }}>
          <Box component="dl" sx={{ display: "grid", gridTemplateColumns: "max-content 1fr", columnGap: 2, rowGap: 0.5, m: 0 }}>
            <dt>Provider</dt>
            <dd style={{ margin: 0 }}>{message.provider_label}</dd>
            <dt>Provider reference</dt>
            <dd style={{ margin: 0, fontFamily: "monospace" }}>{message.provider_message_id ?? (message.status === "failed" ? "None (the provider did not accept it)" : "Not assigned yet")}</dd>
            <dt>Attempts</dt>
            <dd style={{ margin: 0 }}>
              {message.attempt_count} of {message.max_attempts}
            </dd>
            {message.error?.technical_detail && (
              <>
                <dt>Technical detail</dt>
                <dd style={{ margin: 0 }}>{message.error.technical_detail}</dd>
              </>
            )}
          </Box>

          {message.attempts.length > 0 && (
            <>
              <Typography sx={{ fontWeight: 700, fontSize: 13, mt: 2, mb: 0.5 }}>Send attempts</Typography>
              <Box component="ol" sx={{ m: 0, pl: 2.5 }}>
                {message.attempts.map((a) => (
                  <li key={a.number}>
                    {TRIGGER_LABEL[a.trigger]} at {formatTimeWithSeconds(a.started_at)} —{" "}
                    {a.outcome === "accepted" ? "accepted by provider" : a.outcome === "failed" ? `failed (${a.error_code || "error"})` : "in progress"}
                  </li>
                ))}
              </Box>
            </>
          )}

          <Typography sx={{ fontWeight: 700, fontSize: 13, mt: 2, mb: 0.5 }}>Timeline</Typography>
          <Box component="ol" sx={{ m: 0, pl: 2.5 }}>
            {message.events.map((e) => (
              <li key={e.id} style={{ color: e.applied ? undefined : "rgba(0,0,0,0.5)" }}>
                {formatDate(e.occurred_at)} {formatTimeWithSeconds(e.occurred_at)} · {e.source === "provider" ? "Provider" : "Platform"}:{" "}
                {e.detail || e.kind_label}
              </li>
            ))}
          </Box>
        </Box>
      </Collapse>
    </Box>
  );
}
