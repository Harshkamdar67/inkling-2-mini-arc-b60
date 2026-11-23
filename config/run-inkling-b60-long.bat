@echo off
rem Inkling 2 Mini on one Arc Pro B60: two streams sharing one 4-bit cache pool, long contexts.
rem POOL is the total context the two streams share (either stream may take more than half).
rem   458752: about 21.5 GB on the card
rem   524288: tested with 2 x 237.5K tokens live, 22.6 GB, the practical ceiling of a 24 GB card
rem Two streams at 95K tokens each: both prompts read in 231 s, decode 30.7 tok/s alone,
rem 19.3 tok/s each when both write, 15.3 tok/s while the other stream reads its prompt.
rem Reasoning effort goes in the request: "chat_template_kwargs": {"reasoning_effort": "none" | "low" | "medium" | "high"}
set LLAMA=C:\path\to\llama.cpp\build\bin
set MODEL=C:\path\to\Inkling-2-Mini-IQ4_NL.gguf
set POOL=458752
if not "%1"=="" set POOL=%1

rem GGML_VK_DEVICE_NAME keeps only the B60 visible, so it is Vulkan0 whatever order the driver lists the GPUs in.
set GGML_VK_DEVICE_NAME=B60
rem the compact attention mask for long caches (Xe Vulkan and the CPU backend only, so it is opt-in)
set LLAMA_INKLING_REL_TAG=1

rem High priority and the performance cores (mask FFFF = 16 threads of a 12700K): one thread feeds the GPU about
rem 2,700 launches per token, and when other work pushes it off a P-core decode drops from 43 to about 25 tok/s.
start "inkling" /b /wait /high /affinity FFFF "%LLAMA%\llama-server.exe" -m "%MODEL%" -dev Vulkan0 -ngl 99 -fa on -bs ^
  -c %POOL% -np 2 --kv-unified -ctk q4_0 -ctv q4_0 -ub 512 -b 2048 ^
  --host 127.0.0.1 --port 8080
