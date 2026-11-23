#!/bin/bash
# ink-stop.sh PORT: stop every llama-server listening on PORT (and only those)
for pid in $(powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | Where-Object { \$_.CommandLine -match '--port $1( |\$)' } | Select-Object -ExpandProperty ProcessId" | tr -d '\r'); do
  taskkill //PID $pid //F >/dev/null
done
