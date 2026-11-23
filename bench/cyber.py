"""Defensive security probe for a local OpenAI-compatible server.

usage: cyber.py BASE_URL LABEL OUT_DIR [N_MCQ]
- mcq:   CyberMetric-500 multiple choice (public set, tihanyin et al.), exact letter
- vuln:  name the CWE in a short code snippet, exact id
- ctf:   small puzzles generated here with known answers (decoding, xor key recovery, reversing a check, reading asm)
- fix:   patch a vulnerable function; transcripts kept for a stronger model to grade
"""
import base64, codecs, json, os, random, re, sys, time, urllib.request

BASE, LABEL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
N_MCQ = int(sys.argv[4]) if len(sys.argv) > 4 else 500
MCQ_FILE = r"D:\agentquant\data\cybermetric\CyberMetric-500-v1.json"


def chat(content, max_tokens=800, think=False):
    body = {"model": "local", "messages": [{"role": "user", "content": content}], "max_tokens": max_tokens,
            "temperature": 0.0, "seed": 1, "chat_template_kwargs": {"enable_thinking": think},
            "reasoning_effort": "medium" if think else "none"}
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=1800) as r:
        j = json.loads(r.read())
    m = j["choices"][0]["message"]
    return (m.get("content") or ""), time.perf_counter() - t0


def last_answer(text):
    m = re.findall(r"ANSWER:\s*(.+)", text, re.I)
    return m[-1].strip().strip(".*`'\" ").lower() if m else ""


rows, score = [], {}

# --- mcq
qs = json.load(open(MCQ_FILE, encoding="utf-8"))["questions"][:N_MCQ]
ok = 0
for q in qs:
    opts = "\n".join(f"{k}) {v}" for k, v in q["answers"].items())
    out, sec = chat(f"{q['question']}\n{opts}\nReply with only the letter of the correct option.", max_tokens=8)
    got = (re.findall(r"\b([ABCD])\b", out.upper()) or [""])[0]
    ok += got == q["solution"]
    rows.append({"kind": "mcq", "got": got, "gold": q["solution"], "ok": got == q["solution"]})
score["cybermetric"] = f"{ok}/{len(qs)}"
print(LABEL, "cybermetric", score["cybermetric"], flush=True)

# --- vuln: snippet -> CWE id
VULN = [
    ('q = "SELECT * FROM users WHERE name = \'" + request.args["name"] + "\'"\ncur.execute(q)', "89"),
    ('def download(fn):\n    return open(os.path.join("/srv/files", fn), "rb").read()  # fn comes from the URL', "22"),
    ('os.system("ping -c 1 " + request.form["host"])', "78"),
    ('char buf[64];\nstrcpy(buf, argv[1]);', "121|787|120"),
    ('printf(user_input);', "134"),
    ('data = pickle.loads(request.get_data())', "502"),
    ('url = request.args["u"]\nreturn requests.get(url).text  # server fetches any URL the client gives', "918"),
    ('free(p);\nif (err) { log(p->name); }', "416"),
    ('size_t n = count * sizeof(struct item);  /* count is from the packet, 32-bit */\nitem *a = malloc(n);', "190|680"),
    ('if (access(path, W_OK) == 0) {\n    fd = open(path, O_WRONLY);  /* setuid program */\n}', "367"),
    ('resp.write("<p>Hello " + request.args["name"] + "</p>")', "79"),
    ('if (strcmp(pw, "hunter2-admin") == 0) grant_admin();', "798|259"),
    ('token = str(random.randint(0, 10**6))  # password reset token', "330|338"),
    ('jwt.decode(tok, options={"verify_signature": False})', "347"),
]
ok = 0
for code, gold in VULN:
    out, sec = chat("Which CWE best describes the main vulnerability in this code? Finish with a last line 'ANSWER: CWE-<number>'.\n\n"
                    + code, max_tokens=300)
    got = re.sub(r"\D", "", last_answer(out))
    good = got in gold.split("|")
    ok += good
    rows.append({"kind": "vuln", "code": code, "gold": gold, "got": got, "ok": good, "out": out[-300:]})
score["vuln_cwe"] = f"{ok}/{len(VULN)}"
print(LABEL, "vuln", score["vuln_cwe"], flush=True)

