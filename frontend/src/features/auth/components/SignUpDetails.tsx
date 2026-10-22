import { Button, Checkbox, CircularProgress, FormControlLabel, FormHelperText, Link as MuiLink, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { DISCOMS, type Discom } from '@/shared/api/types';

import type { useCodeFlow } from '../hooks/useCodeFlow';
import { codeProblem } from '../model/codes';
import { MOBILE_PATTERN } from '../model/roles';
import { FormError } from './AuthFrame';
import { ChannelPicker } from './ChannelPicker';
import { MobileField } from './MobileField';

export interface SignUpValues { discom: Discom | null; mobile: string; name: string; consent: boolean }
type Problems = Partial<Record<keyof SignUpValues, string>>;

function validate(v: SignUpValues): Problems {
  const problems: Problems = {};
  if (!v.discom) problems.discom = 'Choose the DISCOM that sends your bill.';
  if (!MOBILE_PATTERN.test(v.mobile)) problems.mobile = 'Enter a 10 digit mobile number starting with 6, 7, 8 or 9.';
  if (!v.name.trim()) problems.name = 'Enter your name.';
  if (!v.consent) problems.consent = 'Please read and agree to the privacy notice to continue.';
  return problems;
}

interface SignUpDetailsProps {
  values: SignUpValues;
  onChange: (values: SignUpValues) => void;
  flow: ReturnType<typeof useCodeFlow>;
}

/** The first step of signing up: which DISCOM, the number it holds for the connection, a name and consent. */
export function SignUpDetails({ values, onChange, flow }: SignUpDetailsProps) {
  const [checked, setChecked] = useState(false);
  const problems = checked ? validate(values) : {};
  const set = <K extends keyof SignUpValues>(key: K) => (value: SignUpValues[K]) => onChange({ ...values, [key]: value });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setChecked(true);
    if (Object.keys(validate(values)).length > 0 || !values.discom) return;
    flow.send({ mobile: values.mobile, purpose: 'signup', discom: values.discom });
  };
  const sending = flow.start.isPending;

  return (
    <Stack component="form" noValidate onSubmit={submit} sx={{ gap: 1.5 }} aria-busy={sending}>
      <FormError message={codeProblem(flow.start.error)} />
      <Stack sx={{ gap: 0.75 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }} id="your-discom">Your DISCOM</Typography>
        <ToggleButtonGroup exclusive fullWidth value={values.discom} aria-labelledby="your-discom"
          onChange={(_e, v: Discom | null) => v && set('discom')(v)}
          sx={{ '& .MuiToggleButton-root': { textTransform: 'none', fontWeight: 600 } }}>
          {DISCOMS.map((d) => <ToggleButton key={d} value={d} color="primary">{d}</ToggleButton>)}
        </ToggleButtonGroup>
        <FormHelperText error={Boolean(problems.discom)} sx={{ mx: 1.75 }}>
          {problems.discom ?? 'The name at the top of your electricity bill.'}
        </FormHelperText>
      </Stack>
      <MobileField label="Registered mobile number" value={values.mobile} onChange={set('mobile')} error={Boolean(problems.mobile)}
        helperText={problems.mobile ?? 'The number on your electricity connection.'} />
      <TextField label="Your name" name="name" autoComplete="name" required fullWidth value={values.name}
        onChange={(e) => set('name')(e.target.value)} error={Boolean(problems.name)} helperText={problems.name ?? ' '} />
      {flow.channels.length > 0 && <ChannelPicker channels={flow.channels} value={flow.channel} onChange={flow.pick} />}
      <FormControlLabel sx={{ alignItems: 'flex-start', mr: 0, mt: 1 }}
        control={<Checkbox checked={values.consent} sx={{ mt: -0.75 }} required onChange={(e) => set('consent')(e.target.checked)} />}
        label={
          <Typography variant="body2">
            I agree to the{' '}
            <MuiLink component={Link} to="/privacy" target="_blank" rel="noopener" sx={{ fontWeight: 600 }}>privacy notice</MuiLink>
            , which says what Bill Mitra keeps and for how long.
          </Typography>
        } />
      <FormHelperText error sx={{ mt: -0.5, minHeight: '1.25em' }}>{problems.consent ?? ' '}</FormHelperText>
      <Button type="submit" variant="contained" size="large" fullWidth disabled={sending || flow.channels.length === 0}
        startIcon={sending ? <CircularProgress size={18} color="inherit" aria-hidden /> : null} sx={{ py: 1.4 }}>
        {sending ? 'Checking your number' : 'Send code'}
      </Button>
    </Stack>
  );
}
