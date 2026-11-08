"""
The whole RAG loop for one turn of conversation:

  triage (code) -> retrieve (hybrid search) -> generate (LLM, sources only)
  -> check citations (code) -> answer + sources + warnings
"""

from . import guardrails, llm
from .retrieve import retrieve

SYSTEM_PROMPT = """You are "Nyaya Saathi", a legal-help assistant for ordinary people in India.

HOW TO ANSWER: SHORT, EXACT, USEFUL
- Reply in the SAME language AND SCRIPT the person used. If they write Hindi in English letters
  (Hinglish, e.g. "meri salary nahi mili"), reply in Hinglish in English letters, NOT in Devanagari.
- At most about 150 words. Simple words. No greeting, no self-introduction, no disclaimer
  (the app shows one), no restating their story.
- Use exactly this format (headings translated into their language):
  **Where you stand**: 1-3 short bullets; each legal point carries its citation tag.
  **What to do**: up to 4 numbered steps, most effective first, specific (who, where, by when).
  **Keep as proof**: one line.
  **See a lawyer if**: one line, only when it genuinely matters.
- Do not ask questions; the app already asked them. If an essential fact is still unknown,
  state your assumption in a few words inside the relevant bullet.
- Say less rather than say something uncertain.

RULES ABOUT LAW (STRICT)
- You may state legal rules ONLY if they appear in the SOURCES below. Cite each one with its tag exactly as given, e.g. [consumer_protection_act_2019__s35].
- Before applying a section, read its conditions. Many sections only apply to money due "under
  Chapter X", to certain kinds of workers, or after a certain step. If the person's situation
  does not clearly meet those conditions, do not use that section; say the sources may not cover it.
- Never cite a section, Act, rule, or court case that is not in SOURCES. Never use IPC/CrPC/Indian Evidence Act numbers (they were replaced in 2024 by BNS/BNSS/BSA).
- If SOURCES do not cover the question, say plainly: "I could not find the law on this in my sources" and suggest a lawyer or free legal aid (NALSA helpline 15100).
- Practical, non-legal facts (helplines, portals) are fine if you are sure: National Consumer Helpline 1915 / e-Daakhil portal for consumer complaints, cybercrime 1930 / cybercrime.gov.in, police 112, women's helpline 181, NALSA legal aid 15100.
- State-specific rules (rent, stamp duty, etc.) vary; say so instead of guessing.
- Never promise an outcome."""


import re

# Common Hindi words written in English letters; 2+ hits => Hinglish.
HINGLISH_WORDS = {"mera", "meri", "mere", "mujhe", "maine", "nahi", "nahin", "hai", "hain", "kya", "kar",
                  "karun", "karna", "raha", "rahi", "diya", "di", "ho", "gaya", "gayi", "aur", "bhi", "sir ji",
                  "paisa", "paise", "kaise", "kab", "kyun", "abhi", "deta", "deti", "sakta", "sakti", "hoon", "ab"}


def detect_language(text):
    """Decided in code, because models were seen replying in Hindi to English questions."""
    if re.search(r"[ऀ-ॿ]", text):
        return "Hindi, in Devanagari script"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if len(words & HINGLISH_WORDS) >= 2:
        return "Hinglish (Hindi written in English/Latin letters, NOT Devanagari)"
    return "English"


# ------------------------------------------------------- clarifying questions
CLARIFY_PROMPT = """You decide whether a person's description of a legal problem in India has the facts needed for
accurate guidance. Ask ONLY about facts that would change the legal answer, such as:
what exactly happened; when (dates); how much money; who the other party is (company, person, employer,
builder, government office); whether there is a written agreement, bill or receipt; what they already tried;
and the state, ONLY for state-specific matters such as rent or tenancy.

Rules:
- Never ask about something already stated in the conversation.
- Never ask for names, phone numbers, addresses or ID numbers.
- If the message is a general question about the law, a follow-up answerable from the conversation,
  or already has the key facts, return no questions.
- At most 3 questions, most important first. One fact per question, under 12 words.
- Give 2-4 short answer options when the answer is a choice (e.g. Yes / No); otherwise options = [].
- Write the questions and options in LANGUAGE.
Return ONLY JSON: {"questions": [{"q": "...", "options": ["...", "..."]}]}"""


def clarifying_questions(history, max_q=3):
    """
    Returns [] when the description is complete enough, or up to `max_q` questions
    ({"q": str, "options": [str]}) for the UI to ask one at a time.
    Never delays urgent situations, and fails open (no questions) if the model errors.
    """
    latest = [m["content"] for m in history if m["role"] == "user"][-1]
    if any(f["type"] in ("danger", "arrest_court") for f in guardrails.triage(latest)):
        return []
    convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-6:])
    try:
        out = llm.chat_json([
            {"role": "system", "content": CLARIFY_PROMPT.replace("LANGUAGE", detect_language(latest))},
            {"role": "user", "content": convo},
        ], max_tokens=1500)
    except Exception:
        return []
    questions = []
    for item in out.get("questions", [])[:max_q]:
        if isinstance(item, dict) and isinstance(item.get("q"), str) and item["q"].strip():
            opts = [o for o in item.get("options", []) if isinstance(o, str) and o.strip()][:4]
            questions.append({"q": item["q"].strip(), "options": opts})
    return questions


