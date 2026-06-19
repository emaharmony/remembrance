@echo off
set "REMEMBRANCE_HOME=C:\Users\emaha\.remembrance"
set "REMEMBRANCE_GATE_BACKENDS=heuristic"
cd /d "D:\_projects_\remembrance-mcp"
"D:\_projects_\remembrance-mcp\.venv\Scripts\python.exe" -m remembrance_mcp
