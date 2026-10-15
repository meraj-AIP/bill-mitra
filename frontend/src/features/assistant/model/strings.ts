import type { Language } from '@/shared/lib/languages';

export { isRtl, LANGUAGES } from '@/shared/lib/languages';

interface PhoneStrings {
  welcome: string;
  placeholder: string;
  transcript: string;
  online: string;
  typing: string;
  attach: string;
  suggestions: [string, string];
}

/** Phone chrome strings. Message content always comes from the engine, never from here. */
export const UI: Record<Language, PhoneStrings> = {
  te: {
    welcome: 'నమస్కారం! నేను బిల్ మిత్ర. మీ కరెంటు బిల్లు ఫోటో పంపండి. బిల్లును తెలుగులో వివరిస్తాను, సరిచూస్తాను, వచ్చే నెల ఎంత రావచ్చో చెబుతాను.',
    placeholder: 'సందేశం టైప్ చేయండి',
    transcript: 'పాఠ్యం చూపించు',
    online: 'ఆన్‌లైన్',
    typing: 'టైప్ చేస్తోంది…',
    attach: 'బిల్లు ఫోటో పంపండి',
    suggestions: ['బిల్లు ఇంత ఎక్కువ ఎందుకు వచ్చింది?', 'వచ్చే నెల ఎంత రావచ్చు?'],
  },
  en: {
    welcome: 'Namaskaram! I am Bill Mitra. Send a photo of your electricity bill and I will explain it, check it and tell you what next month will cost.',
    placeholder: 'Message',
    transcript: 'Show text',
    online: 'online',
    typing: 'typing…',
    attach: 'Send a bill photo',
    suggestions: ['Why is my bill so high?', 'What will next month cost?'],
  },
  hi: {
    welcome: 'नमस्ते! मैं बिल मित्र हूँ। अपने बिजली बिल की फ़ोटो भेजिए, मैं उसे समझाऊँगा, जाँचूँगा और अगले महीने का अनुमान बताऊँगा।',
    placeholder: 'संदेश लिखें',
    transcript: 'लिखा हुआ देखें',
    online: 'ऑनलाइन',
    typing: 'लिख रहा है…',
    attach: 'बिल की फ़ोटो भेजें',
    suggestions: ['बिल इतना ज़्यादा क्यों आया?', 'बिल कब तक भरना है?'],
  },
  ur: {
    welcome: 'السلام علیکم! میں بل متر ہوں۔ اپنے بجلی بل کی تصویر بھیجیں، میں اسے سمجھاؤں گا، جانچوں گا اور اگلے مہینے کا اندازہ بتاؤں گا۔',
    placeholder: 'پیغام لکھیں',
    transcript: 'متن دیکھیں',
    online: 'آن لائن',
    typing: 'لکھ رہا ہے…',
    attach: 'بل کی تصویر بھیجیں',
    suggestions: ['بل اتنا زیادہ کیوں آیا؟', 'بل کب تک بھرنا ہے؟'],
  },
};
