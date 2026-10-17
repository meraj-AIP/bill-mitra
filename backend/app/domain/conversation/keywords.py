"""Word lists the message rules read, grouped by meaning, in English, Telugu (script and romanised), Hindi and Urdu.

Each entry is a small regex fragment. Latin fragments match whole words only (a trailing `*` allows an ending, so
`complain*` covers complaint and complaining). Telugu, Hindi and Urdu fragments must start a word but may run on,
because those languages add endings to the word itself (బిల్లులో, बिलों).
"""

import re
import unicodedata

# Spelling variants folded away before matching: Hindi nukta and chandrabindu, Telugu joiners, Arabic letter forms.
_FOLD = str.maketrans({"‌": None, "‍": None, "़": None, "ँ": "ं", "ي": "ی",
                       "ك": "ک", "’": "'", "‘": "'", "؟": "?", "۔": "."}
                      | {chr(c): None for c in range(0x064B, 0x0660)})
_SPACES = re.compile(r"[\s\-_‐-―]+")
_STARTS_WORD = r"(?<![^\s.,!?;:।॥۔،\"'()\[\]/])"


def fold(value: str) -> str:
    return unicodedata.normalize("NFC", value).lower().translate(_FOLD)


def normalise(message: str) -> str:
    return _SPACES.sub(" ", fold(message)).strip()


def _bounded(fragment: str) -> str:
    # Fragments are written in lower case already; lower() here would turn a regex \S into \s.
    frag = unicodedata.normalize("NFC", fragment).translate(_FOLD).replace(" ", r"\s+")
    first = next((c for c in frag if c.isalpha()), "a")
    if first.isascii():
        return r"(?<![a-z0-9'])" + re.sub(r"(?<=[a-z)])\*", "[a-z']*", frag) + r"(?![a-z0-9])"
    return _STARTS_WORD + frag


def rx(*fragments: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{_bounded(f)})" for f in fragments))


WRONG = ("wrong", "incorrect", "not correct", "mistake*", "galat", "tappu*", "thappu*", "తప్పు", "गलत", "غلط")
COMPLAINT_WORDS = ("complain*", "complan*", "grievance", "firyadu", "phiryadu", "ఫిర్యాదు", "shikayat", "शिकायत",
                   "شکایت")

# Exact words only, so "don't stop the supply" is not read as a request to delete data.
STOP = {"stop", "ఆపండి", "ఆపు", "रोको", "बंद करो", "بند کرو", "روکو"}
WHAT_IF = rx("what if", "if i use", "if we use", "suppose i use", "వాడితే", "vadite", "vaadithe", "इस्तेमाल करूं",
             "use karun", "استعمال کروں")

# "don't want to complain", "no complaint", ఫిర్యాదు వద్దు, शिकायत नहीं करनी, کوئی شکایت نہیں.
NEG_COMPLAINT = re.compile("|".join((
    r"(?<![a-z])(?:no|not|don'?t|do not|never|no need to|nothing to)(?:\s+(?:want|wanna|to|raise|file|make|a|any|"
    r"need|register|lodge|filing|raising|making|i|am|this|is|just|it'?s|mean|really))*\s+(?:complain|grievance)",
    r"(?<![a-z])(?:complaint|firyadu|phiryadu|shikayat)\s+(?:vaddu|kadu|ledu|cheyanu|nahi|nahin|mat)(?![a-z])",
    r"ఫిర్యాదు\S*\s+(?:(?:చేయడం|ఇవ్వడం|చేయాలని|ఇవ్వాలని|చేసే)\s+)?(?:వద్దు|కాదు|లేదు|చేయను|ఇవ్వను|అక్కర్లేదు|అవసరం లేదు)",
    r"शिकायत\s+(?:(?:करनी|करना|दर्ज|करवानी)\s+)?(?:नहीं|मत)", r"कोई\s+शिकायत",
    r"شکایت\s+(?:(?:کرنی|کرنا|درج)\s+)?(?:نہیں|مت)", r"کوئی\s+شکایت",
)))
COMPLAINT = rx(*COMPLAINT_WORDS, "raise a ticket", "lodge a ticket")

