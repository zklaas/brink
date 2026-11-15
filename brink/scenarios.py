"""Built-in scenarios, the random-world generator, and JSON load/save.

Scenario format (JSON):
{
  "name": "...", "description": "...",
  "map": {"aspect": 1.25, "land_radius": 0.09},
  "settings": {...Settings fields...},
  "regions": [{"id", "name", "x", "y", "value", "links": [ids]}],
  "groups":  [{"id", "name", "colour", "power", "strategy", "growth",
               "mobilisation", "aggression", "regions": [ids]}],
  "alliances": [{"name", "leader", "members": [ids]}]
}
x, y run 0..1 across the map (y downward); a Region's value is its
contribution to its holder's capacity (the ceiling Power grows toward).
"""
from __future__ import annotations

import json
import math
import random

from . import geo
from .model import STRATEGIES, STRATEGY_ORDER

PALETTE = ["#2f6db5", "#d1495b", "#3a9a5b", "#e0a030", "#7b4fa8", "#1f9eb0", "#c2672b", "#5d6d7e",
           "#b04f8f", "#88a838", "#2c3e8f", "#a83232", "#4f9c8c", "#c9a227", "#8c5a3c", "#6b8fd6",
           "#9e4f4f", "#3f7f3f", "#a070c0", "#d07a50", "#507090", "#b0a040", "#7a3f6a", "#40a0a0",
           "#c05080", "#708040", "#405080", "#a06030"]


def _lonlat(lon, lat, lon0, lon1, lat0, lat1):
    return (lon - lon0) / (lon1 - lon0), (lat1 - lat) / (lat1 - lat0)


def _build(meta, regions, groups, links, alliances, box=None, cap_factor=1.25):
    """regions: [(id, name, lon, lat)] (or raw map x, y when box is None);
    groups: [(id, name, power, strategy, [region ids], extra dict)]."""
    owner = {}
    caps = {}
    for i, (gid, name, power, strat, rids, *extra) in enumerate(groups):
        weight = {r: 1.0 for r in rids}
        if extra and extra[0].get("weights"):
            weight.update(extra[0]["weights"])
        tot = sum(weight.values())
        for r in rids:
            owner[r] = gid
            caps[r] = power * cap_factor * weight[r] / tot
    adj = {r[0]: [] for r in regions}
    for a, b in links:
        adj[a].append(b)
    out_regions = []
    for rid, name, lon, lat in regions:
        x, y = _lonlat(lon, lat, *box) if box else (lon, lat)
        out_regions.append(dict(id=rid, name=name, x=round(x, 4), y=round(y, 4),
                                value=round(caps.get(rid, 3.0), 2), links=adj[rid]))
    out_groups = []
    for i, (gid, name, power, strat, rids, *extra) in enumerate(groups):
        g = dict(id=gid, name=name, colour=PALETTE[i % len(PALETTE)], power=power, strategy=strat,
                 growth=0.08, regions=list(rids))
        if extra:
            g.update({k: v for k, v in extra[0].items() if k != "weights"})
        out_groups.append(g)
    sc = dict(meta)
    sc.update(regions=out_regions, groups=out_groups, alliances=alliances)
    return sc


