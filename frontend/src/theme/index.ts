import '@fontsource/noto-sans/400.css';
import '@fontsource/noto-sans/500.css';
import '@fontsource/noto-sans/600.css';
import '@fontsource/noto-sans/700.css';
import '@fontsource/noto-sans-telugu/400.css';
import '@fontsource/noto-sans-telugu/600.css';
import '@fontsource/noto-sans-devanagari/400.css';
import '@fontsource/noto-sans-devanagari/600.css';
import '@fontsource/noto-sans-arabic/400.css';
import '@fontsource/noto-sans-arabic/600.css';
import '@fontsource/source-serif-4/500.css';
import '@fontsource/source-serif-4/600.css';
import { createTheme } from '@mui/material/styles';

import { palette } from '@/theme/palette';

// One family stack covers every script the assistant speaks; the browser picks per glyph.
const SCRIPTS = '"Noto Sans Telugu", "Noto Sans Devanagari", "Noto Sans Arabic"';
export const FONT_STACK = `"Noto Sans", ${SCRIPTS}, system-ui, sans-serif`;
// Latin headings get an editorial serif; Telugu, Hindi and Urdu fall through to Noto.
const DISPLAY_STACK = `"Source Serif 4", ${SCRIPTS}, Georgia, serif`;

const base = createTheme({ palette, shape: { borderRadius: 8 }, spacing: 8 });
const { palette: p } = base;

export const theme = createTheme(base, {
  typography: {
    fontFamily: FONT_STACK,
    h1: { fontFamily: DISPLAY_STACK, fontSize: 'clamp(1.75rem, 1.4rem + 1.2vw, 2.375rem)', fontWeight: 600, lineHeight: 1.15, letterSpacing: '-0.015em', textWrap: 'balance' },
    h2: { fontFamily: DISPLAY_STACK, fontSize: '1.5rem', fontWeight: 600, lineHeight: 1.25, letterSpacing: '-0.01em', textWrap: 'balance' },
    h3: { fontSize: '1.0625rem', fontWeight: 600, lineHeight: 1.35 },
    h4: { fontSize: '0.9375rem', fontWeight: 600 },
    subtitle1: { fontSize: '0.9375rem', fontWeight: 600, lineHeight: 1.4 },
    subtitle2: { fontSize: '0.8125rem', fontWeight: 600 },
    body1: { fontSize: '0.9375rem', lineHeight: 1.6, textWrap: 'pretty' },
    body2: { fontSize: '0.8125rem', lineHeight: 1.55 },
    caption: { fontSize: '0.75rem', lineHeight: 1.45 },
    overline: { fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'none', lineHeight: 1.5 },
    button: { textTransform: 'none', fontWeight: 600, letterSpacing: 0 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { WebkitFontSmoothing: 'antialiased', backgroundColor: p.background.default },
        '::selection': { backgroundColor: p.info.light },
        ':focus-visible': { outline: `2px solid ${p.primary.main}`, outlineOffset: 2 },
        // No smooth scrolling on html: it made every page change glide. Jumps within a page ask for it themselves.
        '@media (prefers-reduced-motion: reduce)': {
          '*, *::before, *::after': { animationDuration: '0.01ms !important', transitionDuration: '0.01ms !important' },
        },
      },
    },
    MuiButtonBase: { defaultProps: { disableRipple: true } },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          borderRadius: 6,
          transition: 'background-color 200ms, border-color 200ms, transform 120ms',
          '&:active': { transform: 'translateY(1px)' },
          '&.Mui-focusVisible': { outline: `2px solid ${p.primary.main}`, outlineOffset: 2 },
        },
        sizeLarge: { padding: '10px 20px', fontSize: '0.9375rem' },
        outlined: { borderColor: p.grey[300], '&:hover': { borderColor: p.primary.main, backgroundColor: p.action.hover } },
      },
    },
    MuiIconButton: { styleOverrides: { root: { '&.Mui-focusVisible': { outline: `2px solid ${p.primary.main}`, outlineOffset: 2 } } } },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: { outlined: { borderColor: p.divider }, rounded: { borderRadius: 10 } },
    },
    MuiCard: { defaultProps: { variant: 'outlined' } },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 600, borderRadius: 4 },
        sizeSmall: { height: 22, fontSize: '0.71875rem' },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 8, alignItems: 'flex-start' },
        message: { width: '100%' },
      },
    },
    MuiTooltip: { defaultProps: { arrow: true } },
    MuiTab: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          fontSize: '0.875rem',
          color: p.text.secondary,
          transition: 'color 200ms',
          '&:hover': { color: p.text.primary },
          '&.Mui-selected': { color: p.primary.main },
          '&.Mui-focusVisible': { outline: `2px solid ${p.primary.main}`, outlineOffset: -2 },
        },
      },
    },
    MuiTabs: { styleOverrides: { indicator: { height: 3, borderRadius: '3px 3px 0 0' } } },
    MuiTableCell: {
      styleOverrides: {
        head: { fontWeight: 600, color: p.text.secondary, fontSize: '0.75rem', backgroundColor: p.grey[50] },
        root: { fontVariantNumeric: 'tabular-nums', borderColor: p.divider },
      },
    },
    MuiTableRow: { styleOverrides: { hover: { '&:hover': { backgroundColor: p.action.hover } } } },
    MuiLinearProgress: { styleOverrides: { root: { borderRadius: 4, backgroundColor: p.grey[200] } } },
    MuiSkeleton: { defaultProps: { animation: 'wave' } },
  },
});
