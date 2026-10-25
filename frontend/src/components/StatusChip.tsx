"use client";

import BlockIcon from "@mui/icons-material/Block";
import CheckIcon from "@mui/icons-material/Check";
import DoneAllIcon from "@mui/icons-material/DoneAll";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import ReplayIcon from "@mui/icons-material/Replay";
import ScheduleIcon from "@mui/icons-material/Schedule";
import Chip from "@mui/material/Chip";
import Tooltip from "@mui/material/Tooltip";
import type { SvgIconComponent } from "@mui/icons-material";
import type { MessageStatus } from "@/lib/api/types";

interface ChipStyle {
  label: string;
  bg: string;
  fg: string;
  Icon?: SvgIconComponent;
  hint: string;
}

// Read / Failed / Sent colours come from the design; the rest extend the same palette.
export const STATUS_STYLES: Record<MessageStatus | "retrying", ChipStyle> = {
  read: { label: "Read", bg: "#E8F5E9", fg: "#2E7D32", Icon: CheckIcon, hint: "The provider confirmed the candidate read it." },
  delivered: { label: "Delivered", bg: "#E0F2F1", fg: "#00695C", Icon: DoneAllIcon, hint: "The provider confirmed delivery to the phone." },
  sent: { label: "Sent", bg: "#E3F2FD", fg: "#1565C0", hint: "Accepted by the provider; waiting for delivery confirmation." },
  failed: { label: "Failed", bg: "#FEEBEE", fg: "#C62828", Icon: ErrorOutlineIcon, hint: "The message could not be sent or delivered." },
  queued: { label: "Queued", bg: "#F5F5F5", fg: "#616161", Icon: HourglassEmptyIcon, hint: "Saved and waiting to be handed to the provider." },
  sending: { label: "Sending", bg: "#F5F5F5", fg: "#616161", Icon: HourglassEmptyIcon, hint: "Being handed to the provider right now." },
  retrying: { label: "Retrying", bg: "#FFF3E0", fg: "#E65100", Icon: ReplayIcon, hint: "A temporary problem occurred; the platform will retry automatically." },
  scheduled: { label: "Scheduled", bg: "#F3E5F5", fg: "#7B1FA2", Icon: ScheduleIcon, hint: "Will be sent at the scheduled time." },
  cancelled: { label: "Cancelled", bg: "#F5F5F5", fg: "#757575", Icon: BlockIcon, hint: "The scheduled message was cancelled." },
};

export function StatusChip({ status, retrying = false }: { status: MessageStatus; retrying?: boolean }) {
  const style = STATUS_STYLES[retrying && status === "queued" ? "retrying" : status];
  const Icon = style.Icon;
  return (
    <Tooltip title={style.hint} arrow>
      <Chip
        size="small"
        label={style.label}
        icon={Icon ? <Icon /> : undefined}
        sx={{
          height: 24,
          bgcolor: style.bg,
          color: style.fg,
          fontFamily: "var(--font-lato), Lato, sans-serif",
          fontSize: 13,
          letterSpacing: 0.16,
          borderRadius: "100px",
          "& .MuiChip-icon": { color: style.fg, fontSize: 16, ml: "6px", mr: "-2px" },
          "& .MuiChip-label": { px: "10px" },
        }}
      />
    </Tooltip>
  );
}