def europe_1815():
    regions = [
        ("ire", "Ireland", -8.0, 53.2), ("sco", "Scotland", -4.2, 56.9), ("eng", "England", -1.5, 52.3),
        ("parn", "Paris & the North", 2.4, 48.6), ("fsou", "Southern France", 2.0, 44.3),
        ("spa", "Spain", -3.7, 40.2), ("por", "Portugal", -8.2, 39.6), ("low", "Low Countries", 5.0, 51.6),
        ("rhi", "Rhineland", 7.3, 50.3), ("sax", "Hanover & Saxony", 10.6, 51.8),
        ("bra", "Brandenburg", 13.9, 52.9), ("epr", "East Prussia", 20.5, 54.3), ("den", "Denmark", 9.5, 55.8),
        ("swe", "Sweden", 15.5, 59.3), ("nwy", "Norway", 9.0, 61.0), ("bav", "Bavaria & the South", 10.5, 48.6),
        ("swi", "Switzerland", 8.2, 46.8), ("boh", "Bohemia", 14.8, 49.8), ("aus", "Austria", 15.0, 47.4),
        ("hun", "Hungary", 19.5, 47.0), ("gal", "Galicia", 23.0, 49.6), ("pol", "Congress Poland", 20.5, 51.8),
        ("lit", "Lithuania & Belarus", 26.5, 54.2), ("stp", "Baltic Russia", 30.0, 59.5),
        ("mos", "Moscow", 37.0, 55.6), ("ukr", "Ukraine", 32.0, 49.0), ("lom", "Lombardy-Venetia", 11.0, 45.5),
        ("pie", "Piedmont", 7.7, 44.8), ("pap", "Papal States", 12.5, 42.8), ("nap", "Naples & Sicily", 15.5, 40.4),
        ("bal", "The Balkans", 21.0, 42.5), ("wal", "Danubian Principalities", 26.0, 45.0),
        ("ana", "Constantinople & Anatolia", 31.0, 40.3),
    ]
    links = [
        ("ire", "eng"), ("sco", "eng"), ("eng", "low"), ("eng", "parn"), ("sco", "nwy"), ("parn", "fsou"),
        ("parn", "low"), ("parn", "rhi"), ("fsou", "spa"), ("fsou", "pie"), ("fsou", "swi"), ("parn", "swi"),
        ("spa", "por"), ("low", "rhi"), ("low", "sax"), ("rhi", "sax"), ("rhi", "bav"), ("rhi", "swi"),
        ("bav", "swi"), ("bav", "aus"), ("bav", "boh"), ("bav", "sax"), ("sax", "bra"), ("sax", "boh"),
        ("sax", "den"), ("bra", "den"), ("bra", "epr"), ("bra", "pol"), ("bra", "boh"), ("epr", "pol"),
        ("epr", "lit"), ("epr", "swe"), ("den", "swe"), ("den", "nwy"), ("swe", "nwy"), ("swe", "stp"),
        ("boh", "aus"), ("boh", "gal"), ("aus", "hun"), ("aus", "lom"), ("aus", "swi"), ("lom", "pie"),
        ("lom", "pap"), ("lom", "swi"), ("pie", "swi"), ("pap", "nap"), ("pap", "pie"), ("hun", "gal"),
        ("hun", "bal"), ("hun", "wal"), ("gal", "pol"), ("gal", "ukr"), ("pol", "lit"), ("lit", "stp"),
        ("lit", "mos"), ("lit", "ukr"), ("stp", "mos"), ("mos", "ukr"), ("ukr", "wal"), ("wal", "bal"),
        ("bal", "ana"), ("wal", "ana"), ("ukr", "ana"), ("nap", "bal"), ("aus", "bal"),
    ]
    groups = [
        ("gbr", "Britain", 30, "Offshore balancer", ["eng", "sco", "ire"], {"weights": {"eng": 3}}),
        ("fra", "France", 24, "Pole", ["parn", "fsou"]),
        ("rus", "Russia", 30, "Pole", ["stp", "mos", "ukr", "lit", "pol"]),
        ("aut", "Austria", 20, "Threat balancer", ["aus", "boh", "hun", "lom", "gal"]),
        ("pru", "Prussia", 14, "Expansionist", ["bra", "epr", "rhi"]),
        ("ger", "German States", 7, "Bandwagoner", ["sax", "bav"], {"short": "German States"}),
        ("ott", "Ottoman Empire", 14, "Threat balancer", ["ana", "bal", "wal"]),
        ("esp", "Spain", 7, "Bandwagoner", ["spa"]),
        ("prt", "Portugal", 2, "Bandwagoner", ["por"]),
        ("ned", "Netherlands", 4, "Bandwagoner", ["low"]),
        ("swn", "Sweden-Norway", 5, "Neutral", ["swe", "nwy"]),
        ("dan", "Denmark", 2, "Neutral", ["den"]),
        ("sar", "Sardinia-Piedmont", 3, "Expansionist", ["pie"], {"short": "Piedmont"}),
        ("pst", "Papal States", 2, "Neutral", ["pap"]),
        ("sic", "Two Sicilies", 4, "Bandwagoner", ["nap"]),
        ("sui", "Switzerland", 1.5, "Neutral", ["swi"]),
    ]
    alliances = [dict(name="Quadruple Alliance", leader="rus", members=["rus", "gbr", "aut", "pru"])]
    zones = [dict(name="Western Europe", regions=["ire", "sco", "eng", "parn", "fsou", "spa", "por", "low"]),
             dict(name="Germany & the North", regions=["rhi", "sax", "bra", "epr", "den", "swe", "nwy", "bav", "swi"]),
             dict(name="Italy & the Danube", regions=["lom", "pie", "pap", "nap", "aus", "boh", "hun"]),
             dict(name="The East", regions=["gal", "pol", "lit", "stp", "mos", "ukr", "wal", "bal", "ana"])]
    meta = dict(name="Europe after 1815 (stylized)",
                description=("The Congress of Vienna settlement with the Quadruple Alliance in place. Power figures "
                             "are rough illustrative weights, not data; strategies are caricatures of each state's "
                             "habits (Britain the offshore balancer, Austria wary of its neighbours, Prussia restless)."),
                map=dict(aspect=1.25, land_radius=0.115, seed=3),
                settings=dict(decay=0.7, reach=3, sea_cost=1.2), zones=zones)
    return _build(meta, regions, groups, links, alliances, (-11, 39, 36, 62))


