import { useNavigate } from 'react-router-dom';

import { useMarkRead } from '../api/alertsApi';
import type { AlertItem } from '../api/types';
import { alertHref } from '../model/labels';

/** Opening an alert marks it read, then goes to its case when it has one. */
export function useOpenAlert(after?: () => void) {
  const markRead = useMarkRead();
  const navigate = useNavigate();
  return (alert: AlertItem) => {
    if (!alert.read) markRead.mutate(alert.id);
    after?.();
    const href = alertHref(alert);
    if (href) navigate(href);
  };
}
