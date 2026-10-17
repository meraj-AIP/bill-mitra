import PeopleOutlineIcon from '@mui/icons-material/PeopleOutlined';
import PersonAddAltOutlinedIcon from '@mui/icons-material/PersonAddAltOutlined';
import UploadFileOutlinedIcon from '@mui/icons-material/UploadFileOutlined';
import { Button, Container, MenuItem, Stack, TextField } from '@mui/material';
import { useState } from 'react';

import { useAuth, type Account } from '@/features/auth';
import { ListPanel } from '@/shared/components/ListPanel';
import { PageHeader } from '@/shared/components/PageHeader';
import { SearchField } from '@/shared/components/SearchField';
import { EmptyState } from '@/shared/components/States';

import { useAccounts } from '../api/adminApi';
import { useRoles } from '../api/rolesApi';
import { AccountsTable } from '../components/AccountsTable';
import { CreateAccountDialog } from '../components/CreateAccountDialog';
import { EditAccountDialog } from '../components/EditAccountDialog';
import { ImportAccountsDialog } from '../components/ImportAccountsDialog';
import { ResetPasswordDialog } from '../components/ResetPasswordDialog';
import { useAccountsParams } from '../hooks/useAdminParams';

type OpenDialog = { kind: 'create' | 'import' } | { kind: 'edit' | 'reset'; account: Account } | null;

function Filters({ params }: { params: ReturnType<typeof useAccountsParams> }) {
  const { query, setFilter } = params;
  const roles = useRoles();
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, flexWrap: 'wrap' }}>
      <SearchField label="Search" placeholder="Name, email or mobile" value={query.q} onChange={(v) => setFilter('q', v)} />
      <TextField select size="small" label="Role" value={query.role} onChange={(e) => setFilter('role', e.target.value)} sx={{ minWidth: 180 }}>
        <MenuItem value="">All roles</MenuItem>
        {roles.data?.map((r) => <MenuItem key={r.slug} value={r.slug}>{r.name}</MenuItem>)}
        {query.role && !roles.data && <MenuItem value={query.role}>{query.role}</MenuItem>}
      </TextField>
      <TextField select size="small" label="Status" value={query.active} onChange={(e) => setFilter('active', e.target.value)} sx={{ minWidth: 150 }}>
        <MenuItem value="">Any status</MenuItem>
        <MenuItem value="true">Active</MenuItem>
        <MenuItem value="false">Deactivated</MenuItem>
      </TextField>
    </Stack>
  );
}

export function AccountsPage() {
  const { account: me } = useAuth();
  const params = useAccountsParams();
  const { query } = params;
  const result = useAccounts(query);
  const [dialog, setDialog] = useState<OpenDialog>(null);
  const filtered = Boolean(query.role || query.active || query.q);
  const close = () => setDialog(null);

  const empty = filtered ? (
    <EmptyState icon={<PeopleOutlineIcon />} title="No accounts match these filters" hint="Try another role or status, or clear the search."
      action={<Button variant="outlined" onClick={params.clearFilters}>Clear filters</Button>} />
  ) : (
    <EmptyState icon={<PeopleOutlineIcon />} title="No accounts yet" hint="Create the first staff account to get started." />
  );

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <PageHeader eyebrow="Administration" title="Accounts"
          lead="Consumers register themselves. Staff accounts are created here, each with one role and the units it covers."
          actions={(
            <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1 }}>
              <Button variant="outlined" startIcon={<UploadFileOutlinedIcon />} onClick={() => setDialog({ kind: 'import' })}>
                Import from CSV
              </Button>
              <Button variant="contained" startIcon={<PersonAddAltOutlinedIcon />} onClick={() => setDialog({ kind: 'create' })}>
                Create staff account
              </Button>
            </Stack>
          )} />
        <Filters params={params} />
        <ListPanel result={result} page={query.page} pageSize={query.pageSize} onPage={params.setPage} onPageSize={params.setPageSize}
          empty={empty}>
          {(rows, dimmed) => (
            <AccountsTable rows={rows} loadingRows={query.pageSize} dimmed={dimmed} selfId={me?.id}
              onEdit={(account) => setDialog({ kind: 'edit', account })} onReset={(account) => setDialog({ kind: 'reset', account })} />
          )}
        </ListPanel>
      </Stack>
      <CreateAccountDialog open={dialog?.kind === 'create'} onClose={close} />
      {dialog?.kind === 'import' && <ImportAccountsDialog onClose={close} />}
      {dialog?.kind === 'edit' && (
        <EditAccountDialog key={dialog.account.id} account={dialog.account} isSelf={dialog.account.id === me?.id} onClose={close} />
      )}
      {dialog?.kind === 'reset' && <ResetPasswordDialog key={dialog.account.id} account={dialog.account} onClose={close} />}
    </Container>
  );
}
