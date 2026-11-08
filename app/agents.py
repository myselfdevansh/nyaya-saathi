"""
Six specialised legal agents, plus a general fallback.

An agent is not a separate model. It is a scope of law plus domain knowledge:
  acts:     the only Acts its search may look in, so unrelated law can't crowd out the right section
  asks:     the facts that change the outcome in this area (used for clarifying questions)
  guidance: how a specialist approaches this area, and where a person can actually complain

Complaint channels below were checked on the official sites in Nov 2026. Scheme rules that are not in
our data (for example RBI ombudsman deadlines) are deliberately left out, so the agents can't state them.
"""

import re

CONTRACT = "The Indian Contract Act, 1872"
LIMITATION = "The Limitation Act, 1963"
LEGAL_AID = "The Legal Services Authorities Act, 1987"
SPECIFIC_RELIEF = "The Specific Relief Act, 1963"
BNS = "The Bharatiya Nyaya Sanhita, 2023"
BNSS = "The Bharatiya Nagarik Suraksha Sanhita, 2023"
BSA = "The Bharatiya Sakshya Adhiniyam, 2023"
IT_ACT = "The Information Technology Act, 2000"
CONSUMER_ACT = "The Consumer Protection Act, 2019"

AGENTS = {
    "consumer": {
        "name": "Consumer Rights",
        "icon": ":material/shopping_bag:",
        "blurb": "Refunds, defects, insurance",
        "acts": [CONSUMER_ACT, "The Sale of Goods Act, 1930", "The Insurance Act, 1938",
                 CONTRACT, SPECIFIC_RELIEF, LIMITATION, LEGAL_AID],
        "route": "online shopping refunds and replacements, defective products, poor services, e-commerce "
                 "disputes, insurance claims, misleading advertisements",
        "asks": "what was bought and from whom; price paid; date of purchase and of the problem; whether "
                "the seller was contacted in writing and what they said; bill, order ID or policy in hand",
        "guidance": "Think in this order: seller's written reply, then National Consumer Helpline, then a "
                    "complaint before the Consumer Commission. Check limitation and which Commission fits. "
                    "Channels: National Consumer Helpline 1915 or consumerhelpline.gov.in; Consumer "
                    "Commission complaints at e-jagriti.gov.in. Insurance: complain to the insurer first, "
                    "then Bima Bharosa (bimabharosa.irdai.gov.in) or the Insurance Ombudsman (cioins.co.in).",
    },
    "property": {
        "name": "Property & Rental",
        "icon": ":material/home:",
        "blurb": "Deposits, eviction, title",
        "acts": ["The Transfer of Property Act, 1882", "The Real Estate (Regulation and Development) Act, 2016",
                 "The Registration Act, 1908", "The Indian Stamp Act, 1899", "The Indian Easements Act, 1882",
                 "The Partition Act, 1893", "The Code of Civil Procedure, 1908", SPECIFIC_RELIEF, CONTRACT,
                 LIMITATION, BNS, LEGAL_AID],
        "route": "landlord and tenant disputes, security deposits, illegal eviction, rent, rent agreements, "
                 "property ownership and title, encroachment, possession, builder delays",
        "asks": "tenant, owner or buyer; which state; whether there is a registered agreement or title "
                "document; amount or area involved; what notice was given and when",
        "guidance": "Rent, deposits and eviction are mostly governed by STATE law, which is not in your "
                    "sources: say so plainly and never guess a state rule. Separate a civil dispute from "
                    "criminal trespass. Builder matters go to the state's RERA authority. Land title and "
                    "possession disputes almost always need a lawyer: say so.",
    },
    "employment": {
        "name": "Employment & Labour",
        "icon": ":material/work:",
        "blurb": "Unpaid salary, termination",
        "acts": ["The Code on Wages, 2019", "The Industrial Relations Code, 2020",
                 "The Code on Social Security, 2020",
                 "The Occupational Safety, Health and Working Conditions Code, 2020",
                 "The Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013",
                 CONTRACT, LIMITATION, LEGAL_AID],
        "route": "unpaid salary, wrongful termination, unpaid bonus and dues, employment contracts, "
                 "workplace harassment and grievances",
        "asks": "private or government employer; employee or contract worker; which months or amount are "
                "due; written contract, offer letter or payslips in hand; whether HR was told in writing",
        "guidance": "For unpaid pay, look first for the Code on Wages sections on payment of wages, time "
                    "limit for payment, claims and the authority that hears them. Check each section's "
                    "conditions: lay-off or retrenchment sections do not apply to ordinary unpaid salary. "
                    "Workplace sexual harassment goes to the Internal Committee under the 2013 Act. "
                    "Channels: Samadhan portal (samadhan.labour.gov.in), the local Labour Commissioner.",
    },
    "cyber_criminal": {
        "name": "Cybercrime & Criminal",
        "icon": ":material/shield:",
        "blurb": "UPI fraud, threats, FIR",
        "acts": [BNS, BNSS, BSA, IT_ACT, "The Digital Personal Data Protection Act, 2023", LEGAL_AID],
        "route": "UPI and online payment fraud, cyberstalking, online threats, identity theft, impersonation, "
                 "blackmail, extortion, cheating, police complaints, FIR, evidence",
        "asks": "when it happened; money lost and how it was paid; whether the bank, 1930 or police were "
                "told yet; whether screenshots, messages or transaction IDs were saved",
        "guidance": "If money was lost online, the first step is always to report at 1930 or cybercrime.gov.in "
                    "and call the bank, because speed matters. Then explain how to file a police complaint and "
                    "what evidence to preserve without editing it. Anyone accused, arrested or summoned "
                    "needs a lawyer today.",
    },
    "family": {
        "name": "Family Law",
        "icon": ":material/family_restroom:",
        "blurb": "Divorce, custody, maintenance",
        "acts": ["The Protection of Women from Domestic Violence Act, 2005", "The Hindu Marriage Act, 1955",
                 "The Special Marriage Act, 1954", "The Divorce Act, 1869",
                 "The Dissolution of Muslim Marriages Act, 1939",
                 "The Muslim Women (Protection of Rights on Marriage) Act, 2019",
                 "The Hindu Adoptions and Maintenance Act, 1956", "The Hindu Minority and Guardianship Act, 1956",
                 "The Guardians and Wards Act, 1890", "The Family Courts Act, 1984", "The Hindu Succession Act, 1956",
                 "The Indian Succession Act, 1925", "The Prohibition of Child Marriage Act, 2006",
                 "The Dowry Prohibition Act, 1961",
                 "The Maintenance and Welfare of Parents and Senior Citizens Act, 2007", BNS, BNSS, LEGAL_AID],
        "route": "maintenance, divorce, separation, domestic violence, child custody, matrimonial property, "
                 "dowry, inheritance between family members, care of elderly parents",
        "asks": "the law the marriage falls under (Hindu, Muslim, Christian, Special Marriage Act); whether "
                "any case is already filed; children and their ages; whether the person is safe now",
        "guidance": "Safety comes first. Family law depends on the person's personal law: apply only the Act "
                    "that fits, and say which assumption you made. Muslim personal law on many points is not "
                    "codified and not in your sources: say so. Be warm and plain. Always recommend a lawyer "
                    "or free legal aid (NALSA 15100) for divorce, custody and contested property. "
                    "Women's helpline 181.",
    },
    "banking": {
        "name": "Banking & Finance",
        "icon": ":material/account_balance:",
        "blurb": "Bank disputes, loans, cheques",
        "acts": ["The Banking Regulation Act, 1949", "The Reserve Bank of India Act, 1934",
                 "The Payment and Settlement Systems Act, 2007",
                 "The Securitisation and Reconstruction of Financial Assets and Enforcement of Security "
                 "Interest Act, 2002",
                 "The Recovery of Debts and Bankruptcy Act, 1993", "The Credit Information Companies (Regulation) Act, 2005",
                 "The Banning of Unregulated Deposit Schemes Act, 2019", "The Negotiable Instruments Act, 1881",
                 CONSUMER_ACT, CONTRACT, LIMITATION, BNS, IT_ACT, LEGAL_AID],
        "route": "unauthorised bank transactions, account freezes, loan recovery harassment, credit card "
                 "disputes, banking ombudsman complaints, credit score errors, cheque bounce, deposit schemes",
        "asks": "which bank or lender; amount; date of the transaction or notice; whether the bank was told "
                "in writing and its reply; whether a loan is secured against property",
        "guidance": "Complain to the bank in writing first and keep the reference number, then escalate to the "
                    "RBI ombudsman at cms.rbi.org.in or contact centre 14448. The RBI scheme itself is not "
                    "in your sources, so don't state its deadlines or limits: tell the person to check them "
                    "on that site. For fraud, also report at 1930. Harassment or threats by recovery agents "
                    "can be reported to the police. A property seizure notice needs a lawyer quickly.",
    },
    "general": {
        "name": "General",
        "icon": ":material/gavel:",
        "blurb": "",
        "acts": None,  # searches every Act
        "route": "anything else, for example road accidents, right to information, or government services",
        "asks": "what happened; when; who the other party is; what has been tried; documents in hand",
        "guidance": "If this needs a specialist or falls outside your sources, say so and point to free legal "
                    "aid (NALSA 15100).",
    },
}

