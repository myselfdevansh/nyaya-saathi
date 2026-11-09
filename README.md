---
title: Nyaya Saathi
emoji: ⚖️
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
pinned: false
short_description: Free legal help in India, grounded in official law
---

# Nyaya Saathi: a multi-agent AI legal assistant (Kuku assignment, Problem 2)

A conversational assistant with six specialist agents that helps ordinary people in India understand and act on everyday legal problems, grounded **only** in official law text.

## Quick start

```bash
pip install -r requirements.txt
```

```bash
python scripts/build_index.py
```

```bash
python scripts/ask.py --retrieval-only "my cheque bounced"
```

To get full answers, copy `.env.example` to `.env` and add a free key (Groq: console.groq.com, or Gemini: aistudio.google.com). Then:

```bash
python scripts/ask.py
```

```bash
python scripts/run_cases.py
```

**Chat app (text + voice + document drafting):**

```bash
streamlit run streamlit_app.py
```

The first start takes about a minute while the embedding model loads. In the app:
- **Six specialist agents:** Consumer Rights, Property & Rental, Employment & Labour, Cybercrime & Criminal, Family Law, and Banking & Finance. The app picks one automatically, or the person can choose an area. Anything else goes to a general agent that searches every Act. See [app/agents.py](app/agents.py).
- **Clarifying questions in a pop-up.** If a message is missing facts that change the legal answer, the chosen agent asks up to 8 questions **one at a time**, with quick-pick options where possible. Skip or close skips the rest. Urgent messages (danger, arrest) skip the questions.
- **Voice in the text box.** The mic is inside the chat input. Hindi speech is written out in Hinglish, and the questions, urgent warnings and answer come back in about 50-50 Hinglish.
- **Full Hindi button.** With the "हिंदी" button on, Hindi speech, questions, answers, warnings and screen text are all in Devanagari.
- **Short answers:** about 150 words in a fixed format (Where you stand / What to do / Keep as proof / See a lawyer if), with no greeting or filler.
- Sources (collapsed) with India Code links, and urgent-help banners.
- A "Draft a document" pop-up (legal notice, consumer complaint, employer/labour complaint, police complaint, RTI). It uses only the facts given and leaves `[PLACEHOLDERS]` for anything missing.
- 👍/👎 feedback, logged to `logs/feedback.jsonl`.

With no API key it falls back to "law search only".

**Free-tier resilience:** set `LLM_FALLBACK_MODELS=gemini-2.5-flash,gemini-3.1-flash-lite`. When the main model hits its quota, the next one answers, and the app shows which model answered.

**Deploy:** see [DEPLOY.md](DEPLOY.md). It deploys to a Hugging Face Space (Docker, 16 GB RAM; creating one needs a PRO account) with the search index built inside the image, plus GitHub for the code and raw outputs. Never commit `.env`.

To swap models, change `LLM_PROVIDER` / `LLM_MODEL` in `.env`. No code changes are needed: every provider is called through the same OpenAI-compatible client ([app/llm.py](app/llm.py)).

## How it works

```
user message (any language)
  │
  ├─ triage (code)           danger / arrest / fraud / out-of-scope → helplines & "see a lawyer"
  │                          (English + Hindi patterns and messages)
  ├─ language (code)         English / Hindi (Devanagari) / Hinglish (Latin) → told to the model
  ├─ front desk (LLM)        picks the specialist agent and asks its clarifying questions
  │                          (keywords pick the agent for urgent messages or if the LLM fails)
  ├─ rewrite (LLM)           lay words → English statutory phrases + legal area
  ├─ search (code)           multilingual embeddings over user words + rewrites, only in the
  │                          agent's Acts, grouped by section → top 8 official sections
  ├─ answer (LLM + agent)    specialist guidance; may only state law found in those 8 sections, citing their IDs
  └─ citation check (code)   tags, sub-sections, free-form/Hindi citations and "Section N"/"धारा N"
                             are matched to retrieved sections or removed/flagged;
                             IPC/CrPC and case names flagged → numbered sources with India Code links
```

BM25 keyword search and hybrid fusion are still in the code (`mode="hybrid"`), but embeddings alone scored best in the evaluation, so they're the default.

| File | Role |
|---|---|
| [app/agents.py](app/agents.py) | the six agents: their Acts, questions, guidance, complaint channels |
| [app/kb.py](app/kb.py) | loads sections, chunks long ones, builds/loads the index |
| [app/retrieve.py](app/retrieve.py) | query rewrite + hybrid search |
| [app/guardrails.py](app/guardrails.py) | triage rules + citation checker (code, not prompts) |
| [app/pipeline.py](app/pipeline.py) | one conversation turn, system prompt, rendering |
| [app/llm.py](app/llm.py) | swappable LLM client |

## How we know it's good (and where it isn't)

