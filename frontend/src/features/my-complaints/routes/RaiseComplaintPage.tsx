import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { Box, Button, Container, Paper, Stack } from '@mui/material';
import { Link, useSearchParams } from 'react-router-dom';

import { PageHeader } from '@/shared/components/PageHeader';

import { RaiseForm } from '../components/RaiseForm';

export function RaiseComplaintPage() {
  const [search] = useSearchParams();
  return (
    <Container maxWidth="md" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <Box>
          <Button component={Link} to="/complaints" startIcon={<ArrowBackIcon />} size="small" sx={{ ml: -1, mb: 1 }}>Your complaints</Button>
          <PageHeader title="Raise a complaint" lead="Tell us what is wrong. You get a ticket number straight away and our replies show on the complaint page." />
        </Box>
        <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
          <RaiseForm initialBill={search.get('bill')} />
        </Paper>
      </Stack>
    </Container>
  );
}
