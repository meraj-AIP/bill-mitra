import type { Modes } from '@/shared/api/health';

/** What each switch in /api/health means for a consumer. The status itself always comes from the API. */
export const CAPABILITIES: Array<{ key: keyof Modes; label: string; on: string; off: string }> = [
  { key: 'vision', label: 'Bill reading',
    on: 'Bill photos and PDFs are read, then every figure is checked by the rule engine.',
    off: 'Bill photos cannot be read right now. Typed questions and the tariff explorer still work.' },
  { key: 'language_model', label: 'Plain-language answers',
    on: 'The language model words the engine\'s figures. An answer with any other number is replaced by a checked template.',
    off: 'Answers use fixed, checked templates. The figures are the same, the wording is plainer.' },
  { key: 'voice', label: 'Voice notes',
    on: 'Replies come with a voice note in the consumer\'s language.',
    off: 'Replies are text only.' },
  { key: 'listening', label: 'Voice questions',
    on: 'Spoken questions are turned into text and answered like typed ones.',
    off: 'Only typed questions are understood.' },
  { key: 'whatsapp', label: 'WhatsApp',
    on: 'Consumers send bills and get replies on WhatsApp, and officer replies reach them there.',
    off: 'No WhatsApp number is connected, so only the web app is in use. Officer replies to WhatsApp complaints are saved but not delivered.' },
];

/** Modes the API reports as running. Anything else ("off", "template", "ready, not connected") is not. */
export const RUNNING = new Set(['live', 'connected']);

export const PRINCIPLES: Array<[string, string]> = [
  ['Rules calculate, AI explains', 'Every rupee comes from the TGERC tariff engine. The language model only reads the photo and puts the engine\'s figures into plain words.'],
  ['Every figure is checked', 'Before a reply goes out, each number in it is matched against the engine. If one does not match, a checked template answer is sent instead.'],
  ['We show what we read', 'Each report lists every field we looked for, whether we found it, and the checks run across them, so nothing is silently guessed.'],
  ['History from every source', 'The usage trend comes from the table printed on the bill and from bills uploaded earlier. When the DISCOM billing records are connected, they join in and are labelled as such.'],
  ['Telugu first', 'Replies are in Telugu unless the consumer picks English, Hindi or Urdu. When voice is on, a voice note comes with the text.'],
  ['Complaints stay with Bill Mitra', 'A complaint gets a BM- ticket and DISCOM officers answer it in the Bill Mitra inbox. It is not passed to 1912, so the consumer is told to call 1912 as well.'],
  ['A wrong bill goes to the right desk', 'Bill looks wrong opens a check by the section office named on the bill, with the evidence already gathered. If the bill is revised, the revised amount is what is owed.'],
  ['Each person sees their own part', 'Staff see only their unit and the units below it, and only the screens their role allows. Every decision and every change is logged with who made it.'],
];

/** Tariff parts the engine marks as assumptions until the DISCOM confirms them. */
export const VERIFY_LABEL: Record<string, string> = {
  customer_charges: 'customer charges',
  fixed_charge_per_kw: 'fixed charge',
  duty_per_unit: 'electricity duty',
  fsa_per_unit: 'FSA',
  billing_period_proration: 'stretching slabs by billing days',
};