def cold_war():
    regions = [
        ("usw", "US West", 0.08, 0.3), ("usc", "US Central", 0.17, 0.29), ("use", "US East", 0.26, 0.31),
        ("can", "Canada", 0.17, 0.12), ("mex", "Mexico & Central America", 0.13, 0.46), ("car", "Caribbean", 0.24, 0.48),
        ("col", "Andes", 0.21, 0.62), ("bra", "Brazil", 0.3, 0.72), ("arg", "Southern Cone", 0.23, 0.88),
        ("uk", "Britain", 0.4, 0.16), ("fra", "France", 0.42, 0.29), ("ibe", "Iberia", 0.37, 0.4),
        ("wger", "West Germany & Benelux", 0.47, 0.21), ("ita", "Italy", 0.49, 0.34), ("nor", "Nordic", 0.5, 0.06),
        ("eger", "East Germany & Poland", 0.54, 0.18), ("bal", "Balkans & Hungary", 0.56, 0.3), ("tur", "Turkey", 0.62, 0.38),
        ("urw", "Russia", 0.62, 0.11), ("ukr", "Ukraine & Belarus", 0.6, 0.22), ("ura", "Urals & Central Asia", 0.71, 0.19),
        ("sib", "Siberia", 0.81, 0.08), ("fea", "Soviet Far East", 0.93, 0.12), ("mde", "Arabia & Levant", 0.59, 0.5),
        ("egy", "North Africa", 0.47, 0.47), ("waf", "West Africa", 0.42, 0.61), ("caf", "Central & East Africa", 0.53, 0.66),
        ("saf", "Southern Africa", 0.53, 0.86), ("irn", "Iran", 0.67, 0.42), ("pak", "Pakistan", 0.74, 0.36),
        ("ind", "India", 0.77, 0.52), ("chn", "North China", 0.84, 0.27), ("chs", "South China", 0.84, 0.42),
        ("kor", "Korea", 0.91, 0.24), ("jpn", "Japan", 0.97, 0.31), ("sea", "Southeast Asia", 0.86, 0.58),
        ("ins", "Indonesia", 0.89, 0.72), ("aus", "Australia", 0.92, 0.88),
    ]
    links = [
        ("usw", "usc"), ("usc", "use"), ("usw", "can"), ("usc", "can"), ("use", "can"), ("usw", "mex"),
        ("usc", "mex"), ("mex", "car"), ("use", "car"), ("mex", "col"), ("car", "col"), ("col", "bra"),
        ("col", "arg"), ("bra", "arg"), ("bra", "waf"), ("use", "uk"), ("usw", "jpn"),
        ("uk", "fra"), ("uk", "nor"), ("uk", "wger"), ("fra", "wger"), ("fra", "ibe"), ("fra", "ita"),
        ("ibe", "egy"), ("wger", "ita"), ("wger", "nor"), ("wger", "eger"), ("ita", "bal"), ("ita", "egy"),
        ("eger", "bal"), ("eger", "ukr"), ("eger", "nor"), ("nor", "urw"), ("bal", "ukr"), ("bal", "tur"),
        ("tur", "ukr"), ("tur", "mde"), ("ukr", "urw"), ("urw", "ura"), ("ukr", "ura"), ("ura", "sib"),
        ("sib", "fea"), ("ura", "irn"), ("ura", "pak"), ("ura", "chn"), ("sib", "chn"), ("fea", "chn"),
        ("fea", "kor"), ("fea", "jpn"), ("mde", "egy"), ("mde", "irn"), ("mde", "caf"), ("egy", "caf"),
        ("egy", "waf"), ("waf", "caf"), ("caf", "saf"), ("irn", "pak"), ("pak", "ind"), ("ind", "chs"),
        ("ind", "sea"), ("chn", "chs"), ("chn", "kor"), ("kor", "jpn"), ("chs", "sea"), ("sea", "ins"),
        ("ins", "aus"), ("tur", "irn"),
    ]
    groups = [
        ("usa", "United States", 100, "Pole", ["usw", "usc", "use"], {"weights": {"use": 1.5}, "short": "USA"}),
        ("sov", "Soviet Union", 60, "Pole", ["urw", "ukr", "ura", "sib", "fea"], {"weights": {"urw": 2, "ukr": 1.5}, "short": "USSR"}),
        ("prc", "China", 20, "Threat balancer", ["chn", "chs"]),
        ("gbr", "Britain", 14, "Balancer", ["uk"]),
        ("fra", "France", 10, "Threat balancer", ["fra"]),
        ("frg", "West Germany", 10, "Bandwagoner", ["wger"], {"short": "W. Germany"}),
        ("ita", "Italy", 6, "Bandwagoner", ["ita"]),
        ("can", "Canada", 5, "Bandwagoner", ["can"]),
        ("jap", "Japan", 8, "Bandwagoner", ["jpn"]),
        ("ind", "India", 10, "Neutral", ["ind"]),
        ("pak", "Pakistan", 3, "Bandwagoner", ["pak"]),
        ("eeu", "Eastern Europe", 8, "Bandwagoner", ["eger"], {"short": "E. Europe"}),
        ("bal", "Balkan states", 5, "Bandwagoner", ["bal"], {"short": "Balkans"}),
        ("tur", "Turkey", 4, "Threat balancer", ["tur"]),
        ("irn", "Iran", 3, "Bandwagoner", ["irn"]),
        ("arb", "Arab states", 6, "Neutral", ["mde", "egy"]),
        ("lat", "Mexico & the Caribbean basin", 5, "Bandwagoner", ["mex", "car", "col"], {"short": "Caribbean basin"}),
        ("bzl", "Brazil & the Southern Cone", 7, "Neutral", ["bra", "arg"], {"short": "Brazil & S. Cone"}),
        ("esp", "Iberia", 4, "Bandwagoner", ["ibe"]),
        ("nrd", "Nordic states", 5, "Neutral", ["nor"]),
        ("afr", "Africa", 5, "Neutral", ["waf", "caf"]),
        ("rsa", "South Africa", 3, "Bandwagoner", ["saf"]),
        ("kor", "Korea", 3, "Bandwagoner", ["kor"]),
        ("asn", "Southeast Asia", 5, "Neutral", ["sea", "ins"]),
        ("aus", "Australia", 4, "Bandwagoner", ["aus"]),
    ]
    alliances = [
        dict(name="Western alliance", leader="usa",
             members=["usa", "gbr", "fra", "frg", "ita", "can", "tur", "jap", "aus", "kor"]),
        dict(name="Eastern bloc", leader="sov", members=["sov", "eeu", "bal", "prc"]),
    ]
    zones = [dict(name="Americas", regions=["usw", "usc", "use", "can", "mex", "car", "col", "bra", "arg"]),
             dict(name="Europe", regions=["uk", "fra", "ibe", "wger", "ita", "nor", "eger", "bal", "ukr", "urw"]),
             dict(name="Middle East & Africa", regions=["tur", "mde", "egy", "waf", "caf", "saf", "irn"]),
             dict(name="Central & South Asia", regions=["ura", "pak", "ind"]),
             dict(name="East Asia & Pacific", regions=["sib", "fea", "chn", "chs", "kor", "jpn", "sea", "ins", "aus"])]
    meta = dict(name="Cold War world (stylized)", zones=zones,
                description=("Two blocs around the early-1950s superpowers, with China inside the Eastern bloc and much "
                             "of the world neutral. Power figures are rough illustrative weights, not data. Watch "
                             "whether China, as a threat balancer, stays with its neighbour."),
                map=dict(aspect=2.0, land_radius=0.085, seed=11),
                settings=dict(decay=0.75, reach=3, war_rate=0.35, sea_cost=1.3, air_range=0.3, air_cost=1.5,
                              airspace_respect=0.6))
    return _build(meta, regions, groups, links, alliances)


