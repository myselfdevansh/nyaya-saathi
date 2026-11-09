"""
Rules kept in code, not left to the model:

1. triage(): spots situations that need a human (lawyer, police, helpline) now.
2. check_citations(): every legal citation in the answer must be one of the
   sections we actually retrieved and showed the model. Anything else (an
   invented section, an old IPC/CrPC reference, a case name) is removed or
   flagged before the user sees it.
"""

import re

# ---------------------------------------------------------------- 1. triage
URGENT = {
    "danger": (r"\b(kill|murder|suicide|beat(ing|s)? me|hit(s|ting)? me|threat(en)?|attack|weapon|"
               r"maar|maarta|maarti|maarte|marta|marti|marte|peet(ta|ti|te)|pitai|jaan se|khudkushi|aatmahatya|dhamki)\b",
               "If you are in immediate danger, call 112 (police). For women in distress: 181. "
               "If you are having thoughts of self-harm, please call Tele-MANAS 14416."),
    "arrest_court": (r"\b(arrest(ed)?|police (took|custody|station)|summons|warrant|bail|court date|hearing|"
                     r"FIR (against|on) me|giraftar|girftar|zamanat|peshi)\b",
                     "This involves police or court proceedings with deadlines. Please speak to a lawyer "
                     "today. Free legal aid: call NALSA 15100 or visit your District Legal Services Authority."),
    "cyber_fraud": (r"\b(otp|upi fraud|money (was )?debited|scam(med)?|fraud call|hack(ed)?|thagi|paise kat(e|gaye))\b",
                    "For online financial fraud, report immediately at 1930 or cybercrime.gov.in; "
                    "speed matters for freezing the money."),
}

OUT_OF_SCOPE = r"\b(immigration|visa|patent|trademark|tax notice|income tax|gst)\b"


# Devanagari patterns: no \b, because Python's \b breaks on Hindi vowel signs.
URGENT_HI = {
    "danger": r"मार(ते|ता|ती|ना|पीट)|पीट(ते|ता|ती)|धमकी|जान से|आत्महत्या|खुदकुशी|हमला",
    "arrest_court": r"गिरफ्तार|जमानत|समन|वारंट|पेशी|अदालत में तारीख",
    "cyber_fraud": r"ओटीपी|ठगी|पैसे कट",
}


# Same warnings in Hindi, shown when the user writes in Devanagari.
MESSAGES_HI = {
    "danger": "अगर आप अभी खतरे में हैं, तो तुरंत 112 (पुलिस) पर कॉल करें। महिलाओं के लिए हेल्पलाइन: 181। "
              "अगर आपके मन में खुद को नुकसान पहुँचाने के विचार आ रहे हैं, तो Tele-MANAS 14416 पर कॉल करें।",
    "arrest_court": "यह मामला पुलिस या अदालत से जुड़ा है और इसमें समय-सीमा होती है। आज ही वकील से बात करें। "
                    "मुफ्त कानूनी सहायता: NALSA 15100 या अपना ज़िला विधिक सेवा प्राधिकरण (DLSA)।",
    "cyber_fraud": "ऑनलाइन ठगी की तुरंत शिकायत 1930 या cybercrime.gov.in पर करें; जल्दी करने से पैसा रोका जा सकता है।",
    "out_of_scope": "यह विषय इस सहायक के दायरे से बाहर है। कृपया वकील से सलाह लें; मुफ्त कानूनी सहायता: NALSA 15100।",
}


# Same warnings in Hinglish, shown for Hinglish messages and for Hindi speech.
MESSAGES_HINGLISH = {
    "danger": "Agar aap abhi danger mein hain, turant 112 (police) par call karein. Women's helpline: 181. "
              "Agar self-harm ke thoughts aa rahe hain, Tele-MANAS 14416 par call karein.",
    "arrest_court": "Yeh police ya court ka matter hai aur isme deadlines hoti hain. Aaj hi lawyer se baat karein. "
                    "Free legal aid: NALSA 15100 ya aapki District Legal Services Authority.",
    "cyber_fraud": "Online fraud ki complaint turant 1930 ya cybercrime.gov.in par karein; jaldi report karne se "
                   "money freeze ho sakta hai.",
    "out_of_scope": "Yeh topic is assistant ke scope se bahar hai. Please lawyer se advice lein; free legal aid: "
                    "NALSA 15100.",
}


