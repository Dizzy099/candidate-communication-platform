"use client";

import { useEffect, useRef } from "react";
import { useNotifications } from "@/components/Notifications";
import { useBatch } from "@/hooks/data";
import type { Batch } from "@/lib/api/types";
import { plural } from "@/lib/format";

export interface TrackedBatch {
  batchId: string;
  toastId: string;
  recipientName: string | null;
}

/** Final wording. "Sent" means accepted by the provider; it never claims delivery. */
export function outcomeMessage(batch: Batch, recipientName: string | null) {
  const s = batch.summary;
  const who = recipientName ?? plural(s.total, "candidate");
  if (s.failed === 0) {
    return { severity: "success" as const, text: `Message sent to ${who}` };
  }
  if (s.submitted === 0) {
    const reason = s.total === 1 ? `: ${batch.messages[0]?.error?.title ?? "failed"}` : "";
    return { severity: "error" as const, text: `Message to ${who} failed${reason}` };
  }
  return { severity: "warning" as const, text: `Message sent to ${s.submitted} of ${s.total} candidates. ${s.failed} failed.` };
}

/** Polls one batch and keeps its toast up to date until every recipient is processed. */
export function BatchWatcher({
  tracked,
  onDone,
  onViewDetails,
}: {
  tracked: TrackedBatch;
  onDone: (batchId: string) => void;
  onViewDetails: (batchId: string) => void;
}) {
  const { data: batch } = useBatch(tracked.batchId);
  const { update } = useNotifications();
  const finished = useRef(false);

  useEffect(() => {
    if (!batch || finished.current) return;
    const s = batch.summary;
    if (!s.complete) {
      const done = s.submitted + s.failed;
      const retrying = s.retrying ? ` · ${s.retrying} retrying after a temporary error` : "";
      update(tracked.toastId, {
        message: `Sending to ${plural(s.total, "candidate")}… ${done} of ${s.total} processed${retrying}`,
        action: { label: "Details", onClick: () => onViewDetails(tracked.batchId) },
      });
      return;
    }
    finished.current = true;
    const outcome = outcomeMessage(batch, tracked.recipientName);
    update(tracked.toastId, {
      severity: outcome.severity,
      message: outcome.text,
      progress: false,
      autoHideMs: outcome.severity === "success" ? 5000 : null,
      action: { label: outcome.severity === "success" ? "Details" : "View details", onClick: () => onViewDetails(tracked.batchId) },
    });
    onDone(tracked.batchId);
  }, [batch, tracked, update, onDone, onViewDetails]);

  return null;
}
