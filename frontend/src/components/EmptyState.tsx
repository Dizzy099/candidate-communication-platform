import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Image from "next/image";
import type { ReactNode } from "react";

/** Illustration + copy, as in the design's "No candidates" / "No communication history" screens. */
export function EmptyState({ title, description, action }: { title: string; description: ReactNode; action?: ReactNode }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", py: 6, px: 2 }}>
      <Image src="/empty-state.svg" alt="" width={220} height={220} priority />
      <Typography sx={{ mt: 1, fontSize: 18, fontWeight: 700, color: "#212121" }}>{title}</Typography>
      <Typography sx={{ mt: 1, fontSize: 16, color: "#212121", maxWidth: 400, lineHeight: 1.15 }}>{description}</Typography>
      {action && <Box sx={{ mt: 2 }}>{action}</Box>}
    </Box>
  );
}
