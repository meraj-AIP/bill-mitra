import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useFilePreview } from '@/shared/hooks/useFilePreview';
import type { Language } from '@/shared/lib/languages';

import { useUploadBill, validateFile } from '../api/billsApi';
import { canResend, viewOf } from '../model/upload';
import { useExtractWait } from './useExtractWait';

export interface Sending {
  /** 0 to 1, how much of the photo has reached the server. */
  progress: number;
  retrying: boolean;
  paused: boolean;
}

/**
 * The dashboard upload flow: validate, preview, send with progress, then open the saved report on its own page.
 * With returnTo (a bill uploaded for a report), it goes back to the reported bill instead.
 */
export function useBillUpload(returnTo: string | null = null) {
  const navigate = useNavigate();
  const [progress, setProgress] = useState(0);
  const upload = useUploadBill(setProgress);
  const { preview, show, clear } = useFilePreview();
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState<Language>('te');
  const [problem, setProblem] = useState<string | null>(null);
  const wait = useExtractWait(returnTo, language);

  const send = (chosen: File) => {
    setProgress(0);
    upload.mutate({ file: chosen, language }, {
      onSuccess: (outcome) => {
        if (outcome.kind === 'job') wait.setJob(outcome.job.job_id);
        // An unsaved report (not a bill, retake) stays here so the consumer can try again.
        else if (outcome.report.id) navigate(`/bills/${encodeURIComponent(returnTo ?? outcome.report.id)}?lang=${language}`);
      },
    });
  };

  const onFile = (chosen: File) => {
    const invalid = validateFile(chosen);
    setProblem(invalid);
    if (invalid) return;
    setFile(chosen);
    show(chosen);
    send(chosen);
  };

  const startOver = () => {
    upload.reset();
    clear();
    setFile(null);
    setProblem(null);
    wait.setJob(null);
    window.scrollTo({ top: 0 });
  };

  const failure = upload.error;
  const unsaved = (upload.data?.kind === 'report' && !upload.data.report.id ? upload.data.report : null) ?? wait.ended;
  const resend = file && failure && canResend(failure) ? () => send(file) : null;

  return {
    view: viewOf({ pending: upload.isPending, waiting: wait.waiting, unsaved: unsaved !== null, failedWithPhoto: Boolean(failure && preview) }),
    language,
    setLanguage,
    preview,
    sending: upload.isPending ? { progress, retrying: upload.failureCount > 0, paused: upload.isPaused } : null,
    waitCheckFailed: wait.checkFailed,
    unsaved,
    /** A file the browser refused before sending. */
    problem,
    /** The send itself failed. */
    failure,
    // Try again resends the same photo, kept with its preview.
    tryAgain: resend,
    onFile,
    startOver,
  };
}
