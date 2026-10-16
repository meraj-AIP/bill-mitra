import { useMe } from '../api/authApi';
import { can, type Permission } from '../model/permissions';

/** The signed-in account, or null when signed out. undefined while the first check runs. */
export function useAuth() {
  const me = useMe();
  const account = me.data;
  return {
    account,
    can: (permission: Permission) => can(account, permission),
    loading: me.isPending,
    error: me.isError ? me.error : null,
    retry: () => void me.refetch(),
  };
}
