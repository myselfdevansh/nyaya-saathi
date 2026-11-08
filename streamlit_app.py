"""
Nyaya Saathi: minimal chat UI for the AI lawyer.

    streamlit run streamlit_app.py

Flow per message: if key facts are missing, ask up to 3 clarifying questions one at a time in a
pop-up, then answer briefly from official law text. On a hosted Space, set LLM_* as secrets.
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

from app import llm  # noqa: E402
from app.guardrails import triage  # noqa: E402
from app.kb import load_index  # noqa: E402
from app.pipeline import (DOC_TYPES, answer, clarifying_questions, detect_language,  # noqa: E402
                          draft_document, with_details)
from app.retrieve import retrieve  # noqa: E402

FEEDBACK_LOG = Path(__file__).parent / "logs" / "feedback.jsonl"

st.markdown("""<style>
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="collapsedControl"] {display: none;}
.block-container {padding-top: 2.5rem; max-width: 720px;}
[data-testid="stAppViewContainer"] {overflow-x: hidden;}
/* keep title, mic and New chat on one row on phones */
.st-key-header [data-testid="stHorizontalBlock"] {flex-wrap: nowrap; align-items: center;}
.st-key-header [data-testid="stColumn"] {min-width: 0;}
.st-key-header h3 {white-space: nowrap; font-size: clamp(1.15rem, 5vw, 1.75rem);}
.st-key-header button p {white-space: nowrap;}
</style>""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading…")
def warm_up():
    load_index()
    retrieve("warm up", use_rewrite=False)  # loads the embedding model
    return True


def init_state():
    for k, v in {"history": [], "results": {}, "pending": None, "last_audio": None, "draft": None}.items():
        st.session_state.setdefault(k, v)


# ------------------------------------------------------------------ actions
def submit(text):
    """New message from the person: ask clarifying questions first if facts are missing."""
    st.session_state.draft = None
    st.session_state.draft_open = False
    if not llm.is_configured():
        st.session_state.history.append({"role": "user", "content": text})
        return
    with st.spinner("Thinking…"):
        questions = clarifying_questions(st.session_state.history + [{"role": "user", "content": text}])
    if questions:
        st.session_state.pending = {"text": text, "questions": questions, "answers": [], "done": False}
    else:
        respond(text)


def respond(text):
    st.session_state.history.append({"role": "user", "content": text})
    with st.spinner("Thinking…"):
        try:
            res = answer(st.session_state.history)
        except Exception as e:
            why = ("The free AI quota is used up for now. Please try again in a few minutes."
                   if isinstance(e, llm.RateLimited) else "Something went wrong. Please try again.")
            res = {"answer": f"{why} For urgent help: legal aid 15100, police 112.",
                   "flags": triage(text), "cited_sources": [], "citation_issues": []}
    idx = len(st.session_state.history)
    st.session_state.history.append({"role": "assistant", "content": res["answer"]})
    st.session_state.results[idx] = res


def finish_pending():
    p = st.session_state.pending
    pairs = list(zip([q["q"] for q in p["questions"]], p["answers"]))
    st.session_state.pending = None
    respond(with_details(p["text"], pairs))


def skip_remaining():
    if st.session_state.pending:
        st.session_state.pending["done"] = True


def record(answer_text):
    p = st.session_state.pending
    p["answers"].append(answer_text)
    if len(p["answers"]) >= len(p["questions"]):
        p["done"] = True


def log_feedback(idx, score):
    FEEDBACK_LOG.parent.mkdir(exist_ok=True)
    res = st.session_state.results.get(idx, {})
    with FEEDBACK_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"), "helpful": bool(score),
            "question": st.session_state.history[idx - 1]["content"] if idx > 0 else "",
            "cited": [s["id"] for s in res.get("cited_sources", [])],
            "issues": res.get("citation_issues", []), "model": res.get("model"),
        }, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ pop-ups
