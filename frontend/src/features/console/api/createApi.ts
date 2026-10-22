import { useMutation, useQueryClient } from '@tanstack/react-query';

import type { ComplaintDetail, NewStaffComplaint } from '@/features/complaints';
import { sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';

/** POST /api/console/complaints. The server checks complaints.create and that the section is in scope. */
export function useCreateComplaint() {
  const client = useQueryClient();
  return useMutation({ meta: { action: 'Logging the complaint', success: 'Complaint logged' },
    mutationFn: (body: NewStaffComplaint) => sendJson<ComplaintDetail>('/api/console/complaints', body),
    onSuccess: (detail) => {
      client.setQueryData(queryKeys.consoleComplaint(detail.ticket), detail);
      void client.invalidateQueries({ queryKey: queryKeys.consoleComplaints });
      void client.invalidateQueries({ queryKey: queryKeys.consoleSummary });
    },
  });
}