METER = rx("meter*", "మీటర్", "मीटर", "میٹر")
BURN = rx("burn*", "fire", "smoke", "melt*", "spark*", "blast*", "short circuit", "కాలిపోయ", "కాలిన", "కాలింది",
          "మంట", "పొగ", "నిప్పు", "స్పార్క్", "పేలి", "kalipoy*", "kaalipoy*", "kalipoindi", "kaalindi", "kalindi",
          "mantalu", "manta", "poga", "jal gaya", "jal gya", "jala", "aag", r"जल(?!\S*\s+नहीं)", "आग", "धुआं",
          "चिंगारी", "स्पार्क", r"جل(?!\S*\s+نہیں)", "آگ", "دھواں", "چنگاری", "اسپارک")

PAID = rx("paid", "payment (is |was )?(done|made|completed|successful)", "already paid",
          "transaction (was )?(successful|done|completed)", "కట్టాను", "కట్టేశాను", "కట్టేసాను", "కట్టిన", "కట్టినా",
          "చెల్లించాను", "చెల్లించిన", "పే చేశాను", "పే చేసాను", "kattanu", "kattesanu", "kattesa", "kattina",
          "pay chesanu", "pay chesa", "payment chesanu", "bhar diya", "payment kar diya", "jama kar diya",
          "भुगतान कर दिया", "भुगतान किया", "पेमेंट कर दिया", "पेमेंट किया", "पेमेंट की", "भर दिया", "जमा कर दिया",
          "जमा किया", "चुका दिया", "पैसे कट", "ادا کر دیا", "ادا کیا", "ادائیگی کر دی", "ادائیگی کی", "پیمنٹ کر دی",
          "پیمنٹ کی", "بھر دیا", "جمع کر دیا", "جمع کرا دیا", "پیسے کٹ")
NOT_SHOWN = rx("not (yet )?(updated|showing|shown|reflect*|credited|posted|received|update*)", "no update",
               "still (showing|shows|show) (as )?(due|pending|unpaid|the amount|full amount|old)", "still pending",
               "still due", "showing (as )?(due|unpaid|pending)", "(asking|asked) (me )?(to pay )?again",
               "pay again", "still show*", "అప్‌డేట్ కాలేదు", "అప్డేట్ కాలేదు", "చూపించడం లేదు", "చూపించట్లేదు", "చూపిస్తలేదు",
               "పడలేదు", "జమ కాలేదు", "ఇంకా బాకీ", "మళ్లీ కట్టమ", "పెండింగ్", "update kaledu", "update avvaledu",
               "chupinchatledu", "chupistaledu", "chupinchadam ledu", "padaledu", "pending", "malli kattamani",
               "inka baaki", "update nahi", "dikh nahi", "nahi dikha", "nahi dikh", "अपडेट नहीं", "नहीं दिख",
               "दिखा नहीं", "अभी भी बाकी", "बकाया दिखा", "पेंडिंग", "जमा नहीं हुआ", "फिर से भरने", "اپڈیٹ نہیں",
               "اپ ڈیٹ نہیں", "نہیں دکھ", "دکھا نہیں", "ابھی بھی باقی", "پینڈنگ", "جمع نہیں ہوا", "دوبارہ بھرنے")
DEBITED = rx("(amount|money|rs|rupees|paisa|paise) (was |got |is |has been )?(debited|deducted|cut)", "debited",
             "deducted", "డబ్బులు కట్", "పైసలు కట్", "paise kat gaye", "पैसे कट गए", "پیسے کٹ گئے")
PAY_APP = rx("phone ?pe", "g ?pay", "google pay", "paytm", "bhim", "upi", "amazon pay", "t ?wallet", "mee ?seva",
             "net ?banking", "utr", "transaction id", "ఫోన్‌పే", "ఫోన్ పే", "గూగుల్ పే", "పేటీఎం", "फोनपे",
             "फोन पे", "पेटीएम", "गूगल पे", "فون پے", "گوگل پے", "پے ٹی ایم")

CATEGORY = rx("categor*", "categery", "tariff class", "commercial", "non domestic", "lt ?2", "lt ?ii", "load",
              "sanctioned load", "contracted load", "కేటగిరీ", "కమర్షియల్", "లోడ్", "श्रेणी", "कैटेगरी", "कमर्शियल",
              "लोड", "کیٹیگری", "زمرہ", "کمرشل", "لوڈ")
CATEGORY_WRONG = rx(*WRONG, "change", "should be", "instead of", "(charged|billed|put|shown) as", "but (it is|we are|this is)",
                    "for (a |my )?(house|home)", "domestic", "vesaru", "వేశారు", "మార్చ", "ఇంటికి", "ఇల్లు",
                    "lagaya", "लगा दिया", "बदल", "گھر", "بدل", "لگا دیا")

