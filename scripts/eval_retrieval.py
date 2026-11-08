"""
Measures whether search finds the right law, separately from the LLM.

For each question in tests/retrieval_eval.json we check whether any 'gold'
section appears in the top-k results. Compares BM25, embeddings and hybrid.

    python scripts/eval_retrieval.py              # raw question only (no API key needed)
    python scripts/eval_retrieval.py --rewrite    # + LLM query rewriting (needs .env)
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import llm  # noqa: E402
from app.retrieve import rewrite, search  # noqa: E402

K = 8  # matches app.retrieve.DEFAULT_K


def main():
    use_rewrite = "--rewrite" in sys.argv
    if use_rewrite and not llm.is_configured():
        sys.exit("--rewrite needs an LLM configured in .env")
    cases = json.loads((ROOT / "tests" / "retrieval_eval.json").read_text(encoding="utf-8"))
    # bm25/dense/hybrid: each method alone on all queries.
    # pipeline: exactly what the app does (app.retrieve.retrieve).
    modes = ["bm25", "dense", "hybrid", "pipeline"]
    stats = {m: {"hit1": 0, "hit3": 0, "hitk": 0, "mrr": 0.0} for m in modes}
    rows = []

    for c in cases:
        if use_rewrite:
            rw = rewrite(c["q"])
            queries, areas = list(dict.fromkeys(rw["queries"] + [c["q"]])), rw["areas"]
        else:
            rw, queries, areas = None, [c["q"]], []
        row = {"q": c["q"], "lang": c["lang"], "gold": c["gold"], "rewrite": rw}
        rewritten = [q for q in queries if q != c["q"]]
        for m in modes:
            if m == "pipeline":  # mirrors app.retrieve.retrieve (dense, user words + rewrites)
                res = search(rewritten + [c["q"]], areas, k=K, mode="dense")
            else:
                res = search(queries, areas, k=K, mode=m)
            ids = [r["id"] for r in res]
            rank = next((i + 1 for i, x in enumerate(ids) if x in c["gold"]), None)
            s = stats[m]
            s["hit1"] += rank == 1
            s["hit3"] += bool(rank and rank <= 3)
            s["hitk"] += bool(rank)
            s["mrr"] += 1 / rank if rank else 0
            row[m] = {"rank": rank, "top": ids}
        rows.append(row)

    n = len(cases)
    label = "with LLM rewrite" if use_rewrite else "raw question"
    lines = [f"Retrieval eval ({label}), {n} questions, k={K}",
             f"{'mode':8} {'hit@1':>6} {'hit@3':>6} {'hit@'+str(K):>6} {'MRR':>6}"]
    for m in modes:
        s = stats[m]
        lines.append(f"{m:8} {s['hit1']/n:6.0%} {s['hit3']/n:6.0%} {s['hitk']/n:6.0%} {s['mrr']/n:6.2f}")
    lines.append(f"\nPer question (pipeline rank; '-' = not in top {K}):")
    for r in rows:
        mark = r["pipeline"]["rank"] or "-"
        lines.append(f"  [{mark}] ({r['lang']}) {r['q'][:80]}")
        if not r["pipeline"]["rank"]:
            lines.append(f"       got: {', '.join(r['pipeline']['top'][:3])}")
    report = "\n".join(lines)
    sys.stdout.reconfigure(encoding="utf-8")  # Hindi on a Windows console
    print(report)

    out = ROOT / "raw_outputs"
    out.mkdir(exist_ok=True)
    tag = "rewrite" if use_rewrite else "raw"
    (out / f"retrieval_eval_{tag}.txt").write_text(report, encoding="utf-8")
    (out / f"retrieval_eval_{tag}.json").write_text(
        json.dumps({"stats": stats, "n": n, "rows": rows, "model": llm.model_name() if use_rewrite else None,
                    "time": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
