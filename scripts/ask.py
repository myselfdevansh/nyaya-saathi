"""
Talk to the AI lawyer in the terminal.

    python scripts/ask.py                     # interactive chat (needs .env)
    python scripts/ask.py "my cheque bounced"  # one question
    python scripts/ask.py --retrieval-only "my cheque bounced"   # just show which law it found (no API key needed)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import llm  # noqa: E402
from app.guardrails import triage  # noqa: E402
from app.pipeline import answer, render  # noqa: E402
from app.retrieve import retrieve  # noqa: E402


def show_retrieval(q):
    for f in triage(q):
        print(f"⚠ [{f['type']}] {f['message']}")
    results, rw = retrieve(q)
    if rw.get("queries"):
        print("Search queries:", rw["queries"], "areas:", rw["areas"])
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['act']}, s.{r['section']}: {r['heading']}  (score {r['score']})")
        print(f"   {r['source_url']}")


def main():
    args = sys.argv[1:]
    if "--retrieval-only" in args:
        args.remove("--retrieval-only")
        show_retrieval(" ".join(args) or input("Question: "))
        return
    if not llm.is_configured():
        sys.exit("No LLM configured: copy .env.example to .env and add a key, or use --retrieval-only.")
    print(f"Model: {llm.model_name()}. Type 'quit' to exit.\n")
    history = []
    first = " ".join(args)
    while True:
        q = first or input("You: ").strip()
        first = ""
        if q.lower() in ("quit", "exit", ""):
            break
        history.append({"role": "user", "content": q})
        res = answer(history)
        print("\nNyaya Saathi:\n" + render(res) + "\n")
        history.append({"role": "assistant", "content": res["answer"]})
        if args:  # one-shot mode
            break


if __name__ == "__main__":
    main()
