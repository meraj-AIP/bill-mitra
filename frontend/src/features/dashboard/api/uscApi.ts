import { useMutation, useQueryClient } from '@tanstack/react-query';

import { sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import type { Language } from '@/shared/lib/languages';

import type { BillReport } from './types';
import type { UscRequest, UscStarted } from './uscTypes';

const BASE = '/api/bills/by-usc';
const verifyBill = (body: UscRequest & { code?: string }, language: Language) =>
  sendJson<BillReport>(`${BASE}/verify?language=${language}`, body);

function useKeepReport() {
  const client = useQueryClient();
  return (report: BillReport | null, language: Language) => {
    if (!report?.id) return;
    client.setQueryData(queryKeys.bill(report.id, language), report);
    void client.invalidateQueries({ queryKey: [...queryKeys.bills, 'list'] });
  };
}

/**
 * Asks for a code. The reply never says whether the service number is known.
 * On a development server no code is needed, so the bill is fetched straight away and handed back.
 */
export function useUscStart(language: Language) {
  const keep = useKeepReport();
  return useMutation({ meta: { quiet: true },
    mutationFn: async (body: UscRequest) => {
      const started = await sendJson<UscStarted>(`${BASE}/start?language=${language}`, body);
      const report = started.code_required ? null : await verifyBill(body, language);
      return { message: started.message, report };
    },
    onSuccess: ({ report }) => keep(report, language),
  });
}

export function useUscVerify(language: Language) {
  const keep = useKeepReport();
  return useMutation({ meta: { quiet: true },
    mutationFn: (body: UscRequest & { code: string }) => verifyBill(body, language),
    onSuccess: (report) => keep(report, language),
  });
}
