"""Long-context retrieval check for a local llama-server: hide facts at set depths in real text, ask for all of them.

usage: needle.py BASE_URL N_TOKENS OUT_JSONL [SEED]
Haystack is wikitext-2 train text (unique, not repeated). Five locker codes go in at 5/25/50/75/95% depth.
Scores each code exactly and records prompt-read and decode speed from the server's own timings.
"""
import json, random, sys, time, urllib.request

BASE, N, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
SEED = int(sys.argv[4]) if len(sys.argv) > 4 else 1
WIKI = r"D:\agentquant\data\wikitext-2-raw\wiki.train.raw"
DEPTHS = [0.05, 0.25, 0.50, 0.75, 0.95]
NAMES = ["Heron", "Saffron", "Basalt", "Juniper", "Cobalt"]


def post(path, body, timeout=14400):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


text = open(WIKI, encoding="utf-8").read()
# the wiki file is about 2.4M tokens with this tokenizer family; cut by characters first, then trim by real token count
chars = int(N * 4.6)
if chars > len(text):
    sys.exit(f"wikitext too short for {N} tokens")
hay = text[:chars]
ntok = len(post("/tokenize", {"content": hay})["tokens"])
hay = hay[: int(len(hay) * (N - 400) / ntok)]

rng = random.Random(SEED)
codes = {n: f"{rng.randrange(100000, 999999)}" for n in NAMES}
paras = hay.split("\n")
for depth, name in sorted(zip(DEPTHS, NAMES), reverse=True):
    i = int(len(paras) * depth)
    paras.insert(i, f" The locker code for the {name} locker is {codes[name]} . ")
hay = "\n".join(paras)

q = ("The document above contains several sentences giving locker codes. List the code for each of these lockers: "
     + ", ".join(NAMES) + ". Answer with one line per locker in the form 'Name: code' and nothing else.")
msgs = [{"role": "user", "content": hay + "\n\n" + q}]
t0 = time.perf_counter()
j = post("/v1/chat/completions", {"model": "local", "messages": msgs, "max_tokens": 200, "temperature": 0.0, "seed": 1,
                                  "chat_template_kwargs": {"enable_thinking": False}})
sec = time.perf_counter() - t0
out = j["choices"][0]["message"].get("content") or ""
hits = {n: (codes[n] in out) for n in NAMES}
tm = j.get("timings") or {}
row = {"n_target": N, "prompt_tokens": (j.get("usage") or {}).get("prompt_tokens"), "seed": SEED,
       "found": sum(hits.values()), "of": len(NAMES), "hits": {f"{n}@{int(d*100)}%": hits[n] for d, n in zip(DEPTHS, NAMES)},
       "prompt_tps": tm.get("prompt_per_second"), "decode_tps": tm.get("predicted_per_second"),
       "wall_sec": round(sec, 1), "answer": out[:400]}
print(json.dumps(row), flush=True)
with open(OUT, "a", encoding="utf-8") as f:
    f.write(json.dumps(row) + "\n")
