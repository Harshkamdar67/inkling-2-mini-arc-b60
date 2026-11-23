"""Greedy decode speed and draft acceptance on fixed prompts, saving the text so two server setups can be diffed.

usage: specbench.py BASE_URL LABEL OUT_DIR [MAX_TOKENS] [EXTRA_JSON]
Writes OUT_DIR/LABEL-spec.jsonl. Compare two labels with: specbench.py --diff OUT_DIR LABEL_A LABEL_B
"""
import json, sys, time, urllib.request

PROMPTS = [
    ("prose", "Explain how a bicycle stays upright, for a curious teenager. About 300 words."),
    ("code", "Write a Python function that parses a CSV line with quoted fields and escaped quotes, with doctests."),
    ("code2", "Write a TypeScript debounce function with proper generic types and a cancel method, then show one usage example."),
    ("reason", "A train leaves at 14:35 and the trip takes 3 hours 50 minutes, with a 25 minute delay on the way. Work out the arrival time step by step."),
    ("email", "Draft a short, polite email to a landlord asking to fix a leaking kitchen tap this week. Sign as Harsh."),
    ("hinglish", "bhai mujhe kal subah 7 baje ki flight pakadni hai, packing checklist bana de short mein"),
]

if sys.argv[1] == "--diff":
    out, a, b = sys.argv[2], sys.argv[3], sys.argv[4]
    ra = [json.loads(l) for l in open(f"{out}/{a}-spec.jsonl", encoding="utf-8")]
    rb = [json.loads(l) for l in open(f"{out}/{b}-spec.jsonl", encoding="utf-8")]
    for x, y in zip(ra, rb):
        same = x["text"] == y["text"]
        n = next((i for i, (p, q) in enumerate(zip(x["text"], y["text"])) if p != q), min(len(x["text"]), len(y["text"])))
        print(f"{x['name']:9s} identical={same} first_diff_char={'-' if same else n} "
              f"tps {x['decode_tps']:.1f} -> {y['decode_tps']:.1f}  accept {y.get('accept')}")
    sys.exit(0)

BASE, LABEL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
MAXTOK = int(sys.argv[4]) if len(sys.argv) > 4 else 400
EXTRA = json.loads(sys.argv[5]) if len(sys.argv) > 5 else {}

rows = []
for name, p in PROMPTS:
    body = {"model": "x", "messages": [{"role": "user", "content": p}], "max_tokens": MAXTOK, "temperature": 0.0, "seed": 1,
            "reasoning_effort": "none", "chat_template_kwargs": {"enable_thinking": False}, **EXTRA}
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=1800) as r:
        j = json.loads(r.read())
    m = j["choices"][0]["message"]
    tm = j.get("timings") or {}
    acc = None
    if tm.get("draft_n"):
        acc = round(tm.get("draft_n_accepted", 0) / tm["draft_n"], 3)
    row = {"name": name, "text": (m.get("reasoning_content") or "") + "\n----\n" + (m.get("content") or ""),
           "decode_tps": tm.get("predicted_per_second") or 0.0, "n": tm.get("predicted_n"), "accept": acc,
           "draft_n": tm.get("draft_n"), "wall": round(time.perf_counter() - t0, 1)}
    rows.append(row)
    print(f"{LABEL} {name:9s} {row['decode_tps']:.1f} tok/s over {row['n']} tok, accept {acc}", flush=True)

with open(f"{OUT}/{LABEL}-spec.jsonl", "w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
