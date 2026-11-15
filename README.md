# Brink

A balance-of-power simulation. The world is made of **Regions** held by **Groups**, each with an amount of
**Power**. Every turn Groups grow, realign, and fight: they either use Power in **Wars** (where proximity in
Regions matters and the ratio of marshaled Power decides who wins and what proportion of Power the losers
lose), or they join **Alliances** to become a pole, to balance between poles, or to bandwagon with one.

    ./install.sh        # puts `brink` in ~/.local/bin and adds Brink (with its icon) to the app grid
    brink               # the window
    brink strategies    # what each strategy does
    brink run europe --turns 100 --seed 3
    brink many four --runs 200 --turns 100 --set decay=0.6

Needs Python 3 and PyQt6 (`sudo apt install python3-pyqt6`); otherwise standard library only.
`make_icon.py` (Pillow) rebuilds the icon: a balance scale standing on top of the world.

## The model in one paragraph

Power grows logistically toward the summed value of a Group's Regions (times a drifting productivity, so
Groups rise and decline unevenly). Groups then reconsider alliances by strategy - Pole, Balancer, Offshore
balancer, Threat balancer, Bandwagoner, Expansionist, Neutral. Wars: an attacker picks a target within reach
whose expected odds clear its aggression threshold; allies join by reliability; Power arrives at the theatre
times `decay^steps`; P(attacker wins) = `A^k/(A^k+D^k)`; losers lose `severity * r/(1+r)` of what they
marshaled, winners `attrition * severity/(1+r)`; a lopsided ratio takes the Region. Poles guarantee
unaligned Groups in their spheres of influence.

## What it measures

* **System**: Hegemony, Unipolar, Bipolar, Lopsided bipolar, ... with balancer(s), Tripolar, Multipolar, Diffuse.
* **Roles**: Pole, Holds the balance, Bandwagoning with X, Balancing with X, In X's sphere, Offshore, ...
* **Regional systems**: the same labels per zone, from the Power present in it, plus outside-power penetration.
* **Spheres of influence**: Regions where one pole supplies most of the Power that can reach them.
* Concentration (Singer-Bremer-Stuckey CON), balance between the top two poles, Wars, survival over many runs.

## Files

* `brink_app.py` - CLI and launcher
* `brink/model.py` - World, strategies, settings, diplomacy, War, measures, `run_many`
* `brink/scenarios.py` - Europe after 1815, Cold War world (both stylized), Four powers, random worlds; JSON format
* `brink/geo.py` - Voronoi-with-coastlines raster for the map and random-world borders
* `brink/mapview.py`, `brink/charts.py`, `brink/gui.py`, `brink/guide.py` - the window
* `test_model.py` - `python3 -m unittest test_model`
* `scenarios/` - where Save setup / Save current state put JSON scenarios by default

## Windows and macOS

The same code runs on Windows and macOS. To install it there:

* **Windows:** see [WINDOWS.md](WINDOWS.md) (`install.ps1`).
* **macOS:** see [MACOS.md](MACOS.md) (`install-macos.sh`).
