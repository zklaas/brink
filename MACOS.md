# Brink on macOS

The same code runs on macOS, Windows and Linux. Brink needs **Python 3.10 or newer**
(macOS's own `python3` is too old):

    brew install python@3.13        # Homebrew: https://brew.sh
    # or the installer from https://www.python.org/downloads/macos/

Then, in Terminal:

    git clone https://github.com/zklaas/brink.git Brink
    cd Brink
    bash install-macos.sh

That creates `.venv` (PyQt6), a `brink` command in `~/.local/bin`, and a
**Brink** app in your Applications folder (Launchpad, Spotlight, the Dock).

Settings are kept in `~/Library/Application Support/Brink`.

To remove it: delete the folder, `~/Applications/Brink.app` and `~/.local/bin/brink`.

macOS support has not yet been tested on a Mac; please report anything that does
not work.
