import { Step, StepLabel, Stepper, Typography, useMediaQuery, type Theme } from '@mui/material';

import type { MyStatus } from '../api/types';
import { MY_STATUS, STEPS, stepIndex } from '../model/status';

/** Where the complaint stands. Waiting for you is only lit when we actually asked something. */
export function StatusSteps({ status }: { status: MyStatus }) {
  const phone = useMediaQuery((t: Theme) => t.breakpoints.down('sm'));
  const active = stepIndex(status);
  const done = status === 'resolved' || status === 'closed';
  return (
    <Stepper activeStep={done ? STEPS.length : active} orientation={phone ? 'vertical' : 'horizontal'} alternativeLabel={!phone}
      aria-label="Complaint progress">
      {STEPS.map((s, i) => {
        // Skipped when we never needed to ask: shown as passed, not as something that happened.
        const skipped = s === 'waiting_for_you' && active > i && status !== 'waiting_for_you';
        const waiting = s === 'waiting_for_you' && status === 'waiting_for_you';
        const label = s === 'resolved' && status === 'closed' ? MY_STATUS.closed.label : MY_STATUS[s].label;
        return (
          <Step key={s} completed={i < active || done}>
            <StepLabel
              optional={waiting ? <Typography variant="caption" sx={{ color: 'warning.dark' }}>Please reply below</Typography> : undefined}
              sx={[skipped && { '& .MuiStepLabel-label': { color: 'text.disabled' } },
                waiting && { '& .MuiStepIcon-root.Mui-active': { color: 'warning.main' } }]}>
              {label}
            </StepLabel>
          </Step>
        );
      })}
    </Stepper>
  );
}
