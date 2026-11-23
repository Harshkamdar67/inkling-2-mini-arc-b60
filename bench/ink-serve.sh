#!/bin/bash
# ink-serve.sh PORT CTX NP [extra llama-server args...]: start the patched server on the B60, wait for health
export GGML_VK_DEVICE_NAME=B60; DEV=$(bash /d/llama-dev/up-bench/b60dev.sh); [ -n "$DEV" ] || { echo "no B60 found"; exit 1; }
B=/d/llama-dev/build-inkling/bin; M=/d/models/inkling-2-mini/Inkling-2-Mini-IQ4_NL.gguf
P=$1; C=$2; N=$3; shift 3
cd $B && (./llama-server.exe -m $M -dev $DEV -ngl 99 -fa on -c $C -np $N --port $P --host 127.0.0.1 --no-webui "$@" > /d/llama-dev/up-bench/ink-srv-$P.log 2>&1 &)
for i in $(seq 1 400); do sleep 2; curl -s -m 2 http://127.0.0.1:$P/health | grep -q ok && { echo "up on $P"; exit 0; }; done
echo "not up"; tail -20 /d/llama-dev/up-bench/ink-srv-$P.log; exit 1