# Used when no LLM decision is available, and for urgent messages, which must not wait for one.
KEYWORDS = {
    "consumer": r"refund|replacement|defective|warranty|e-?commerce|amazon|flipkart|customer care|misleading|"
                r"insurance|insurer|claim rejected|consumer|रिफंड|खराब सामान|बीमा|उपभोक्ता|kharab saman|bima",
    "property": r"landlord|tenant|\brent\b|security deposit|evict|encroach|possession|title deed|registry|"
                r"builder|\bflat\b|\bplot\b|makan malik|kiraya|kirayedar|किराय|मकान मालिक|कब्ज़ा|कब्जा|जमीन|zameen",
    "employment": r"salary|wages|employer|terminat|fired|\bbonus\b|gratuity|\bpf\b|\bhr\b|office|workplace|"
                  r"naukri|tankhwah|वेतन|सैलरी|तनख्वाह|नौकरी|कंपनी",
    "cyber_criminal": r"\bupi\b|otp|cyber|hack|scam|fraud|blackmail|extort|stalk|impersonat|fake profile|\bfir\b|"
                      r"police|thagi|ठगी|ओटीपी|ब्लैकमेल|पुलिस",
    "family": r"husband|wife|divorce|custody|maintenance|dowry|in-?laws|domestic violence|inherit|talaq|"
              r"beat(s|ing)? me|\bpati\b|patni|dahej|talak|पति|पत्नी|तलाक|दहेज|ससुराल|मारते",
    "banking": r"\bbank\b|\bloan\b|\bemi\b|credit card|recovery agent|cheque|cibil|account (was )?(frozen|freeze)|"
               r"बैंक|लोन|चेक|क्रेडिट कार्ड",
}


def get(key):
    return AGENTS.get(key) or AGENTS["general"]


def route_keywords(text):
    """Best agent by keyword hits, or 'general'."""
    scores = {k: len(re.findall(p, text, re.I)) for k, p in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "general"


def router_menu():
    return "\n".join(f"- {k}: {a['route']}. Facts that matter: {a['asks']}." for k, a in AGENTS.items())
