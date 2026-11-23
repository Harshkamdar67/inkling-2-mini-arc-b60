"""N concurrent streams with a prompt of a given size each: per-stream prompt reading, decode, and a check of the text.

usage: fnbench.py BASE_URL STREAMS PROMPT_TOKENS [MAX_TOKENS] [prio]
prio: stream 0 is sent with "priority": 1 (llama-server lanes) and "priority": "high" is not used.
A stream counts as degenerate when its text has a run of '!' or is nearly empty.
"""
import json, random, sys, threading, time, urllib.request

BASE, N, PT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
MAXTOK = int(sys.argv[4]) if len(sys.argv) > 4 else 250
PRIO = "prio" in sys.argv[5:]
PRIO_LEVEL = next((int(a[5:]) for a in sys.argv[5:] if a.startswith("prio=")), 1)
PRIO = PRIO or any(a.startswith("prio=") for a in sys.argv[5:])
TWICE = "twice" in sys.argv[5:]   # run the same prompts again so both streams decode together from a cached context
RUN_ID = time.time_ns()
WORDS = ("the server reads a prompt and then writes tokens one at a time while the cache keeps earlier work so that a "
         "second request with the same start is quick but a new start must be read in full by the model on the card").split()
TASKS = ["Write a detailed explanation of how a bicycle stays upright.",
         "Write a complete Python module implementing an LRU cache with TTL support, with type hints and docstrings.",
         "Explain step by step how a TCP connection is opened and closed.",
         "Write a Rust function that parses a CSV line with quoted fields, with tests."]


def one(i, out):
    rnd = random.Random(f"{i}-{PT}-{RUN_ID}")
    filler = " ".join(rnd.choice(WORDS) for _ in range(int(PT * 0.95)))
    msg = f"[s{i}-{RUN_ID}] Notes follow.\n{filler}\n\nIgnore the notes. {TASKS[i % len(TASKS)]}"
    body = {"model": "x", "stream": True, "max_tokens": MAXTOK * (3 if PRIO and i != 0 else 1), "temperature": 0, "stream_options": {"include_usage": True},
            "reasoning_effort": "none", "chat_template_kwargs": {"enable_thinking": False}, "messages": [{"role": "user", "content": msg}]}
    if PRIO and i == 0:
        body["priority"] = PRIO_LEVEL
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter(); first = last = None; usage = {}; text = []; err = None; stamps = []
    try:
        with urllib.request.urlopen(req, timeout=7200) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                    continue
                j = json.loads(line[5:])
                if j.get("error"):
                    err = str(j["error"])[:160]
                for ch in j.get("choices") or []:
                    dl = ch.get("delta") or {}
                    piece = (dl.get("content") or "") + (dl.get("reasoning_content") or "")
                    if piece:
                        now = time.perf_counter(); first = first or now; last = now; text.append(piece); stamps.append(now)
                usage = j.get("usage") or usage
    except Exception as e:  # noqa: BLE001
        err = repr(e)[:160]
    s = "".join(text)
    pt, ct = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    out[i] = {"pt": pt, "read": pt / (first - t0) if first else 0.0, "ttft": (first - t0) if first else None,
              "decode": (ct - 1) / (last - first) if first and last and last > first else 0.0, "ct": ct,
              "bad": ("!!!!!!!!" in s) or len(s.strip()) < 20, "err": err, "high": PRIO and i == 0,
              "stamps": stamps, "first": first, "last": last}


def round_():
    out = [None] * N
    ths = [threading.Thread(target=one, args=(i, out)) for i in range(N)]
    t0 = time.perf_counter()
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    return out, time.perf_counter() - t0


for r in range(2 if TWICE else 1):
    out, wall = round_()
    if TWICE:
        print(" first pass (reads the prompts):" if r == 0 else " second pass (contexts cached, streams decode together):", flush=True)
    for i, o in enumerate(out):
        print(f"  stream {i}{' (high)' if o['high'] else ''}: prompt {o['pt']} tok, read {o['read']:.0f} tok/s (first token {o['ttft'] or 0:.1f} s), "
              f"decode {o['decode']:.1f} tok/s over {o['ct']} tok{'  DEGENERATE' if o['bad'] else ''}{'  ERR ' + o['err'] if o['err'] else ''}", flush=True)
    hi = [o for o in out if o["high"] and o["first"]]
    if hi:
        h = hi[0]
        for i, o in enumerate(out):
            if not o["high"] and o["stamps"]:
                inside = [t for t in o["stamps"] if h["first"] <= t <= h["last"]]
                tok_per_piece = o["ct"] / max(len(o["stamps"]), 1)
                print(f"  while the high stream decoded ({h['last'] - h['first']:.1f} s): stream {i} produced about "
                      f"{len(inside) * tok_per_piece / max(h['last'] - h['first'], 1e-9):.1f} tok/s", flush=True)
    print(f"streams {N}, prompt ~{PT}: decode sum {sum(o['decode'] for o in out):.1f} tok/s, degenerate {sum(o['bad'] for o in out)}/{N}, wall {wall:.0f} s", flush=True)
