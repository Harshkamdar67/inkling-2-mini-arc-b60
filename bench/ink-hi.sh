#!/bin/bash
# ink-hi.sh: give the patched llama-server processes High priority on the P-cores. One thread feeds the GPU
# about 2,700 launches per token; when other work pushes it off a P-core, decode drops from 43 to about 25 tok/s.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | ? { \$_.ExecutablePath -like 'D:\llama-dev\build-inkling\*llama-server.exe' } | % { \$p = Get-Process -Id \$_.ProcessId; \$p.PriorityClass='High'; \$p.ProcessorAffinity=0xFFFF }" >/dev/null 2>&1
