"use client";

import Alert, { type AlertColor } from "@mui/material/Alert";
import Button from "@mui/material/Button";
import LinearProgress from "@mui/material/LinearProgress";
import Slide from "@mui/material/Slide";
import Stack from "@mui/material/Stack";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

export interface Toast {
  id: string;
  severity: AlertColor;
  message: ReactNode;
  action?: { label: string; onClick: () => void };
  progress?: boolean;
  /** null keeps the toast until dismissed. */
  autoHideMs?: number | null;
}

interface NotificationsApi {
  notify: (toast: Omit<Toast, "id"> & { id?: string }) => string;
  update: (id: string, patch: Partial<Omit<Toast, "id">>) => void;
  dismiss: (id: string) => void;
}

const NotificationsContext = createContext<NotificationsApi | null>(null);
let counter = 0;

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: string) => {
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
    setToasts((all) => all.filter((t) => t.id !== id));
  }, []);

  const schedule = useCallback(
    (toast: Toast) => {
      clearTimeout(timers.current.get(toast.id));
      const ms = toast.autoHideMs === undefined ? (toast.severity === "error" ? 8000 : 5000) : toast.autoHideMs;
      if (ms !== null) timers.current.set(toast.id, setTimeout(() => dismiss(toast.id), ms));
    },
    [dismiss],
  );

  const notify = useCallback<NotificationsApi["notify"]>(
    (input) => {
      const toast: Toast = { ...input, id: input.id ?? `toast-${++counter}` };
      setToasts((all) => [...all.filter((t) => t.id !== toast.id), toast].slice(-4));
      schedule(toast);
      return toast.id;
    },
    [schedule],
  );

  const update = useCallback<NotificationsApi["update"]>(
    (id, patch) => {
      setToasts((all) =>
        all.map((t) => {
          if (t.id !== id) return t;
          const next = { ...t, ...patch };
          if ("autoHideMs" in patch || "severity" in patch) schedule(next);
          return next;
        }),
      );
    },
    [schedule],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  const api = useMemo(() => ({ notify, update, dismiss }), [notify, update, dismiss]);

  return (
    <NotificationsContext.Provider value={api}>
      {children}
      <Stack
        spacing={1}
        aria-live="polite"
        sx={{ position: "fixed", right: { xs: 16, sm: 18 }, bottom: { xs: 16, sm: 20 }, zIndex: 1500, maxWidth: "min(480px, calc(100vw - 32px))" }}
      >
        {toasts.map((toast) => (
          <Slide key={toast.id} direction="left" in mountOnEnter>
            <Alert
              severity={toast.severity}
              variant="standard"
              onClose={() => dismiss(toast.id)}
              action={
                toast.action ? (
                  <Button
                    color="inherit"
                    size="small"
                    onClick={() => {
                      toast.action?.onClick();
                      dismiss(toast.id);
                    }}
                  >
                    {toast.action.label}
                  </Button>
                ) : undefined
              }
              sx={{ boxShadow: "0px 2px 8px rgba(0,0,0,0.12)", alignItems: "center", position: "relative", overflow: "hidden" }}
            >
              {toast.message}
              {toast.progress && (
                <LinearProgress color="inherit" sx={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 2, opacity: 0.6 }} />
              )}
            </Alert>
          </Slide>
        ))}
      </Stack>
    </NotificationsContext.Provider>
  );
}

export function useNotifications(): NotificationsApi {
  const context = useContext(NotificationsContext);
  if (!context) throw new Error("useNotifications must be used inside NotificationsProvider");
  return context;
}