| Check | Command | Needs key? |
|---|---|---|
| Guardrail unit tests (10: citation formats seen in real outputs, triage incl. Hindi) | `python tests/test_guardrails.py` | no |
| UI test with a stand-in LLM (chat, removed citation, feedback, drafting, danger banner, reset) | `python tests/test_ui.py` | no |
| Routing: does a problem reach the right agent? 26 problems, en/hi/hinglish | `python scripts/eval_agents.py [--llm]` | only for `--llm` |
| Retrieval: is the right section in the top 8? 22 questions, en/hi/hinglish | `python scripts/eval_retrieval.py [--rewrite]` | only for `--rewrite` |
| 13 conversation cases (normal, Hindi, multi-turn, safety, adversarial, out of scope) | `python scripts/run_cases.py` (`RUN_TAG=x` for a separate folder) | yes |

**Retrieval** (`raw_outputs/retrieval_eval_*.txt`): is a correct section in the top 8?

| setup | hit@8 |
|---|---|
| keywords (BM25) on the user's words | 9% |
| embeddings on the user's words (no LLM), 49 Acts | 55% (59% with the original 23 Acts) |
| embeddings on the user's words, searching only the agent's Acts (keyword routing) | 59% |
| embeddings + Gemini rewrite, original 23 Acts, before agents | 64–73% (varies between runs because the rewrites vary) |

**Routing** (`raw_outputs/agent_eval_*.txt`): the Gemini router sent 26 of 26 test problems to the right agent. Keyword routing alone (the backup router) got 21 of 26, and its misses go to the general agent. The test set is small and I wrote it myself, so treat these as optimistic. Agent-scoped search with the Gemini rewrite has not yet been measured on the retrieval set.

Lay wording ("time to file a complaint") rarely matches statute wording ("Limitation period"). The LLM rewrite closes part of that gap. Consistent misses: Hinglish cheque bounce, fake-profile identity theft (IT Act 66C/66D), RTI for a pension file, contractor damages (Contract Act s.73), and Hinglish threats.

**Conversations:** see [raw_outputs/FINDINGS.md](raw_outputs/FINDINGS.md) for a hand review of every case, with each legal claim checked against the official text. Summary after fixes: 13/13 replies in the right language and script; 0 invented cases; 0 invented state laws; safety banners 3/3; 0 citations bypassing the checker. Before the fixes, 5 replies were in the wrong language and 2 cases had unchecked citations.

Known failure modes:
- **Correct section, wrong use.** In one run the model applied Industrial Relations Code s.59 (lay-off/retrenchment dues) to ordinary unpaid salary. The citation check proves a cited section *exists and was shown to the model*; it can't prove the model *applied it correctly*. This is the biggest remaining risk, and it needs human review or a second "verifier" pass.
- Retrieval brings in unrelated sections, and sometimes misses the best one (e.g. Code on Wages s.45 for salary claims).
- "Section N" mentions are checked by number only, not by Act.
- Agents are a scope of law plus specialist instructions on one model, not separate models. A wrongly routed problem searches the wrong Acts, and a person's chosen area is never overruled.
- Triage is keyword-based, so it over-flags (e.g. "threatened to cut my salary" → danger) and misses phrasing it doesn't know. Over-flagging is the safer error.
- The eval set is small (22) and I wrote it while building, so the scores are optimistic. Add questions you didn't tune on.

## Project layout

```
ai-lawyer/
├── app/              # RAG pipeline (see table above)
├── data/
│   ├── raw_acts/     # raw India Code API responses, one JSON per Act (audit trail)
│   ├── processed/
│   │   ├── sections.jsonl   # 5,004 cleaned sections from 49 Central Acts (the knowledge base)
│   │   └── manifest.csv     # what was fetched, section counts, missing Acts
│   └── index/        # built search index (regenerate with build_index.py)
├── scripts/          # fetch_indiacode, build_index, ask, eval_retrieval, run_cases
├── tests/            # test_guardrails.py, retrieval_eval.json, cases.json
└── raw_outputs/      # unedited outputs per model/run + FINDINGS.md (hand review)
```

## The data

