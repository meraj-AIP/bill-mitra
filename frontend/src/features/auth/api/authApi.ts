import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, isStatus, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import type { Discom, UnitRef } from '@/shared/api/types';

/** A unit the account works in. It covers that unit and everything under it. */
export type Scope = UnitRef;

export interface Account {
  id: string;
  /** Role slug. Never branch on it: access is decided by permissions. */
  role: string;
  role_name: string;
  permissions: string[];
  scopes: Scope[];
  login: string;
  name: string;
  /** Kept for compatibility: the DISCOM of the first scope, or null. */
  discom: Discom | null;
  active: boolean;
  /** Privacy notice version a consumer agreed to. */
  consent_version?: string | null;
  last_login_at: string | null;
  created_at: string;
}

/** Signed out is a normal state here, so a 401 resolves to null instead of failing. */
async function fetchMe(signal: AbortSignal): Promise<Account | null> {
  try {
    return await getJson<Account>('/api/auth/me', signal);
  } catch (error) {
    if (isStatus(error, 401)) return null;
    throw error;
  }
}

export function useMe() {
  return useQuery({ queryKey: queryKeys.me, queryFn: ({ signal }) => fetchMe(signal), staleTime: 5 * 60_000 });
}

function useSignedIn() {
  const client = useQueryClient();
  // Drop anything cached for the previous account before the new one sees a page.
  return (account: Account) => {
    client.removeQueries({ predicate: (q) => q.queryKey[0] !== 'auth' });
    client.setQueryData(queryKeys.me, account);
  };
}

export function useLogin() {
  const signedIn = useSignedIn();
  return useMutation({
    mutationFn: (body: { login: string; password: string }) => sendJson<Account>('/api/auth/login', body),
    onSuccess: signedIn,
  });
}

export function useRegister() {
  const signedIn = useSignedIn();
  return useMutation({
    mutationFn: (body: { name: string; mobile: string; password: string; consent: true }) => sendJson<Account>('/api/auth/register', body),
    onSuccess: signedIn,
  });
}

/**
 * A full page load, not a client-side redirect: it drops every cached screen and any open chat stream at once,
 * so nothing from the signed-out account can linger on screen.
 */
export function leaveTo(path: string): void {
  window.location.replace(path);
}

export function useLogout() {
  return useMutation({
    mutationFn: () => sendJson<void>('/api/auth/logout'),
    onSettled: () => leaveTo('/login'),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) => sendJson<void>('/api/auth/password', body),
  });
}

export interface PrivacyNotice {
  version: string;
  retention_days: number;
  contact: string | null;
  purposes: string[];
}

export function usePrivacy() {
  return useQuery({
    queryKey: queryKeys.privacy,
    queryFn: ({ signal }) => getJson<PrivacyNotice>('/api/privacy', signal),
    staleTime: Infinity,
  });
}

/** Consumers only. The server erases their data and ends the session. */
export function useDeleteMe() {
  return useMutation({
    mutationFn: () => sendJson<void>('/api/me', undefined, 'DELETE'),
    onSuccess: () => leaveTo('/login?deleted=1'),
  });
}
