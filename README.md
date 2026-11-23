# Inkling 2 Mini on one Intel Arc Pro B60 (24 GB), Windows

Setup and llama.cpp patches for [Inkling 2 Mini](https://huggingface.co/thinkingmachines/Inkling-2-Mini) (Thinking
Machines, released 2026-11-20) on a single Arc Pro B60 with the Vulkan backend. One stream decodes at 42-43 tok/s
(stock llama.cpp: 19) and reads prompts at about 1,275 tok/s (stock: about 410). Two streams share one cache pool and
have been run with 237.5K tokens of context each. Everything here was measured on one machine.

Machine: i7-12700K, 128 GB DDR4-2667, Arc Pro B60 24 GB, Windows 11. Model: the official
`ggml-org/Inkling-2-Mini-GGUF` IQ4_NL file (16.4 GiB). Measured 2026-11-21 to 2026-11-23.

## Results

Empty context:

| case | patched | stock master `418fe97b5` |
|---|---|---|
| decode, one stream | 42-43 tok/s | 19.0 |
| prompt reading | about 1,275 tok/s (`-ub 512`), 1,372 (`-ub 1024`) | about 410 |

Deep context, 4-bit cache (`-ctk q4_0 -ctv q4_0 -ub 512`). Stock llama.cpp was not measured at depth.

| one stream | prompt reading | decode |
|---|---|---|
| with 128K tokens already in the cache | 616-633 tok/s | 27.7 tok/s |
| a whole 120K-token document, read from empty | 741 tok/s average | 29.4 tok/s after it |
| at 237K | | 22.2 tok/s |

| two streams, one shared pool | 95K tokens each | 237.5K tokens each |
|---|---|---|
| both prompts read | 231 s | 765 s |
| first prompt reading speed | 798 tok/s | 607 tok/s |
| decode, one stream writing alone | 30.7 tok/s | 22.2 tok/s |
| decode, both writing | 19.3 tok/s each | 12.5 tok/s each |
| decode while the other stream reads its prompt | 15.3 tok/s | 12.8 tok/s |
| memory on the card | 19.6 GB | 22.6 GB |

The most context that fit is 475K live tokens (2 x 237.5K) in a 524,288-token pool. The model's own limit is 1,048,576;
a pool that size does not fit next to the 16.4 GiB model on a 24 GB card.

Quality checks:

| check | result |
|---|---|
| output against stock llama.cpp (KL divergence, 20 x 512 tokens) | KLD 0.0018, same top token 98.4%; two stock runs against each other give 98.3% |
| perplexity at a 32K context, before and after the long-context changes | 6.1345 both |
| five facts hidden in a 120K-token document | 5/5 |
| two streams at once, five facts each in their own 100K-token document | 5/5 and 5/5 |
| 16 reasoning questions, reasoning effort none / medium | 15/16 and 16/16 |
| 6 tool calls | 4/6 |
| refusals on a 16-prompt probe | 0/16 |
| CyberMetric-500, CWE naming, small CTF puzzles | 300/500, 7/14, 6/8 |

For scale: the only other deep-context numbers published for this model are from maya-ik2 on an RTX 3090 (CUDA), which
is about three times faster at every depth (128.7 tok/s empty, 90.6 at 128K) and holds 344K tokens with an 8-bit cache.

Short contexts, measured 2026-11-22 and not run again on the final build:

| case | result |
|---|---|
| two streams, 64K shared f16 cache, 2K prompts | 31.8 tok/s each |
| one of two streams sent with `"priority": 1` | 40.2 tok/s; the other pauses, then runs at 39 |
| DSpark drafting, one stream | 57 reasoning / 49 code / 33 prose tok/s |

## Streams and context

There is one cache pool and `-c` is its total size. With `-np 2 --kv-unified` the two streams share it, and either one
can take more than half: the pool is not split in two.

| pool (`-c`) | what it holds | memory on the card |
|---|---|---|
| 262,144 | 2 x 95K measured | 19.6 GB |
| 458,752 | the launcher's default | about 21.5 GB (estimated from the two rows around it) |
| 524,288 | 2 x 237.5K measured (475K live) | 22.6 GB |
| 1,048,576 | the model's limit | does not fit: 16.4 GiB of model + 9.2 GiB of cache |

The pool is allocated up front, so its size sets the memory, not how much of it is in use. A cached token costs 9.2 KB
at 4 bits. That is small for a model with 48 layer visits because only 8 of them keep a full-length cache (see below);
the other 40 look back 1,024 tokens.

Each stream writes into its own region of the pool. A stream's attention reads only its own region, so the second
stream does not pay for the first one's tokens.

What a stream gets depends on what the other one is doing (95K tokens each):

