#!/usr/bin/env python3
"""Brink - a balance-of-power simulation of Groups, Regions, Wars and Alliances.

    brink                          open the window
    brink scenarios                the built-in scenarios
    brink strategies               every strategy, explained
    brink run [SCENARIO] [opts]    one history in the terminal, turn by turn
    brink many [SCENARIO] [opts]   many runs, summarised

SCENARIO is europe (default), coldwar, four, random[:SEED], or a path to a .json file.
"""
from __future__ import annotations

import argparse
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brink import scenarios as SC  # noqa: E402
from brink.model import STRATEGY_ORDER, Settings, World, run_many, strategy_info  # noqa: E402


def get_scenario(name):
    key = (name or "europe").lower()
    if key in ("europe", "1815", "europe1815"):
        return SC.europe_1815()
    if key in ("coldwar", "cold-war", "cold"):
        return SC.cold_war()
    if key in ("four", "fourpowers", "multipolar"):
        return SC.four_powers()
    if key.startswith("random"):
        seed = int(key.split(":", 1)[1]) if ":" in key else 1
        return SC.random_world(seed)
    if os.path.exists(name):
        return SC.load(name)
    sys.exit(f"No scenario '{name}'. Use europe, coldwar, random[:SEED] or a .json file.")


def settings_for(sc, a):
    st = Settings.from_dict(sc.get("settings"))
    st.seed = a.seed
    for kv in a.set or []:
        k, _, v = kv.partition("=")
        if not hasattr(st, k):
            sys.exit(f"Unknown setting '{k}'. Settings: {', '.join(st.to_dict())}")
        cur = getattr(st, k)
        setattr(st, k, (v.lower() in ("1", "true", "yes")) if isinstance(cur, bool) else type(cur)(v))
    return st


def cmd_scenarios(a):
    for f in (SC.europe_1815, SC.cold_war, SC.four_powers, lambda: SC.random_world(1)):
        sc = f()
        print(sc["name"])
        print(textwrap.fill(sc.get("description", ""), 88, initial_indent="    ", subsequent_indent="    "))


def cmd_strategies(a):
    for n in STRATEGY_ORDER:
        print()
        for para in strategy_info(n).split("\n\n"):
            print(textwrap.fill(para, 88))
            print()


def cmd_run(a):
    sc = get_scenario(a.scenario)
    w = World(sc, settings_for(sc, a))
    print(f"{sc['name']}  (seed {w.settings.seed})")
    for t in range(a.turns):
        snap = w.step()
        pol = snap["polarity"]
        if not a.quiet and (snap["events"] or t == a.turns - 1):
            print(f"\n--- Turn {snap['turn']}: {pol['label']}, {pol['poles']} pole(s), largest bloc {pol['top_share']:.0%}")
            for e in snap["events"]:
                print("  " + e)
    T = w.total_power()
    print("\nAt the end:")
    for g in sorted(w.groups.values(), key=lambda g: -g.power):
        if not g.alive:
            continue
        al = w.alliances[g.alliance].name if g.alliance else "-"
        print(f"  {g.name:28s} {g.power:7.1f} {g.power / T:6.1%}  {g.strategy:18s} {al:24s} {w.history[-1]['roles'][g.id]}")
    print("Regional systems:")
    for z in w.history[-1]["regional"]:
        print(f"  {z['name']:24s} {z['label']:30s} outside powers {z['penetration']:4.0%}  poles: "
              + ", ".join(w.bloc_name(k) for k in z["pole_keys"]))
    roles = w.history[-1]["roles"]
    for label in ("Subjugated", "Gone"):
        names = [g.name for g in w.groups.values() if not g.alive and roles.get(g.id) == label]
        if names:
            print(f"  {label}: " + ", ".join(names))
    from brink.model import running_stats
    rs = running_stats(w.history)
    print(f"Rate of pacifism {rs['pacifism']:.1%} ({rs['wars_per_round']:.2f} Wars per round, "
          f"{rs['armed_per_round']:.2f} armed uprisings per round, {rs['peaceful_rounds']} of {rs['rounds']} rounds "
          f"without either); rate of freedom {rs['freedom']:.1%} "
          f"({rs['bandwagoning_per_round']:.2f} Groups bandwagoning per round)")
    print(f"Rate of self-determination {rs['self_rule']:.1%}; {rs['uprisings']} uprisings, {rs['liberations']} liberations, "
          f"{rs['reborn']} Groups reborn, {rs['breakaways']} breakaways from blocs, {rs['upheavals']} upheavals "
          f"(peaceful: {rs['protests']} protests, {rs['home_protests']} changes of government)")
    fmt = lambda v: "-" if v is None else f"{v:.0%}"
    print(f"Integration of occupied Regions {fmt(rs['integration'])}; cohesion of followers {fmt(rs['cohesion'])}; "
          f"mean war weariness {rs['weariness']:.2f}")
    pol = w.history[-1]["polarity"]
    print(f"System: {pol['label']}; balance {pol['balance']:.2f}; concentration {pol['con_blocs']:.2f}; "
          f"Wars fought {sum(len(h['wars']) for h in w.history)}")


