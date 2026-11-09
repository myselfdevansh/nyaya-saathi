"""
Nyaya Saathi: chat UI for the multi-agent legal assistant.

    streamlit run streamlit_app.py

Flow per message: the front desk picks a specialist agent and, if key facts are missing, asks up to
8 questions one at a time in a pop-up. The agent then answers briefly from official law text.
Hindi speech gets its questions and answer in Hinglish, or in Devanagari Hindi when the Hindi button
is on. On a hosted app, set LLM_* as secrets.
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Nyaya Saathi", page_icon="⚖️", layout="centered",
                   initial_sidebar_state="collapsed")

try:  # hosted secrets -> environment, so app/llm.py works the same locally and in the cloud
    for key in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "LLM_REASONING_EFFORT",
                "LLM_FALLBACK_MODELS"):
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = str(st.secrets[key])
except Exception:
    pass
# A person is waiting: on a rate limit, move to the next fallback model at once.
os.environ.setdefault("LLM_RETRIES", "1")

from app import agents, llm  # noqa: E402
from app.guardrails import triage  # noqa: E402
from app.kb import load_index  # noqa: E402
from app.pipeline import (DOC_TYPES, HINDI, HINGLISH, answer, detect_language, draft_document,  # noqa: E402
                          intake, with_details)
from app.retrieve import retrieve  # noqa: E402

FEEDBACK_LOG = Path(__file__).parent / "logs" / "feedback.jsonl"
CARD_AGENTS = [k for k in agents.AGENTS if k != "general"]

# Screen text in full Hindi mode. Anything not listed stays in English.
HINDI_TEXT = {
    "New chat": "नई चैट",
    "What happened?": "क्या हुआ?",
    "Tell us in your own words, or pick an area.": "अपने शब्दों में बताइए, या कोई विषय चुनिए।",
    "Legal information, not legal advice.": "यह कानूनी जानकारी है, कानूनी सलाह नहीं।",
    "Describe your problem…": "अपनी समस्या बताइए…",
    "Change area": "विषय बदलें",
    "Thinking…": "सोच रहे हैं…",
    "Listening…": "सुन रहे हैं…",
    "Checking the law…": "कानून देख रहे हैं…",
    "Question": "प्रश्न",
    "of": "/",
    "Type your answer": "अपना जवाब लिखिए",
    "Next": "आगे",
    "Skip": "छोड़ें",
    "Sources": "स्रोत",
    "Notes": "टिप्पणियाँ",
    "Draft a document": "दस्तावेज़ बनाइए",
    "Draft": "बनाइए",
    "Drafting…": "बना रहे हैं…",
    "Document": "दस्तावेज़",
    "Language": "भाषा",
    "Download": "डाउनलोड",
    "Voice isn't available right now. Please type.": "आवाज़ अभी उपलब्ध नहीं है। कृपया लिखिए।",
    "The free AI quota is used up for now. Please try again in a few minutes.":
        "मुफ्त AI कोटा अभी खत्म हो गया है। कृपया कुछ मिनट बाद फिर कोशिश करें।",
    "Something went wrong. Please try again.": "कुछ गड़बड़ हो गई। कृपया फिर कोशिश करें।",
    "For urgent help: legal aid 15100, police 112.": "तुरंत मदद के लिए: कानूनी सहायता 15100, पुलिस 112।",
}


def t(text):
    """Screen text in the current mode."""
    return HINDI_TEXT.get(text, text) if st.session_state.get("hindi") else text


def agent_label(agent):
    """(name, blurb) in the current mode."""
    if st.session_state.get("hindi"):
        return agent["name_hi"], agent["blurb_hi"]
    return agent["name"], agent["blurb"]

st.markdown("""<style>
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="collapsedControl"], [data-testid="stHeader"] {display: none;}
.block-container {padding-top: 1.75rem; padding-bottom: 7rem; max-width: 760px;}
[data-testid="stAppViewContainer"] {overflow-x: hidden;}

/* header */
.st-key-header [data-testid="stHorizontalBlock"] {flex-wrap: nowrap; align-items: center;}
.st-key-header [data-testid="stColumn"] {min-width: 0;}
.st-key-header p {font-size: 1.1rem; font-weight: 700; letter-spacing: -0.01em; margin: 0; white-space: nowrap;}
.st-key-header button p {font-size: .875rem; font-weight: 500;}

