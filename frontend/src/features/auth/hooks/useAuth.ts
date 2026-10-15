import { useMe } from '../api/authApi';

/** The signed-in account, or null when signed out. undefined while the first check runs. */
export function useAuth() {
  const me = useMe();
  const account = me.data;
  return {
    account,
    role: account?.role ?? null,
    loading: me.isPending,
    error: me.isError ? me.error : null,
    retry: () => void me.refetch(),
  };
}
