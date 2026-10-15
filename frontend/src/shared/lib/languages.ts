export type Language = 'te' | 'en' | 'hi' | 'ur';

/** Each language is labelled in its own script so a reader can find theirs. */
export const LANGUAGES: Array<{ code: Language; label: string }> = [
  { code: 'te', label: 'తెలుగు' },
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'ur', label: 'اردو' },
];

export const isRtl = (language: Language) => language === 'ur';

export function toLanguage(value: string | null): Language {
  return LANGUAGES.find((l) => l.code === value)?.code ?? 'te';
}
