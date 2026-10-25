"use client";

import { createTheme } from "@mui/material/styles";

/**
 * Design tokens taken from the Figma file (decoded, not eyeballed):
 * Lato for app text, Roboto inside MUI controls (buttons, chips, captions),
 * contained buttons #4081DD, outlined buttons #2196F3, page #F2F2F2.
 */
export const tokens = {
  pageBackground: "#F2F2F2",
  text: "#212121",
  textMuted: "#9D9D9D",
  caption: "rgba(0, 0, 0, 0.6)",
  link: "#4081DD",
  outlinedPrimary: "#2196F3",
  tableHeader: "#F6F6F6",
  tableHeaderBorder: "#CCCCCC",
  rowBorder: "#EEEEEE",
  selectedRow: "#E3F2FD",
  inputBorder: "#CCCCCC",
  recipientChip: "#ECEFF1",
  drawerShadow: "-2px 0px 12px rgba(0, 0, 0, 0.16)",
  backdrop: "rgba(0, 0, 0, 0.12)",
} as const;

const lato = "var(--font-lato), Lato, 'Helvetica Neue', Arial, sans-serif";
const roboto = "var(--font-roboto), Roboto, 'Helvetica Neue', Arial, sans-serif";

export const theme = createTheme({
  palette: {
    primary: { main: "#4081DD", contrastText: "#FFFFFF" },
    error: { main: "#D32F2F" },
    text: { primary: tokens.text, secondary: tokens.caption },
    background: { default: tokens.pageBackground, paper: "#FFFFFF" },
    divider: tokens.rowBorder,
  },
  shape: { borderRadius: 4 },
  typography: {
    fontFamily: lato,
    h1: { fontSize: 24, fontWeight: 700, lineHeight: 1, color: "#000" },
    h2: { fontSize: 20, fontWeight: 700, lineHeight: 1.2, color: "#000" },
    h3: { fontSize: 24, fontWeight: 700, lineHeight: 1, color: "#000" },
    body1: { fontSize: 16, lineHeight: 1.2 },
    body2: { fontSize: 14, lineHeight: "26px" },
    caption: { fontFamily: roboto, fontSize: 12, letterSpacing: 0.4, color: tokens.caption },
    button: { fontFamily: roboto, fontWeight: 500, fontSize: 14, letterSpacing: 0.4, lineHeight: "24px" },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: { body: { backgroundColor: tokens.pageBackground } },
    },
    MuiButton: {
      defaultProps: { disableElevation: false },
      styleOverrides: {
        root: { padding: "6px 16px" },
        outlinedPrimary: {
          color: tokens.outlinedPrimary,
          borderColor: "rgba(33, 150, 243, 0.5)",
          "&:hover": { borderColor: tokens.outlinedPrimary, backgroundColor: "rgba(33, 150, 243, 0.04)" },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontFamily: roboto, fontSize: 13, letterSpacing: 0.16 },
      },
    },
    MuiDialog: {
      defaultProps: { slotProps: { backdrop: { sx: { backgroundColor: tokens.backdrop } } } },
      styleOverrides: { paper: { borderRadius: 0, boxShadow: "0px 8px 24px rgba(0,0,0,0.16)" } },
    },
    MuiDrawer: {
      defaultProps: { slotProps: { backdrop: { sx: { backgroundColor: tokens.backdrop } } } },
      styleOverrides: { paper: { boxShadow: tokens.drawerShadow } },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        notchedOutline: { borderColor: tokens.inputBorder },
      },
    },
    MuiAlert: {
      styleOverrides: {
        message: { fontFamily: roboto, fontWeight: 500, fontSize: 16, letterSpacing: 0.15 },
      },
    },
    MuiTooltip: {
      styleOverrides: { tooltip: { fontFamily: roboto, fontSize: 12 } },
    },
  },
});
