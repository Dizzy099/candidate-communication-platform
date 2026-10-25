"use client";

import CloseIcon from "@mui/icons-material/Close";
import Box from "@mui/material/Box";
import Dialog from "@mui/material/Dialog";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import { useId, type FormEvent, type ReactNode } from "react";

/** Dialog layout from the design: 40px padding, bold title + close, bordered footer. */
export function DialogShell({
  open,
  title,
  onClose,
  children,
  footer,
  onSubmit,
  busy = false,
  width = 600,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer: ReactNode;
  onSubmit?: (event: FormEvent) => void;
  busy?: boolean;
  width?: number;
}) {
  const titleId = useId();
  return (
    <Dialog
      open={open}
      onClose={busy ? undefined : onClose}
      aria-labelledby={titleId}
      slotProps={{ paper: { component: onSubmit ? "form" : "div", onSubmit, noValidate: true, sx: { width, maxWidth: "calc(100vw - 32px)", m: 2 } } as object }}
    >
      <Box sx={{ px: { xs: 3, sm: 5 }, pt: { xs: 3, sm: 5 }, pb: 3, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Typography id={titleId} variant="h2" component="h2">
          {title}
        </Typography>
        <IconButton aria-label="Close" onClick={onClose} disabled={busy} edge="end">
          <CloseIcon />
        </IconButton>
      </Box>
      <Box sx={{ px: { xs: 3, sm: 5 }, pb: 5 }}>{children}</Box>
      <Box
        sx={{
          borderTop: "1px solid #EEEEEE",
          px: { xs: 3, sm: 5 },
          py: 3.75,
          display: "flex",
          justifyContent: "flex-end",
          gap: 1.5,
        }}
      >
        {footer}
      </Box>
    </Dialog>
  );
}