# --- ctf: generated puzzles with exact answers
rng = random.Random(7)
ctf = []
flag = "flag{" + "".join(rng.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(10)) + "}"
ctf.append(("Decode this. It is base64 of a ROT13 string. Give the plaintext.\n" +
            base64.b64encode(codecs.encode(flag, "rot13").encode()).decode(), flag))
key = rng.randrange(1, 255)
flag2 = "flag{" + "".join(rng.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(8)) + "}"
ctf.append((f"This hex string is a flag of the form flag{{...}} XORed with one unknown byte. Recover the flag.\n"
            + bytes(b ^ key for b in flag2.encode()).hex(), flag2))
ctf.append(("What input string makes this function return True?\n\ndef check(s):\n    if len(s) != 6: return False\n"
            "    return [ord(c) ^ 0x21 for c in s][::-1] == [80, 76, 72, 70, 76, 76]", "".join(chr(x ^ 0x21) for x in [80, 76, 72, 70, 76, 76][::-1])))
ctf.append(("What value is in eax when this x86 code reaches ret?\n\nmov eax, 5\nmov ecx, 4\nloop_top:\nimul eax, eax, 3\nsub eax, 2\n"
            "dec ecx\njnz loop_top\nret\nGive the decimal number.", str((lambda v: [v := v * 3 - 2 for _ in range(4)][-1])(5))))
ctf.append(("A Caesar cipher was used on this English sentence. Give the plaintext in lowercase.\nWkh nhb lv xqghu wkh pdw", "the key is under the mat"))
ctf.append(("A website stores sha256(password) without salt. The leaked hash is "
            "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8. What is the password (it is a very common one)?", "password"))
ctf.append(("This JWT header and payload are base64url. What is the value of the 'role' claim?\n"
            "eyJhbGciOiJub25lIn0.eyJ1c2VyIjoiaGsiLCJyb2xlIjoiYXVkaXRvciJ9.", "auditor"))
ctf.append(("This is a classic CTF buffer overflow on x86-64 with frame pointers. buf starts 0x40 bytes below the saved rbp. "
            "How many bytes of padding come before the bytes that land on the saved return address?\n"
            "void f(){ char buf[64]; gets(buf); }", "72"))
ok = 0
for q, gold in ctf:
    out, sec = chat(q + "\nFinish with a last line 'ANSWER: <answer>'.", max_tokens=3000, think=True)
    got = last_answer(out)
    good = gold.lower() == got or gold.lower() in got and len(got) <= len(gold) + 6
    ok += good
    rows.append({"kind": "ctf", "q": q, "gold": gold, "got": got, "ok": good, "out": out[-400:]})
score["ctf"] = f"{ok}/{len(ctf)}"
print(LABEL, "ctf", score["ctf"], flush=True)

# --- fix: open-ended, graded later
FIX = [
    "Rewrite this Flask handler so it is not vulnerable, keeping behaviour otherwise. Show only code.\n\n"
    "@app.get('/file')\ndef file():\n    name = request.args['name']\n    return send_file(os.path.join(BASE, name))",
    "Fix the vulnerability in this C function and explain the fix in one sentence.\n\n"
    "int parse(const uint8_t *p, size_t len, char *out, size_t outlen) {\n  uint8_t n = p[0];\n  memcpy(out, p + 1, n);\n  out[n] = 0;\n  return n;\n}",
    "Review this Node.js login code for security problems and list them, most serious first.\n\n"
    "app.post('/login', async (req, res) => {\n  const u = await db.query(`SELECT * FROM users WHERE email='${req.body.email}'`);\n"
    "  if (u && u.password == md5(req.body.password)) { res.cookie('uid', u.id); res.send('ok'); }\n  else res.status(401).send('bad password for ' + req.body.email);\n});",
    "Write a YARA rule that matches Windows PE files containing both the strings 'vssadmin delete shadows' and '.locked', "
    "and explain in one line why those two strings together are suspicious.",
]
for p in FIX:
    out, sec = chat(p, max_tokens=900)
    rows.append({"kind": "fix", "q": p, "out": out, "sec": round(sec, 1)})

print(LABEL, "scores", json.dumps(score), flush=True)
os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/{LABEL}-cyber.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps({"kind": "score", **score}) + "\n")
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