def with_details(text, qa_pairs):
    """Fold the answers to clarifying questions into the user's message."""
    answered = [(q, a) for q, a in qa_pairs if a and a.strip()]
    if not answered:
        return text
    return text + "\n\n" + "\n".join(f"- {q} {a.strip()}" for q, a in answered)


def format_sources(sources):
    return "\n\n".join(
        f"[{s['id']}] {s['act']}, Section {s['section']}: {s['heading']}\n{s['excerpt']}" for s in sources
    )


def answer(history, k=8):
    """
    history: list of {"role": "user"|"assistant", "content": str}, last item = latest user message.
    Returns a dict with the answer and everything needed to audit it.
    """
    user_turns = [m["content"] for m in history if m["role"] == "user"]
    latest = user_turns[-1]
    # Search on the recent conversation so follow-ups ("what if he still refuses?") keep context.
    search_text = " ".join(user_turns[-3:])

    flags = guardrails.triage(latest)
    sources, rewrite = retrieve(search_text, k=k)

    language = detect_language(latest)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT
         + "\n\nCITATION FORMAT: use the tag exactly, e.g. [consumer_protection_act_2019__s35]. "
           "Do not translate or rewrite tags."
         + "\n\nSOURCES\n" + format_sources(sources)
         + f"\n\nLANGUAGE: The person wrote in {language}. Write your ENTIRE reply in {language}."},
        *history[-8:],
    ]
    raw = llm.chat(messages)
    checked, cited, issues = guardrails.check_citations(raw, sources)

    return {
        "answer": checked,
        "cited_sources": cited,
        "retrieved": sources,
        "flags": flags,
        "language": language,
        "citation_issues": issues,
        "rewrite": rewrite,
        "raw_answer": raw,
        "model": llm.last_model_used(),
    }


# ------------------------------------------------------------------ drafting
DOC_TYPES = {
    "Legal notice / demand letter": "a formal legal notice / demand letter to the other party, demanding a specific "
                                    "action (refund, payment, return of deposit) within a clear deadline (e.g. 15 days) "
                                    "and stating that legal remedies will follow otherwise",
    "Consumer complaint (draft for e-Daakhil / District Commission)":
        "a draft consumer complaint for the District Consumer Disputes Redressal Commission, with headings: "
        "parties, facts in numbered paragraphs, cause of action, relief sought, list of documents, verification",
    "Complaint to employer / Labour office": "a written complaint about unpaid wages or employment dues, addressed to "
                                             "the employer (copy to the Labour Commissioner), listing amounts and months",
    "Police complaint (for FIR)": "a written complaint to the Station House Officer describing the incident in "
                                  "chronological order, requesting registration of an FIR",
    "RTI application": "an application under the Right to Information Act to the Public Information Officer, "
                       "with numbered, specific information requests",
}

DRAFT_PROMPT = """You draft documents for ordinary people in India, based on the conversation below.
Write {doc}.

RULES
- Write the document in {language}. Formal but simple.
- Use ONLY facts the person gave. For anything missing, put a clear placeholder in CAPITALS in square
  brackets, e.g. [YOUR FULL NAME], [DATE OF PURCHASE], [ORDER ID]. Never invent names, dates, amounts.
- Legal provisions: you may refer ONLY to the SOURCES below, using the tag exactly, e.g.
  [consumer_protection_act_2019__s35]. If no source fits, do not cite any law; describe the facts and demand.
- Never cite IPC/CrPC, court cases, or any section not in SOURCES.
- Output only the document text (no explanation before or after).
After the document, on a new line, write "CHECKLIST:" followed by a short bullet list of the placeholders the person
must fill in and the documents they should attach.

SOURCES
{sources}"""


def draft_document(history, doc_type, language="English", k=8):
    convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
    user_text = " ".join(m["content"] for m in history if m["role"] == "user")
    sources, _ = retrieve(f"{doc_type}. {user_text[-1500:]}", k=k)
    prompt = DRAFT_PROMPT.format(doc=DOC_TYPES[doc_type], language=language, sources=format_sources(sources))
    raw = llm.chat([{"role": "system", "content": prompt},
                    {"role": "user", "content": "CONVERSATION:\n" + convo}], temperature=0.2)
    checked, cited, issues = guardrails.check_citations(raw, sources)
    checked = re.sub(r"\*{2,3}", "", checked)  # plain-text document: drop markdown bold markers
    if cited:  # replace [1] markers with readable references inside a formal document
        for i, s in enumerate(cited, 1):
            checked = checked.replace(f"[{i}]", f"(Section {s['section']}, {s['act']})")
    return {"text": checked, "cited_sources": cited, "citation_issues": issues, "model": llm.last_model_used()}


def render(result):
    """Plain-text rendering for CLI / saved outputs."""
    out = []
    for f in result["flags"]:
        out.append(f"⚠ {f['message']}")
    out.append(result["answer"])
    if result["cited_sources"]:
        out.append("\nSources (official text, India Code):")
        for i, s in enumerate(result["cited_sources"], 1):
            out.append(f"  [{i}] {s['act']}, Section {s['section']} ({s['heading']}) {s['source_url']}")
    if result["citation_issues"]:
        out.append("\nChecker notes:")
        out += [f"  - {x}" for x in result["citation_issues"]]
    out.append("\nThis is legal information, not legal advice. For your specific case, consult a lawyer "
               "or free legal aid (NALSA 15100).")
    return "\n".join(out)
