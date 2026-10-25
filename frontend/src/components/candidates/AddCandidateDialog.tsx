"use client";

import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import { useState, type ChangeEvent, type FormEvent } from "react";
import { DialogShell } from "@/components/DialogShell";
import { ApiError, errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { Candidate, NewCandidate } from "@/lib/api/types";

type Field = keyof NewCandidate;
const EMPTY: NewCandidate = { full_name: "", phone: "", email: "" };

// Quick client-side checks for instant feedback; the API remains the source of truth.
export function validateCandidate(values: NewCandidate): Partial<Record<Field, string>> {
  const errors: Partial<Record<Field, string>> = {};
  const name = values.full_name.trim().replace(/\s+/g, " ");
  if (name.length < 2) errors.full_name = "Enter the candidate's full name (at least 2 characters).";
  const digits = values.phone.replace(/[\s\-().]/g, "");
  if (!/^(?:\+91|91|0)?[6-9]\d{9}$/.test(digits)) {
    errors.phone = "Enter a valid 10-digit Indian mobile number, e.g. +91 98765 43210.";
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) {
    errors.email = "Enter a valid email address, e.g. name@example.com.";
  }
  return errors;
}

export function AddCandidateDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (candidate: Candidate) => void;
}) {
  const [values, setValues] = useState<NewCandidate>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const allFilled = Object.values(values).every((v) => v.trim().length > 0);

  function reset() {
    setValues(EMPTY);
    setErrors({});
    setFormError(null);
  }

  function close() {
    if (saving) return;
    reset();
    onClose();
  }

  function change(field: Field, value: string) {
    setValues((v) => ({ ...v, [field]: value }));
    if (errors[field]) setErrors((e) => ({ ...e, [field]: undefined }));
  }

  function blur(field: Field) {
    if (values[field].trim()) setErrors((e) => ({ ...e, [field]: validateCandidate(values)[field] }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const clientErrors = validateCandidate(values);
    if (Object.keys(clientErrors).length) {
      setErrors(clientErrors);
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const candidate = await api.createCandidate(values);
      reset();
      onCreated(candidate);
    } catch (error) {
      if (error instanceof ApiError && Object.keys(error.fields).length) {
        setErrors(error.fields as Partial<Record<Field, string>>);
      } else {
        setFormError(errorMessage(error));
      }
    } finally {
      setSaving(false);
    }
  }

  const fieldProps = (field: Field, label: string, extra: object = {}) => ({
    label,
    value: values[field],
    onChange: (e: ChangeEvent<HTMLInputElement>) => change(field, e.target.value),
    onBlur: () => blur(field),
    error: Boolean(errors[field]),
    helperText: errors[field],
    fullWidth: true,
    disabled: saving,
    slotProps: { htmlInput: { "aria-required": true } },
    ...extra,
  });

  return (
    <DialogShell
      open={open}
      title="Add Candidate"
      onClose={close}
      onSubmit={submit}
      busy={saving}
      footer={
        <>
          <Button variant="outlined" onClick={close} disabled={saving}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={!allFilled || saving}
            startIcon={saving ? <CircularProgress size={16} color="inherit" /> : undefined}
          >
            {saving ? "Adding…" : "Add candidate"}
          </Button>
        </>
      }
    >
      <Stack spacing={4}>
        {formError && <Alert severity="error">{formError}</Alert>}
        <TextField {...fieldProps("full_name", "Candidate Name *", { autoFocus: true, autoComplete: "off" })} />
        <TextField
          {...fieldProps("phone", "Mobile Number *", {
            type: "tel",
            placeholder: "+91 98765 43210",
            autoComplete: "off",
          })}
        />
        <TextField {...fieldProps("email", "Email *", { type: "email", autoComplete: "off" })} />
      </Stack>
    </DialogShell>
  );
}
