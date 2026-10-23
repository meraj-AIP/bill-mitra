import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import type { Language } from '@/shared/lib/languages';

import { useExtractJob } from '../api/billsApi';
import { jobEnding } from '../model/upload';

/**
 * Waits on a bill read the server queued (a 202). The job id lives in the URL, so a reload keeps waiting for the
 * same bill. When it is done the saved report opens, or returnTo when the bill was sent for another report. A read
 * that ends with nothing saved (retake, not a bill, failed) hands back a report to show here instead.
 */
export function useExtractWait(returnTo: string | null, language: Language) {
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const jobId = search.get('job');
  const job = useExtractJob(jobId);
  const done = job.data?.status === 'done' ? job.data.bill_id : null;
  const ended = jobId ? jobEnding(job.data) : null;

  useEffect(() => {
    if (done) navigate(`/bills/${encodeURIComponent(returnTo ?? done)}?lang=${language}`, { replace: true });
  }, [done, navigate, returnTo, language]);

  const setJob = (id: string | null) => setSearch((current) => {
    const next = new URLSearchParams(current);
    if (id) next.set('job', id);
    else next.delete('job');
    return next;
  }, { replace: true });

  return { waiting: jobId !== null && !ended && !done, checkFailed: job.isError, ended, setJob };
}