/* empty state */
.hero {text-align: center; padding: 3.5rem 0 1.75rem;}
.hero h1 {font-size: clamp(1.7rem, 6vw, 2.4rem); font-weight: 700; letter-spacing: -0.025em; padding: 0; margin: 0;}
.hero p {color: #5B6478; margin: .6rem 0 0; font-size: 1rem;}

/* agent cards: a real grid, so phones get two columns instead of one long list */
.st-key-cards {display: grid !important; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem;}
.st-key-cards > div {width: 100% !important; min-width: 0;}
.st-key-cards button {height: 100%; min-height: 6.25rem; width: 100%; padding: .9rem 1rem; display: flex;
    flex-direction: column; align-items: flex-start; justify-content: flex-start; gap: .4rem; text-align: left;
    background: #FFFFFF; border: 1px solid #E2E6EF; box-shadow: 0 1px 2px rgba(23, 32, 51, .04);
    transition: border-color .15s, box-shadow .15s, transform .15s;}
.st-key-cards button:hover {border-color: #1F3A8A; box-shadow: 0 6px 18px rgba(31, 58, 138, .1);
    transform: translateY(-1px);}
.st-key-cards button [data-testid="stIconMaterial"] {color: #1F3A8A; font-size: 1.35rem;}
.st-key-cards button div {text-align: left; justify-content: flex-start;}
.st-key-cards button p {font-size: .8rem; color: #5B6478; line-height: 1.35; margin: 0; text-align: left;}
.st-key-cards button strong {display: block; font-size: .925rem; font-weight: 600; color: #172033;
    margin-bottom: .2rem;}
.disclaimer {text-align: center; color: #8089A0; font-size: .78rem; margin-top: 1.5rem;}
@media (max-width: 640px) {
  .st-key-cards {grid-template-columns: repeat(2, minmax(0, 1fr));}
  .hero {padding-top: 1.5rem;}
}

/* the chosen agent */
.st-key-pinned [data-testid="stHorizontalBlock"] {flex-wrap: nowrap; align-items: center;}
.st-key-pinned [data-testid="stColumn"] {min-width: 0; width: auto; flex: 0 1 auto;}

/* chat */
[data-testid="stChatMessage"] {background: transparent; padding: .5rem 0;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {background: #F3F5FA;
    padding: .75rem 1rem; border-radius: .9rem;}
[data-testid="stChatMessage"] h5 {font-size: .95rem; font-weight: 600; padding: .4rem 0 .1rem;}
[data-testid="stChatInput"] {box-shadow: 0 4px 20px rgba(23, 32, 51, .08); border-radius: 1.25rem;}
[data-testid="stExpander"] details {border-color: #E2E6EF; background: #FBFCFE;}
[data-testid="stDialog"] [role="dialog"] {border-radius: 1rem;}
</style>""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading…")
def warm_up():
    load_index()
    retrieve("warm up", use_rewrite=False)  # loads the embedding model
    return True


def init_state():
    for k, v in {"history": [], "results": {}, "pending": None, "draft": None, "pinned": None,
                 "agent": None, "hindi": False}.items():
        st.session_state.setdefault(k, v)


# ------------------------------------------------------------------ actions
def submit(text, language=None):
    """New message: the front desk picks the agent and asks questions if facts are missing."""
    st.session_state.draft = None
    st.session_state.draft_open = False
    if not llm.is_configured():
        st.session_state.history.append({"role": "user", "content": text})
        return
    with st.spinner(t("Thinking…")):
        desk = intake(st.session_state.history + [{"role": "user", "content": text}],
                      pinned=st.session_state.pinned, language=language)
    st.session_state.agent = desk["agent"]
    if desk["questions"]:
        st.session_state.pending = {"text": text, "questions": desk["questions"], "answers": [], "done": False,
                                    "language": language}
    else:
        respond(text, language)


def respond(text, language=None):
    agent = st.session_state.agent or "general"
    st.session_state.history.append({"role": "user", "content": text})
    with st.spinner(t("Checking the law…")):
        try:
            res = answer(st.session_state.history, agent=agent, language=language)
        except Exception as e:
            why = t("The free AI quota is used up for now. Please try again in a few minutes."
                    if isinstance(e, llm.RateLimited) else "Something went wrong. Please try again.")
            res = {"answer": f"{why} {t('For urgent help: legal aid 15100, police 112.')}", "agent": agent,
                   "flags": triage(text, language), "cited_sources": [], "citation_issues": []}
    idx = len(st.session_state.history)
    st.session_state.history.append({"role": "assistant", "content": res["answer"]})
    st.session_state.results[idx] = res


def finish_pending():
    p = st.session_state.pending
    pairs = list(zip([q["q"] for q in p["questions"]], p["answers"]))
    st.session_state.pending = None
    respond(with_details(p["text"], pairs), p.get("language"))


def skip_remaining():
    if st.session_state.pending:
        st.session_state.pending["done"] = True


def record(answer_text):
    p = st.session_state.pending
    p["answers"].append(answer_text)
    if len(p["answers"]) >= len(p["questions"]):
        p["done"] = True


def from_voice(audio_bytes, hindi=False):
    """
    Returns (text, reply language). Hindi speech is answered in Hinglish, or in Devanagari Hindi
    when the Hindi button is on.
    """
    heard = llm.transcribe(audio_bytes, "wav", devanagari=hindi)
    if hindi:
        return heard["text"], HINDI
    return heard["text"], HINGLISH if heard["language"] == "hindi" else None


def log_feedback(idx, score):
    FEEDBACK_LOG.parent.mkdir(exist_ok=True)
    res = st.session_state.results.get(idx, {})
    with FEEDBACK_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"), "helpful": bool(score), "agent": res.get("agent"),
            "question": st.session_state.history[idx - 1]["content"] if idx > 0 else "",
            "cited": [s["id"] for s in res.get("cited_sources", [])],
            "issues": res.get("citation_issues", []), "model": res.get("model"),
        }, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ pop-ups
def question_dialog():
    p = st.session_state.pending
    i, n = len(p["answers"]), len(p["questions"])
    q = p["questions"][i]

    @st.dialog(f"{t('Question')} {i + 1} {t('of')} {n}", on_dismiss=skip_remaining)
    def ask():
        st.markdown(f"**{q['q']}**")
        if q["options"]:
            cols = st.columns(len(q["options"]))
            for j, opt in enumerate(q["options"]):
                if cols[j].button(opt, key=f"opt_{i}_{j}", use_container_width=True):
                    record(opt)
                    st.rerun()
        typed = st.text_input("Answer", key=f"ans_{i}", label_visibility="collapsed",
                              placeholder=t("Type your answer"))
        c1, c2 = st.columns(2)
        if c1.button(t("Next"), type="primary", use_container_width=True, key=f"next_{i}"):
            record(typed)
            st.rerun()
        if c2.button(t("Skip"), use_container_width=True, key=f"skip_{i}"):
            record("")
            st.rerun()

    ask()


def close_draft():
    st.session_state.draft_open = False


def draft_dialog():
    st.dialog(t("Draft a document"), width="large", on_dismiss=close_draft)(draft_form)()


def draft_form():
    first_user = next(m["content"] for m in st.session_state.history if m["role"] == "user")
    c1, c2 = st.columns([3, 1])
    doc_type = c1.selectbox(t("Document"), list(DOC_TYPES))
    language = c2.selectbox(t("Language"), ["English", "Hindi"],
                            index=1 if st.session_state.hindi or detect_language(first_user).startswith("Hindi") else 0)
    if st.button(t("Draft"), type="primary"):
        with st.spinner(t("Drafting…")):
            try:
                st.session_state.draft = {"type": doc_type, **draft_document(
                    st.session_state.history, doc_type, language, agent=st.session_state.agent)}
            except llm.RateLimited:
                st.error("The free AI quota is used up for now. Please try again later.")
            except Exception:
                st.error("Could not draft right now. Please try again.")
    d = st.session_state.draft
    if d:
        key = "draft_" + hashlib.md5(d["text"].encode()).hexdigest()[:8]
        edited = st.text_area("Draft", d["text"], height=380, key=key, label_visibility="collapsed")
        st.download_button(t("Download"), edited, use_container_width=True,
                           file_name=re.sub(r"[^A-Za-z]+", "_", d["type"].split(" (")[0]).strip("_") + ".txt")


# ------------------------------------------------------------------ rendering
def show_answer(idx, res):
    a = agents.get(res.get("agent"))
    st.badge(agent_label(a)[0], icon=a["icon"], color="blue")
    for f in res.get("flags", []):
        (st.error if f["type"] == "danger" else st.warning)(f["message"])
    st.markdown(re.sub(r"^#{1,4} ", "##### ", res["answer"], flags=re.M))
    if res.get("cited_sources"):
        with st.expander(t("Sources")):
            for i, s in enumerate(res["cited_sources"], 1):
                st.markdown(f"[{i}] [{s['act']}, s.{s['section']}]({s['source_url']}): {s['heading']}")
    if res.get("citation_issues"):
        with st.expander(t("Notes")):
            for x in res["citation_issues"]:
                st.caption(x)
    fb = st.feedback("thumbs", key=f"fb_{idx}")
    if fb is not None and not st.session_state.get(f"fb_logged_{idx}"):
        log_feedback(idx, fb)
        st.session_state[f"fb_logged_{idx}"] = True


def search_only(text):
    """No API key: list the official sections that match."""
    for f in triage(text):
        st.warning(f["message"])
    results, _ = retrieve(text, use_rewrite=False, agent=agents.route_keywords(text))
    st.markdown("\n".join(f"- [{r['act']}, s.{r['section']}]({r['source_url']}): {r['heading']}"
                          for r in results))


def empty_state():
    st.markdown(f'<div class="hero"><h1>{t("What happened?")}</h1>'
                f'<p>{t("Tell us in your own words, or pick an area.")}</p></div>', unsafe_allow_html=True)
    with st.container(key="cards"):
        for k in CARD_AGENTS:
            a = agents.AGENTS[k]
            name, blurb = agent_label(a)
            if st.button(f"**{name}**\n\n{blurb}", key=f"card_{k}", icon=a["icon"]):
                st.session_state.pinned = k
                st.rerun()
    st.markdown(f'<p class="disclaimer">{t("Legal information, not legal advice.")}</p>', unsafe_allow_html=True)


def pinned_state():
    a = agents.get(st.session_state.pinned)
    name, blurb = agent_label(a)
    st.markdown(f'<div class="hero"><h1>{name}</h1><p>{blurb}</p></div>', unsafe_allow_html=True)
    _, mid, _ = st.columns([2, 1, 2])
    if mid.button(t("Change area"), type="tertiary", use_container_width=True):
        st.session_state.pinned = None
        st.rerun()
    st.markdown(f'<p class="disclaimer">{t("Legal information, not legal advice.")}</p>', unsafe_allow_html=True)


def main():
    init_state()
    warm_up()

    with st.container(key="header"):
        left, mid, right = st.columns([4, 1.5, 2.2], vertical_alignment="center")
        left.markdown("⚖️ Nyaya Saathi")
        # Full Hindi: questions, answers, warnings and Hindi speech all in Devanagari.
        if mid.button("हिंदी", key="hindi_btn", use_container_width=True,
                      type="primary" if st.session_state.hindi else "secondary"):
            st.session_state.hindi = not st.session_state.hindi
            st.rerun()
        if right.button(t("New chat"), icon=":material/add:", use_container_width=True):
            for k in ("history", "results", "pending", "draft", "draft_open", "pinned", "agent"):
                st.session_state.pop(k, None)
            st.rerun()

    start = st.empty()
    if not st.session_state.history and not st.session_state.pending:
        with start.container():
            if st.session_state.pinned:
                pinned_state()
            else:
                empty_state()

    for i, m in enumerate(st.session_state.history):
        with st.chat_message(m["role"], avatar="⚖️" if m["role"] == "assistant" else None):
            if m["role"] == "assistant" and i in st.session_state.results:
                show_answer(i, st.session_state.results[i])
            elif m["role"] == "user" and not llm.is_configured():
                st.markdown(m["content"])
                search_only(m["content"])
            else:
                st.markdown(m["content"])

    p = st.session_state.pending
    if p:
        with st.chat_message("user"):
            st.markdown(p["text"])

    if llm.is_configured() and st.session_state.results and not p:
        if st.button(t("Draft a document"), icon=":material/description:"):
            st.session_state.draft_open = True
        if st.session_state.get("draft_open"):  # stays open across reruns until dismissed
            draft_dialog()

    sent = st.chat_input(t("Describe your problem…"), accept_audio=True)
    hindi = st.session_state.hindi
    text, language = None, HINDI if hindi else None
    if sent:
        text = (sent.text or "").strip() or None
        if sent.audio and not text:
            start.empty()
            try:
                with st.spinner(t("Listening…")):
                    text, language = from_voice(sent.audio.getvalue(), hindi)
            except Exception:
                st.toast(t("Voice isn't available right now. Please type."))
    if text:
        start.empty()
        st.session_state.pending = None  # a new message replaces unanswered questions
        with st.chat_message("user"):
            st.markdown(text)
        submit(text, language)
        st.rerun()

    p = st.session_state.pending
    if p and p["done"]:
        finish_pending()
        st.rerun()
    elif p:
        question_dialog()


main()
