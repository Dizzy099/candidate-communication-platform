"use client";

import ClearIcon from "@mui/icons-material/Clear";
import SearchIcon from "@mui/icons-material/Search";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { ProviderStatus } from "@/components/provider/ProviderStatus";

export function PageHeader({
  search,
  onSearchChange,
  selectedCount,
  onAdd,
  onDelete,
  onSend,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  selectedCount: number;
  onAdd: () => void;
  onDelete: () => void;
  onSend: () => void;
}) {
  const nothingSelected = selectedCount === 0;
  return (
    <Box
      component="header"
      sx={{
        bgcolor: "#fff",
        minHeight: 72,
        px: 3,
        py: { xs: 1.5, md: 0 },
        display: "flex",
        alignItems: "center",
        gap: 2,
        flexWrap: "wrap",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap", mr: "auto" }}>
        <Typography variant="h1" component="h1">
          Candidate communication
        </Typography>
        <ProviderStatus />
      </Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
        <Button variant="outlined" onClick={onAdd} sx={{ px: 4 }}>
          Add candidate
        </Button>
        <Button variant="contained" onClick={onDelete} disabled={nothingSelected} sx={{ px: 4 }}>
          Delete candidate
        </Button>
        <Button variant="contained" onClick={onSend} disabled={nothingSelected} sx={{ px: 4 }}>
          Send message
        </Button>
        <TextField
          size="small"
          placeholder="Search"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          sx={{ width: { xs: "100%", sm: 240 }, "& .MuiInputBase-root": { height: 40, fontSize: 14 } }}
          slotProps={{
            htmlInput: { "aria-label": "Search candidates by name, mobile, email or ID" },
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ fontSize: 18, color: "#717171" }} />
                </InputAdornment>
              ),
              endAdornment: search ? (
                <InputAdornment position="end">
                  <IconButton size="small" aria-label="Clear search" onClick={() => onSearchChange("")} edge="end">
                    <ClearIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                </InputAdornment>
              ) : undefined,
            },
          }}
        />
      </Box>
    </Box>
  );
}
