"""Quick checks: negotiate vs email vs filter (run with OPENAI_API_KEY + optional SMTP)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import run_agent


def main():
    tests = [
        (
            "negotiate",
            "Should I try to negotiate rent on a $3,200/mo 1br in 94108?",
            lambda r: "negotiate" in r.type
            and "dear" not in r.reply.lower()
            and "subject:" not in r.reply.lower(),
        ),
        (
            "filter",
            "1 bedroom San Francisco under 4000 rent",
            lambda r: r.type == "filter" and len(r.listings) >= 0,
        ),
    ]
    for name, msg, ok in tests:
        r = run_agent(msg, "smoke-" + name, "en")
        passed = ok(r)
        print(f"{'OK' if passed else 'FAIL'} {name}: type={r.type} listings={len(r.listings)}")
        if name == "negotiate":
            print("  reply preview:", (r.reply[:280] + "…") if len(r.reply) > 280 else r.reply)
    print("\nEmail test: set SMTP_* then ask with email + send + properties + under X")


if __name__ == "__main__":
    main()