| the other stream is | this stream decodes at |
|---|---|
| idle | 30.7 tok/s |
| also writing | 19.3 tok/s |
| reading a long prompt | 15.3 tok/s (the reader gets 256-token turns between this stream's tokens) |

## What the loop does to the cost

The model has 24 layers. Layers 6 to 17 run three times per token, each pass steered by small controllers that read
what the previous pass produced. So a token makes 48 layer visits with the weights of 24.

What that means when you run it:

- **Every per-visit cost is paid 48 times.** A visit has a loop gate, a mix over earlier block outputs, a
  relative-position bias, a short convolution and the SITU activation around its matmuls. Stock llama.cpp turned that
  into about 6,300 GPU dispatches per token, and on this card a dispatch costs 2-3 us whatever it does. One op that
  fell back to the CPU 194 times per token was the first fix (19 -> 30 tok/s); fusing the small ops (6,300 -> 2,700
  dispatches) took it to 43.
- **Decode is limited by how fast the card reads memory.** A token reads about 4.1 GB of weights: 1.3 GiB of attention
  projections, 1.8 GiB of experts (8 of 128 per visit), 0.5 GiB for the output head, 0.2 GiB of loop controllers. At
  43 tok/s that is 176 GB/s on a card whose bus does 456. The fastest kernel here runs at 252 GB/s; if everything ran
  at that rate the ceiling would be about 62 tok/s empty and 48 at 128K. That is an estimate from byte counts, not a
  measurement.
- **Long context is cheaper than the layer count suggests.** Only layers 5, 11, 17 and 23 attend to the whole context.
  11 and 17 are inside the loop, so they run three times: 8 full-context reads per token, 6 of them from the loop. The
  cost grows by about 0.1 ms per token for every 1,000 tokens of context.
- **The passes cannot share a cache.** Each pass of layers 11 and 17 writes different keys and values, because the
  controllers change the inputs. Sharing them or cutting the later passes to a recent window would halve the depth cost
  and the cache, and it breaks the model (see below).
- **The pass count is fixed for this model.** Perplexity is 7.69 at 3 passes, 13.6 at 2 and 11.8 at 4.

Where the loop can be used: the separate `TML-d24-varloop-research` model was trained with 1 to 5 passes, and the pass
count is a setting at load time (`--override-kv inkling2_loop.loop.count=int:N`). One pass decodes at 77 tok/s against
42 at three. A fast lane for easy requests and a slow one for hard ones would be possible with it, but its tool calls
fail at any pass count and it refuses more, so it is not a replacement today. The table is further down.

## What the patches change

Inkling 2 Mini is a looped mixture-of-experts model: 24 physical layers, the middle 12 run three times, so a token makes
48 layer visits. On this card each GPU dispatch costs about 2-3 us and stock llama.cpp ran about 6,300 of them per
token, plus some ops on the CPU.

1. **SITU's scale ran on the CPU.** Vulkan `SCALE` only accepted contiguous input, so the scale of the gate/up view
   moved to the CPU twice per visit: 194 graph splits per token. Strided indexing in the scale shader: decode 19.0 ->
   30.3, prompt reading 408 -> 714. This affects every Vulkan GPU.
2. **IQ4_NL had no integer-dot mat-vec path** (IQ4_XS and MXFP4 do). Added, and used at one token on Xe2.
3. **Fused ops** for the per-visit work (`GGML_OP_INKLING_LOOP_GATE`, `_REL_MASK`, `_MIX`, `_SITU`, `_CONV`, `_PROJ`),
   each with a CPU reference and `test-backend-ops` cases that pass on the B60. `LLAMA_INKLING_NO_FUSE=1` (or `_NO_MIX`,
   `_NO_CONV`, `_NO_GATE`, `_NO_MASK`, `_NO_SITU`, `_NO_PROJ`) turns them off for comparison. Dispatches per token:
   about 6,300 -> 2,700.
4. **Attention over a long 4-bit cache.** Only 8 of the 48 visits read the whole context (layers 5, 11, 17, 23; 11 and
   17 run three times and each run keeps its own cache), 9.2 KB per token at 4 bits.
   - decode: a kernel that scores the 4-bit keys with integer dot products against an 8-bit query, then sums the
     values of the keys that matter. 131K keys: 1.16 ms per layer, was 12.3 ms before the first fix.
   - prompt reading: the Xe prefill kernel reads the 4-bit cache directly, with no conversion pass or f16 scratch.
   - the per-head relative-position mask is replaced by one mask that tags the keys near the query, with the bias read
     from a small table inside the kernel. The tagged mask is filled on the CPU, which knows the few cells near the
     batch: 118 ms -> 15 ms of CPU work per 512 tokens at 128K, and no distance array of every cell to every token.
5. **Two streams in one cache.** Each stream keeps to its own region of the shared pool and attention is given only
   that region, so a stream no longer scans the other one's keys. Two 95K prompts: 440 s -> 231 s.
6. **Server:** a stream that is generating goes first; other streams read their prompts in 256-token chunks between
   its steps (`LLAMA_ARG_GEN_SHARE`). Requests may send `"priority": N`.
7. Smaller: `GGML_VK_DEVICE_NAME=B60` picks the card by name (the Vulkan index changes between processes on a machine
   with several GPUs); `LLAMA_LAYER_DEVICES` maps layers to devices; backend sampling with an unaligned vocabulary;
   DSpark (PR #32218) fixes.

## What was tried and did not help

- **Limiting the later loop passes of layers 11 and 17 to a recent window** (it would halve the depth cost and the
  cache). Perplexity at 32K: 6.13 unmodified, 6.46 with a 1,024-token window, 6.16 with 8,192. Retrieval from a 120K
  document: 5/5 -> 0/5 at both. Every pass needs the whole context.
- **Skipping keys with small attention weight:** about 10% faster at an aggressive threshold on real text at 120K, with
  no bound on the error. Attention is spread out, not peaked.
- **A low-rank shortcut for the keys:** the projections are full rank (99% of the energy needs about 125 of 128 dims).
- **Cooperative matrices for the value sum at decode:** the integer matrix path is 2.4-3.3 TFLOPS at this shape, slower
  than the plain loop.
- **Per-slot branches in the value loop, and an 8-slot kernel for two tokens:** both slower than one token per
  workgroup.
- **DSpark with two streams:** 49 tok/s total against 63 without it. Use it for one stream only.
- **Changing the pass count of the released model:** perplexity 7.69 at 3 passes, 13.6 at 2, 11.8 at 4.
- **A 131K f16 cache with two streams:** overcommits the card; Windows pages to system RAM and a 2K prompt takes 75 s.

## The variable-loop research model

Thinking Machines also released `TML-d24-varloop-research`, trained with 1 to 5 passes. Same card, same tests:

| | reasoning (none / medium) | tools | refused | CyberMetric | CWE | CTF | decode |
|---|---|---|---|---|---|---|---|
| Inkling 2 Mini | 15/16, 16/16 | 4/6 | 0/16 | 300/500 | 7/14 | 6/8 | 42.0 tok/s |
| varloop, 1 pass | 11/16, 14/16 | 1/6 | 5/16 | 308/500 | 3/14 | 3/8 | 77.1 tok/s |
| varloop, 3 passes | 15/16, 16/16 | 1/6 | 4/16 | 345/500 | 10/14 | 5/8 | 41.9 tok/s |

One pass is almost twice as fast and clearly weaker. Tool calls fail at any pass count.

## Not done

- 40-50 tok/s per stream at depth was the goal. It was not reached: 28-30 tok/s at 128K for one stream.
- Stock llama.cpp was not measured at depth, so the deep numbers have no baseline on this card.
- Nothing here has been proposed upstream yet.
- Benchmarks ran with the server at high priority on the performance cores. Other programs were running on the
  machine during some runs.

## What is in here

- `patches/`: 32 commits on llama.cpp master `418fe97b5` with PR #32218 merged. The same commits are on the
  [`inkling-b60` branch](https://github.com/Harshkamdar67/llama.cpp/tree/inkling-b60) of my fork.
- `config/run-inkling-b60-long.bat`: two streams, one 4-bit pool, long contexts. `config/run-inkling-b60.bat`: two
  streams in a 64K f16 cache with priority lanes.
- `bench/fnbench.py`: N streams, optional priority. `bench/needle.py`: facts hidden at five depths in long real text.
  `bench/cyber.py`: CyberMetric-500, CWE naming, CTF puzzles. `bench/specbench.py`: speed and text diff between two
  setups. `bench/c2-depth.sh`, `bench/c2-needle.sh` and the `ink-*.sh` helpers are the scripts the tables above came
  from; they have this machine's paths in them.
- `results/raw/`: the outputs behind the tables.

## Setup

1. Clone llama.cpp, check out `418fe97b5`, merge PR #32218 at the commit tested here
   (`git fetch origin pull/32218/head && git merge 8ea436311`), then `git am patches/*.patch`. Or check out the fork
   branch above.
2. Build with `-DGGML_VULKAN=ON` (Vulkan SDK 1.4, MSVC 2022).
3. Download `Inkling-2-Mini-IQ4_NL.gguf` from `ggml-org/Inkling-2-Mini-GGUF`.
4. Edit the paths in a `config/*.bat` and run it.
