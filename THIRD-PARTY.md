# Third-party sources

Brink uses these open-source sources, each under its own licence.

| Source | Licence | Note |
|---|---|---|
| Python package PIL | MIT-CMU | make_icon.py imports Pillow (PIL.Image, ImageDraw) as a dev tool to draw the icon. Nothing from Pillow is copied in, and Pillow is under the MIT-CMU (HPND-style) licence. |
| Python package PyQt6 | GPL-3.0-only | charts.py, gui.py and mapview.py import PyQt6, which the README says to install from apt. Nothing is copied in. PyQt6 is GPL-3.0 (or commercial), so Brink's own licence should be GPL-compatible if it is distributed to run against it. |
