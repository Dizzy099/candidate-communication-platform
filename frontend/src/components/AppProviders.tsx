"use client";

import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider } from "@mui/material/styles";
import type { ReactNode } from "react";
import { SWRConfig } from "swr";
import { NotificationsProvider } from "@/components/Notifications";
import { theme } from "@/theme/theme";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <SWRConfig value={{ revalidateOnFocus: true, errorRetryCount: 2, keepPreviousData: true }}>
        <NotificationsProvider>{children}</NotificationsProvider>
      </SWRConfig>
    </ThemeProvider>
  );
}
