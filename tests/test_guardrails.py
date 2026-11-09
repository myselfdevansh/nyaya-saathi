"""Run: python tests/test_guardrails.py   (no API key needed)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.guardrails import check_citations, triage  # noqa: E402

RETRIEVED = [
    {"id": "negotiable_instruments_act_1881__s138", "act": "The Negotiable Instruments Act, 1881",
     "section": "138", "heading": "Dishonour of cheque", "source_url": "u1", "excerpt": ""},
    {"id": "consumer_protection_act_2019__s35", "act": "The Consumer Protection Act, 2019",
     "section": "35", "heading": "Manner in which complaint shall be made.", "source_url": "u2", "excerpt": ""},
]


def test_valid_citations_are_numbered():
    text, cited, issues = check_citations(
        "Bounced cheque is an offence [negotiable_instruments_act_1881__s138]. "
        "Again [negotiable_instruments_act_1881__s138]; complaint [consumer_protection_act_2019__s35].",
        RETRIEVED)
    assert "[1]" in text and "[2]" in text and "__s" not in text
    assert [c["section"] for c in cited] == ["138", "35"]
    assert issues == []


def test_invented_citation_is_removed():
    text, cited, issues = check_citations("You can also use [consumer_protection_act_2019__s999].", RETRIEVED)
    assert "s999" not in text and "citation removed" in text
    assert cited == [] and len(issues) == 1


def test_untagged_section_number_is_flagged():
    _, _, issues = check_citations("Under Section 420 you can file a case.", RETRIEVED)
    assert any("420" in i for i in issues)


def test_old_criminal_codes_flagged():
    _, _, issues = check_citations("This is cheating under the IPC.", RETRIEVED)
    assert any("IPC" in i for i in issues)


def test_case_law_flagged():
    _, _, issues = check_citations("As held in Ramesh Kumar vs State of Punjab, ...", RETRIEVED)
    assert any("court case" in i for i in issues)


def test_subsection_tag_accepted():
    # Seen in real output (gemini-3.1-flash-lite): tag with sub-section suffix
    text, cited, issues = check_citations("Refund with interest [consumer_protection_act_2019__s35(1)].", RETRIEVED)
    assert "[1]" in text and [c["section"] for c in cited] == ["35"] and issues == []


def test_loose_hindi_citation_resolved_or_removed():
    # Seen in real output: free-form Hindi citation instead of the tag
    text, cited, issues = check_citations("चेक बाउंस अपराध है [परक्राम्य लिखत अधिनियम, धारा 138]।", RETRIEVED)
    assert "[1]" in text and [c["section"] for c in cited] == ["138"]
    text, cited, issues = check_citations("गिरफ्तारी [भारतीय नागरिक सुरक्षा संहिता, 2023, धारा 47(1)]।", RETRIEVED)
    assert "citation removed" in text and cited == [] and len(issues) == 1


def test_hindi_section_mention_flagged():
    _, _, issues = check_citations("धारा 420 के तहत केस करें।", RETRIEVED)
    assert any("420" in i for i in issues)


def test_plain_mention_gets_source_link():
    # Seen in real output: "Code on Wages, 2019, Section 59" written without a tag
    _, cited, issues = check_citations("Under Section 138 the drawer can be punished.", RETRIEVED)
    assert [c["section"] for c in cited] == ["138"] and issues == []


def test_triage():
    assert {f["type"] for f in triage("my husband beats me every night")} == {"danger"}
    assert "arrest_court" in {f["type"] for f in triage("I got a court summons for next week")}
    assert "cyber_fraud" in {f["type"] for f in triage("I shared OTP and money was debited")}
    assert "out_of_scope" in {f["type"] for f in triage("I got an income tax notice")}
    assert "out_of_scope" not in {f["type"] for f in triage("I want a divorce and I will file soon")}
    # Hindi speech is transcribed into Latin letters, so urgent Hinglish must be caught, in Hinglish.
    flags = triage("mera pati mujhe roz marta hai", "Hinglish (Hindi written in English/Latin letters)")
    assert flags and flags[0]["type"] == "danger" and "turant 112" in flags[0]["message"]
    # Full Hindi mode: warnings are in Devanagari even when the text isn't.
    flags = triage("my husband beats me", "Hindi, in Devanagari script")
    assert flags and "तुरंत" in flags[0]["message"]
    assert triage("Amazon did not refund my money for a returned phone") == []
    # Hindi (Devanagari)
    assert "danger" in {f["type"] for f in triage("मेरे पति मुझे रोज़ मारते हैं")}
    assert "arrest_court" in {f["type"] for f in triage("पुलिस ने मेरे भाई को गिरफ्तार किया")}
    assert triage("मेरी कंपनी ने तनख्वाह नहीं दी") == []


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} passed")
