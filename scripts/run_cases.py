"""
Run every conversation in tests/cases.json and save UNEDITED outputs to
raw_outputs/<model>/ (one .md per case + a summary.json).

    python scripts/run_cases.py                    # all cases
    python scripts/run_cases.py rent_deposit_state  # one case

Rerun with a different LLM_PROVIDER / LLM_MODEL in .env to compare models.
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import llm  # noqa: E402
from app.pipeline import answer, render  # noqa: E402


def main():
    if not llm.is_configured():
        sys.exit("No LLM configured: copy .env.example to .env and add a key.")
    cases = json.loads((ROOT / "tests" / "cases.json").read_text(encoding="utf-8"))
    only = set(sys.argv[1:])
    import os
    tag = os.getenv("RUN_TAG", "")  # e.g. RUN_TAG=after-fixes keeps earlier runs intact
    out_dir = ROOT / "raw_outputs" / (re.sub(r"[^a-zA-Z0-9.-]+", "_", llm.model_name()) + (f"_{tag}" if tag else ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []

    for case in cases:
        if only and case["id"] not in only:
            continue
        print(f"- {case['id']}")
        history, md = [], [f"# {case['id']} ({case['type']})", f"Model: {llm.model_name()}",
                           f"Expected: {case['expect']}", ""]
        turn_logs = []
        for user_msg in case["turns"]:
            history.append({"role": "user", "content": user_msg})
            t0 = time.time()
            try:
                res = answer(history)
            except Exception as e:
                md += [f"## User\n{user_msg}", f"## ERROR\n{e}"]
                turn_logs.append({"error": str(e)})
                break
            history.append({"role": "assistant", "content": res["answer"]})
            md += [f"## User\n{user_msg}", f"## Assistant\n{render(res)}",
                   "<details><summary>Retrieved sources</summary>\n",
                   *[f"- {r['id']} ({r['heading']}) score={r['score']}" for r in res["retrieved"]],
                   f"\nRewrite: {json.dumps(res['rewrite'], ensure_ascii=False)}\n</details>", ""]
            turn_logs.append({
                "seconds": round(time.time() - t0, 1),
                "flags": [f["type"] for f in res["flags"]],
                "language": res["language"],
                "cited": [s["id"] for s in res["cited_sources"]],
                "retrieved": [r["id"] for r in res["retrieved"]],
                "citation_issues": res["citation_issues"],
            })
            time.sleep(2)  # stay under free-tier rate limits
        (out_dir / f"{case['id']}.md").write_text("\n".join(md), encoding="utf-8")
        summary.append({"id": case["id"], "type": case["type"], "expect": case["expect"], "turns": turn_logs})

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved to {out_dir}")


if __name__ == "__main__":
    main()
