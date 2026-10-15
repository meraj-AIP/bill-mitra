import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { Language } from '@/shared/lib/languages';

import { useUploadBill, validateFile } from '../api/billsApi';
import { useFilePreview } from './useFilePreview';

/** The dashboard upload flow: validate, preview, read, then open the saved report on its own page. */
export function useBillUpload() {
  const navigate = useNavigate();
  const upload = useUploadBill();
  const { preview, show, clear } = useFilePreview();
  const [language, setLanguage] = useState<Language>('te');
  const [problem, setProblem] = useState<string | null>(null);

  const onFile = (file: File) => {
    const invalid = validateFile(file);
    setProblem(invalid);
    if (invalid) return;
    show(file);
    upload.mutate({ file, language }, {
      onSuccess: (report) => {
        if (report.id) navigate(`/bills/${encodeURIComponent(report.id)}?lang=${language}`);
      },
    });
  };

  const startOver = () => {
    upload.reset();
    clear();
    setProblem(null);
    window.scrollTo({ top: 0 });
  };

  return {
    language,
    setLanguage,
    preview,
    reading: upload.isPending ? preview : null,
    // Only an unsaved report (not a bill, retake, reading off or failed) is shown on the dashboard itself.
    unsaved: upload.data && !upload.data.id ? upload.data : null,
    error: problem ?? upload.error?.message ?? null,
    onFile,
    startOver,
  };
}
