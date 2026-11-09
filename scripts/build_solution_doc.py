"""Builds Nyaya_Saathi_Solution_Doc.pdf. Case counts are read from the latest test run."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, NextPageTemplate, PageTemplate, Paragraph, Spacer,
                                Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "raw_outputs" / "gemini_gemini-3.5-flash_final-agents"
OUT = ROOT / "Nyaya_Saathi_Solution_Doc.pdf"
CASES = len(list(RUN.glob("*.md")))

INK = colors.HexColor("#111111")
RULE = colors.HexColor("#777777")
SHADE = colors.HexColor("#EEF1F6")

body = ParagraphStyle("body", fontName="Times-Roman", fontSize=10, leading=11.9, alignment=TA_JUSTIFY, textColor=INK,
                      spaceAfter=2.6)
head = ParagraphStyle("head", fontName="Times-Bold", fontSize=11, leading=13, spaceBefore=6, spaceAfter=1.8,
                      textColor=INK)
title = ParagraphStyle("title", fontName="Times-Bold", fontSize=16, leading=19, alignment=TA_CENTER, textColor=INK)
sub = ParagraphStyle("sub", fontName="Times-Roman", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=INK)
abstract = ParagraphStyle("abstract", parent=body, fontName="Times-Italic", fontSize=9.1, leading=10.8, leftIndent=8,
                          rightIndent=8, spaceAfter=0)
cell = ParagraphStyle("cell", fontName="Times-Roman", fontSize=8.7, leading=10)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Times-Bold")
caption = ParagraphStyle("caption", fontName="Times-Italic", fontSize=7.9, leading=9.2, alignment=TA_CENTER,
                         spaceBefore=1.5, spaceAfter=3.5)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=8, bulletIndent=0, spaceAfter=1.5)


def P(text, style=body):
    return Paragraph(text, style)


def B(text):
    return Paragraph(text, bullet, bulletText="•")


def table(rows, widths, header=True):
    data = [[P(c, cellb if header and i == 0 else cell) for c in row] for i, row in enumerate(rows)]
    t = Table(data, colWidths=widths)
    style = [("LINEABOVE", (0, 0), (-1, 0), 0.8, INK), ("LINEBELOW", (0, -1), (-1, -1), 0.8, INK),
             ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
             ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6)]
    if header:
        style.append(("LINEBELOW", (0, 0), (-1, 0), 0.4, INK))
    t.setStyle(TableStyle(style))
    return t


def pipeline(width):
    steps = ["Message or voice", "Triage (code)", "Front desk: pick agent, ask questions (LLM)",
             "Search agent's Acts (code)", "Answer from sources (LLM)", "Citation and limit checks (code)"]
    t = Table([[P(s, ParagraphStyle("f", parent=cell, alignment=TA_CENTER, fontSize=7.3, leading=8.3)) for s in steps]],
              colWidths=[width / 6] * 6)
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, RULE), ("INNERGRID", (0, 0), (-1, -1), 0.5, RULE),
                           ("BACKGROUND", (0, 0), (-1, -1), SHADE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 1.5), ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
                           ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


W, H = A4
M = 15 * mm
GAP = 6 * mm
COL = (W - 2 * M - GAP) / 2
TOP_H = 43 * mm


def footer(canvas, doc):
    canvas.setFont("Times-Roman", 8)
    canvas.setFillColor(RULE)
    canvas.drawCentredString(W / 2, 8.5 * mm, f"Page {doc.page} of 2")


doc = BaseDocTemplate(str(OUT), pagesize=A4, leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M,
                      title="Nyaya Saathi: A Multi-Agent Legal Assistant for India", author="Devansh Verma",
                      subject="Kuku AI Generalist Assignment, Problem 2")
y_top = H - M - TOP_H
first = [Frame(M, y_top, W - 2 * M, TOP_H, id="top", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
         Frame(M, 13 * mm, COL, y_top - 13 * mm - 2 * mm, id="c1", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
         Frame(M + COL + GAP, 13 * mm, COL, y_top - 13 * mm - 2 * mm, id="c2", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]
second = [Frame(M, 13 * mm, COL, H - M - 13 * mm, id="c3", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
          Frame(M + COL + GAP, 13 * mm, COL, H - M - 13 * mm, id="c4", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]
doc.addPageTemplates([PageTemplate(id="first", frames=first, onPage=footer),
                      PageTemplate(id="second", frames=second, onPage=footer)])

s = [
    P("Nyaya Saathi: A Multi-Agent Legal Assistant for India", title),
    Spacer(1, 2),
    P("Devansh Verma &nbsp;|&nbsp; Kuku AI Generalist Assignment, Problem 2: Build an AI Lawyer", sub),
    P('Prototype: <a href="https://nyaya-saathi.streamlit.app/" color="#1F3A8A">nyaya-saathi.streamlit.app</a> &nbsp;|&nbsp; '
      'Code and raw outputs: <a href="https://github.com/myselfdevansh/nyaya-saathi" color="#1F3A8A">github.com/myselfdevansh/nyaya-saathi</a>', sub),
    Spacer(1, 4),
    P("<b>Abstract.</b> Most people in India never get help with everyday legal problems. Nyaya Saathi takes a problem by "
      "text or voice in English, Hindi or Hinglish, sends it to one of six specialist agents, asks only the questions that "
      "change the answer, and replies in about 150 words with what to do and when a lawyer is needed. Legal claims are limited "
      "to official text from 49 Central Acts, and code checks every citation before the user sees it. The router placed 26 of "
      "26 test problems correctly. The main weakness is search: it found the right section for only about two-thirds of test "
      "questions in the best earlier run, and when it misses, answers get thinner or lean on weaker sections.", abstract),
    NextPageTemplate("second"),
    FrameBreak(),

    P("1. Problem choice and scope", head),
    P("I chose Problem 2 because the harm is concrete and the output can be checked: every legal claim can be compared with "
      "the official text. Covering all Indian law is not realistic, so I scoped to the everyday problems named in the brief, "
      "grouped into six agents: Consumer Rights, Property and Rental, Employment and Labour, Cybercrime and Criminal, Family "
      "Law, and Banking and Finance. A general agent handles anything else, such as road accidents or RTI."),

    P("2. Assumptions", head),
    B("Users have a phone and little legal knowledge, and prefer short steps to long explanations."),
    B("Central Acts are the right free starting point. State rent law, rules, notifications and case law are out of scope, "
      "and the assistant says so rather than guessing."),
    B("This gives legal information, not advice. It should get people moving and tell them when a lawyer is needed."),
    B("Payment of Wages and Payment of Gratuity Acts had no section records on India Code, so they are excluded."),

    P("3. How it works", head),
    pipeline(COL),
    P("Fig. 1. One turn of conversation. Code owns safety and verification.", caption),
    P("<b>Data.</b> 5,004 sections from 49 Acts come from India Code's public API, split into 6,749 chunks with multilingual "
      "embeddings that run on CPU. <b>Agents.</b> An agent is one model plus its own Acts, questions, guidance and complaint "
      "channels, not a separate model. If a person picks an area, the router doesn't overrule them. <b>Questions.</b> Up to 8, "
      "one at a time in a pop-up, skipped for danger or arrest. <b>Language.</b> Replies follow the user's script. Hindi "
      "speech gets about 50-50 Hinglish, or full Devanagari with the Hindi button. <b>Output.</b> Where you stand, what to do, "
      "what to keep as proof, when to see a lawyer, linked sources, and a draft notice or complaint with placeholders for "
      "missing facts. <b>Model swap.</b> One line in <font name='Courier' size='7.8'>.env</font>; every provider uses the same "
      "client, with automatic fallback when a model hits its limit."),
    table([["Given to the LLM", "Kept as code or rules"],
           ["Routing, clarifying questions, query rewriting, plain-language answers, drafting, speech-to-text",
            "Danger, arrest and fraud triage; language detection; Act scope per agent; citation checks; removing unverifiable ombudsman limits"]],
          [COL * 0.48, COL * 0.52]),
    P("Table 1. Division of work.", caption),

    P("4. How it avoids invented law", head),
    B("<b>Closed sources.</b> The model sees 8 retrieved sections and may cite only their IDs."),
    B("<b>Citation checker.</b> Any cited section not retrieved is removed and noted. Free-form and Hindi citations are matched "
      "to retrieved sections or removed."),
    B("<b>Flags.</b> IPC/CrPC references and case names are flagged, since the system has no case-law database."),
    B("<b>Scheme limits.</b> Ombudsman deadlines aren't in the data, so code replaces any such line with a pointer to the official site."),
    B("<b>Human route.</b> Urgent banners and lawyer or NALSA 15100 referrals are built in; 👍/👎 feedback is logged."
      .replace("👍/👎", "thumbs up/down")),

    P("5. How I know it is good", head),
    table([["Check", "Result"],
           ["Agent routing, 26 problems in 3 languages", "Gemini 26/26; backup keywords 21/26"],
           ["Right section in top 8, user's words only, 22 questions", "BM25 9%; embeddings 55%; embeddings in keyword-routed agent's Acts 59%"],
           ["Same, with LLM rewrite (earlier 23-Act version)", "64-73%, varying by run"],
           ["Automated guardrail and UI tests, with a stand-in LLM", "11 and 11 pass"],
           ["Fixed: unverifiable ombudsman limits, 4 real answers", "Model stated one in 2; 0 reached the user"],
           ["Voice, generated Hindi audio", "Transcribed correctly in both scripts"],
           [f"End-to-end conversations, {CASES} in raw outputs", "Unedited, with retrieved sources and checker notes"]],
          [COL * 0.56, COL * 0.44]),
    P("Table 2. Results from real runs. The test sets are small and self-written, so scores are optimistic.", caption),
    P("Good examples from the runs: a delayed flat cites RERA s.18 on return of amount and compensation; an elderly parent "
      "gets the Senior Citizens Act maintenance route; a Hindi domestic violence message shows 112 and 181 first. Asked for "
      "Supreme Court judgments it can't verify, it doesn't supply them."),

    P("6. Where it fails", head),
    table([["Failure seen", "Status"],
           ["<b>Right law not retrieved.</b> Job scam: BNS s.318 (cheating) wasn't retrieved, the checker removed the citation, and the answer cited weaker forgery sections. Cheque bounce: NI Act s.138 was flagged as unverified.",
            "Open. Search is the top priority."],
           ["<b>Thin answers.</b> Unpaid salary cites only Code on Wages s.59 (burden of proof) and misses when wages are due and how to claim.",
            "Open."],
           ["<b>Misapplied law.</b> An earlier run applied Industrial Relations Code s.59 (lay-off dues) to ordinary salary. The checker proves a section was retrieved, not that it fits.",
            "Reduced by a prompt rule, not solved. Needs a verifier or human review."],
           ["<b>Model ignores instructions.</b> It stated a 30-day RBI wait despite being told not to.",
            "Fixed in code for one-line cases. A limit on a separate line could pass."],
           ["<b>Untested.</b> Real microphone speech; languages beyond English and Hindi.", "Open."]],
          [COL * 0.68, COL * 0.32]),
    P("Table 3. Known failures.", caption),

    P("7. Scale and cost", head),
    P("Each message makes 3 model calls (front desk, rewrite, answer), plus 1 for voice. Embeddings run locally and hosting is "
      "free, so the model is the main running cost. The free tier is the first limit: one earlier run exhausted a model's quota "
      "after about 45 calls, and fallback models only delay that. Real traffic needs a paid API, which needs no code change, "
      "plus a real server, because the free host sleeps when idle and takes a minute or more to restart. New law scales cheaply: "
      "add an Act's title, rerun the script, rebuild the index (about 10 minutes for 49 Acts on a laptop). State law is the "
      "highest-value addition. Paid case-law APIs could help, and I'd use them to improve questions before showing any case to users."),

    P("8. Human in the loop", head),
    P("The assistant doesn't replace review. Before real use, a lawyer should sample answers each week, starting with "
      "thumbs-down cases, and approve every agent's question list and complaint channels. I'd measure whether people took the "
      "next step, not only whether they liked the answer."),

    P("9. AI tools, and where they got it wrong", head),
    P("I used Claude Code to build and test the system and Gemini as the app's model. Both made mistakes. Claude told me "
      "Hugging Face Docker Spaces were free; the site showed them as paid, and I moved to Streamlit Cloud. Gemini misapplied "
      "law and stated the RBI wait above. The lesson shaped the design: check against the source, and keep the rules that "
      "matter in code."),

    P("10. Next steps", head),
    P("Fix search first, using questions I didn't tune on. Then add a verifier pass and state rent law. Then distil the deciding "
      "facts from 20-30 judgments per agent into better questions, using the CC-BY Supreme Court and High Court datasets, and "
      "compare the questions before and after."),
]
doc.build(s)
print("built", OUT, "cases", CASES)
