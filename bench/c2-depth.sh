#!/bin/bash
# c2-depth.sh: two streams, each with a prompt of PT tokens, sharing one cache pool of CTX tokens (4-bit cache,
# tagged-mask attention, 256-token batches). Prints per-stream prompt reading and decode from fnbench.py.
# usage: c2-depth.sh PT CTX [label]
H="$(cd "$(dirname "$0")" && pwd)"; S=/d/llama-dev/up-bench
PT=${1:-100000}; CTX=${2:-262144}; L=${3:-c2}
export LLAMA_INKLING_REL_TAG=1
bash $S/ink-serve.sh 8095 $CTX 2 --kv-unified -ctk q4_0 -ctv q4_0 -ub ${UB:-256} -b 2048 -bs && bash $S/ink-hi.sh
python -I "$H/fnbench.py" http://127.0.0.1:8095 1 300 40 >/dev/null
echo "=== $L: 2 streams x $PT tokens, pool $CTX $(date +%T)"
python -I "$H/fnbench.py" http://127.0.0.1:8095 2 $PT 200 $4 | tail -8
powershell -NoProfile -Command "(Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage','\GPU Adapter Memory(*)\Shared Usage').CounterSamples | ? { \$_.CookedValue -gt 2e9 } | % { '{0:N0} MB' -f (\$_.CookedValue/1MB) }"
grep -iE "DeviceLost|device lost" $S/ink-srv-8095.log | tail -1
bash $S/ink-stop.sh 8095
echo "=== $L done $(date +%T)"