**Source:** India Code (https://indiacode.gov.in), the Government of India's official repository of Central and State Acts. The old domain `indiacode.nic.in` now redirects there.

**Method:** India Code runs DSpace, which has a public REST API. Every section of a Central Act is its own record, with the official text in the field `dc.identifier.section_page_note`. The script searches for each Act, pages through its sections and cleans the HTML. No PDF parsing is needed.

**Each line of `sections.jsonl`:**

```json
{"id": "consumer_protection_act_2019__s35",
 "act": "The Consumer Protection Act, 2019", "act_year": "2019",
 "section": "35", "heading": "Manner in which complaint shall be made.",
 "text": "(1) A complaint, in relation to any goods ...",
 "repealed": "false",
 "source_url": "https://indiacode.gov.in/handle/123456789/538611"}
```

The `id` is what the bot cites. The citation checker can then confirm that every cited section really exists.

**Acts covered (49):** see [manifest.csv](data/processed/manifest.csv). The original 23 are Consumer Protection 2019, Indian Contract 1872, Specific Relief 1963, Limitation 1963, Sale of Goods 1930, Negotiable Instruments 1881 (cheque bounce), Code on Wages 2019, Industrial Relations Code 2020, Code on Social Security 2020, POSH 2013, Transfer of Property 1882, RERA 2016, Bharatiya Nyaya Sanhita 2023, Bharatiya Nagarik Suraksha Sanhita 2023, Bharatiya Sakshya Adhiniyam 2023, Domestic Violence 2005, Senior Citizens Maintenance 2007, Dowry Prohibition 1961, IT Act 2000, DPDP Act 2023, RTI 2005, Legal Services Authorities 1987, Motor Vehicles 1988. Added for the agents:
- **Family:** Hindu Marriage, Special Marriage, Divorce, Dissolution of Muslim Marriages, Muslim Women (Protection of Rights on Marriage), Hindu Adoptions and Maintenance, Hindu Minority and Guardianship, Guardians and Wards, Family Courts, Hindu Succession, Indian Succession, Prohibition of Child Marriage.
- **Banking:** Banking Regulation, RBI Act, Payment and Settlement Systems, SARFAESI, Recovery of Debts and Bankruptcy, Credit Information Companies, Banning of Unregulated Deposit Schemes.
- **Other:** Insurance 1938, Registration 1908, Indian Stamp 1899, Indian Easements 1882, Partition 1893, Code of Civil Procedure 1908, Occupational Safety, Health and Working Conditions Code 2020.

**Known limits of the data (put these in your doc):**
- **Central Acts only.** State laws are not included; rent control in particular is state-specific.
- **Payment of Wages Act 1936 and Payment of Gratuity Act 1972 are missing.** India Code no longer has section records for them as Central Acts, which suggests they've been folded into the labour codes. Verify their status before telling users anything about gratuity.
- **Amendment markers remain in the text**, e.g. `1 [` or `2 [...]`, which point to footnotes. They're harmless for retrieval but look odd if shown raw.
- **Regulator schemes are not in the data.** For example, the RBI ombudsman scheme: the banking agent points to the official portal instead of stating its deadlines.
- **Statutes only.** No rules (e.g. Consumer Protection (E-Commerce) Rules 2020), notifications (fee or ceiling amounts) or case law.
- A snapshot as of the download date. Rerun the script to refresh it.

## Refresh or extend the data

```bash
python scripts/fetch_indiacode.py
```

```bash
python scripts/fetch_indiacode.py "The Limitation Act, 1963"
```

To add an Act, copy its **exact title** from indiacode.gov.in into the `ACTS` list in the script.

## Getting data the script can't fetch (manual guide)

### 1. State Acts (e.g. rent control)
1. Open https://indiacode.gov.in and browse to **State Acts → your state**. Or search, e.g., "Rent Control".
2. Open the Act and download the **PDF** of the bare Act.
3. Save it to `data/manual/<state>_<act>.pdf`.
4. Convert it to text with `pip install pypdf`, then split it into sections. Most state Acts have headings like `5. Security deposit.`, so a regex on `^\d+[A-Z]?\.\s` works.

Suggested starting points: the Delhi Rent Control Act 1958, the Maharashtra Rent Control Act 1999 and the Karnataka Rent Act 1999. Also the Model Tenancy Act 2021, a central *model* Act that states adopt; it's useful for explaining general principles, but it's **not binding law** unless a state has adopted it.

### 2. Rules (e.g. Consumer Protection (E-Commerce) Rules, 2020)
- India Code: open the parent Act's page and find the **Rules** tab.
- Or the ministry website, e.g. https://consumeraffairs.nic.in → Acts & Rules.

### 3. Practical "how to file" information (very useful for the bot)
These are processes, not law, so write them up as short hand-checked notes in `data/manual/procedures.md`, each with its source link:
- Consumer complaints: e-Daakhil portal (https://edaakhil.nic.in), National Consumer Helpline 1915 / https://consumerhelpline.gov.in
- Free legal aid: NALSA (https://nalsa.gov.in), helpline 15100, and the State/District Legal Services Authorities
- Cyber fraud: https://cybercrime.gov.in, helpline 1930
- RTI online: https://rtionline.gov.in
- Women's helpline 181, police 112

### 4. Case law (optional, paid)
Indian Kanoon (https://indiankanoon.org) has a paid API. The brief says to describe paid tools rather than buy them, so mention it as a scale-up path. You can read individual judgments for free in the browser to hand-check things, but don't scrape the site.

**Always check facts like helpline numbers and fee limits on the official site before putting them in the bot.**
