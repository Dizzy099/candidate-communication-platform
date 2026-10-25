"use client";

import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useLayoutEffect, useRef, useState } from "react";
import { tokens } from "@/theme/theme";

const MAX_LINES = 2;

/**
 * Design note: "The recipient chips can only flow through 2 lines. If there
 * are more, truncate with a +n suffix." Chips are measured after layout and
 * the overflow is replaced by "+ n".
 */
export function RecipientChips({ names, onRemove }: { names: string[]; onRemove?: (index: number) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(names.length);

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const measure = () => {
      const chips = Array.from(container.querySelectorAll<HTMLElement>("[data-measure-chip]"));
      const tops = [...new Set(chips.map((c) => c.offsetTop))].sort((a, b) => a - b);
      if (tops.length <= MAX_LINES) {
        setVisible(names.length);
        return;
      }
      const lastAllowedTop = tops[MAX_LINES - 1];
      const fitting = chips.filter((c) => c.offsetTop <= lastAllowedTop).length;
      setVisible(Math.max(1, fitting - 1)); // leave room for the "+ n" label
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(container);
    return () => observer.disconnect();
  }, [names]);

  const hidden = names.slice(visible);
  const chipSx = { bgcolor: tokens.recipientChip, height: 32, color: "rgba(0,0,0,0.87)" };

  return (
    <Box sx={{ position: "relative" }}>
      {/* Invisible copy used only for measuring how many chips fit in two lines. */}
      <Box ref={containerRef} aria-hidden sx={{ display: "flex", flexWrap: "wrap", gap: 1, visibility: "hidden", position: "absolute", inset: 0, height: 0, overflow: "visible" }}>
        {names.map((name, i) => (
          <Chip key={`m-${i}`} data-measure-chip label={name} sx={chipSx} onDelete={onRemove ? () => undefined : undefined} />
        ))}
      </Box>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
        {names.slice(0, visible).map((name, i) => (
          <Chip key={`${name}-${i}`} label={name} sx={chipSx} onDelete={onRemove ? () => onRemove(i) : undefined} />
        ))}
        {hidden.length > 0 && (
          <Tooltip title={hidden.join(", ")}>
            <Typography component="span" tabIndex={0} sx={{ fontSize: 13, fontFamily: "var(--font-roboto)", px: 0.5, cursor: "default" }}>
              + {hidden.length}
            </Typography>
          </Tooltip>
        )}
      </Box>
    </Box>
  );
}