ARREARS = rx("arrear*", "old dues", "previous dues", "past dues", "old balance", "previous balance",
             "old (pending )?amount", "outstanding", "dues", "బకాయి", "పాత బాకీ", "బాకీ", "bakayi*", "baaki", "baki",
             "paata baki", "बकाया", "arrears", "بقایا", "پرانا بقایا")
ARREARS_WRONG = rx(*WRONG, "again", "already paid", "paid", "not (mine|ours)", "never", "extra", "added",
                   "మళ్లీ", "కట్టాను", "కలిపారు", "వేశారు", "malli", "kattanu", "phir se", "दोबारा", "फिर से", "जोड़",
                   "भर दिया", "دوبارہ", "پھر سے", "جوڑ", "ادا کر دیا")

ESTIMATED = rx("estimat*", "average bill", "avg bill", "meter (was )?not read", "not read (the |my )?meter",
               "no ?(one|body) (came|come|comes) (to read|for reading)", "reader (did not|didn't|never|not) (come|came)",
               "without (taking )?(the )?reading", "reading (was )?not taken", "door lock*", "అంచనా", "సగటు బిల్లు",
               "రీడింగ్ తీయలేదు", "రీడింగ్ తీసుకోలేదు", "మీటర్ చూడలేదు", "ఎవరూ రాలేదు", "reading teeyaledu",
               "reading tiyaledu", "evaru raledu", "anchana", "अनुमानित", "औसत बिल", "एवरेज बिल", "रीडिंग नहीं ली",
               "कोई नहीं आया", "reading nahi li", "koi nahi aaya", "اندازے", "تخمینہ", "اوسط بل", "ایوریج بل",
               "ریڈنگ نہیں لی", "کوئی نہیں آیا")

READING = rx("reading*", "misread*", "రీడింగ్", "रीडिंग", "ریڈنگ")
READING_WRONG = rx(*WRONG, "misread*", "more than (the )?meter", "less than (the )?meter", "read (it )?wrong",
                   "ఎక్కువ రాశారు", "ఎక్కువ వేశారు", "సరిగ్గా లేదు", "correct ga ledu", "sariga ledu", "ज्यादा लिखी", "ज्यादा लिखा", "زیادہ لکھی")

BILL_NOT_RECEIVED = rx(
    "(did not|didn't|didnt|not|never|haven't|havent|have not|no|dont|don't) (yet )?(get|got|receive*|come|came) "
    "(my |the |this month'?s |this months |any |a )?(electricity |current )?bill",
    "bill (has |is |was )?(not|never|didn't|did not|hasn't|has not) (yet )?(come|came|received|arrived|delivered|given|"
    "generated|issued)", "no bill (this month|came|yet)", "bill (did not|didn't) reach", "where is (my|this month'?s) bill",
    "బిల్లు రాలేదు", "బిల్ రాలేదు", "బిల్లు ఇవ్వలేదు", "బిల్లు అందలేదు", "బిల్లు ఇంకా రాలేదు", "bill raledu",
    "billu raledu", "bill ivvaledu", "bill inka raledu", "bill andaledu", "bill nahi aaya", "bill nahi mila",
    "बिल नहीं आया", "बिल नहीं मिला", "बिल अभी तक नहीं", "बिल नहीं दिया", "بل نہیں آیا", "بل نہیں ملا",
    "بل ابھی تک نہیں")

VOLTAGE = rx("volt*", "fluctuat*", "dim light*", "lights? (are |is )?(dim*|flicker*)", "flicker*", "brown ?out",
             "fans? (is |are )?(running |moving )?(very )?slow*", "stabili[sz]er", "tube ?light (is )?not (starting|glowing)",
             "వోల్టేజ్", "వోల్టేజి", "లైట్లు డిమ్", "ఫ్యాన్ స్లో", "ఫ్యాన్లు నెమ్మదిగా", "ఫ్యాన్ నెమ్మదిగా", "లో వోల్టేజ్",
             "fan slow", "current takkuva", "वोल्टेज", "बिजली कम आ रही", "लाइट धीमी", "पंखा धीरे", "وولٹیج",
             "پنکھا آہستہ", "بجلی کم آ رہی")

FREQUENT = rx("frequent*", "again and again", "every (day|hour|night|evening|few minutes)", "daily", "repeated*",
              "many times", "on and off", "keeps? (going|cutting|tripping)", "(10|ten|several|many) times",
              "మాటిమాటికీ", "మళ్లీ మళ్లీ", "పదే పదే", "రోజూ", "రోజుకు", "తరచూ", "తరచుగా", "malli malli",
              "maatimaatiki", "matimatiki", "prati roju", "prathi roju", "pade pade", "bar bar", "baar baar", "बार बार", "रोज", "हर रोज",
              "कई बार", "بار بار", "روز", "کئی بار")
