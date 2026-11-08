"""
Headless UI test with a stand-in LLM (no API calls, no quota used).
Run: python tests/test_ui.py
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LLM_PROVIDER", "gemini")
os.environ.setdefault("LLM_API_KEY", "test-key")

from streamlit.testing.v1 import AppTest  # noqa: E402

from app import llm  # noqa: E402

CALLS = []
FIRST = {}
SEEN = {}


def fake_chat(messages, **kw):
    system = messages[0]["content"]
    CALLS.append(system[:30])
    if "front desk" in system:  # intake: routing and clarifying questions
        SEEN["intake_system"] = system
        return ('{"agent": "consumer", "questions": [{"q": "Did they confirm the pickup in writing?", '
                '"options": ["Yes", "No"]}, {"q": "What was the price?", "options": []}]}')
    if "search queries" in system:  # rewrite step
        return '{"english_summary": "refund", "queries": ["refund of consideration defective goods"], "areas": ["consumer"]}'
    real = re.search(r"^\[([a-z0-9_]+__s[0-9A-Z]+)\]", system.split("SOURCES", 1)[1], re.M).group(1)
    FIRST["id"] = real
    if "You draft documents" in system:
        return f"LEGAL NOTICE\nTo: [SELLER NAME]\nRefund Rs 18,000 [{real}] and [made_up_act__s9].\nCHECKLIST:\n- [SELLER NAME]"
    SEEN["last_user"] = messages[-1]["content"]
    SEEN["answer_system"] = system
    return f"**Where you stand**\n- You can complain [{real}]. Also [consumer_protection_act_2019__s999]."


llm.chat = fake_chat


def voice_module_from_voice():
    """The same rule as streamlit_app.from_voice, which can't be imported without running the app."""
    src = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    body = src[src.index("def from_voice"):src.index("def log_feedback")]
    from app.pipeline import HINGLISH
    scope = {"llm": llm, "HINGLISH": HINGLISH}
    exec(body, scope)
    return scope["from_voice"](b"audio")


def buttons(at, label):
    return [b for b in at.button if b.label == label]


def fresh(at, **overrides):
    """
    New AppTest with the same session state. AppTest keeps closed pop-ups' widgets in its element
    tree and tries to resend their state, so after a pop-up closes we continue in a fresh tree.
    """
    keys = ("history", "results", "pending", "draft", "draft_open", "pinned", "agent")
    state = {k: at.session_state[k] for k in keys if k in at.session_state}
    state.update(overrides)
    new = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=180)
    for k, v in state.items():
        new.session_state[k] = v
    new.run()
    return new