def cmd_many(a):
    sc = get_scenario(a.scenario)
    st = settings_for(sc, a)

    def prog(d, n):
        print(f"\r{d}/{n}", end="", file=sys.stderr)
    res = run_many(sc, st, a.runs, a.turns, progress=prog)
    print(file=sys.stderr)
    n = max(1, res["runs"])
    print(f"{sc['name']}: {res['runs']} runs x {res['turns']} turns (seeds {st.seed}..{st.seed + n - 1})")
    print("System at the end: " + ", ".join(f"{k} {v / n:.0%}" for k, v in sorted(res["labels"].items(), key=lambda kv: -kv[1])))
    print(f"Mean poles {res['poles']:.2f}; mean Wars per run {res['wars']:.1f}; "
          f"rate of pacifism {res['pacifism']:.1%}; rate of freedom {res['freedom']:.1%}")
    u = res["unrest"]
    print(f"Rate of self-determination {u['self_rule']:.1%}; per run {u['uprisings']:.1f} uprisings, {u['liberations']:.1f} liberations, "
          f"{u['reborn']:.1f} rebirths, {u['breakaways']:.1f} breakaways, {u['upheavals']:.1f} upheavals "
          f"(peaceful: {u['protests']:.1f} protests, {u['home_protests']:.1f} changes of government)")
    for zname, d in res["zones"].items():
        print(f"  {zname}: " + ", ".join(f"{k} {v / n:.0%}" for k, v in sorted(d.items(), key=lambda kv: -kv[1])))
    print()
    print(f"  {'Group':28s} {'Strategy':18s} {'Survived':>9s} {'Share':>7s} {'Largest':>8s} {'Pole':>6s}")
    for g in sorted(sc["groups"], key=lambda g: -res["per"][g["id"]]["share"]):
        p = res["per"][g["id"]]
        print(f"  {g['name']:28s} {g.get('strategy', ''):18s} {p['survived'] / n:9.0%} {p['share']:7.1%} "
              f"{p['largest'] / n:8.0%} {p['pole'] / n:6.0%}")


def main():
    if len(sys.argv) == 1:
        from brink.gui import main as gui_main
        sys.exit(gui_main(sys.argv))
    ap = argparse.ArgumentParser(prog="brink", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("gui", help="open the window")
    sub.add_parser("scenarios", help="list the built-in scenarios")
    sub.add_parser("strategies", help="explain every strategy")
    for name in ("run", "many"):
        p = sub.add_parser(name)
        p.add_argument("scenario", nargs="?", default="europe")
        p.add_argument("--turns", type=int, default=100)
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--set", action="append", metavar="NAME=VALUE",
                       help="override a setting, e.g. --set decay=0.5 (repeatable)")
        if name == "run":
            p.add_argument("--quiet", action="store_true", help="only the final standings")
        else:
            p.add_argument("--runs", type=int, default=100)
    a = ap.parse_args()
    if a.cmd in (None, "gui"):
        from brink.gui import main as gui_main
        sys.exit(gui_main(sys.argv[:1]))
    {"scenarios": cmd_scenarios, "strategies": cmd_strategies, "run": cmd_run, "many": cmd_many}[a.cmd](a)


if __name__ == "__main__":
    main()
