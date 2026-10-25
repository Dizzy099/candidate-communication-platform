import { ThemeProvider } from "@mui/material/styles";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { validateCandidate } from "@/components/candidates/AddCandidateDialog";
import { outcomeMessage } from "@/components/messaging/BatchWatcher";
import { StatusChip } from "@/components/StatusChip";
import type { Batch, BatchMessage } from "@/lib/api/types";
import { theme } from "@/theme/theme";

const wrap = (ui: ReactNode) => render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);

describe("validateCandidate", () => {
  it("accepts common Indian mobile formats", () => {
    for (const phone of ["9876543210", "+91 98765 43210", "09876543210", "919876543210", "+91-98765-43210"]) {
      expect(validateCandidate({ full_name: "Priya Shah", phone, email: "p@example.com" })).toEqual({});
    }
  });

  it("flags each invalid field with guidance", () => {
    const errors = validateCandidate({ full_name: "P", phone: "12345", email: "nope" });
    expect(errors.full_name).toMatch(/full name/);
    expect(errors.phone).toMatch(/10-digit Indian mobile/);
    expect(errors.email).toMatch(/valid email/);
  });
});

function batch(summary: Partial<Batch["summary"]>, messages: Partial<BatchMessage>[] = []): Batch {
  return {
    id: "b",
    body: "Hi",
    channel: "sms",
    provider: "simulator",
    recipient_count: summary.total ?? 0,
    scheduled_at: null,
    created_at: new Date().toISOString(),
    summary: { total: 0, processing: 0, scheduled: 0, submitted: 0, delivered: 0, read: 0, failed: 0, cancelled: 0, retrying: 0, complete: true, ...summary },
    messages: messages as BatchMessage[],
  };
}

describe("outcomeMessage", () => {
  it("reports full success in the design's words", () => {
    expect(outcomeMessage(batch({ total: 5, submitted: 5 }), null)).toEqual({ severity: "success", text: "Message sent to 5 candidates" });
    expect(outcomeMessage(batch({ total: 1, submitted: 1 }), "Krishna Khandelwal").text).toBe("Message sent to Krishna Khandelwal");
  });

  it("never calls a partially failed bulk send a success", () => {
    expect(outcomeMessage(batch({ total: 5, submitted: 3, failed: 2 }), null)).toEqual({
      severity: "warning",
      text: "Message sent to 3 of 5 candidates. 2 failed.",
    });
  });

  it("explains a single failure", () => {
    const result = outcomeMessage(
      batch({ total: 1, failed: 1 }, [{ error: { title: "Invalid mobile number", category: "", code: "", explanation: "", technical_detail: "" } }]),
      "Rohit Deshmukh",
    );
    expect(result).toEqual({ severity: "error", text: "Message to Rohit Deshmukh failed: Invalid mobile number" });
  });
});

describe("StatusChip", () => {
  it("shows provider-confirmed labels", () => {
    wrap(
      <>
        <StatusChip status="read" />
        <StatusChip status="failed" />
        <StatusChip status="queued" retrying />
      </>,
    );
    expect(screen.getByText("Read")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Retrying")).toBeInTheDocument();
  });
});
