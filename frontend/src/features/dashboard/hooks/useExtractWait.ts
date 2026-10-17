import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import type { Language } from '@/shared/lib/languages';

import { useExtractJob } from '../api/billsApi';

const JOB_FAILED = 'We could not read this bill. Please try a clearer photo.';

/**
 * Waits on a bill read the server queued (a 202). The job id lives in the URL, so a reload keeps waiting for the
 * same bill. When it is done the saved report opens, or returnTo when the bill was sent for another report.
 */
export function useExtractWait(returnTo: string | null, language: Language) {
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const jobId = search.get('job');
  const job = useExtractJob(jobId);
  const done = job.data?.status === 'done' ? job.data.bill_id : null;
  const failed = job.data?.status === 'failed' ? (job.data.detail ?? JOB_FAILED) : null;

  useEffect(() => {
    if (done) navigate(`/bills/${encodeURIComponent(returnTo ?? done)}?lang=${language}`, { replace: true });
  }, [done, navigate, returnTo, language]);

  const setJob = (id: string | null) => setSearch((current) => {
    const next = new URLSearchParams(current);
    if (id) next.set('job', id);
    else next.delete('job');
    return next;
  }, { replace: true });

  return { waiting: jobId !== null && !failed && !done, checkFailed: job.isError, error: failed, setJob };
}
