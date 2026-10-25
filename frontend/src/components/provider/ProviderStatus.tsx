"use client";

import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import Chip from "@mui/material/Chip";
import Collapse from "@mui/material/Collapse";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import Popover from "@mui/material/Popover";
import Switch from "@mui/material/Switch";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { useNotifications } from "@/components/Notifications";
import { useProviderHealth } from "@/hooks/data";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { channelLabel, shortProviderName } from "@/lib/channels";
import { formatTimeWithSeconds } from "@/lib/format";

const STATUS = {
  operational: { label: "Operational", color: "#2E7D32" },
  degraded: { label: "Degraded", color: "#ED6C02" },
  unavailable: { label: "Unavailable", color: "#C62828" },
  unknown: { label: "Checking…", color: "#9E9E9E" },
} as const;

export function ProviderStatus() {
  const { data, error, mutate } = useProviderHealth();
  const { notify } = useNotifications();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [showScenarios, setShowScenarios] = useState(false);
  const [toggling, setToggling] = useState(false);

  const key = error ? "unavailable" : (data?.status ?? "unknown");
  const status = STATUS[key];
  const outage = data?.status === "unavailable";

  async function toggleOutage(enabled: boolean) {
    setToggling(true);
    try {
      await api.setSimulatorOutage(enabled);
      await mutate();
      notify({
        severity: enabled ? "warning" : "success",
        message: enabled ? "Simulated provider outage started." : "Simulated provider outage ended.",
      });
    } catch (err) {
      notify({ severity: "error", message: errorMessage(err) });
    } finally {
      setToggling(false);
    }
  }

  const stats = data?.stats;
  const simulated = data?.providers.some((p) => p.simulated) ?? false;
  return (
    <>
      <ButtonBase
        onClick={(event) => setAnchor(event.currentTarget)}
        aria-label={`Messaging service status: ${status.label}. Show details`}
        sx={{ borderRadius: 16, px: 1.25, py: 0.5, gap: 0.75, border: "1px solid #E0E0E0", "&:hover": { bgcolor: "#FAFAFA" } }}
      >
        <Box component="span" sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: status.color, flexShrink: 0 }} />
        <Typography component="span" sx={{ fontSize: 13, color: "#424242", whiteSpace: "nowrap" }}>
          {simulated ? "Simulated providers" : "Providers"} · {status.label}
        </Typography>
      </ButtonBase>
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        slotProps={{ paper: { sx: { width: 340, p: 2.5, mt: 1 } } }}
      >
        <Typography sx={{ fontSize: 13, color: "rgba(0,0,0,0.6)" }}>Communication services</Typography>
        {error && (
          <Typography sx={{ fontSize: 13, mt: 1, color: "#C62828" }}>
            Couldn&apos;t check the messaging services. Messages will be retried when they&apos;re reachable.
          </Typography>
        )}
        {data?.providers.map((p) => {
          const s = STATUS[p.status] ?? STATUS.unknown;
          return (
            <Box key={p.name} sx={{ mt: 1.5 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: s.color, flexShrink: 0 }} />
                <Typography sx={{ fontWeight: 700, fontSize: 15 }}>
                  {channelLabel(p.channel)} · {shortProviderName(p.display_name)}
                </Typography>
                {p.simulated && <Chip size="small" label="Simulated" sx={{ height: 20, fontSize: 11 }} />}
              </Box>
              <Typography sx={{ fontSize: 13, ml: 2.25, color: s.color, fontWeight: 700 }}>{s.label}</Typography>
              <Typography sx={{ fontSize: 13, ml: 2.25, color: "#424242" }}>{p.detail}</Typography>
            </Box>
          );
        })}

        {stats && (
          <Box component="dl" sx={{ display: "grid", gridTemplateColumns: "1fr auto", rowGap: 0.75, mt: 2, mb: 0 }}>
            {[
              ["Messages sent", stats.sent],
              ["Messages delivered", stats.delivered],
              ["Messages read", stats.read],
              ["Messages failed", stats.failed],
              ["In progress", stats.in_progress],
              ["Scheduled", stats.scheduled],
            ].map(([label, value]) => (
              <Box key={label} sx={{ display: "contents" }}>
                <Typography component="dt" sx={{ fontSize: 14 }}>{label}</Typography>
                <Typography component="dd" sx={{ fontSize: 14, fontWeight: 700, m: 0, textAlign: "right" }}>{value}</Typography>
              </Box>
            ))}
          </Box>
        )}
        {data && (
          <Typography variant="caption" component="p" sx={{ mt: 1.5 }}>
            Checked at {formatTimeWithSeconds(data.checked_at)} · refreshes every 10 s
          </Typography>
        )}

        {simulated && data && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography sx={{ fontSize: 12, color: "rgba(0,0,0,0.6)" }}>
              This demo uses simulated providers (SimuText for SMS, SimuMail for email). No real messages are sent.
            </Typography>
            {data.scenarios.length > 0 && (
              <>
                <ButtonBase
                  onClick={() => setShowScenarios((v) => !v)}
                  aria-expanded={showScenarios}
                  sx={{ mt: 1, fontSize: 13, color: "primary.main", gap: 0.5 }}
                >
                  Test numbers for failure scenarios
                  <ExpandMoreIcon fontSize="small" sx={{ transform: showScenarios ? "rotate(180deg)" : "none", transition: "transform .2s" }} />
                </ButtonBase>
                <Collapse in={showScenarios}>
                  <Box component="ul" sx={{ pl: 2, my: 1, fontSize: 12, lineHeight: 1.6 }}>
                    {data.scenarios.map((s) => (
                      <li key={`${s.channel}-${s.match}`}>
                        <b>
                          {channelLabel(s.channel)} · {s.match}
                        </b>
                        : {s.behaviour}
                      </li>
                    ))}
                  </Box>
                </Collapse>
              </>
            )}
            {data.demo_controls_enabled && (
              <FormControlLabel
                sx={{ mt: 1, ml: 0 }}
                control={
                  <Switch size="small" checked={outage} disabled={toggling} onChange={(e) => toggleOutage(e.target.checked)} />
                }
                label={<Typography sx={{ fontSize: 13, ml: 1 }}>Simulate provider outage (demo)</Typography>}
              />
            )}
          </>
        )}
      </Popover>
    </>
  );
}
