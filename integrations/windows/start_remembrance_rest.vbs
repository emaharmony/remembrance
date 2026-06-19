Set shell = CreateObject("WScript.Shell")
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""D:\_projects_\remembrance-mcp\integrations\windows\start_remembrance_rest.ps1""", 0, False
