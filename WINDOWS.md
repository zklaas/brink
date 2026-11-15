# Brink on Windows

The same code runs on Windows, macOS and Linux.

## Where to type the commands

Everything below is typed into **PowerShell**: open the Start menu, type
*PowerShell* and press Enter. (On Windows 11, *Terminal* opens PowerShell too, and
the Command Prompt also works for these commands.) Press Enter after each line.

## 1. Install Python

Brink needs **Python 3.10 or newer**. If you don't have it:

    winget install --id Python.Python.3.13 -e --scope user

Then close PowerShell and open it again, so it finds the new Python.

## 2. Get Brink

**With git** (`winget install --id Git.Git -e` installs it):

    git clone https://github.com/zklaas/brink.git Brink
    cd Brink

**Without git:** on https://github.com/zklaas/brink click **Code > Download ZIP**,
unpack it, open the unpacked folder (`brink-main`) in File Explorer, click the
address bar, type `powershell` and press Enter. PowerShell opens in that folder.

## 3. Install it

    powershell -ExecutionPolicy Bypass -File install.ps1

That creates `.venv` (PyQt6), a `brink` command (open a new PowerShell
window to use it), and a **Brink** entry in the Start menu, which is the easiest
way to start it from then on.

Settings are kept in `%APPDATA%\Brink`.

To remove it: delete the folder, the Start-menu entry (Brink) and
`%LOCALAPPDATA%\Programs\Brink`.

If something doesn't work, please write to zklaas@yahoo.ca.
