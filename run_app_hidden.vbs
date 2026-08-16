Option Explicit

Dim fso, shell, scriptDir, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "cmd /c """ & scriptDir & "\run_app.bat"""

shell.Run cmd, 0, False