CUTS = rx("power cut*", "cuts", "(power|current|electricity|light) (goes|going|went|keeps going) (off|out)?",
          "load shedding", "power off", "outage*", "tripp*", "trips", "కరెంటు పో", "కరెంట్ పో", "కరెంటు కట్", "కట్ అవుతో",
          "కోత", "పోతోంది", "పోతుంది", "potundi", "pothundi", "potondi", "pothondi", "current po*", "karent po*", "current cut", "bijli (chali|jati|kat)", "light (chali|jati)",
          "बिजली (चली|जाती|कट)", "कटौती", "लाइट (चली|जाती|कट)", "بجلی (چلی|جاتی|کٹ)", "کٹوتی", "لائٹ (چلی|جاتی)")
# On and off through the day: a supply problem, not an outage happening now.
INTERMITTENT = rx("comes and goes", "on and off", "on off", "coming and going", "వస్తూ పోతూ", "వస్తా పోతా",
                  "vastu potu", "vasthu pothu", "aati jaati", "aata jaata", "आती जाती", "आता जाता", "آتی جاتی",
                  "آتا جاتا", "roju (sayantram|ratri|raatri|poddunna)", "రోజూ (సాయంత్రం|రాత్రి)", "روز شام", "روز رات",
                  "रोज शाम", "रोज रात")
PHASE = rx("one phase", "single phase (only|not|missing)", "phase (is )?(missing|gone|not coming|problem)",
           "two phases?", "neutral", "phase (not|nahi|ledu|raledu)", "ఒక ఫేజ్", "ఫేజ్", "phase raledu", "एक फेज", "फेज", "ایک فیز", "فیز")

OUTAGE = rx("no (power|current|electricity|supply|light)(?! cut)", "(power|current|electricity|supply|light) (is |has )?"
            "(off|gone|out|cut|down|not there|not coming|not come|not came|went)", "power outage", "outage",
            "blackout", "without (power|electricity|current)", "dark since", "don'?t have (power|current|electricity)",
            "lights? (are |is )?(off|out|gone)", "power (failure|failed)", "transformer (burst|blast*|failed|gone|burnt|"
            "repair*|problem)", "power has gone", "current ledu", "karent ledu", "current poyindi", "karent poyindi",
            "current raledu", "current ravatledu", "current ravadam ledu", "power ledu", "current leka", "current lekunda",
            "current poi", "(power|current|electricity|light|bijli) (since|from) (morning|last night|yesterday|evening)",
            "(bijli|light|current) kab (aayegi|aaegi|ayegi|aayega)", "ghante ho gaye", "ghante se", "current eppudu vast*",
            "बिजली कब आ", "लाइट कब आ", "घंटे हो गए", "घंटे से", "కరెంటు ఎప్పుడు వస్తుంది", "కరెంట్ ఎప్పుడు వస్తుంది",
            "بجلی کب آ", "لائٹ کب آ", "گھنٹے ہو گئے", "گھنٹے سے", "కరెంటు లేదు", "కరెంట్ లేదు", "కరెంటు పోయ", "కరెంట్ పోయ", "కరెంటు రాలేదు", "కరెంట్ రాలేదు",
            "కరెంటు రావడం లేదు", "కరెంట్ రావట్లేదు", "కరెంటు రావట్లేదు", "కరెంటు కట్", "పవర్ కట్", "పవర్ లేదు",
            "సరఫరా లేదు", "కరెంటు లేక", "కరెంట్ లేక", "చీకట్లో", "ట్రాన్స్‌ఫార్మర్", "bijli nahi", "bijli gayi",
            "bijli chali gayi", "light nahi", "light gayi", "light chali gayi", "current nahi", "bijli gul", "बिजली नहीं",
            "बिजली गई", "बिजली चली गई", "बिजली गुल", "लाइट नहीं", "लाइट गई", "लाइट चली गई", "बत्ती गुल", "करंट नहीं",
            "बिजली कटी", "अंधेरा", "بجلی نہیں", "بجلی گئی", "بجلی چلی گئی", "بجلی غائب", "لائٹ نہیں", "لائٹ گئی",
            "لائٹ چلی گئی", "کرنٹ نہیں", "اندھیرا")

