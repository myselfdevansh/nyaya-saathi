"""
Measures whether a problem reaches the right specialist agent.

    python scripts/eval_agents.py              # keyword router only (no API key needed)
    python scripts/eval_agents.py --llm        # the app's router (needs .env)

Writes raw_outputs/agent_eval_<mode>.txt. Set LLM_RETRIES to wait out free-tier limits.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import agents, llm  # noqa: E402
from app.pipeline import intake  # noqa: E402


def main():
    use_llm = "--llm" in sys.argv
    if use_llm and not llm.is_configured():
        sys.exit("--llm needs an LLM configured in .env")
    cases = json.loads((ROOT / "tests" / "agent_eval.json").read_text(encoding="utf-8"))
    right, lines = 0, []
    for c in cases:
        if use_llm:
            got = intake([{"role": "user", "content": c["q"]}])["agent"]
        else:
            got = agents.route_keywords(c["q"])
        ok = got == c["agent"]
        right += ok
        lines.append(f"{'ok  ' if ok else 'MISS'} ({c['lang']}) want={c['agent']} got={got}: {c['q']}")
    mode = llm.last_model_used() if use_llm else "keywords"
    report = "\n".join([f"Agent routing ({mode}), {time.strftime('%Y-%m-%d')}: {right}/{len(cases)} correct", *lines])
    sys.stdout.reconfigure(encoding="utf-8")  # Hindi on a Windows console
    print(report)
    out = ROOT / "raw_outputs"
    out.mkdir(exist_ok=True)
    (out / f"agent_eval_{'llm' if use_llm else 'keywords'}.txt").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
