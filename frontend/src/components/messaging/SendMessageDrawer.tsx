"use client";

import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import FormControlLabel from "@mui/material/FormControlLabel";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Switch from "@mui/material/Switch";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMemo, useRef, useState } from "react";
import { DialogShell } from "@/components/DialogShell";
import { DrawerShell } from "@/components/DrawerShell";
import { useNotifications } from "@/components/Notifications";
import { useTemplates, useTemplateVariables } from "@/hooks/data";
import { ApiError, errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { Candidate } from "@/lib/api/types";
import { localInputToIso, plural, toLocalInputValue } from "@/lib/format";
import { newRequestId } from "@/lib/ids";
import { RecipientChips } from "./RecipientChips";

const MAX_LENGTH = 1000;

export interface SendResult {
  batchId: string;
  recipientCount: number;
  scheduledAt: string | null;
  recipientName: string | null;
}

interface Props {
  recipients: Candidate[] | null;
  onClose: () => void;
  onSent: (result: SendResult) => void;
}

export function SendMessageDrawer({ recipients, onClose, onSent }: Props) {
  const open = recipients !== null;
  // Remount the form for every new compose session so state never leaks between sends.
  return open ? <SendMessageForm key={recipients.map((r) => r.id).join(",")} recipients={recipients} onClose={onClose} onSent={onSent} /> : null;
}

function SendMessageForm({ recipients, onClose, onSent }: Props & { recipients: Candidate[] }) {
  const { notify } = useNotifications();
  const { data: templates, mutate: refreshTemplates } = useTemplates(true);
  const { data: variables } = useTemplateVariables(true);
  const textRef = useRef<HTMLTextAreaElement>(null);

  // One ID per compose session: double clicks and network retries can't create a second send.
  const requestId = useMemo(() => newRequestId(), []);
  const [body, setBody] = useState("");
  const [templateId, setTemplateId] = useState<number | "">("");
  const [scheduleOn, setScheduleOn] = useState(false);
  const [scheduleAt, setScheduleAt] = useState(() => toLocalInputValue(new Date(Date.now() + 60 * 60 * 1000)));
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [templateName, setTemplateName] = useState("");
  const [showSaveTemplate, setShowSaveTemplate] = useState(false);

  const count = recipients.length;
  const trimmed = body.trim();
  const tooLong = body.length > MAX_LENGTH;
  const canSend = trimmed.length > 0 && !tooLong && !sending && (!scheduleOn || Boolean(scheduleAt));
  const actionLabel = scheduleOn
    ? count > 1 ? `Schedule for ${count} candidates` : "Schedule message"
    : count > 1 ? `Send to ${count} candidates` : "Send message";

  function applyTemplate(id: number | "") {
    setTemplateId(id);
    const template = templates?.find((t) => t.id === id);
    if (template) setBody(template.body);
    setFieldErrors((e) => ({ ...e, body: "" }));
  }

  function insertVariable(token: string) {
    const el = textRef.current;
    const start = el?.selectionStart ?? body.length;
    const end = el?.selectionEnd ?? body.length;
    const next = body.slice(0, start) + token + body.slice(end);
    setBody(next);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(start + token.length, start + token.length);
    });
  }

  function requestSend() {
    if (!canSend) return;
    if (count > 1) setConfirming(true);
    else void send();
  }

  async function send() {
    setConfirming(false);
    setSending(true);
    setFormError(null);
    setFieldErrors({});
    const scheduledIso = scheduleOn ? localInputToIso(scheduleAt) : null;
    const payload = { body: trimmed, client_request_id: requestId, template_id: templateId || null, scheduled_at: scheduledIso };
    try {
      let batchId: string;
      if (count === 1) {
        const message = await api.sendToCandidate(recipients[0].id, payload);
        batchId = message.batch_id ?? "";
      } else {
        const batch = await api.sendBatch(recipients.map((r) => r.id), payload);
        batchId = batch.id;
      }
      onSent({ batchId, recipientCount: count, scheduledAt: scheduledIso, recipientName: count === 1 ? recipients[0].full_name : null });
    } catch (error) {
      if (error instanceof ApiError && Object.keys(error.fields).length) {
        setFieldErrors(error.fields);
        if (error.fields.candidate_ids) setFormError(error.fields.candidate_ids);
      } else {
        setFormError(errorMessage(error));
      }
    } finally {
      setSending(false);
    }
  }

  async function saveTemplate() {
    setSavingTemplate(true);
    try {
      const created = await api.createTemplate({ name: templateName.trim(), body: trimmed });
      await refreshTemplates();
      setTemplateId(created.id);
      setShowSaveTemplate(false);
      setTemplateName("");
      notify({ severity: "success", message: `Template “${created.name}” saved` });
    } catch (error) {
      const fields = error instanceof ApiError ? error.fields : {};
      notify({ severity: "error", message: fields.name || fields.body || errorMessage(error) });
    } finally {
      setSavingTemplate(false);
    }
  }

  const names = useMemo(() => recipients.map((r) => r.full_name), [recipients]);

  return (
    <>
      <DrawerShell
        open
        title="Send Message"
        onClose={onClose}
        busy={sending}
        footer={
          <>
            {formError && (
              <Alert severity="error" sx={{ flexBasis: "100%", mb: 1 }}>
                {formError}
              </Alert>
            )}
            <Button variant="outlined" onClick={onClose} disabled={sending}>
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={requestSend}
              disabled={!canSend}
              startIcon={sending ? <CircularProgress size={16} color="inherit" /> : undefined}
            >
              {sending ? "Sending…" : actionLabel}
            </Button>
          </>
        }
      >
        <Typography sx={{ fontSize: 16, mt: 3, mb: 1.5 }}>{plural(count, "Recipient")}</Typography>
        <RecipientChips names={names} />

        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mt: 4 }} alignItems={{ sm: "center" }}>
          <TextField
            select
            size="small"
            label="Use a template"
            value={templateId}
            onChange={(e) => applyTemplate(e.target.value === "" ? "" : Number(e.target.value))}
            sx={{ minWidth: 240 }}
            disabled={sending}
          >
            <MenuItem value="">
              <em>No template</em>
            </MenuItem>
            {(templates ?? []).map((t) => (
              <MenuItem key={t.id} value={t.id}>
                {t.name}
              </MenuItem>
            ))}
          </TextField>
          {trimmed && !showSaveTemplate && (
            <Button size="small" onClick={() => setShowSaveTemplate(true)} disabled={sending}>
              Save as template
            </Button>
          )}
        </Stack>
        {showSaveTemplate && (
          <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} alignItems="center">
            <TextField
              size="small"
              label="Template name"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              autoFocus
            />
            <Button size="small" variant="contained" onClick={saveTemplate} disabled={!templateName.trim() || savingTemplate}>
              Save
            </Button>
            <Button size="small" onClick={() => setShowSaveTemplate(false)}>
              Cancel
            </Button>
          </Stack>
        )}

        <Box sx={{ mt: 4 }}>
          <Typography component="label" htmlFor="message-body" sx={{ fontSize: 16 }}>
            Message *
          </Typography>
          <Typography variant="caption" component="p" sx={{ mt: 0.5, mb: 1.5 }}>
            Type, or paste the message you want to send.
          </Typography>
          <TextField
            id="message-body"
            inputRef={textRef}
            multiline
            minRows={7}
            fullWidth
            value={body}
            onChange={(e) => {
              setBody(e.target.value);
              if (fieldErrors.body) setFieldErrors((f) => ({ ...f, body: "" }));
            }}
            placeholder="Type or paste here..."
            disabled={sending}
            error={tooLong || Boolean(fieldErrors.body)}
            helperText={fieldErrors.body || (tooLong ? `Messages can be at most ${MAX_LENGTH} characters.` : " ")}
            slotProps={{
              htmlInput: { "aria-required": true, style: { resize: "vertical" } },
              input: { sx: { alignItems: "flex-start", fontSize: 16, "& textarea": { lineHeight: 1.5 } } },
            }}
          />
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 1, mt: -1 }}>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, alignItems: "center" }}>
              {variables && variables.length > 0 && (
                <>
                  <Typography variant="caption">Insert:</Typography>
                  {variables.map((v) => (
                    <Chip
                      key={v.name}
                      size="small"
                      variant="outlined"
                      label={v.token}
                      title={`${v.description} — filled in for each candidate`}
                      onClick={() => insertVariable(v.token)}
                      disabled={sending}
                      sx={{ fontSize: 12, height: 22 }}
                    />
                  ))}
                </>
              )}
            </Box>
            <Typography variant="caption" sx={{ color: tooLong ? "error.main" : undefined, whiteSpace: "nowrap" }}>
              {body.length}/{MAX_LENGTH}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ mt: 3 }}>
          <FormControlLabel
            control={<Switch checked={scheduleOn} onChange={(e) => setScheduleOn(e.target.checked)} disabled={sending} />}
            label="Schedule for later"
          />
          {scheduleOn && (
            <TextField
              type="datetime-local"
              label="Send at (your local time)"
              size="small"
              value={scheduleAt}
              onChange={(e) => {
                setScheduleAt(e.target.value);
                if (fieldErrors.scheduled_at) setFieldErrors((f) => ({ ...f, scheduled_at: "" }));
              }}
              error={Boolean(fieldErrors.scheduled_at)}
              helperText={fieldErrors.scheduled_at || "Recipients will see the message at this time."}
              sx={{ mt: 1.5, display: "flex", maxWidth: 320 }}
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { min: toLocalInputValue(new Date()) } }}
            />
          )}
        </Box>
      </DrawerShell>

      <DialogShell
        open={confirming}
        title={scheduleOn ? "Schedule message?" : "Send message?"}
        onClose={() => setConfirming(false)}
        width={520}
        footer={
          <>
            <Button variant="outlined" onClick={() => setConfirming(false)}>
              Go back
            </Button>
            <Button variant="contained" onClick={send} autoFocus>
              {actionLabel}
            </Button>
          </>
        }
      >
        <Typography sx={{ fontSize: 16 }}>
          This message will be {scheduleOn ? "scheduled" : "sent"} to <b>{plural(count, "candidate")}</b>. Each
          candidate&apos;s delivery is tracked separately.
        </Typography>
        <Box sx={{ mt: 2, p: 1.5, bgcolor: "#F6F6F6", borderRadius: 1, fontSize: 14, whiteSpace: "pre-wrap", maxHeight: 160, overflow: "auto" }}>
          {trimmed}
        </Box>
      </DialogShell>
    </>
  );
}
