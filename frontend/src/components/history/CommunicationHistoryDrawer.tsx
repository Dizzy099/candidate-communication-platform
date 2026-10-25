"use client";

import SendIcon from "@mui/icons-material/Send";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import Skeleton from "@mui/material/Skeleton";
import Typography from "@mui/material/Typography";
import { DrawerShell } from "@/components/DrawerShell";
import { EmptyState } from "@/components/EmptyState";
import { useNotifications } from "@/components/Notifications";
import { useHistory } from "@/hooks/data";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { Candidate, MessageDetail } from "@/lib/api/types";
import { MessageHistoryItem } from "./MessageHistoryItem";

export function CommunicationHistoryDrawer({
  candidate,
  onClose,
  onSendMessage,
  onChanged,
}: {
  candidate: Candidate | null;
  onClose: () => void;
  onSendMessage: (candidate: Candidate) => void;
  onChanged: () => void;
}) {
  const { data, error, isLoading, mutate } = useHistory(candidate?.id ?? null);
  const { notify } = useNotifications();
  const messages = data?.results ?? [];

  async function retry(message: MessageDetail) {
    try {
      await api.retryMessage(message.id);
      notify({ severity: "info", message: "Retrying the message…" });
      await mutate();
      onChanged();
    } catch (err) {
      notify({ severity: "error", message: errorMessage(err) });
      await mutate();
    }
  }

  async function cancel(message: MessageDetail) {
    try {
      await api.cancelMessage(message.id);
      notify({ severity: "success", message: "Scheduled message cancelled" });
      await mutate();
      onChanged();
    } catch (err) {
      notify({ severity: "error", message: errorMessage(err) });
      await mutate();
    }
  }

  return (
    <DrawerShell open={candidate !== null} title="Communication history" onClose={onClose}>
      {candidate && (
        <>
          <Box sx={{ mt: 3, display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 2, flexWrap: "wrap" }}>
            <Box>
              <Typography variant="caption" component="p">
                Candidate ID: {candidate.candidate_code}
              </Typography>
              <Typography variant="h3" component="p" sx={{ mt: 1.25 }}>
                {candidate.full_name}
              </Typography>
              <Typography sx={{ fontSize: 16, mt: 1.75 }}>{candidate.phone_display}</Typography>
              <Typography sx={{ fontSize: 16, mt: 1.25 }}>{candidate.email}</Typography>
            </Box>
            <Button variant="outlined" startIcon={<SendIcon />} onClick={() => onSendMessage(candidate)}>
              Send message
            </Button>
          </Box>
          <Divider sx={{ mt: 4.5, borderColor: "#E0E0E0" }} />

          {isLoading && (
            <Box aria-label="Loading history">
              {[0, 1, 2].map((i) => (
                <Box key={i} sx={{ py: 3, borderBottom: "1px solid #E0E0E0" }}>
                  <Skeleton width={140} />
                  <Skeleton width="90%" />
                  <Skeleton width="60%" />
                </Box>
              ))}
            </Box>
          )}
          {error && !data && (
            <Alert
              severity="error"
              sx={{ mt: 3 }}
              action={<Button color="inherit" size="small" onClick={() => mutate()}>Try again</Button>}
            >
              {errorMessage(error)}
            </Alert>
          )}
          {data && messages.length === 0 && (
            <EmptyState
              title="No communication history"
              description="You have not communicated with this candidate yet. When you send them a message, it will appear here."
            />
          )}
          {messages.length > 0 && (
            <>
              <Typography variant="caption" component="p" sx={{ mt: 2 }} aria-live="polite">
                Newest first · statuses refresh every few seconds
              </Typography>
              {messages.map((message) => (
                <MessageHistoryItem key={message.id} message={message} onRetry={retry} onCancel={cancel} />
              ))}
              {data && data.count > messages.length && (
                <Typography variant="caption" component="p" sx={{ mt: 2 }}>
                  Showing the latest {messages.length} of {data.count} messages.
                </Typography>
              )}
            </>
          )}
        </>
      )}
    </DrawerShell>
  );
}
