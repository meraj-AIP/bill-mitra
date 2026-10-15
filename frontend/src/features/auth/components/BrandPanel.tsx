import { Box, Stack, Typography } from '@mui/material';
import { alpha, type Theme } from '@mui/material/styles';

export const PURPOSE_TE = 'మీ కరెంటు బిల్లు, మీకు అర్థమయ్యే భాషలో';
export const PURPOSE_EN = 'Your electricity bill, in words you understand.';

// Entry motion only runs for people who have not asked the system for less motion.
export const rise = (delay: number) => ({
  '@media (prefers-reduced-motion: no-preference)': {
    animation: `bmRise 560ms cubic-bezier(0.2, 0.7, 0.2, 1) ${delay}ms both`,
  },
  '@keyframes bmRise': {
    from: { opacity: 0, transform: 'translateY(10px)' },
    to: { opacity: 1, transform: 'none' },
  },
});

const texture = (t: Theme) => ({
  bgcolor: 'primary.dark',
  backgroundImage: [
    `radial-gradient(ellipse at 88% 4%, ${alpha(t.palette.primary.light, 0.6)} 0%, transparent 58%)`,
    `radial-gradient(ellipse at 0% 100%, ${alpha(t.palette.secondary.main, 0.22)} 0%, transparent 50%)`,
    `radial-gradient(${alpha(t.palette.common.white, 0.07)} 1px, transparent 1px)`,
  ].join(', '),
  backgroundSize: 'auto, auto, 20px 20px',
});

/** Rings that spread out from a corner, like current from a source. Pure decoration. */
function Rings() {
  return (
    <Box aria-hidden sx={(t) => ({
      position: 'absolute', right: '-22%', bottom: '-30%', width: '86%', aspectRatio: '1', borderRadius: '50%',
      pointerEvents: 'none',
      backgroundImage: `repeating-radial-gradient(circle, transparent 0 38px, ${alpha(t.palette.common.white, 0.07)} 38px 39px)`,
      maskImage: 'radial-gradient(circle, black 30%, transparent 70%)',
    })} />
  );
}

export function BrandPanel() {
  return (
    <Box component="section" aria-label="About Bill Mitra"
      sx={(t) => ({ ...texture(t), position: 'relative', overflow: 'hidden', color: 'primary.contrastText',
        display: { xs: 'none', md: 'flex' }, flexDirection: 'column', px: { md: 6, lg: 8 }, py: { md: 6, lg: 7 } })}>
      <Rings />
      <Box sx={{ position: 'relative', alignSelf: 'flex-start', bgcolor: 'background.paper', borderRadius: 2, px: 2.5, py: 1.5,
        boxShadow: (t) => `0 18px 40px -18px ${alpha(t.palette.common.black, 0.55)}`, ...rise(0) }}>
        <Box component="img" src="/partners.png" width={720} height={193}
          alt="Government of Telangana, Telangana Rising and AIKAM"
          sx={{ display: 'block', height: { md: 64, lg: 76 }, width: 'auto' }} />
      </Box>
      <Stack sx={{ position: 'relative', flex: 1, justifyContent: 'center', py: 6, maxWidth: 520 }}>
        <Typography variant="overline" component="p" sx={{ color: (t) => alpha(t.palette.common.white, 0.72), ...rise(80) }}>
          Department of Energy, Government of Telangana
        </Typography>
        <Typography variant="h1" sx={{ color: 'inherit', fontSize: { md: '3rem', lg: '3.5rem' }, letterSpacing: '-0.025em', mt: 1, ...rise(140) }}>
          Bill Mitra
        </Typography>
        <Typography lang="te" component="p" sx={{ fontSize: { md: '1.375rem', lg: '1.5rem' }, fontWeight: 600, lineHeight: 1.5, mt: 2, ...rise(200) }}>
          {PURPOSE_TE}
        </Typography>
        <Typography component="p" sx={{ fontSize: '1.0625rem', color: (t) => alpha(t.palette.common.white, 0.82), mt: 0.5, ...rise(240) }}>
          {PURPOSE_EN}
        </Typography>
        <Box sx={{ width: 48, height: 3, borderRadius: 2, bgcolor: 'secondary.light', my: 3.5, ...rise(280) }} />
        <Typography component="p" sx={{ fontSize: '1rem', lineHeight: 1.7, maxWidth: '44ch', color: (t) => alpha(t.palette.common.white, 0.9), ...rise(320) }}>
          Bill Mitra reads your electricity bill, checks every charge against the TGERC tariff in force that month,
          and explains it in Telugu, English, Hindi or Urdu, on WhatsApp and the web.
        </Typography>
      </Stack>
    </Box>
  );
}

/** On a phone the brand panel folds into this header above the form. */
export function CompactBrand() {
  return (
    <Stack sx={{ display: { xs: 'flex', md: 'none' }, alignItems: 'center', textAlign: 'center', gap: 1.5, mb: 3, ...rise(0) }}>
      <Box component="img" src="/partners.png" width={720} height={193}
        alt="Government of Telangana, Telangana Rising and AIKAM"
        sx={{ width: '100%', maxWidth: 300, height: 'auto' }} />
      <Typography variant="h1" sx={{ mt: 1 }}>Bill Mitra</Typography>
      <Typography lang="te" component="p" sx={{ fontWeight: 600, fontSize: '1.0625rem', color: 'primary.main' }}>
        {PURPOSE_TE}
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mt: -1 }}>{PURPOSE_EN}</Typography>
    </Stack>
  );
}
