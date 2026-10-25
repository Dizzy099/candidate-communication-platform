"use client";

import FilterListIcon from "@mui/icons-material/FilterList";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Link from "@mui/material/Link";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import IconButton from "@mui/material/IconButton";
import Skeleton from "@mui/material/Skeleton";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TablePagination from "@mui/material/TablePagination";
import TableRow from "@mui/material/TableRow";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useState, type MouseEvent } from "react";
import { EmptyState } from "@/components/EmptyState";
import { STATUS_STYLES, StatusChip } from "@/components/StatusChip";
import type { Candidate, MessageStatus } from "@/lib/api/types";
import { formatDate, formatTimeWithSeconds } from "@/lib/format";
import { tokens } from "@/theme/theme";

type SortableColumn = "full_name" | "phone" | "last_message_at" | "candidate_code";

const SORT_LABELS: Record<SortableColumn, [string, string]> = {
  full_name: ["Sort A → Z", "Sort Z → A"],
  phone: ["Sort ascending", "Sort descending"],
  last_message_at: ["Oldest first", "Newest first"],
  candidate_code: ["Sort A → Z", "Sort Z → A"],
};
const STATUS_FILTERS: (MessageStatus | "none")[] = ["read", "delivered", "sent", "failed", "queued", "scheduled", "none"];

export interface CandidateTableProps {
  rows: Candidate[];
  totalCount: number;
  loading: boolean;
  error: string | null;
  refreshError: boolean;
  lastUpdated: string | null;
  isFiltered: boolean;
  page: number;
  rowsPerPage: number;
  onPageChange: (page: number) => void;
  onRowsPerPageChange: (rows: number) => void;
  ordering: string;
  onOrderingChange: (ordering: string) => void;
  statusFilter: string[];
  onStatusFilterChange: (statuses: string[]) => void;
  selectedIds: Set<number>;
  onToggle: (candidate: Candidate) => void;
  onToggleAll: (checked: boolean) => void;
  onOpenHistory: (candidate: Candidate) => void;
  onRetryLoad: () => void;
  onClearFilters: () => void;
}

const headCell = {
  bgcolor: tokens.tableHeader,
  borderBottom: `1px solid ${tokens.tableHeaderBorder}`,
  height: 48,
  py: 0,
  px: 1.5,
  fontWeight: 700,
  fontSize: 14,
  color: tokens.text,
  whiteSpace: "nowrap" as const,
};
const bodyCell = { height: 42, py: 0, px: 1.5, borderBottom: `1px solid ${tokens.rowBorder}`, fontSize: 14, color: tokens.text };

function NA() {
  return <Typography component="span" sx={{ fontSize: 14, color: tokens.textMuted }}>NA</Typography>;
}