METER_FAULT = rx("not working", "stopped", "stuck", "dead", "blank", "display (is )?(off|gone|not)", "no display",
                 "(running|runs|rotating|spinning) (very )?(fast|too fast|quick*)", "fast", "faulty", "defective",
                 "jump*", "not moving", "slow", "broken", "damaged", "beep*", "blink*", "red light", "not recording",
                 "పని చేయడం లేదు", "పనిచేయడం లేదు", "పని చేయట్లేదు", "ఆగిపోయ", "తిరగడం లేదు", "వేగంగా", "ఫాస్ట్",
                 "స్పీడ్", "డిస్‌ప్లే", "డిస్ప్లే", "పాడైపోయ", "పాడైంది", "పాడయ్యింది", "చెడిపోయ", "ఖరాబ్", "రిపేర్",
                 "pani cheyatledu", "pani cheyyatledu", "panicheyyatledu", "aagipoyindi", "agipoyindi", "fast ga",
                 "speed ga", "padaipoyindi", "chedipoyindi", "kharab", "repair", "kaam nahi", "band ho gaya", "tez",
                 "काम नहीं", "बंद हो गया", "बंद पड़ा", "रुक गया", "तेज", "खराब", "डिस्प्ले", "फास्ट", "जंप",
                 "ठीक से नहीं", "کام نہیں", "بند ہو گیا", "رک گیا", "تیز", "خراب", "ڈسپلے", "فاسٹ")

HIGH = rx("high", "too much", "so much", "very much", "huge", "excess*", "inflated", "overcharg*", "over charg*",
          "charged (too much|more|extra)", "double*", "tripled", "increase*", "gone up", "shot up", "jumped",
          "more than (usual|normal|last month|every month|before)", "bill (is |looks )?(wrong|incorrect|not correct)",
          "wrong bill", "incorrect bill", "ఎక్కువ", "బిల్లు తప్పు", "తప్పు బిల్లు", "తప్పుగా వచ్చింది", "రెట్టింపు",
          "డబుల్", "పెరిగింది", "ఇంత బిల్లు", "ekkuva", "intha bill", "perigindi", "bill tappu", "zyada", "jyada",
          "bill galat", "ज्यादा", "बिल गलत", "गलत बिल", "दोगुना", "डबल", "बढ गया", "इतना बिल", "زیادہ", "بل غلط",
          "غلط بل", "دوگنا", "ڈبل", "بڑھ گیا", "اتنا بل")
HIGH_STRONG = rx("too (high|much)", "very high", "so high", "huge", "excess*", "inflated", "overcharg*", "over charg*",
                 "charged (too much|more|extra)", "double*", "tripled", "shot up", "bill (is |looks )?(wrong|incorrect|not "
                 "correct)", "wrong bill", "incorrect bill", "చాలా ఎక్కువ", "మరీ ఎక్కువ", "బిల్లు తప్పు", "తప్పు బిల్లు",
                 "తప్పుగా వచ్చింది", "రెట్టింపు", "డబుల్", "chala ekkuva", "bill tappu", "bahut zyada", "bill galat",
                 "बहुत ज्यादा", "बिल गलत", "गलत बिल", "दोगुना", "डबल", "بہت زیادہ", "بل غلط", "غلط بل", "دوگنا", "ڈبل")
REPORT = rx(*WRONG, *COMPLAINT_WORDS, "please check", "check (it|my bill|this|the bill|and)", "kindly check",
            "verify", "correct (it|this|my bill)", "rectify", "revise", "do something", "look into", "చెక్ చేయండి",
            "చెక్ చెయ్యండి", "చూడండి", "సరిచేయ", "పరిశీలించ", "check cheyandi", "chudandi", "sarichey*",
            "check karo", "check kijiye", "check karein", "theek karo", "जांच", "चेक करें", "चेक कीजिए", "चेक करो",
            "ठीक करें", "ठीक कीजिए", "چیک کریں", "جانچ", "ٹھیک کریں", "درست کریں")
QUESTION = rx("why", "how come", "what is the reason", "reason", "explain", "ఎందుకు", "enduku", "endhuku", "కారణం",
              "karanam", "kyun", "kyon", "kyu", "क्यों", "वजह", "کیوں", "وجہ")

