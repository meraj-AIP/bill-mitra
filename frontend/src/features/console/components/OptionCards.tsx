import { Box, ButtonBase, Typography } from '@mui/material';

export interface OptionCard { id: string; label: string; why: string }

interface OptionCardsProps {
  items: OptionCard[];
  selected: string | null;
  onSelect: (id: string) => void;
  label: string;
  disabled?: boolean;
}

/** Choices that fit this complaint, each with one line on why it fits. */
export function OptionCards({ items, selected, onSelect, label, disabled }: OptionCardsProps) {
  return (
    <Box role="radiogroup" aria-label={label} sx={{ display: 'grid', gap: 1 }}>
      {items.map((item) => {
        const on = item.id === selected;
        return (
          <ButtonBase key={item.id} role="radio" aria-checked={on} disabled={disabled} onClick={() => onSelect(item.id)}
            sx={{
              display: 'block', textAlign: 'left', p: 1.25, borderRadius: 1, border: 1,
              borderColor: on ? 'primary.main' : 'divider', bgcolor: on ? 'action.selected' : 'background.paper',
              '&:hover': { borderColor: 'primary.main' }, '&.Mui-focusVisible': { outline: 2, outlineColor: 'primary.main' },
            }}>
            <Typography variant="subtitle2" component="span" sx={{ display: 'block' }}>{item.label}</Typography>
            <Typography variant="caption" component="span" sx={{ display: 'block', color: 'text.secondary', mt: 0.25 }}>
              {item.why}
            </Typography>
          </ButtonBase>
        );
      })}
    </Box>
  );
}
