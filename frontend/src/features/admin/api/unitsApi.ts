import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, postForm, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import type { Discom, Unit, UnitKind } from '@/shared/api/types';

export interface NewUnit {
  kind: UnitKind;
  name: string;
  code?: string;
  parent_id: string;
  ero_id?: string | null;
  aliases?: string[];
}

export type UnitChanges = Partial<{ name: string; code: string | null; ero_id: string | null; aliases: string[]; active: boolean }>;

export interface ImportResult { created: number; updated: number; errors: Array<{ line: number; detail: string }> }

export interface Unmapped { name: string; discom: Discom; count: number; last_seen: string }

function useRefreshUnits() {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: queryKeys.units });
    void client.invalidateQueries({ queryKey: ['admin', 'audit'] });
  };
}

export function useCreateUnit() {
  const onSuccess = useRefreshUnits();
  return useMutation({ mutationFn: (body: NewUnit) => sendJson<Unit>('/api/admin/units', body), onSuccess });
}

export function useUpdateUnit() {
  const onSuccess = useRefreshUnits();
  return useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: UnitChanges }) =>
      sendJson<Unit>(`/api/admin/units/${encodeURIComponent(id)}`, changes, 'PATCH'),
    onSuccess,
  });
}

export function useImportUnits() {
  const onSuccess = useRefreshUnits();
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append('file', file, file.name);
      return postForm<ImportResult>('/api/admin/units/import', form);
    },
    onSuccess,
  });
}

export function useUnmapped() {
  return useQuery({
    queryKey: queryKeys.unmapped,
    queryFn: ({ signal }) => getJson<Unmapped[]>('/api/admin/units/unmapped', signal),
  });
}

export function useMapUnmapped() {
  const onSuccess = useRefreshUnits();
  return useMutation({
    mutationFn: (body: { name: string; discom: Discom; section_id: string }) => sendJson<void>('/api/admin/units/unmapped/map', body),
    onSuccess,
  });
}

export const CSV_COLUMNS = 'kind,name,code,parent_code,discom,ero_code,aliases';

/** A filled-in sample, so the person sees every column in use. Codes are made up for the template. */
export const CSV_TEMPLATE = [
  CSV_COLUMNS,
  'circle,Hyderabad Central,HYC,,TGSPDCL,,',
  'division,Banjara Hills,BJH,HYC,TGSPDCL,,',
  'ero,Banjara Hills ERO,BJH-ERO,BJH,TGSPDCL,,',
  'subdivision,Road No 12,BJH-12,BJH,TGSPDCL,,',
  'section,Film Nagar,FNR,BJH-12,TGSPDCL,BJH-ERO,FILMNAGAR;FILM NGR',
].join('\n');
