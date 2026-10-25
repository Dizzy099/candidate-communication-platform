"use client";

import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { DialogShell } from "@/components/DialogShell";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { Candidate } from "@/lib/api/types";

export interface DeleteResult {
  deletedIds: number[];
  deleted: number;
  alreadyGone: number;
}

export function DeleteCandidatesDialog({
  candidates,
  onClose,
  onDeleted,
}: {
  candidates: Candidate[] | null;
  onClose: () => void;
  onDeleted: (result: DeleteResult) => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const targets = candidates ?? [];
  const many = targets.length > 1;

  function close() {
    if (deleting) return;
    setError(null);
    onClose();
  }

  async function confirm() {
    setDeleting(true);
    setError(null);
    try {
      const ids = targets.map((c) => c.id);
      if (many) {
        const result = await api.bulkDeleteCandidates(ids);
        onDeleted({ deletedIds: ids, deleted: result.deleted, alreadyGone: result.not_found.length });
      } else {
        await api.deleteCandidate(ids[0]);
        onDeleted({ deletedIds: ids, deleted: 1, alreadyGone: 0 });
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <DialogShell
      open={candidates !== null}
      title={many ? "Delete Candidates" : "Delete Candidate"}
      onClose={close}
      busy={deleting}
      footer={
        <>
          <Button variant="outlined" onClick={close} disabled={deleting}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={confirm}
            disabled={deleting || targets.length === 0}
            startIcon={deleting ? <CircularProgress size={16} color="inherit" /> : undefined}
          >
            {many ? `Delete ${targets.length} candidates` : "Delete candidate"}
          </Button>
        </>
      }
    >
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Typography sx={{ fontSize: 16 }}>
        {many ? `Are you sure you want to delete ${targets.length} Candidates?` : "Are you sure you want to delete this Candidate?"}
      </Typography>
      <Typography variant="caption" component="p" sx={{ mt: 1.5 }}>
        {many
          ? "This action cannot be undone, and you’ll lose all communication history with these candidates."
          : `This action cannot be undone, and you’ll lose all communication history with ${targets[0]?.full_name ?? "this candidate"}.`}
      </Typography>
    </DialogShell>
  );
}
