import { describeError } from './errors';
import { notify } from './store';

/** Raise a failed action as a message. `retry` is offered only when the error says trying again is safe. Returns
 * whether the screen should be reloaded (someone else acted, or an answer was lost). */
export function reportError(error: unknown, action?: string, retry?: () => void): boolean {
  const said = describeError(error, action);
  notify({ severity: said.severity, title: said.title, message: said.message, reference: said.ref,
    action: said.retry && retry ? { label: 'Try again', run: retry } : undefined });
  return said.refresh;
}
