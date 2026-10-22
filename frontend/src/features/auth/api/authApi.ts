import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, isStatus, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import { IDEMPOTENT } from '@/shared/api/retry';
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

export interface DemoLogin {
  role: string;
  role_name: string;
  login: string;
}

/** Sample logins on a demo server. Always empty in production, so the sign in page shows nothing extra. */
export function useDemoLogins() {
  return useQuery({
    queryKey: ['auth', 'demo-accounts'],
    queryFn: ({ signal }) => getJson<DemoLogin[]>('/api/auth/demo-accounts', signal),
    staleTime: Infinity,
    retry: false,
  });
}

export function useLogin() {
  const signedIn = useSignedIn();
  return useMutation({ meta: { quiet: true },
    mutationFn: (body: { login: string; password: string }) => sendJson<Account>('/api/auth/login', body),
    onSuccess: signedIn,
  });
}

export type CodeChannel = 'sms' | 'whatsapp';
export type CodePurpose = 'signup' | 'login';

export interface CodeChannels {
  channels: CodeChannel[];
  /** Development only: no channel is connected, so the code is shown on the page. */
  on_screen: boolean;
  /** Where phones are sent to chat instead of signing in here. */
  whatsapp_number: string | null;
}

export interface CodeSent {
  channel: CodeChannel;
  expires_in: number;
  resend_in: number;
  /** On sign up: how many connections the DISCOM holds for the number. */
  connections: number | null;
  dev_code: string | null;
}

export interface Connection {
  discom: Discom;
  service_masked: string;
  section: string | null;
}

export function useCodeChannels() {
  return useQuery({
    queryKey: ['auth', 'code-channels'],
    queryFn: ({ signal }) => getJson<CodeChannels>('/api/auth/otp/channels', signal),
    staleTime: Infinity,
  });
}

export function useStartCode() {
  return useMutation({ meta: { quiet: true },
    mutationFn: (body: { mobile: string; purpose: CodePurpose; channel: CodeChannel; discom?: Discom }) =>
      sendJson<CodeSent>('/api/auth/otp/start', body),
  });
}

export function useSignUpWithCode() {
  const signedIn = useSignedIn();
  return useMutation({ meta: { quiet: true },
    mutationFn: (body: { mobile: string; code: string; name: string; discom: Discom; consent: true }) =>
      sendJson<Account>('/api/auth/otp/signup', body),
    onSuccess: signedIn,
  });
}

export function useSignInWithCode() {
  const signedIn = useSignedIn();
  return useMutation({ meta: { quiet: true },
    mutationFn: (body: { mobile: string; code: string }) => sendJson<Account>('/api/auth/otp/login', body),
    onSuccess: signedIn,
  });
}

export function useMyConnections(enabled: boolean) {
  return useQuery({
    queryKey: ['auth', 'connections'],
    queryFn: ({ signal }) => getJson<Connection[]>('/api/auth/connections', signal),
    enabled,
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
  return useMutation({ meta: { action: 'Signing out' },
    ...IDEMPOTENT,
    mutationFn: () => sendJson<void>('/api/auth/logout'),
    onSettled: () => leaveTo('/login'),
  });
}

export function useChangePassword() {
  return useMutation({ meta: { quiet: true, success: 'Password changed' },
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
  return useMutation({ meta: { quiet: true },
    mutationFn: () => sendJson<void>('/api/me', undefined, 'DELETE'),
    onSuccess: () => leaveTo('/login?deleted=1'),
  });
}