# --------------------------------------------------------------------------
# Random worlds
# --------------------------------------------------------------------------

_ON = ["k", "t", "v", "s", "m", "r", "d", "l", "th", "br", "g", "z", "n", "kh", "p", "dr", "f", "h"]
_NU = ["a", "e", "i", "o", "u", "ae", "y", "ai", "ou"]
_CO = ["n", "r", "s", "l", "th", "nd", "rk", "x", "m", "sh", "", "", ""]
_SUFFIX_GROUP = ["", "", "", " League", " Realm", " Union", " Commonwealth", " Empire", " Republic"]


def _word(rnd, syl=None):
    syl = syl or rnd.choice([2, 2, 2, 3])
    w = "".join(rnd.choice(_ON) + rnd.choice(_NU) for _ in range(syl - 1)) + rnd.choice(_ON) + rnd.choice(_NU) + rnd.choice(_CO)
    return w.capitalize()


def random_world(seed=1, n_regions=30, n_groups=8, aspect=1.6):
    rnd = random.Random(seed)
    # Best-candidate sampling, clustered round a few continent centres.
    centres = [(rnd.uniform(0.2, 0.8), rnd.uniform(0.2, 0.8)) for _ in range(rnd.choice([2, 3, 3, 4]))]
    pts = []
    while len(pts) < n_regions:
        best, bd = None, -1
        for _ in range(12):
            cx, cy = rnd.choice(centres)
            x = min(0.96, max(0.04, rnd.gauss(cx, 0.2)))
            y = min(0.95, max(0.05, rnd.gauss(cy, 0.2)))
            d = min([((x - a) * aspect) ** 2 + (y - b) ** 2 for a, b in pts] or [1])
            if d > bd:
                best, bd = (x, y), d
        pts.append(best)
    spacing = math.sqrt(aspect / n_regions)
    radius = spacing * 0.55
    W, H, idx = geo.raster(pts, aspect, radius, 260, seed=seed)
    pairs = geo.touching(W, H, idx)
    # Connect separate landmasses with sea links between their closest Regions.
    parent = list(range(n_regions))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b in pairs:
        parent[find(a)] = find(b)

    def d2(a, b):
        return ((pts[a][0] - pts[b][0]) * aspect) ** 2 + (pts[a][1] - pts[b][1]) ** 2
    while len({find(i) for i in range(n_regions)}) > 1:
        cands = [(d2(a, b), a, b) for a in range(n_regions) for b in range(a + 1, n_regions) if find(a) != find(b)]
        _, a, b = min(cands)
        pairs.add((a, b))
        parent[find(a)] = find(b)
    used = set()
    names = []
    while len(names) < n_regions:
        w = _word(rnd)
        if w not in used:
            used.add(w)
            names.append(w)
    regions = []
    for i, (x, y) in enumerate(pts):
        regions.append(dict(id=f"r{i + 1}", name=names[i], x=round(x, 4), y=round(y, 4),
                            value=round(rnd.uniform(4, 12), 1), links=[]))
    for a, b in sorted(pairs):
        regions[a]["links"].append(regions[b]["id"])
    # Seed Groups far apart, then grow territories breadth-first.
    adj = {i: set() for i in range(n_regions)}
    for a, b in pairs:
        adj[a].add(b)
        adj[b].add(a)
    seeds = [rnd.randrange(n_regions)]
    while len(seeds) < n_groups:
        seeds.append(max(range(n_regions), key=lambda i: min(d2(i, s) for s in seeds) + rnd.random() * 1e-6))
    owner = {s: k for k, s in enumerate(seeds)}
    frontier = list(range(n_groups))
    # Uneven sizes: some Groups get more growth turns.
    weights = [rnd.uniform(0.5, 2.0) for _ in range(n_groups)]
    while len(owner) < n_regions:
        k = rnd.choices(range(n_groups), weights)[0]
        options = [n for r, o in owner.items() if o == k for n in adj[r] if n not in owner]
        if not options:
            weights[k] = 0.0001
            if all(w < 0.001 for w in weights):
                for r in range(n_regions):  # stragglers on unreachable land
                    if r not in owner:
                        owner[r] = min(owner.items(), key=lambda it: d2(it[0], r))[1]
            continue
        owner[rnd.choice(options)] = k
    groups = []
    strategies = list(STRATEGY_ORDER)
    for k in range(n_groups):
        rids = [regions[r]["id"] for r, o in owner.items() if o == k]
        cap = sum(regions[r]["value"] for r, o in owner.items() if o == k)
        strat = rnd.choice(strategies)
        base = STRATEGIES[strat]
        name = _word(rnd, rnd.choice([2, 3])) + rnd.choice(_SUFFIX_GROUP)
        groups.append(dict(id=f"g{k + 1}", name=name, colour=PALETTE[k % len(PALETTE)],
                           power=round(cap * rnd.uniform(0.6, 0.9), 1), strategy=strat, growth=0.08,
                           mobilisation=base["mobilisation"], aggression=base["aggression"], regions=rids))
    return dict(name=f"Random world #{seed}",
                description=f"{n_regions} Regions and {n_groups} Groups with random strategies (seed {seed}).",
                map=dict(aspect=aspect, land_radius=round(radius, 4), seed=seed),
                settings={}, regions=regions, groups=groups, alliances=[])


