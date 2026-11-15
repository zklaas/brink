# Brink on Windows

The same code runs on Windows, macOS and Linux. Brink needs **Python 3.10 or newer**:

    winget install --id Python.Python.3.13 -e --scope user

Then install with PowerShell:

    git clone https://github.com/zklaas/brink.git Brink
    cd Brink
    powershell -ExecutionPolicy Bypass -File install.ps1

That creates `.venv` (PyQt6), a `brink` command on your PATH (open a
new terminal first), and a **Brink** Start-menu entry.

Settings are kept in `%APPDATA%\Brink`.

To remove it: delete the folder, the Start-menu entry (Brink) and
`%LOCALAPPDATA%\Programs\Brink`.

Windows support has not yet been tested on a Windows machine; please report anything
that does not work.