def triage(text, language=None):
    """language: the reply language, when the caller knows it. Otherwise follow the script of the text."""
    flags = []
    hinglish = bool(language and language.startswith("Hinglish"))
    hindi = bool(language and language.startswith("Hindi")) or (not hinglish and bool(re.search(r"[ऀ-ॿ]", text)))
    translated = MESSAGES_HINGLISH if hinglish else MESSAGES_HI if hindi else None
    for name, (pattern, message) in URGENT.items():
        if re.search(pattern, text, re.I) or re.search(URGENT_HI[name], text):
            flags.append({"type": name, "message": translated[name] if translated else message})
    if re.search(OUT_OF_SCOPE, text, re.I):
        flags.append({"type": "out_of_scope",
                      "message": translated["out_of_scope"] if translated else
                      "This topic is outside what this assistant covers reliably "
                      "(tax and intellectual property law are not in its knowledge base). "
                      "Please consult a lawyer; free legal aid: NALSA 15100."})
    return flags


# -------------------------------------------------------- 2. citation check
CITE_TAG = re.compile(r"\[([a-z0-9_]+__s[0-9]+[A-Z]{0,2})((?:\([0-9a-zA-Z]+\))*)\]")
# Free-text mentions like "Section 138", "Sec. 35", "s. 18", Hindi "धारा 47"
SECTION_MENTION = re.compile(r"(?:\b(?:section|sec\.?|s\.)|धारा)\s*(\d+[A-Z]{0,2})\b", re.I)
# Any other bracketed text that looks like a citation, e.g. "[BNSS, 2023, धारा 47(1)]"
LOOSE_CITE = re.compile(r"\[([^\[\]]*?(?:section|sec\.|धारा|__s)[^\[\]]*?)\]", re.I)
SECTION_NUM = re.compile(r"(?:__s|section|sec\.?|धारा)\s*(\d+[A-Z]{0,2})", re.I)
OLD_CODES = re.compile(r"\b(IPC|Indian Penal Code|CrPC|Cr\.P\.C\.?|Code of Criminal Procedure|Indian Evidence Act)\b", re.I)
CASE_LAW = re.compile(r"\b[A-Z][A-Za-z.]+(?:\s[A-Z][A-Za-z.]+)*\s+(?:v\.|vs\.?|versus)\s+[A-Z][A-Za-z.]+|"
                      r"\(\d{4}\)\s*\d+\s*SCC|AIR\s+\d{4}\s+SC")


def check_citations(answer, retrieved):
    allowed = {r["id"]: r for r in retrieved}
    allowed_numbers = {r["section"].upper() for r in retrieved}
    issues, used = [], []

    def number(sid):
        if sid not in used:
            used.append(sid)
        return f"[{used.index(sid) + 1}]"

    # 1. Exact tags, optionally with a sub-section: [id] or [id(1)(b)] (sub-section is dropped
    #    from the marker; the answer text normally names it).
    def tag_to_number(m):
        sid = m.group(1)
        if sid not in allowed:
            issues.append(f"Removed citation to a section that was not in the retrieved sources: {sid}")
            return "[citation removed: unverified]"
        return number(sid)

    checked = CITE_TAG.sub(tag_to_number, answer)

    # 2. Any other bracketed citation (wrong format, Act name in Hindi, ...).
    #    Accept it only if its section number matches exactly one retrieved section.
    def loose_to_number(m):
        nm = SECTION_NUM.search(m.group(1))
        matches = [r["id"] for r in retrieved if nm and r["section"].upper() == nm.group(1).upper()]
        if len(matches) == 1:
            return number(matches[0])
        issues.append(f"Removed a citation that could not be matched to a retrieved section: [{m.group(1)}]")
        return "[citation removed: unverified]"

    checked = LOOSE_CITE.sub(loose_to_number, checked)

    # 3. Plain-text mentions ("Section 59", "धारा 47"): unknown numbers are flagged;
    #    a number matching exactly one retrieved section is added to the source list.
    for m in SECTION_MENTION.finditer(checked):
        num = m.group(1).upper()
        if num not in allowed_numbers:
            issues.append(f"Mentions 'Section {m.group(1)}' which is not among the retrieved sources; "
                          "treat it as unverified.")
            continue
        matches = [r["id"] for r in retrieved if r["section"].upper() == num]
        if len(matches) == 1 and matches[0] not in used:
            used.append(matches[0])
    if OLD_CODES.search(checked):
        issues.append("Mentions IPC/CrPC/Evidence Act, which were replaced on 1 July 2024 by BNS/BNSS/BSA.")
    if CASE_LAW.search(checked):
        issues.append("Mentions a court case. This assistant has no case-law database, so the case is unverified.")

    sources = [allowed[sid] for sid in used]
    return checked, sources, issues
