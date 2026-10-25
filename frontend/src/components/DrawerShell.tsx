"use client";

import CloseIcon from "@mui/icons-material/Close";
import Box from "@mui/material/Box";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import { useId, type ReactNode } from "react";

/** 660px right-hand side panel from the design (Send Message, Communication history). */
export function DrawerShell({
  open,
  title,
  onClose,
  children,
  footer,
  busy = false,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  busy?: boolean;
}) {
  const titleId = useId();
  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={busy ? undefined : onClose}
      slotProps={{ paper: { sx: { width: { xs: "100%", sm: 660 } }, role: "dialog", "aria-labelledby": titleId } as object }}
    >
      <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <Box sx={{ px: { xs: 3, sm: 5 }, pt: { xs: 3, sm: 4.5 }, pb: 2, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Typography id={titleId} variant="h2" component="h2">
            {title}
          </Typography>
          <IconButton aria-label="Close" onClick={onClose} disabled={busy} edge="end">
            <CloseIcon />
          </IconButton>
        </Box>
        <Box sx={{ flex: 1, overflowY: "auto", px: { xs: 3, sm: 5 }, pb: 4 }}>{children}</Box>
        {footer && (
          <Box
            sx={{
              borderTop: "1px solid #EEEEEE",
              minHeight: 96,
              px: { xs: 3, sm: 5 },
              py: 2,
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              gap: 1.5,
              flexWrap: "wrap",
            }}
          >
            {footer}
          </Box>
        )}
      </Box>
    </Drawer>
  );
}