FETCH_BILL = rx("(get|fetch|send|show|download|need|want) (me )?(my |the )?(latest |current )?bill",
                "bill (by|with|using|from) (my )?(usc|service number|service no)", "copy of (my )?bill", "bill copy",
                "how (do|can) i get (my )?bill", "సర్వీస్ నంబర్‌తో బిల్లు", "బిల్లు తెప్పించ", "నా బిల్లు చూపించ",
                "బిల్లు పంపండి", "బిల్లు కావాలి", "bill kavali", "bill pampandi", "सर्विस नंबर से बिल", "मेरा बिल मंगा",
                "बिल चाहिए", "बिल भेज", "bill chahiye", "سروس نمبر سے بل", "میرا بل منگوا", "بل چاہیے", "بل بھیج")

# Questions about the bill, in order: the first that matches answers.
EXPLAIN = (
    ("explain_true_up", rx("true up", "trueup", "ట్రూ", "ट्रू", "ٹرو")),
    ("explain_fsa", rx("fsa", "fuel", "fuel cost", "ఇంధన", "ఎఫ్ఎస్ఏ", "ईंधन", "ایندھن")),
    # A bare "fixed" is usually "it got fixed", so only the charge itself counts.
    ("explain_fixed", rx("fixed (charge*|cost|amount|fee)", "what is fixed", "why fixed", "fixed ante", "ఫిక్స్డ్",
                         "ఫిక్సడ్", "ఫిక్స్ ఛార్జ్", "ఫిక్స్‌డ్", "फिक्स्ड", "فکسڈ")),
    ("explain_customer", rx("customer charge*", "కస్టమర్", "कस्टमर", "کسٹمر")),
    ("explain_duty", rx("electricity duty", "duty", "ed charge", "డ్యూటీ", "సుంకం", "बिजली शुल्क", "विद्युत शुल्क",
                        "ड्यूटी", "ڈیوٹی")),
    ("gruha_jyothi", rx("gruha*", "jyothi", "jyoti", "free (units|electricity|current|bijli)", "subsidy", "zero bill",
                        "గృహ", "జ్యోతి", "ఫ్రీ కరెంటు", "गृह", "मुफ्त बिजली", "फ्री बिजली", "گرہ", "مفت بجلی")),
    ("next_bill", rx("next month", "next bill", "predict*", "coming month", "వచ్చే నెల", "vache nela", "vachhe nela",
                     "अगले महीने", "अगला बिल", "agle mahine", "اگلے مہینے", "اگلا بل")),
    ("save", rx("save", "saving*", "reduce", "lower (my |the )?bill", "less bill", "cut (my |the )?bill", "ఆదా",
                "తగ్గించ", "తగ్గాలంటే", "taggin*", "bachat", "बचत", "बचा", "कम कर", "کم کر", "بچت", "بچا")),
    ("why_high", rx("why", "how come", "high", "bill (is )?so much", "(went|gone|go|going) up", "increase*", "ఎందుకు", "enduku", "ఎక్కువ", "ekkuva", "ఇంత బిల్లు",
                    "intha bill", "क्यों", "kyun", "ज्यादा", "zyada", "इतना बिल", "کیوں", "زیادہ", "اتنا بل")),
    ("due", rx("due(?! to)", "last date", "pay by", "when (to|should i|do i|must i|can i) pay", "how (to|can i|do i) pay",
               "where (to|can i|do i) pay", "can i pay", "చివరి తేదీ", "ఎప్పుడు కట్ట", "ఎలా కట్ట", "ఎక్కడ కట్ట",
               "లాస్ట్ డేట్", "eppudu katt*", "ela katt*", "ekkada katt*", "अंतिम तिथि", "आखिरी तारीख", "कब तक",
               "कैसे भर", "कैसे जमा", "kab tak", "آخری تاریخ", "کب تک", "کیسے ادا", "کیسے جمع")),
    ("new_connection", rx("new connection", "కొత్త కనెక్షన్", "kotha connection", "naya connection", "नया कनेक्शन",
                          "نیا کنکشن")),
    ("thanks", rx("thank*", "thx", "ధన్యవాద", "థ్యాంక్స్", "థాంక్స్", "dhanyavad*", "धन्यवाद", "शुक्रिया",
                  "shukriya", "شکریہ")),
    ("greeting", rx("hello", "hi", "hii", "hey", "namaste", "namaskaram", "namaskar", "good (morning|evening|afternoon)",
                    "నమస్కారం", "నమస్తే", "హలో", "हैलो", "नमस्ते", "नमस्कार", "सलाम", "salaam", "assalam*", "السلام",
                    "سلام")),
    ("help", rx("help", "menu", "what can you do", "how does this work", "సహాయం", "సాయం", "మెనూ", "madad", "मदद",
                "सहायता", "مدد")),
)
