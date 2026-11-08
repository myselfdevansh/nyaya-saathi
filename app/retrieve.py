"""
Hybrid retrieval:
  1. (optional) the LLM rewrites a lay question, in any language, into English
     legal search terms and picks likely legal areas,
  2. BM25 keyword search and embedding search each return candidates,
  3. results are merged with Reciprocal Rank Fusion (RRF),
  4. chunks are grouped back into sections, so we cite sections, not fragments.
"""

import numpy as np

from . import agents, llm
from .kb import get_embedder, load_index, tokenize

# Legal areas -> Acts. The rewriter picks areas; we boost Acts in those areas.
AREAS = {
    "consumer": ["The Consumer Protection Act, 2019", "The Sale of Goods Act, 1930"],
    "contract_money": ["The Indian Contract Act, 1872", "The Specific Relief Act, 1963",
                       "The Limitation Act, 1963", "The Negotiable Instruments Act, 1881"],
    "employment": ["The Code on Wages, 2019", "The Industrial Relations Code, 2020",
                   "The Code on Social Security, 2020",
                   "The Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013"],
    "housing": ["The Transfer of Property Act, 1882", "The Real Estate (Regulation and Development) Act, 2016"],
    "criminal": ["The Bharatiya Nyaya Sanhita, 2023", "The Bharatiya Nagarik Suraksha Sanhita, 2023",
                 "The Bharatiya Sakshya Adhiniyam, 2023"],
    "family": agents.AGENTS["family"]["acts"],
    "banking": agents.AGENTS["banking"]["acts"],
    "cyber_privacy": ["The Information Technology Act, 2000", "The Digital Personal Data Protection Act, 2023"],
    "government": ["The Right to Information Act, 2005", "The Legal Services Authorities Act, 1987"],
    "accident": ["The Motor Vehicles Act, 1988"],
}

REWRITE_PROMPT = """You turn a person's description of a legal problem in India into search queries over Indian Central Acts.
The person may write in Hindi, Hinglish, English or another Indian language.
Return ONLY JSON:
{"english_summary": "<one sentence, English>",
 "queries": ["<3-5 short English queries using statutory wording, e.g. 'dishonour of cheque insufficiency of funds', 'time limit for payment of wages'>"],
 "areas": ["<1-3 of: %s>"]}
Do NOT name section numbers; you might be wrong. Use plain legal phrases.""" % ", ".join(AREAS)

RRF_K = 60


def rewrite(question, agent=None):
    system = REWRITE_PROMPT
    if agent and agent != "general":
        system += f"\nThis is a matter about {agents.get(agent)['route']}; write queries for that area of law."
    try:
        out = llm.chat_json([
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ], max_tokens=1500)
        queries = [q for q in out.get("queries", []) if isinstance(q, str)][:5]
        areas = [a for a in out.get("areas", []) if a in AREAS]
        return {"summary": out.get("english_summary", question), "queries": queries or [question], "areas": areas}
    except Exception as e:  # no LLM / bad JSON: fall back to the raw question
        return {"summary": question, "queries": [question], "areas": [], "rewrite_error": str(e)}


def _bm25_ranks(index, query, n, mask=None):
    scores = index["bm25"].get_scores(tokenize(query))
    if mask is not None:
        scores = np.where(mask, scores, -np.inf)
    return list(np.argsort(-scores)[:n])


def _dense_ranks(index, query, n, mask=None):
    q = get_embedder().encode([f"query: {query}"], normalize_embeddings=True)[0]
    sims = index["embeddings"] @ q
    if mask is not None:
        sims = np.where(mask, sims, -np.inf)
    return list(np.argsort(-sims)[:n])


def search(queries, areas=(), k=6, mode="hybrid", per_list=50, dense_queries=(), acts=None):
    """
    Return the top-k sections.
    queries:       searched with `mode` (bm25 / dense / hybrid)
    dense_queries: searched with embeddings only. Used for the user's own words:
                   lay or Hindi phrasing rarely shares keywords with statute text,
                   so BM25 on it adds noise (measured: see raw_outputs/retrieval_eval_raw.txt).
    acts:          if given, only these Acts are searched (an agent's scope of law)
    """
    index = load_index()
    chunks = index["chunks"]
    mask = None
    if acts:
        wanted = set(acts)
        mask = np.array([c["act"] in wanted for c in chunks])
    fused = {}
    jobs = [(q, mode) for q in queries] + [(q, "dense") for q in dense_queries]
    for q, m in jobs:
        lists = []
        if m in ("hybrid", "bm25"):
            lists.append(_bm25_ranks(index, q, per_list, mask))
        if m in ("hybrid", "dense"):
            lists.append(_dense_ranks(index, q, per_list, mask))
        for ranks in lists:
            for rank, ci in enumerate(ranks):
                fused[ci] = fused.get(ci, 0.0) + 1.0 / (RRF_K + rank)

    boosted_acts = {a for area in areas for a in AREAS.get(area, [])}
    by_section = {}
    for ci, score in fused.items():
        c = chunks[ci]
        if c["act"] in boosted_acts:
            score *= 1.5
        best = by_section.get(c["section_id"])
        if best is None or score > best["score"]:
            by_section[c["section_id"]] = {"score": score, "chunk": c}

    top = sorted(by_section.values(), key=lambda x: -x["score"])[:k]
    results = []
    for t in top:
        s = index["sections"][t["chunk"]["section_id"]]
        results.append({
            "id": s["id"], "act": s["act"], "section": s["section"], "heading": s["heading"],
            "excerpt": t["chunk"]["text"], "source_url": s["source_url"], "score": round(t["score"], 4),
        })
    return results


# Chosen by measurement (raw_outputs/retrieval_eval_*.txt): on our 22-question set,
# embeddings alone beat BM25 and hybrid, both with and without the LLM rewrite,
# because BM25 latches onto shared words ("register FIR" -> vehicle "registration").
# k=8 finds the right section for more questions than k=6 at little extra prompt cost.
DEFAULT_MODE = "dense"
DEFAULT_K = 8


def retrieve(question, k=DEFAULT_K, use_rewrite=True, mode=DEFAULT_MODE, agent=None):
    acts = agents.get(agent)["acts"] if agent else None
    if use_rewrite and llm.is_configured():
        rw = rewrite(question, agent)
    else:
        rw = {"summary": question, "queries": [], "areas": [], "rewrite_error": "no LLM configured"}
    # Always also search the user's own words, in case the rewrite misses something.
    rewritten = [q for q in rw["queries"] if q != question]
    if mode == "hybrid":  # BM25 only on legal phrasing; user's words via embeddings
        return search(rewritten, rw["areas"], k=k, mode="hybrid", dense_queries=[question], acts=acts), rw
    return search(rewritten + [question], rw["areas"], k=k, mode=mode, acts=acts), rw