def main():
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    assert any("Nyaya Saathi" in m.value for m in at.markdown)
    cards = [b for b in at.button if (b.key or "").startswith("card_")]
    assert len(cards) == 6, "six agent cards"
    assert "Consumer Rights" in cards[0].label, "consumer agent comes first"
    assert at.chat_input[0].proto.accept_audio, "mic belongs inside the chat input"
    print("PASS empty state: six agent cards, mic in the text box")

    # Picking a card pins that agent
    [b for b in at.button if b.key == "card_banking"][0].click().run()
    assert at.session_state["pinned"] == "banking"
    assert any("Banking & Finance" in m.value for m in at.markdown)
    at.chat_input[0].set_value("My bank froze my account").run()
    assert "- banking:" in SEEN["intake_system"] and "- consumer:" not in SEEN["intake_system"]
    assert at.session_state["agent"] == "banking"
    print("PASS a chosen agent is respected")
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=180)
    at.run()

    # 1. Incomplete message -> pop-up question 1 with options
    at.chat_input[0].set_value("My phone refund is pending").run()
    assert not at.exception, at.exception
    assert any("confirm the pickup" in m.value for m in at.markdown), "question 1 not shown"
    assert buttons(at, "Yes") and buttons(at, "Next") and buttons(at, "Skip")
    print("PASS question 1 shown in pop-up with options")

    # 2. Pick an option -> question 2; type an answer -> answer generated
    buttons(at, "Yes")[0].click().run()
    assert any("What was the price" in m.value for m in at.markdown), "question 2 not shown"
    at.text_input(key="ans_1").set_value("Rs 18,000").run()
    buttons(at, "Next")[0].click().run()
    assert not at.exception, at.exception
    assert at.session_state["pending"] is None
    assert "- Did they confirm the pickup in writing? Yes" in SEEN["last_user"]
    assert "- What was the price? Rs 18,000" in SEEN["last_user"]
    md = " ".join(m.value for m in at.markdown)
    assert "[1]" in md and "citation removed" in md
    assert "YOUR SPECIALITY: Consumer Rights" in SEEN["answer_system"]
    assert at.session_state["results"][1]["agent"] == "consumer"
    assert "ENTIRE reply in English" in SEEN["answer_system"], "typed English stays English"
    print("PASS answers folded into the question; answer rendered with checked citations")

    # 3. Feedback (fresh AppTest on the same session state: the old element tree still holds
    #    the closed pop-up's text box, which AppTest would try to resend)
    at = fresh(at)
    log = ROOT / "logs" / "feedback.jsonl"
    before = log.read_text(encoding="utf-8").count("\n") if log.exists() else 0
    at.feedback[0].set_value(1).run()
    assert log.read_text(encoding="utf-8").count("\n") == before + 1
    lines = log.read_text(encoding="utf-8").splitlines()
    log.write_text("".join(x + "\n" for x in lines[:-1]), encoding="utf-8")  # remove the test entry
    print("PASS feedback logged")

    # 4. Draft pop-up
    buttons(at, "Draft a document")[0].click().run()
    buttons(at, "Draft")[0].click().run()
    assert not at.exception, at.exception
    box = [t for t in at.text_area]
    sec = FIRST["id"].split("__s")[1]
    assert box and f"(Section {sec}, " in box[0].value and "made_up_act" not in box[0].value
    print("PASS draft pop-up: real citation expanded, invented one removed")

    # 5. Urgent message -> no questions, danger banner
    at.chat_input[0].set_value("My husband beats me every day").run()
    assert at.session_state["pending"] is None
    assert any("112" in w.value for w in at.error)
    print("PASS urgent message skips questions and shows danger banner")

    # 6. New chat, then skip all questions
    at = fresh(at, draft_open=False)
    buttons(at, "New chat")[0].click().run()
    assert len(at.session_state["history"]) == 0
    at.chat_input[0].set_value("Refund not received").run()
    buttons(at, "Skip")[0].click().run()
    buttons(at, "Skip")[0].click().run()
    assert at.session_state["pending"] is None and SEEN["last_user"] == "Refund not received"
    print("PASS skipping all questions answers with the original message")

    # 7. Hindi speech: questions and answer are forced to Hinglish, including urgent banners
    from app import pipeline
    transcribed = {"language": "hindi", "text": "meri salary nahi mili"}
    llm.transcribe = lambda *a, **k: transcribed
    calls = {}
    real_intake, real_answer = pipeline.intake, pipeline.answer
    def spy_intake(history, pinned=None, language=None, max_q=3):
        calls["intake"] = language
        return {"agent": "employment", "questions": []}
    def spy_answer(history, k=8, agent=None, language=None):
        calls["answer"] = language
        return real_answer(history, k=k, agent=agent, language=language)
    pipeline.intake, pipeline.answer = spy_intake, spy_answer
    text, language = voice_module_from_voice()
    assert text == "meri salary nahi mili" and language == pipeline.HINGLISH
    res = spy_answer([{"role": "user", "content": text}], agent="employment", language=language)
    assert res["language"] == pipeline.HINGLISH and "Write your ENTIRE reply in Hinglish" in SEEN["answer_system"]
    transcribed["language"] = "english"
    assert voice_module_from_voice()[1] is None, "English speech is not forced to Hinglish"
    pipeline.intake, pipeline.answer = real_intake, real_answer
    print("PASS Hindi speech is answered in Hinglish; English speech is not")
    print(f"{len(CALLS)} stand-in LLM calls; all UI tests passed")


if __name__ == "__main__":
    main()