export function CandidateTable(props: CandidateTableProps) {
  const { rows, selectedIds, ordering, statusFilter } = props;
  const [menu, setMenu] = useState<{ anchor: HTMLElement; column: SortableColumn | "status" } | null>(null);

  const selectedOnPage = rows.filter((r) => selectedIds.has(r.id)).length;
  const allOnPage = rows.length > 0 && selectedOnPage === rows.length;
  const showEmpty = !props.loading && !props.error && rows.length === 0;
  const fillerRows = rows.length > 0 ? Math.max(0, Math.min(props.rowsPerPage, 10) - rows.length) : 0;

  function openMenu(event: MouseEvent<HTMLElement>, column: SortableColumn | "status") {
    setMenu({ anchor: event.currentTarget, column });
  }

  function header(label: string, column: SortableColumn | "status", width?: number | string) {
    const active = column === "status" ? statusFilter.length > 0 : ordering.replace("-", "") === column;
    return (
      <TableCell sx={{ ...headCell, width }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
          <span>{label}</span>
          <Tooltip title={column === "status" ? "Filter by status" : "Sort"}>
            <IconButton
              size="small"
              aria-label={column === "status" ? "Filter by status" : `Sort by ${label}`}
              onClick={(e) => openMenu(e, column)}
              sx={{ color: active ? "primary.main" : "rgba(0,0,0,0.54)", p: 0.5 }}
            >
              <FilterListIcon sx={{ fontSize: 20 }} />
            </IconButton>
          </Tooltip>
        </Box>
      </TableCell>
    );
  }

  const menuColumn = menu?.column;
  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <TableContainer sx={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <Table stickyHeader size="small" sx={{ minWidth: 900, tableLayout: "fixed" }} aria-label="Candidates">
          <TableHead>
            <TableRow>
              <TableCell sx={{ ...headCell, width: 56, px: 0, textAlign: "center" }}>
                <Checkbox
                  size="small"
                  checked={allOnPage}
                  indeterminate={selectedOnPage > 0 && !allOnPage}
                  disabled={rows.length === 0}
                  onChange={(e) => props.onToggleAll(e.target.checked)}
                  inputProps={{ "aria-label": "Select all candidates on this page" }}
                />
              </TableCell>
              {header("Full name", "full_name", 240)}
              {header("Mobile number", "phone")}
              {header("Last message", "last_message_at")}
              {header("Status", "status")}
              {header("Candidate ID", "candidate_code")}
            </TableRow>
          </TableHead>
          <TableBody>
            {props.loading &&
              rows.length === 0 &&
              Array.from({ length: 8 }, (_, i) => (
                <TableRow key={`skeleton-${i}`}>
                  {Array.from({ length: 6 }, (__, j) => (
                    <TableCell key={j} sx={bodyCell}>
                      <Skeleton variant="text" width={j === 0 ? 18 : "70%"} />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            {rows.map((candidate) => {
              const selected = selectedIds.has(candidate.id);
              const last = candidate.last_message;
              return (
                <TableRow
                  key={candidate.id}
                  hover
                  selected={selected}
                  sx={{ "&.Mui-selected, &.Mui-selected:hover": { bgcolor: tokens.selectedRow } }}
                >
                  <TableCell sx={{ ...bodyCell, px: 0, textAlign: "center" }}>
                    <Checkbox
                      size="small"
                      checked={selected}
                      onChange={() => props.onToggle(candidate)}
                      inputProps={{ "aria-label": `Select ${candidate.full_name}` }}
                    />
                  </TableCell>
                  <TableCell sx={{ ...bodyCell, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <Link
                      component="button"
                      type="button"
                      underline="hover"
                      onClick={() => props.onOpenHistory(candidate)}
                      title={`Open communication history for ${candidate.full_name}`}
                      sx={{ color: tokens.link, fontWeight: 700, fontSize: 14, verticalAlign: "baseline", textAlign: "left" }}
                    >
                      {candidate.full_name}
                    </Link>
                  </TableCell>
                  <TableCell sx={bodyCell}>{candidate.phone_display}</TableCell>
                  <TableCell sx={bodyCell}>{last ? formatDate(last.created_at) : <NA />}</TableCell>
                  <TableCell sx={bodyCell}>{last ? <StatusChip status={last.status} /> : <NA />}</TableCell>
                  <TableCell sx={bodyCell}>{candidate.candidate_code}</TableCell>
                </TableRow>
              );
            })}
            {Array.from({ length: fillerRows }, (_, i) => (
              <TableRow key={`filler-${i}`} aria-hidden>
                <TableCell colSpan={6} sx={bodyCell} />
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {props.error && rows.length === 0 && (
          <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
            <Alert
              severity="error"
              action={<Button color="inherit" size="small" onClick={props.onRetryLoad}>Try again</Button>}
            >
              {props.error}
            </Alert>
          </Box>
        )}
        {showEmpty &&
          (props.isFiltered ? (
            <EmptyState
              title="No matching candidates"
              description="No candidates match your search or filters."
              action={<Button variant="outlined" onClick={props.onClearFilters}>Clear search and filters</Button>}
            />
          ) : (
            <EmptyState title="No candidates added" description="When you add a candidate, they will appear here." />
          ))}
      </TableContainer>

      <Box sx={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 1, pr: 2 }}>
        <TablePagination
          component="div"
          count={props.totalCount}
          page={props.page}
          rowsPerPage={props.rowsPerPage}
          rowsPerPageOptions={[10, 25, 50]}
          onPageChange={(_, page) => props.onPageChange(page)}
          onRowsPerPageChange={(e) => props.onRowsPerPageChange(Number(e.target.value))}
          showFirstButton
          showLastButton
          sx={{
            border: 0,
            "& .MuiTablePagination-toolbar": { pl: 2 },
            "& .MuiTablePagination-spacer": { display: "none" },
            "& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows": { fontSize: 14, color: "rgba(0,0,0,0.87)" },
          }}
        />
        <Box sx={{ flex: 1 }} />
        <Typography variant="caption" aria-live="polite" sx={{ color: props.refreshError ? "error.main" : undefined }}>
          {props.refreshError
            ? "Couldn't refresh — showing the last loaded data."
            : props.lastUpdated
              ? `Statuses refresh every 4 s · updated ${formatTimeWithSeconds(props.lastUpdated)}`
              : ""}
        </Typography>
      </Box>

      <Menu anchorEl={menu?.anchor} open={Boolean(menu)} onClose={() => setMenu(null)}>
        {menuColumn && menuColumn !== "status" && [
          ...SORT_LABELS[menuColumn].map((label, index) => {
            const value = index === 0 ? menuColumn : `-${menuColumn}`;
            return (
              <MenuItem
                key={value}
                selected={ordering === value}
                onClick={() => {
                  props.onOrderingChange(value);
                  setMenu(null);
                }}
              >
                {label}
              </MenuItem>
            );
          }),
          <MenuItem
            key="clear"
            disabled={!ordering}
            onClick={() => {
              props.onOrderingChange("");
              setMenu(null);
            }}
          >
            Default order (newest added first)
          </MenuItem>,
        ]}
        {menuColumn === "status" && [
          ...STATUS_FILTERS.map((status) => {
            const checked = statusFilter.includes(status);
            return (
              <MenuItem
                key={status}
                dense
                onClick={() =>
                  props.onStatusFilterChange(checked ? statusFilter.filter((s) => s !== status) : [...statusFilter, status])
                }
              >
                <ListItemIcon>
                  <Checkbox size="small" edge="start" checked={checked} tabIndex={-1} disableRipple />
                </ListItemIcon>
                <ListItemText primary={status === "none" ? "Never messaged" : STATUS_STYLES[status].label} />
              </MenuItem>
            );
          }),
          <MenuItem key="clear" disabled={statusFilter.length === 0} onClick={() => props.onStatusFilterChange([])}>
            Clear filter
          </MenuItem>,
        ]}
      </Menu>
    </Box>
  );
}
