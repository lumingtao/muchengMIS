Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pyw = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Python\bin\pythonw.exe"
py = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Python\bin\python.exe"
If fso.FileExists(pyw) Then
    exe = pyw
ElseIf fso.FileExists(py) Then
    exe = py
Else
    exe = "python"
End If
cmd = """" & exe & """ """ & root & "\project_launcher.py"""
shell.Run cmd, 1, False
