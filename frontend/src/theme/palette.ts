import type { PaletteOptions } from '@mui/material/styles';

declare module '@mui/material/styles' {
  interface Palette {
    chat: {
      wallpaper: string; incoming: string; outgoing: string; header: string; onHeader: string; meta: string;
      accent: string; accentDark: string; notice: string; shadow: string; elevation: string;
      tick: string; pattern: string; quickReply: string; bezel: string; bezelEdge: string; island: string;
    };
    step: { ai: string; rules: string; demo: string; channel: string };
    chart: { printed: string; uploaded: string; thisBill: string; reference: string };
  }
  interface PaletteOptions {
    chat?: Palette['chat'];
    step?: Palette['step'];
    chart?: Palette['chart'];
  }
}

// One civic ink blue carries the brand; every gray is a cool slate from the same family.
// Chat colours follow the familiar messaging look so the preview reads as the WhatsApp channel.
const ink = { main: '#163A5F', light: '#2C5A86', dark: '#0E2740', soft: '#E8EEF5' };

export const palette: PaletteOptions = {
  mode: 'light',
  primary: { main: ink.main, light: ink.light, dark: ink.dark, contrastText: '#FFFFFF' },
  secondary: { main: '#1E7A4C', light: '#4F9C74', dark: '#145536', contrastText: '#FFFFFF' },
  success: { main: '#1E7A4C', light: '#E6F2EC', dark: '#145536', contrastText: '#FFFFFF' },
  warning: { main: '#A15C00', light: '#FBF1E2', dark: '#7A4500', contrastText: '#FFFFFF' },
  error: { main: '#B42318', light: '#FBEAE8', dark: '#8A1A12', contrastText: '#FFFFFF' },
  info: { main: ink.light, light: ink.soft, dark: ink.dark, contrastText: '#FFFFFF' },
  text: { primary: '#141C27', secondary: '#525E70', disabled: '#8C96A5' },
  grey: {
    50: '#F8F9FB', 100: '#F1F3F6', 200: '#E4E8EE', 300: '#CDD3DC', 400: '#A7B0BD',
    500: '#808B9A', 600: '#5F6B7B', 700: '#465161', 800: '#2E3846', 900: '#1A222D',
  },
  divider: '#DCE1E8',
  background: { default: '#F4F5F7', paper: '#FFFFFF' },
  action: { hover: 'rgba(22, 58, 95, 0.05)', selected: 'rgba(22, 58, 95, 0.09)', focus: 'rgba(22, 58, 95, 0.14)' },
  chat: {
    wallpaper: '#EFEAE2',
    incoming: '#FFFFFF',
    outgoing: '#D9FDD3',
    header: ink.main,
    onHeader: '#FFFFFF',
    meta: '#667781',
    accent: '#1E8E5A',
    accentDark: '#156B43',
    notice: '#FDF4D3',
    shadow: '0 1px 0.5px rgba(11, 20, 26, 0.13)',
    elevation: '0 40px 80px -24px rgba(14, 39, 64, 0.38), 0 12px 24px -12px rgba(14, 39, 64, 0.22)',
    tick: '#3D9BD6',
    // Ink for the wallpaper motif; kept faint so bubbles stay the only thing that reads.
    pattern: 'rgba(22, 58, 95, 0.05)',
    quickReply: '#1F6FA8',
    bezel: '#151B23',
    bezelEdge: '#3A4452',
    island: '#05080C',
  },
  step: { ai: ink.light, rules: '#1E7A4C', demo: '#A15C00', channel: '#5F6B7B' },
  chart: { printed: '#A9BCD0', uploaded: '#5B82A8', thisBill: ink.main, reference: '#A15C00' },
};