def four_powers(seed=5):
    """A fictional world built to stay multipolar: four regional powers far apart, wary neighbours,
    and Power that fades fast with distance."""
    sc = random_world(seed, n_regions=44, n_groups=12, aspect=1.9)
    plan = ["Pole", "Pole", "Pole", "Pole", "Threat balancer", "Threat balancer", "Bandwagoner",
            "Threat balancer", "Offshore balancer", "Expansionist", "Bandwagoner", "Neutral"]
    for g, strat in zip(sc["groups"], plan):
        g["strategy"] = strat
        g["aggression"] = STRATEGIES[strat]["aggression"]
        g["mobilisation"] = STRATEGIES[strat]["mobilisation"]
        if strat == "Pole":
            for r in sc["regions"]:
                if r["id"] in g["regions"]:
                    r["value"] = round(r["value"] * 1.8, 1)
            g["power"] = round(g["power"] * 1.8, 1)
    sc["name"] = "Four powers (fictional, multipolar)"
    sc["description"] = ("Four regional powers far apart on a made-up map, ringed by threat balancers and a few "
                         "bandwagoners, an offshore balancer, an expansionist and a neutral. Power fades fast with "
                         "distance (decay 0.5, reach 2), so blocs tend to form region by region.")
    sc["settings"] = dict(decay=0.5, reach=2, guarantee=0.6, pole_share=0.12)
    return sc


BUILTINS = {
    "Europe after 1815 (stylized)": europe_1815,
    "Cold War world (stylized)": cold_war,
    "Four powers (fictional, multipolar)": four_powers,
    "Random world": lambda: random_world(1),
}


def load(path):
    with open(path, encoding="utf-8") as f:
        sc = json.load(f)
    for key in ("regions", "groups"):
        if key not in sc:
            raise ValueError(f"Scenario has no '{key}' list")
    sc.setdefault("name", path.rsplit("/", 1)[-1])
    sc.setdefault("map", {})
    sc.setdefault("alliances", [])
    return sc


def save(sc, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sc, f, indent=1)
