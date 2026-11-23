@echo off
rem Inkling 2 Mini on one Arc Pro B60: everything on the card, two streams sharing a 64K f16 cache, backend sampling.
rem Requests may send "priority": N; while a higher one runs, lower ones pause and resume afterwards.
rem A 131K f16 cache with two streams does not fit 24 GB (Windows pages it to RAM and prompts get 15x slower):
rem for longer contexts use -ctk q8_0 -ctv q8_0.
rem GGML_VK_DEVICE_NAME keeps only the B60 visible, so it is Vulkan0 whatever order the driver lists the GPUs in.
set LLAMA=C:\path\to\llama.cpp\build\bin
set MODEL=C:\path\to\Inkling-2-Mini-IQ4_NL.gguf
set GGML_VK_DEVICE_NAME=B60

rem High priority and the performance cores (mask FFFF = 16 threads of a 12700K): one thread feeds the GPU about
rem 2,700 launches per token, and when other work pushes it off a P-core decode drops from 43 to about 25 tok/s.
start "inkling" /b /wait /high /affinity FFFF "%LLAMA%\llama-server.exe" -m "%MODEL%" -dev Vulkan0 -ngl 99 -fa on -bs ^
  -c 65536 -np 2 --kv-unified ^
  --host 127.0.0.1 --port 8080
