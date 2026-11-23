#!/bin/bash
# c2-needle.sh: two streams at once in one shared cache pool, each retrieving five codes from its own long document.
# Checks that a stream reads only its own part of the pool and still finds everything.
# usage: c2-needle.sh PT CTX [label]
H="$(cd "$(dirname "$0")" && pwd)"; S=/d/llama-dev/up-bench
PT=${1:-100000}; CTX=${2:-262144}; L=${3:-c2-needle}
export LLAMA_INKLING_REL_TAG=1
bash $S/ink-serve.sh 8095 $CTX 2 --kv-unified -ctk q4_0 -ctv q4_0 -ub ${UB:-512} -b 2048 -bs >/dev/null && bash $S/ink-hi.sh
rm -f "$H/results/$L-a.jsonl" "$H/results/$L-b.jsonl"
echo "=== $L: 2 streams x $PT tokens, pool $CTX $(date +%T)"
python -I "$H/needle.py" http://127.0.0.1:8095 $PT "$H/results/$L-a.jsonl" 21 > "$H/results/$L-a.out" 2>&1 &
sleep 20
python -I "$H/needle.py" http://127.0.0.1:8095 $PT "$H/results/$L-b.jsonl" 22 > "$H/results/$L-b.out" 2>&1 &
wait
cut -c1-230 "$H/results/$L-a.out" "$H/results/$L-b.out"
powershell -NoProfile -Command "(Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage').CounterSamples | ? { \$_.CookedValue -gt 2e9 } | % { '{0} {1:N0} MB' -f \$_.InstanceName.Substring(0,24), (\$_.CookedValue/1MB) }"
grep -iE "DeviceLost|device lost|assert" $S/ink-srv-8095.log | tail -2
bash $S/ink-stop.sh 8095
echo "=== $L done $(date +%T)"
