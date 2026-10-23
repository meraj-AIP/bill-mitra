import { ApiError, NetworkError } from '@/shared/api/http';
import { BILL_MAX_MB, type BillFileIssue } from '@/shared/lib/billFile';
import type { Language } from '@/shared/lib/languages';

/** Why a chat turn did not get its answer: a file refused before sending, or a request that failed. */
export type ChatFailure = { kind: 'file'; issue: BillFileIssue } | { kind: 'request'; error: unknown };

interface FailureStrings {
  offline: string;
  lost: string;
  failed: string;
  busy: string;
  fileType: string;
  fileSize: string;
  history: string;
  retry: string;
  reference: string;
  unitsHint: string;
}

const MB = String(BILL_MAX_MB);

// The units example stays in English on purpose: it is the form the units parser reads in every language.
export const FAILURE_TEXT: Record<Language, FailureStrings> = {
  te: {
    offline: 'ఇంటర్నెట్ లేదు. ఏమీ పంపలేదు.',
    lost: 'జవాబు వచ్చేలోపే కనెక్షన్ పోయింది.',
    failed: 'బిల్ మిత్ర ఇప్పుడు జవాబు ఇవ్వలేకపోయింది.',
    busy: 'చాలా మెసేజ్‌లు వచ్చాయి. ఒక నిమిషం ఆగి మళ్ళీ పంపండి.',
    fileType: 'ఈ ఫైల్ పంపలేం. JPG, PNG, WEBP, HEIC ఫోటో లేదా PDF పంపండి.',
    fileSize: `ఈ ఫైల్ ${MB} MB కంటే పెద్దది. చిన్న ఫైల్ పంపండి.`,
    history: 'మీ పాత చాట్ తెరవలేకపోయాం.',
    retry: 'మళ్ళీ ప్రయత్నించండి',
    reference: 'రిఫరెన్స్',
    unitsHint: 'ఇలా టైప్ చేయండి: 214 units October 2025',
  },
  en: {
    offline: 'You are offline. Nothing was sent.',
    lost: 'The connection dropped before the reply arrived.',
    failed: 'Bill Mitra could not answer just now.',
    busy: 'Too many messages. Wait a minute, then send it again.',
    fileType: 'This file cannot be sent. Send a JPG, PNG, WEBP or HEIC photo, or a PDF.',
    fileSize: `This file is over ${MB} MB. Send a smaller one.`,
    history: 'Could not load your saved chat.',
    retry: 'Try again',
    reference: 'Reference',
    unitsHint: 'Type it like this: 214 units October 2025',
  },
  hi: {
    offline: 'इंटरनेट नहीं है। कुछ नहीं भेजा गया।',
    lost: 'जवाब आने से पहले कनेक्शन टूट गया।',
    failed: 'बिल मित्र अभी जवाब नहीं दे पाया।',
    busy: 'बहुत सारे संदेश आ गए। एक मिनट रुककर फिर भेजें।',
    fileType: 'यह फ़ाइल नहीं भेजी जा सकती। JPG, PNG, WEBP, HEIC फ़ोटो या PDF भेजें।',
    fileSize: `यह फ़ाइल ${MB} MB से बड़ी है। छोटी फ़ाइल भेजें।`,
    history: 'आपकी पुरानी चैट नहीं खुल पाई।',
    retry: 'फिर से कोशिश करें',
    reference: 'संदर्भ',
    unitsHint: 'ऐसे लिखें: 214 units October 2025',
  },
  ur: {
    offline: 'انٹرنیٹ نہیں ہے۔ کچھ نہیں بھیجا گیا۔',
    lost: 'جواب آنے سے پہلے کنکشن ٹوٹ گیا۔',
    failed: 'بل متر ابھی جواب نہیں دے سکا۔',
    busy: 'بہت زیادہ پیغام آ گئے۔ ایک منٹ رک کر دوبارہ بھیجیں۔',
    fileType: 'یہ فائل نہیں بھیجی جا سکتی۔ JPG, PNG, WEBP, HEIC تصویر یا PDF بھیجیں۔',
    fileSize: `یہ فائل ${MB} MB سے بڑی ہے۔ چھوٹی فائل بھیجیں۔`,
    history: 'آپ کی پرانی چیٹ نہیں کھل سکی۔',
    retry: 'دوبارہ کوشش کریں',
    reference: 'حوالہ',
    unitsHint: 'ایسے لکھیں: 214 units October 2025',
  },
};

const FILE_KEY = { type: 'fileType', size: 'fileSize' } as const;

function requestText(error: unknown, t: FailureStrings): string {
  if (error instanceof NetworkError) return error.sent ? t.lost : t.offline;
  if (!(error instanceof ApiError)) return t.failed;
  if (error.status === 413) return t.fileSize;
  if (error.status === 415) return t.fileType;
  if (error.status === 429) return t.busy;
  // An envelope message is written for the person, in the language the chat sent.
  if (error.status < 500 && error.code && error.serverText) return error.message;
  return t.failed;
}

/** The failure line in the chat's language. A raw JavaScript error (a dropped stream) never reaches the screen. */
export function failureLine(failure: ChatFailure, language: Language): { text: string; ref: string | null } {
  const t = FAILURE_TEXT[language];
  if (failure.kind === 'file') return { text: t[FILE_KEY[failure.issue]], ref: null };
  return { text: requestText(failure.error, t), ref: failure.error instanceof ApiError ? failure.error.ref : null };
}