def question_dialog():
    p = st.session_state.pending
    i, n = len(p["answers"]), len(p["questions"])
    q = p["questions"][i]

    @st.dialog(f"Question {i + 1} of {n}", on_dismiss=skip_remaining)
    def ask():
        st.markdown(f"**{q['q']}**")
        if q["options"]:
            cols = st.columns(len(q["options"]))
            for j, opt in enumerate(q["options"]):
                if cols[j].button(opt, key=f"opt_{i}_{j}", use_container_width=True):
                    record(opt)
                    st.rerun()
        typed = st.text_input("Answer", key=f"ans_{i}", label_visibility="collapsed",
                              placeholder="Type your answer")
        c1, c2 = st.columns(2)
        if c1.button("Next", type="primary", use_container_width=True, key=f"next_{i}"):
            record(typed)
            st.rerun()
        if c2.button("Skip", use_container_width=True, key=f"skip_{i}"):
            record("")
            st.rerun()

    ask()


def close_draft():
    st.session_state.draft_open = False


@st.dialog("Draft a document", width="large", on_dismiss=close_draft)
def draft_dialog():
    first_user = next(m["content"] for m in st.session_state.history if m["role"] == "user")
    c1, c2 = st.columns([3, 1])
    doc_type = c1.selectbox("Document", list(DOC_TYPES))
    language = c2.selectbox("Language", ["English", "Hindi"],
                            index=1 if detect_language(first_user).startswith("Hindi") else 0)
    if st.button("Draft", type="primary"):
        with st.spinner("Drafting…"):
            try:
                st.session_state.draft = {"type": doc_type, **draft_document(
                    st.session_state.history, doc_type, language)}
            except llm.RateLimited:
                st.error("The free AI quota is used up for now. Please try again later.")
            except Exception:
                st.error("Could not draft right now. Please try again.")
    d = st.session_state.draft
    if d:
        key = "draft_" + hashlib.md5(d["text"].encode()).hexdigest()[:8]
        edited = st.text_area("Draft", d["text"], height=380, key=key, label_visibility="collapsed")
        st.download_button("Download", edited, use_container_width=True,
                           file_name=re.sub(r"[^A-Za-z]+", "_", d["type"].split(" (")[0]).strip("_") + ".txt")


# ------------------------------------------------------------------ rendering
def show_answer(idx, res):
    for f in res.get("flags", []):
        (st.error if f["type"] == "danger" else st.warning)(f["message"])
    st.markdown(re.sub(r"^#{1,4} ", "##### ", res["answer"], flags=re.M))
    if res.get("cited_sources"):
        with st.expander("Sources"):
            for i, s in enumerate(res["cited_sources"], 1):
                st.markdown(f"[{i}] [{s['act']}, s.{s['section']}]({s['source_url']}): {s['heading']}")
    if res.get("citation_issues"):
        with st.expander("Notes"):
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
    results, _ = retrieve(text, use_rewrite=False)
    st.markdown("\n".join(f"- [{r['act']}, s.{r['section']}]({r['source_url']}): {r['heading']}"
                          for r in results))


def main():
    init_state()
    warm_up()

    with st.container(key="header"):
        left, mid, right = st.columns([4, 1, 2], vertical_alignment="center")
        left.markdown("### ⚖️ Nyaya Saathi")
        with mid.popover("🎤"):
            audio = st.audio_input("Speak", label_visibility="collapsed")
        if right.button("New chat", use_container_width=True):
            for k in ("history", "results", "pending", "draft", "draft_open"):
                st.session_state.pop(k, None)
            st.rerun()
    if not st.session_state.history and not st.session_state.pending:
        st.caption("Legal information for everyday problems in India. Not legal advice.")

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
        if st.button("📄 Draft a document"):
            st.session_state.draft_open = True
        if st.session_state.get("draft_open"):  # stays open across reruns until dismissed
            draft_dialog()

    # Voice: transcribe once per new recording
    spoken = None
    if audio is not None:
        digest = hashlib.md5(audio.getvalue()).hexdigest()
        if digest != st.session_state.last_audio:
            st.session_state.last_audio = digest
            try:
                with st.spinner("Listening…"):
                    spoken = llm.transcribe(audio.getvalue(), "wav")
            except Exception:
                st.toast("Voice isn't available right now. Please type.")

    typed = st.chat_input("Describe your problem…")
    text = typed or spoken
    if text:
        st.session_state.pending = None  # a new message replaces unanswered questions
        submit(text)
        st.rerun()

    p = st.session_state.pending
    if p and p["done"]:
        finish_pending()
        st.rerun()
    elif p:
        question_dialog()


main()
