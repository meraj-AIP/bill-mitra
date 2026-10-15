import { useCallback, useEffect, useRef, useState } from 'react';

export interface FilePreview {
  url: string;
  name: string;
  isPdf: boolean;
}

/** A local object URL for the chosen file, released when it is replaced or the page closes. */
export function useFilePreview() {
  const [preview, setPreview] = useState<FilePreview | null>(null);
  const current = useRef<string | null>(null);

  const release = () => {
    if (current.current) URL.revokeObjectURL(current.current);
    current.current = null;
  };

  const show = useCallback((file: File) => {
    release();
    current.current = URL.createObjectURL(file);
    setPreview({ url: current.current, name: file.name, isPdf: file.type === 'application/pdf' });
  }, []);

  const clear = useCallback(() => {
    release();
    setPreview(null);
  }, []);

  useEffect(() => release, []);

  return { preview, show, clear };
}
