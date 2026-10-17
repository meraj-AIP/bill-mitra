import AddRoundedIcon from '@mui/icons-material/AddRounded';
import SupportAgentOutlinedIcon from '@mui/icons-material/SupportAgentOutlined';
import { Button, Container, MenuItem, Stack, TextField } from '@mui/material';
import { Link } from 'react-router-dom';

import { ListPanel } from '@/shared/components/ListPanel';
import { PageHeader } from '@/shared/components/PageHeader';
import { EmptyState } from '@/shared/components/States';

import { useMyComplaints } from '../api/myComplaintsApi';
import { MY_STATUSES } from '../api/types';
import { MyComplaintsList } from '../components/MyComplaintsList';
import { useMyComplaintsParams } from '../hooks/useMyComplaintsParams';
import { MY_STATUS } from '../model/status';

export function MyComplaintsPage() {
  const params = useMyComplaintsParams();
  const { query } = params;
  const result = useMyComplaints(query);
  const raise = <Button variant="contained" component={Link} to="/complaints/new" startIcon={<AddRoundedIcon />}>Raise a complaint</Button>;

  const empty = query.status ? (
    <EmptyState title={`No complaints that are ${MY_STATUS[query.status].label.toLowerCase()}`} hint="Try another status."
      action={<Button variant="outlined" onClick={() => params.setStatus('')}>Show all</Button>} />
  ) : (
    <EmptyState icon={<SupportAgentOutlinedIcon />} title="No complaints yet"
      hint="Something wrong with your bill, meter or supply? Tell us and we will look into it." action={raise} />
  );

  return (
    <Container maxWidth="md" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <PageHeader title="Complaints" lead="Raise a complaint about your bill, meter or supply, and follow it here until it is resolved." actions={raise} />
        <TextField select size="small" label="Status" value={query.status} onChange={(e) => params.setStatus(e.target.value)}
          sx={{ width: { xs: '100%', sm: 220 } }}>
          <MenuItem value="">All complaints</MenuItem>
          {MY_STATUSES.map((s) => <MenuItem key={s} value={s}>{MY_STATUS[s].label}</MenuItem>)}
        </TextField>
        <ListPanel result={result} page={query.page} pageSize={query.pageSize} onPage={params.setPage} onPageSize={params.setPageSize} empty={empty}>
          {(rows, dimmed) => <MyComplaintsList rows={rows} loadingRows={query.pageSize} dimmed={dimmed} />}
        </ListPanel>
      </Stack>
    </Container>
  );
}
