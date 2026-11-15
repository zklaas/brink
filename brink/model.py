"""Brink model: Regions, Groups, Alliances, Wars.

A turn has three phases:

1. Growth     - every Group's Power grows toward the capacity of the Regions
                it holds (logistic), so a battered Group recovers and a Group
                that has lost Regions shrinks toward its smaller base.
2. Diplomacy  - Groups reconsider their alignment according to their
                strategy: lead a pole, balance against the strongest bloc,
                balance against the nearest threat, sit offshore until a bloc
                looks hegemonic, bandwagon with the strongest, or stay out.
3. War        - Groups that see a favourable fight start a War.  Each side
                marshals part of its Power; what reaches the theatre shrinks
                with distance in Regions (the loss-of-strength gradient).  The
                ratio of marshaled Power decides the winner and the proportion
                of Power the losers lose; a lopsided win also takes a Region.
"""
from __future__ import annotations

import copy
import heapq
import math
import random
from collections import deque
from dataclasses import asdict, dataclass, field, fields

INF = 10 ** 6

# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------

STRATEGY_ORDER = ["Pole", "Balancer", "Offshore balancer", "Threat balancer",
                  "Bandwagoner", "Expansionist", "Neutral"]

STRATEGIES = {
    "Pole": dict(
        aggression=0.35, mobilisation=0.5,
        gist="Wants to lead a bloc of its own; never follows another Group.",
        blurb=("A Pole stays unaligned so that others can gather round it, or leads the alliance it is in. "
               "It will not sit in an alliance led by someone else once its own Power reaches 80% of the "
               "leader's: it walks out and stands as a rival pole. Others make it a pole by joining it "
               "(bandwagoners when it is the strongest, balancers when it is the counterweight).")),
    "Balancer": dict(
        aggression=0.25, mobilisation=0.5,
        gist="Joins the counterweight to the strongest bloc, wherever that bloc is.",
        blurb=("A Balancer balances against power. It looks at the blocs other than its own and finds the "
               "strongest one. If it is inside that bloc and the bloc holds more than half of all Power, it "
               "defects. If it is unaligned it joins the second-strongest bloc (unless it is itself at least "
               "as strong as that bloc, in which case it stays out and lets others join it). Distance does "
               "not matter to a Balancer - only totals.")),
    "Offshore balancer": dict(
        aggression=0.2, mobilisation=0.45,
        gist="Stays out until one bloc nears hegemony, then backs its strongest rival - and leaves again later.",
        blurb=("The classic balancer between poles (Britain's role in the European balance). It stays "
               "unaligned while no bloc holds more than the 'hegemony alarm' share of all Power. When one "
               "does, it joins the strongest other bloc; if it finds itself inside the alarming bloc it "
               "leaves. When the alarm passes it drifts back offshore. While unaligned it also intervenes "
               "in Wars on the defending side when the attacker belongs to the strongest bloc or brings "
               "far more Power.")),
    "Threat balancer": dict(
        aggression=0.25, mobilisation=0.5,
        gist="Balances against the bloc that threatens it most - Power weighted by proximity and aggression.",
        blurb=("After Stephen Walt's balance of threat. For each other bloc it adds up the Power of the "
               "members as it would arrive at its own Regions (decayed by distance) and weights it by how "
               "aggressive each member is. If the worst threat is serious (more than half its own Power) it "
               "joins the strongest bloc that is not that threat. A distant giant worries it less than a "
               "middling neighbour.")),
    "Bandwagoner": dict(
        aggression=0.2, mobilisation=0.45,
        gist="Joins the bloc with the most Power that can reach it.",
        blurb=("A Bandwagoner sides with strength. It finds the bloc whose Power, decayed by distance, "
               "bears down on it most heavily and joins it (if that bloc is at least 1.5x its own Power). "
               "When another bloc overtakes its current one, it switches - which is how a rising pole "
               "snowballs.")),
    "Expansionist": dict(
        aggression=0.7, mobilisation=0.6,
        gist="Prefers a free hand and makes War readily; allies only when cornered.",
        blurb=("An Expansionist keeps out of alliances and attacks whenever a fight looks favourable. "
               "Only if a bloc's Power bearing on it exceeds twice its own does it look for protection, "
               "and then it behaves like a Threat balancer.")),
    "Neutral": dict(
        aggression=0.0, mobilisation=0.6,
        gist="Never allies and never starts a War; defends itself when attacked.",
        blurb=("A Neutral leaves any alliance it is put in and never begins a War. It still fights when "
               "attacked, with its full mobilisation, and Offshore balancers may come to its aid.")),
}


# A peaceful change of government moves a Group to a less warlike strategy.
DOVISH = {"Expansionist": "Threat balancer", "Pole": "Balancer", "Balancer": "Offshore balancer",
          "Threat balancer": "Offshore balancer", "Bandwagoner": "Neutral", "Offshore balancer": "Neutral",
          "Neutral": "Neutral"}


def strategy_info(name: str) -> str:
    s = STRATEGIES[name]
    return f"{name}\n\nIn short: {s['gist']}\n\n{s['blurb']}"


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

@dataclass
class Settings:
    decay: float = 0.7
    reach: int = 3
    decisiveness: float = 2.0
    severity: float = 0.5
    attrition: float = 0.4
    spoils: float = 0.25
    conquest_ratio: float = 1.6
    last_region_ratio: float = 3.0
    defence_bonus: float = 1.25
    war_rate: float = 0.5
    pole_share: float = 0.2
    alarm: float = 0.4
    balancer_share: float = 0.05
    sphere_share: float = 0.5
    reliability: float = 0.8
    offensive_help: float = 0.4
    guarantee: float = 0.5
    inertia: float = 0.6
    drift: float = 0.04
    lead_share: float = 0.35
    rebellion_rate: float = 0.5
    grievance_growth: float = 0.08
    harshness: float = 0.5
    integration_rate: float = 0.05
    care_cost: float = 0.01
    cohesion_rate: float = 0.03
    grievance_memory: float = 0.95
    nonviolence: float = 0.5
    conduct_memory: float = 0.97
    passage: bool = True
    sea_cost: float = 1.5
    violation_reluctance: float = 2.0
    violation_resistance: float = 0.6
    air_range: float = 0.0
    air_cost: float = 1.5
    airspace_respect: float = 0.5
    unpredictability: float = 0.4
    crisis_rate: float = 0.04
    fervour: float = 1.0
    fervour_rounds: int = 20
    weariness_rate: float = 2.0
    weariness_recovery: float = 0.08
    upheaval_threshold: float = 0.6
    garrison: float = 0.15
    upkeep: float = 0.02
    sponsorship: float = 0.4
    follower_resentment: float = 0.15
    resentment_threshold: float = 0.6
    deterministic: bool = False
    seed: int = 1

    @classmethod
    def from_dict(cls, d: dict | None) -> "Settings":
        s = cls()
        for f in fields(cls):
            if d and f.name in d:
                setattr(s, f.name, type(getattr(s, f.name))(d[f.name]))
        return s

    def to_dict(self) -> dict:
        return asdict(self)


# name: (label, minimum, maximum, step, decimals, help)
SETTING_INFO = {
    "decay": ("Power kept per Region of distance", 0.05, 1.0, 0.05, 2,
              "Loss-of-strength gradient: Power marshaled N Regions away arrives multiplied by decay^N. "
              "Low = geography dominates, local powers are safe; 1 = distance does not matter."),
    "reach": ("Reach (Regions)", 1, 12, 1, 0,
              "A Group can only start a War with a Group whose nearest Region is at most this many steps away."),
    "decisiveness": ("Decisiveness of War", 0.5, 8.0, 0.5, 1,
                     "Exponent k in P(attacker wins) = A^k / (A^k + D^k), where A and D are the marshaled Power "
                     "at the theatre. Higher = the larger force almost always wins."),
    "severity": ("Severity of defeat", 0.05, 1.0, 0.05, 2,
                 "Losers lose severity x r/(1+r) of the Power they marshaled, where r = winner's marshaled "
                 "Power / loser's. An even fight costs a quarter of it at 0.5; a 3:1 rout costs 37.5%."),
    "attrition": ("Winner's attrition", 0.0, 1.0, 0.05, 2,
                  "Winners lose attrition x severity x 1/(1+r) of what they marshaled: costly when the fight "
                  "was close, cheap when it was lopsided."),
    "spoils": ("Spoils", 0.0, 1.0, 0.05, 2,
               "Share of the losers' lost Power that is transferred to the winners (split by contribution)."),
    "conquest_ratio": ("Ratio that takes a Region", 1.0, 10.0, 0.1, 1,
                       "If the winners marshaled at least this many times the losers' Power, the winning "
                       "leader takes the contested Region. A Group with no Regions left is gone."),
    "last_region_ratio": ("Ratio that takes a last Region", 1.0, 20.0, 0.5, 1,
                          "A Group's last Region is harder to take: the winners need at least this ratio. "
                          "Higher = small states survive defeats and live to recover."),
    "defence_bonus": ("Defender's advantage", 1.0, 3.0, 0.05, 2,
                      "The defending side's marshaled Power is multiplied by this."),
    "war_rate": ("War propensity", 0.0, 2.0, 0.05, 2,
                 "Chance per turn that a Group with a favourable target attacks = war propensity x its aggression."),
    "pole_share": ("Share that makes a pole", 0.05, 0.6, 0.01, 2,
                   "A bloc (an alliance, or an unaligned Group) holding at least this share of all Power counts as a pole."),
    "balancer_share": ("Share that makes a balancer", 0.0, 0.5, 0.01, 2,
                       "A bloc outside the poles 'holds the balance' when its Power is at least the gap between "
                       "the two strongest poles (it could tip either way) and it holds at least this share of all Power."),
    "sphere_share": ("Share that makes a sphere", 0.3, 0.95, 0.05, 2,
                     "A Region lies in a pole's sphere of influence when that pole's bloc supplies at least this share "
                     "of all the Power that can reach it (each Group's Power x decay^steps). Guarantees follow "
                     "spheres: a pole defends unaligned Groups in its sphere and stays out of Wars in a rival's."),
    "alarm": ("Hegemony alarm", 0.2, 0.9, 0.01, 2,
              "Share of all Power held by one bloc that brings Offshore balancers in against it."),
    "reliability": ("Alliance reliability", 0.0, 1.0, 0.05, 2,
                    "Chance that each ally honours its commitment to defend an attacked member."),
    "offensive_help": ("Help in attack", 0.0, 1.0, 0.05, 2,
                       "Chance that each ally joins a War its member starts."),
    "drift": ("Differential growth", 0.0, 0.3, 0.01, 2,
              "Each turn every Group's productivity (which scales the capacity of its Regions) takes a random "
              "step of this size. Uneven growth is what shifts the balance and brings power transitions."),
    "lead_share": ("Initiator's share of the attack", 0.0, 1.0, 0.05, 2,
                   "A Group only starts a War if it would bring at least this share of the attacking side's "
                   "expected marshaled Power itself - minor allies cannot start Wars on the strength of their patrons."),
    "guarantee": ("Guarantees", 0.0, 1.0, 0.05, 2,
                  "When a bloc attacks an unaligned Group, the leader of the strongest rival pole comes to its "
                  "defence with this probability (if it can reach the theatre) - poles deny each other easy gains."),
    "rebellion_rate": ("Rebellion propensity", 0.0, 2.0, 0.05, 2,
                       "Scales every occupied Region's chance of an uprising per round (its rebellion threat). "
                       "0 switches rebellions off."),
    "grievance_growth": ("Grievance growth", 0.0, 1.0, 0.01, 2,
                         "Grievance added each round in an occupied Region, raised by distance from the occupier's "
                         "homeland and by the people's own Group still existing nearby."),
    "harshness": ("Harshness of conquest", 0.0, 3.0, 0.05, 2,
                  "Grievance a Region starts with when it is conquered (integration starts again from 0)."),
    "weariness_rate": ("War weariness", 0.0, 10.0, 0.1, 1,
                       "Discontent at home from Power spent in War: each War adds weariness x the share of its Power "
                       "a Group lost - x1.5 for the Group that started it, x1 for allies who joined the attack, x0.25 "
                       "for defenders (who rally round the flag); a defeat adds 0.1 more, and profitable victories ease "
                       "it. A war-weary Group is less aggressive and mobilises less. 0 switches this off."),
    "weariness_recovery": ("Recovery from weariness", 0.0, 0.5, 0.01, 2,
                           "Share of war weariness that fades each round."),
    "upheaval_threshold": ("Weariness that risks upheaval", 0.2, 5.0, 0.1, 1,
                           "Above this weariness a Group risks upheaval at home each round: it loses 15% of its Power, "
                           "a cautious government takes over (aggression falls by 40%), and as a follower with little "
                           "attachment to its alliance it may walk out."),
    "sea_cost": ("Sea crossing cost", 1.0, 4.0, 0.1, 1,
                 "A step along a sea lane counts as this many Regions of distance for a War (force decays per step)."),
    "violation_reluctance": ("Reluctance to violate", 0.0, 10.0, 0.5, 1,
                             "When choosing a route to a War, each third party's territory crossed counts as this many "
                             "extra steps - Groups go round a neutral if they reasonably can."),
    "violation_resistance": ("Resistance to violation", 0.0, 1.0, 0.05, 2,
                             "Chance that a Group whose territory an attacker marches through joins the defence. Its "
                             "alliance leader, or the pole whose sphere it lies in, may follow (with alliance "
                             "reliability or the guarantee chance). The violator's conduct suffers."),
    "air_range": ("Air range", 0.0, 2.0, 0.05, 2,
                  "Air power: any two Regions this far apart or closer on the map (in map heights) are joined by an "
                  "air link, so a War can reach over the ground between. 0 = no air power."),
    "air_cost": ("Air step cost", 0.5, 5.0, 0.1, 1,
                 "An air link counts as this many Regions of distance (force decays per step)."),
    "airspace_respect": ("Respect for neutral airspace", 0.0, 1.0, 0.05, 2,
                         "Flying over a third party's Region violates its airspace, weighted by this (0 = no one "
                         "minds, 1 = as grave as marching through): it scales the reluctance to overfly, the chance "
                         "the overflown Group resists, and the harm to the violator's conduct. Landing in a third "
                         "party's Region is always a full violation."),
    "conduct_memory": ("Conduct memory", 0.5, 0.995, 0.005, 3,
                       "Each Group's conduct (-1 to +1) is a reputation built from what it does: starting Wars "
                       "(worse when bullying the weak or unaligned), joining attacks, conquering, crushing uprisings, "
                       "deserting an attacked ally and dominating its bloc lower it; defending allies and guaranteed "
                       "Groups, conceding to peaceful protest and each round at peace raise it. Each round it keeps "
                       "this share and drifts the rest of the way toward its disposition (0.5 - aggression)."),
    "unpredictability": ("Unpredictability", 0.0, 1.5, 0.05, 2,
                         "Random swing added to conduct each round when it decides whether integration and cohesion "
                         "grow or erode - good conduct does not always pay, bad conduct does not always fail."),
    "crisis_rate": ("Crisis rate", 0.0, 0.5, 0.01, 2,
                    "Chance per round of a crisis, scaled by (1 - conduct)/2 of the Groups involved: in an alliance "
                    "it halves every member's cohesion; in an occupied Region it halves integration and adds grievance."),
    "nonviolence": ("Nonviolence", 0.0, 1.0, 0.05, 2,
                    "How readily discontent takes a peaceful form. A peaceful uprising in an occupied Region is a "
                    "protest that wins concessions (the occupier's benevolence rises, grievance eases) without "
                    "fighting; a peaceful upheaval at home changes the government's strategy to a less warlike one. "
                    "Neither costs anyone Power. Armed uprisings and violent upheavals do. 0 = always violent."),
    "grievance_memory": ("Grievance memory", 0.5, 0.99, 0.01, 2,
                         "Share of an occupied Region's grievance that carries over to the next round. Higher = "
                         "resentment of occupation builds higher and lasts longer."),
    "fervour": ("Fervour of the reborn", 0.0, 5.0, 0.1, 1,
                "A Group reborn by an uprising defends with (1 + fervour) times its usual force, fading to nothing "
                "over the fervour period - nationalist zeal. For that period the Groups that backed its uprising "
                "may also come to its defence (with alliance reliability)."),
    "fervour_rounds": ("Fervour period (rounds)", 1, 100, 1, 0,
                       "How many rounds a reborn Group's fervour, and its backers' protection, last."),
    "integration_rate": ("Integration rate", 0.0, 0.3, 0.005, 3,
                         "How fast an occupied Region's integration with its occupier changes each round, times the "
                         "occupier's conduct (plus unpredictability): good conduct builds it, bad conduct erodes it. "
                         "Faster near the occupier's homeland, at low grievance and under a benevolent occupier; slower "
                         "while the people's own Group survives. Grievance grows only by (1 - integration) of its usual "
                         "amount; at full integration the Region is assimilated."),
    "care_cost": ("Cost of benevolence", 0.0, 0.1, 0.001, 3,
                  "Power an occupier pays each round per unit of occupied Region value at benevolence 1 "
                  "(scaled by its benevolence)."),
    "cohesion_rate": ("Cohesion rate", 0.0, 0.3, 0.005, 3,
                      "How fast an alliance member's cohesion changes each round, times the mean conduct of the "
                      "member and its leader (plus unpredictability): good conduct builds it, bad conduct erodes it. "
                      "A shared threat (a rival pole within reach) adds to it. Being defended by allies raises it; "
                      "allies failing to turn up, or being dragged into Wars it did not start, wear it down. "
                      "Resentment grows only by (1 - cohesion) of its usual amount."),
    "garrison": ("Garrison strength", 0.0, 1.0, 0.01, 2,
                 "Share of the occupier's Power that holds down an occupied Region, decayed by the distance from "
                 "the occupier's homeland (its own people's Regions)."),
    "upkeep": ("Upkeep of occupation", 0.0, 0.2, 0.005, 3,
               "Power an occupier loses each round per occupied Region: upkeep x grievance x Region value "
               "(imperial overstretch)."),
    "sponsorship": ("Rebel sponsorship", 0.0, 1.0, 0.05, 2,
                    "Chance that a rival pole, or a Threat balancer threatened by the occupier, backs an uprising "
                    "(it pays part of what it sends). The people's own Group, if it still exists, always helps."),
    "follower_resentment": ("Follower resentment", 0.0, 1.0, 0.01, 2,
                            "Resentment a follower builds each round in a bloc its leader dominates; resentful "
                            "followers break away to independence or to the rival pole. 0 switches this off."),
    "resentment_threshold": ("Dominance that breeds resentment", 0.3, 0.95, 0.05, 2,
                             "Followers start to resent their leader once it holds more than this share of the bloc's Power."),
    "inertia": ("Diplomatic inertia", 0.0, 1.0, 0.05, 2,
                "Chance per turn that a Group does not reconsider its alignment (Groups attacked last turn always reconsider)."),
}


# --------------------------------------------------------------------------
# Entities
# --------------------------------------------------------------------------

# Eras of warfare: presets for how Wars travel (the link costs of passage).
ERAS = {
    "Pre-modern (march and row)": dict(sea_cost=2.5, air_range=0.0),
    "Age of sail": dict(sea_cost=1.2, air_range=0.0),
    "Industrial (rail and steam)": dict(sea_cost=1.5, air_range=0.0),
    "Air age": dict(sea_cost=1.3, air_range=0.3, air_cost=1.5, airspace_respect=0.6),
    "Missile age": dict(sea_cost=1.2, air_range=0.8, air_cost=1.2, airspace_respect=0.3),
}


def era_of(settings):
    for name, vals in ERAS.items():
        if all(abs(getattr(settings, k) - v) < 1e-9 for k, v in vals.items()) and (
                vals.get("air_range", 0) > 0 or settings.air_range == 0):
            return name
    return "Custom"


@dataclass
class Region:
    id: str
    name: str
    x: float
    y: float
    value: float = 10.0
    links: list = field(default_factory=list)
    owner: str | None = None
    people: str | None = None       # the Group whose people live here
    grievance: float = 0.0
    held_since: int = 0             # round the current holder took it
    integration: float = 0.0        # 0..1, with the current occupier


@dataclass
class Group:
    id: str
    name: str
    colour: str
    power: float
    strategy: str = "Balancer"
    growth: float = 0.08
    mobilisation: float = 0.5
    aggression: float = 0.3
    alliance: str | None = None
    alive: bool = True
    productivity: float = 1.0
    short: str = ""
    attacked: bool = False      # attacked during the last turn
    resentment: float = 0.0
    cohesion: float = 0.0       # 0..1, attachment to its current alliance
    benevolence: float = 0.3    # 0..1, how well it treats occupied Regions
    weariness: float = 0.0      # war weariness at home
    conduct: float = 0.0        # -1..+1 reputation: aggressive/self-interested <-> diplomatic/common-interested
    fought: bool = False        # took part in a War or armed uprising this round
    reborn: int = -1            # round of rebirth after a successful uprising
    protectors: list = field(default_factory=list)   # Groups that backed its rebirth
    spurned: dict = field(default_factory=dict)   # bloc key or leader -> round until which it will not join


@dataclass
class Alliance:
    id: str
    name: str
    leader: str
    members: list
    founded: int
    colour: str = "#888888"
    namesake: str | None = None     # the member its name comes from (None for scenario-named alliances)


# --------------------------------------------------------------------------
# World
# --------------------------------------------------------------------------

def _normalise_links(regions: dict) -> None:
    for r in regions.values():
        for o in list(r.links):
            if o in regions and r.id not in regions[o].links:
                regions[o].links.append(r.id)
        r.links = [o for o in dict.fromkeys(r.links) if o in regions and o != r.id]


_LAND_CACHE = {}


def land_pairs(scenario):
    """Pairs of Region ids whose cells share a land border on the scenario's map; every other link is a sea lane."""
    m = scenario.get("map", {}) or {}
    regs = scenario["regions"]
    aspect, radius, seed = float(m.get("aspect", 1.5)), float(m.get("land_radius", 0.08)), int(m.get("seed", 7))
    key = (tuple((r["id"], round(float(r["x"]), 5), round(float(r["y"]), 5)) for r in regs), aspect, radius, seed)
    if key not in _LAND_CACHE:
        from . import geo
        W, H, idx = geo.raster([(float(r["x"]), float(r["y"])) for r in regs], aspect, radius, 640, seed)
        ids = [r["id"] for r in regs]
        _LAND_CACHE[key] = frozenset(frozenset((ids[a], ids[b])) for a, b in geo.touching(W, H, idx))
    return _LAND_CACHE[key]


def _all_pairs(regions: dict) -> dict:
    dist = {}
    for src in regions:
        d = {src: 0}
        q = deque([src])
        while q:
            u = q.popleft()
            for v in regions[u].links:
                if v not in d:
                    d[v] = d[u] + 1
                    q.append(v)
        dist[src] = d
    return dist


def auto_zones(regions: dict, k=None):
    """Split the map into k geographic zones (k-means on Region positions), named by compass direction."""
    ids = list(regions)
    n = len(ids)
    k = k or max(2, min(6, round(n / 9)))
    pts = [(regions[r].x, regions[r].y) for r in ids]
    # deterministic farthest-point initialisation
    cent = [min(pts, key=lambda p: p[0] + p[1])]
    while len(cent) < k:
        cent.append(max(pts, key=lambda p: min((p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 for c in cent)))
    for _ in range(30):
        lab = [min(range(k), key=lambda j: (p[0] - cent[j][0]) ** 2 + (p[1] - cent[j][1]) ** 2) for p in pts]
        new = []
        for j in range(k):
            mem = [pts[i] for i in range(n) if lab[i] == j]
            new.append((sum(p[0] for p in mem) / len(mem), sum(p[1] for p in mem) / len(mem)) if mem else cent[j])
        if new == cent:
            break
        cent = new

    def compass(x, y):
        ns = "North" if y < 0.38 else ("South" if y > 0.62 else "")
        ew = "west" if x < 0.38 else ("east" if x > 0.62 else "")
        if ns and ew:
            return f"{ns}-{ew}"
        if ns:
            return ns
        return {"west": "West", "east": "East"}.get(ew, "Centre")
    zones, used = [], {}
    for j in range(k):
        mem = [ids[i] for i in range(n) if lab[i] == j]
        if not mem:
            continue
        name = compass(*cent[j])
        used[name] = used.get(name, 0) + 1
        zones.append(dict(name=name if used[name] == 1 else f"{name} {used[name]}", regions=mem))
    return zones


class World:
    def __init__(self, scenario: dict, settings: Settings | None = None):
        self.scenario = copy.deepcopy(scenario)
        self.settings = settings or Settings.from_dict(scenario.get("settings"))
        s = self.settings
        self.rng = random.Random(s.seed)
        self._owned = None
        self._viol = {}
        self.regions: dict[str, Region] = {}
        for r in scenario["regions"]:
            self.regions[r["id"]] = Region(r["id"], r.get("name", r["id"]), float(r["x"]), float(r["y"]),
                                           float(r.get("value", 10)), list(r.get("links", [])))
        _normalise_links(self.regions)
        self.dist = _all_pairs(self.regions)
        self.land = land_pairs(scenario)
        self.aspect = float((scenario.get("map") or {}).get("aspect", 1.5))
        lengths = [math.hypot((r.x - self.regions[o].x) * self.aspect, r.y - self.regions[o].y)
                   for r in self.regions.values() for o in r.links]
        self.cell = (sum(lengths) / len(lengths)) if lengths else 0.1     # typical distance between neighbours
        self._routes = {}
        self._wr = {}
        self._edges = {}
        self.groups: dict[str, Group] = {}
        for g in scenario["groups"]:
            strat = g.get("strategy", "Balancer")
            if strat not in STRATEGIES:
                strat = "Balancer"
            d = STRATEGIES[strat]
            grp = Group(g["id"], g.get("name", g["id"]), g.get("colour", "#888888"), float(g.get("power", 10)),
                        strat, float(g.get("growth", 0.08)),
                        float(g.get("mobilisation", d["mobilisation"])),
                        float(g.get("aggression", d["aggression"])))
            grp.short = g.get("short", "")
            grp.benevolence = min(1.0, max(0.0, float(g.get("benevolence", 0.3))))
            grp.cohesion = min(1.0, max(0.0, float(g.get("cohesion", 0.0))))
            grp.weariness = max(0.0, float(g.get("weariness", 0.0)))
            grp.conduct = float(g.get("conduct", self.disposition(grp)))
            self.groups[grp.id] = grp
            for rid in g.get("regions", []):
                if rid in self.regions:
                    self.regions[rid].owner = grp.id
        self.alliances: dict[str, Alliance] = {}
        self._next_aid = 1
        self.turn = 0
        for a in scenario.get("alliances", []):
            members = [m for m in a.get("members", []) if m in self.groups]
            if len(members) >= 2:
                al = self._new_alliance(a.get("leader", members[0]), members, a.get("name"))
                for m in members:
                    self.groups[m].alliance = al.id
        for r0 in scenario["regions"]:
            reg = self.regions[r0["id"]]
            reg.people = r0.get("people", reg.owner)
            if reg.people not in self.groups:
                reg.people = reg.owner
            reg.grievance = float(r0.get("grievance", 0.0)) if reg.people != reg.owner else 0.0
            reg.held_since = int(r0.get("held_since", 0))
            reg.integration = float(r0.get("integration", 0.0)) if reg.people != reg.owner else 0.0
        for g in self.groups.values():
            if not self.regions_of(g.id):
                g.alive = False
                g.power = 0.0
        self.round_log = dict(uprisings=[], breakaways=[])
        self.stats = {gid: dict(started=0, won=0, lost=0, gained=0, ceded=0) for gid in self.groups}
        self.zones = [dict(name=z["name"], regions=[r for r in z["regions"] if r in self.regions])
                      for z in scenario.get("zones", [])] or auto_zones(self.regions)
        self.zones = [z for z in self.zones if z["regions"]]
        self.history: list[dict] = []
        self._sph = {}
        self._update_leaders()
        self._record([], ["The world as the scenario sets it."])

    # ---- queries ---------------------------------------------------------
    def alive(self):
        return [g for g in self.groups.values() if g.alive]

    def regions_of(self, gid):
        if self._owned is None:
            own = {}
            for r in self.regions.values():
                if r.owner:
                    own.setdefault(r.owner, []).append(r.id)
            self._owned = own
        return self._owned.get(gid, [])

    def capacity(self, gid):
        return sum(self.regions[r].value for r in self.regions_of(gid)) * self.groups[gid].productivity

    def total_power(self):
        return sum(g.power for g in self.alive()) or 1.0

    def hops_to_region(self, gid, rid):
        best = INF
        for r in self.regions_of(gid):
            best = min(best, self.dist[r].get(rid, INF))
        return best

    def hops(self, a, b):
        best = INF
        rb = self.regions_of(b)
        for r in self.regions_of(a):
            d = self.dist[r]
            for o in rb:
                best = min(best, d.get(o, INF))
        return best

    def reach_factor(self, hops):
        return 0.0 if hops >= INF else self.settings.decay ** hops

    def bloc_key(self, gid):
        g = self.groups[gid]
        return g.alliance or gid

    def blocs(self, exclude=None):
        """[(key, [members], power)] strongest first; 'exclude' leaves one Group out entirely."""
        out = {}
        for g in self.alive():
            if g.id == exclude:
                continue
            out.setdefault(g.alliance or g.id, []).append(g.id)
        res = [(k, m, sum(self.groups[x].power for x in m)) for k, m in out.items()]
        res.sort(key=lambda t: -t[2])
        return res

    def bloc_name(self, key):
        if key in self.alliances:
            return self.alliances[key].name
        return self.groups[key].name if key in self.groups else key

    # ---- alliances -------------------------------------------------------
    def _new_alliance(self, leader, members, name=None):
        aid = f"A{self._next_aid}"
        self._next_aid += 1
        lg = self.groups[leader]
        al = Alliance(aid, name or self._free_name(f"{lg.name} bloc"), leader, list(members), self.turn, lg.colour,
                      None if name else leader)
        self.alliances[aid] = al
        if hasattr(self, "_wr"):
            self._clear_routes()
        return al

    def _free_name(self, base, skip=None):
        """base, unless a current alliance already carries it."""
        taken = {a.name for a in self.alliances.values() if a.id != skip}
        name, n = base, 2
        while name in taken:
            name = f"{base} ({n})"
            n += 1
        return name

    def _leave(self, gid, events):
        g = self.groups[gid]
        aid = g.alliance
        if not aid:
            return
        al = self.alliances[aid]
        al.members.remove(gid)
        g.alliance = None
        self._clear_routes()
        g.cohesion = 0.0
        events.append(f"{g.name} leaves the {al.name}.")
        if len(al.members) < 2:
            for m in al.members:
                self.groups[m].alliance = None
            events.append(f"The {al.name} dissolves.")
            del self.alliances[aid]
        else:
            if al.leader == gid:
                al.leader = max(al.members, key=lambda m: self.groups[m].power)
            if al.namesake == gid:
                # the bloc no longer contains the Group it is named after: it takes its leader's name
                old = al.name
                al.namesake = al.leader
                al.name = self._free_name(f"{self.groups[al.leader].name} bloc", skip=al.id)
                events.append(f"Without {g.name}, the {old} is renamed the {al.name}.")

    def _join(self, gid, key, events, why):
        """Join bloc 'key' (an alliance id, or an unaligned Group, which then leads a new alliance)."""
        g = self.groups[gid]
        if key == g.alliance or key == gid:
            return False
        lead_of_target = self.alliances[key].leader if key in self.alliances else key
        if g.spurned.get(key, -1) >= self.turn or g.spurned.get(lead_of_target, -1) >= self.turn:
            return False
        if key in self.alliances:
            al = self.alliances[key]
        else:
            h = self.groups.get(key)
            if h is None or not h.alive or h.strategy == "Neutral" or h.alliance:
                return False
            if h.strategy == "Offshore balancer" and self._alarm_bloc() is None:
                return False
            self._leave(gid, events)
            al = self._new_alliance(h.id, [h.id], None)
            h.alliance = al.id
            events.append(f"{h.name} becomes the head of a new alliance, the {al.name}.")
        self._leave(gid, events)
        al.members.append(gid)
        g.cohesion = 0.0
        self._clear_routes()
        g.alliance = al.id
        events.append(f"{g.name} joins the {al.name} ({why}).")
        return True

    def _update_leaders(self):
        for al in self.alliances.values():
            al.leader = max(al.members, key=lambda m: self.groups[m].power)

    def _alarm_bloc(self):
        T = self.total_power()
        b = self.blocs()
        if b and b[0][2] / T >= self.settings.alarm:
            return b[0][0]
        return None

    # ---- diplomacy --------------------------------------------------------
    def _threats(self, gid):
        """{bloc key: Power bearing on gid weighted by aggression}, gid's own bloc excluded."""
        own = self.bloc_key(gid)
        out = {}
        for h in self.alive():
            if h.id == gid:
                continue
            k = h.alliance or h.id
            if k == own:
                continue
            w = h.power * self.reach_factor(self.hops(h.id, gid)) * (0.5 + h.aggression)
            out[k] = out.get(k, 0.0) + w
        return out

    def _projected(self, gid):
        """{bloc key: Power of that bloc as it would arrive at gid's Regions} (gid excluded)."""
        out = {}
        for h in self.alive():
            if h.id == gid:
                continue
            k = h.alliance or h.id
            out[k] = out.get(k, 0.0) + h.power * self.reach_factor(self.hops(h.id, gid))
        return out

    def _decide(self, g, events):
        s = self.settings
        strat = g.strategy
        T = self.total_power()
        p = g.power
        blocs = self.blocs(exclude=g.id)
        if not blocs:
            return
        own = g.alliance

        if strat == "Neutral":
            if own:
                self._leave(g.id, events)
            return

        if strat == "Expansionist":
            threats = self._projected(g.id)
            worst = max(threats.items(), key=lambda kv: kv[1], default=(None, 0))
            if worst[1] > 2 * p:
                strat = "Threat balancer"
            else:
                return

        if strat == "Pole":
            if own:
                al = self.alliances[own]
                if al.leader != g.id and p >= 0.8 * self.groups[al.leader].power:
                    self._leave(g.id, events)
                    events.append(f"{g.name} strikes out on its own as a rival pole.")
            return

        if strat == "Balancer":
            top_key, _, top_p = blocs[0]
            if own and own == top_key:
                if (top_p + p) / T > 0.5:
                    self._leave(g.id, events)
                return
            if own:
                return
            if len(blocs) < 2:
                return
            second_key, _, second_p = blocs[1]
            if p >= second_p:
                return
            self._join(g.id, second_key, events, f"balancing against the {self.bloc_name(top_key)}")
            return

        if strat == "Offshore balancer":
            top_key, _, top_p = blocs[0]
            share = (top_p + (p if own == top_key else 0)) / T
            if share >= s.alarm:
                if own == top_key:
                    self._leave(g.id, events)
                    events.append(f"{g.name} turns against its former partners, now too strong.")
                    return
                if own:
                    return
                if len(blocs) >= 2:
                    self._join(g.id, blocs[1][0], events,
                               f"to stop the {self.bloc_name(top_key)} holding {share:.0%} of all Power")
            elif own and share < s.alarm * 0.8:
                self._leave(g.id, events)
                events.append(f"{g.name} returns to splendid isolation.")
            return

        if strat == "Threat balancer":
            threats = self._threats(g.id)
            if not threats:
                return
            tkey, tval = max(threats.items(), key=lambda kv: kv[1])
            if tval < 0.5 * p:
                return
            if own and own != tkey:
                return
            if own == tkey:
                return
            cands = [b for b in blocs if b[0] != tkey and b[0] != own and b[2] > 0.5 * p]
            # prefer partners that can actually reach the threat
            cands.sort(key=lambda b: -b[2])
            for key, _, _ in cands:
                if self._join(g.id, key, events, f"against the threat from the {self.bloc_name(tkey)}"):
                    return
            return

        if strat == "Bandwagoner":
            proj = self._projected(g.id)
            if not proj:
                return
            key, val = max(proj.items(), key=lambda kv: kv[1])
            if key == own:
                return
            own_val = proj.get(own, 0.0) if own else 0.0
            if val < 1.5 * p or (own and val < 1.25 * own_val):
                return
            self._join(g.id, key, events, "bandwagoning with the strongest")
            return

    def _diplomacy(self, events):
        s = self.settings
        order = self.alive()
        self.rng.shuffle(order)
        for g in order:
            if not g.alive:
                continue
            if not g.attacked and self.rng.random() < s.inertia:
                continue
            self._decide(g, events)
        self._update_leaders()

    # ---- war --------------------------------------------------------------
    @staticmethod
    def disposition(g):
        """The conduct a Group drifts toward when nothing happens: peaceable Groups high, aggressive ones low."""
        return max(-1.0, min(1.0, 0.5 - g.aggression))

    def _act(self, gid, delta):
        g = self.groups[gid]
        g.conduct = max(-1.0, min(1.0, g.conduct + delta))

    def _swing(self):
        return self.rng.gauss(0, self.settings.unpredictability) if self.settings.unpredictability > 0 else 0.0

    def _conduct_drift(self):
        s = self.settings
        for g in self.alive():
            g.conduct = g.conduct * s.conduct_memory + (1 - s.conduct_memory) * self.disposition(g)
            if not g.fought:
                g.conduct = min(1.0, g.conduct + 0.01)          # a round at peace
        for al in self.alliances.values():
            bloc = sum(self.groups[m].power for m in al.members) or 1
            if self.groups[al.leader].power / bloc > s.resentment_threshold:
                self._act(al.leader, -0.01)                      # dominating its bloc
        for g in self.groups.values():
            g.fought = False

    def fervour(self, gid):
        g = self.groups[gid]
        s = self.settings
        if g.reborn < 0 or s.fervour <= 0:
            return 0.0
        left = 1 - (self.turn - g.reborn) / max(1, s.fervour_rounds)
        return s.fervour * left if left > 0 else 0.0

    # ---- passage: routes to a War --------------------------------------------
    def is_sea(self, a, b):
        return frozenset((a, b)) not in self.land

    def _clear_routes(self):
        self._routes.clear()
        self._wr.clear()

    def _edge_list(self, u):
        """[(v, step cost, Regions flown over)] - land and sea links, plus air links when there is air power."""
        s = self.settings
        key = (s.sea_cost, s.air_range, s.air_cost)
        if self._edges.get("__key__") != key:
            self._edges = {"__key__": key}
        e = self._edges.get(u)
        if e is None:
            e = [(v, s.sea_cost if self.is_sea(u, v) else 1.0, ()) for v in self.regions[u].links]
            if s.air_range > 0:
                for v, over in self._air_links(u):
                    e.append((v, s.air_cost, over))
            self._edges[u] = e
        return e

    def _air_links(self, u):
        """Regions within air range of u that are not already its neighbours, with the Regions flown over."""
        s = self.settings
        a = self.aspect
        ux, uy = self.regions[u].x * a, self.regions[u].y
        out = []
        for v, rv in self.regions.items():
            if v == u or v in self.regions[u].links:
                continue
            vx, vy = rv.x * a, rv.y
            d = math.hypot(vx - ux, vy - uy)
            if d > s.air_range or d == 0:
                continue
            over = []
            for w, rw in self.regions.items():
                if w in (u, v):
                    continue
                wx, wy = rw.x * a, rw.y
                t = max(0.0, min(1.0, ((wx - ux) * (vx - ux) + (wy - uy) * (vy - uy)) / (d * d)))
                if math.hypot(ux + t * (vx - ux) - wx, uy + t * (vy - uy) - wy) < self.cell * 0.45:
                    over.append(w)
            out.append((v, tuple(over)))
        return out

    def is_air(self, a, b):
        return b not in self.regions[a].links

    def routes(self, gid, hostile):
        """Cheapest routes from gid's Regions to every Region, for a War against bloc 'hostile'.

        Own and allied Regions (and unheld ones) are crossed freely; a third party's Region is crossed at the
        price of violating its territory (counted as extra steps when choosing); the hostile bloc's Regions can be
        reached but not crossed.  Returns {rid: (priority, steps, violated owners, previous Region)}."""
        key = (gid, hostile)
        if key in self._routes:
            return self._routes[key]
        s = self.settings
        own = self.bloc_key(gid)
        best, heap, done = {}, [], set()
        for r in self.regions_of(gid):
            best[r] = (0.0, 0.0, (), None)
            heapq.heappush(heap, (0.0, 0.0, r))
        while heap:
            prio, steps, u = heapq.heappop(heap)
            if u in done:
                continue
            done.add(u)
            ou = self.regions[u].owner
            if ou and best[u][3] is not None and self.bloc_key(ou) == hostile:
                continue                       # enemy ground: the march ends here
            for v, step, over in self._edge_list(u):
                if v in done:
                    continue
                viol, pen = best[u][2], 0.0
                seen = {o for o, _ in viol}
                for w in over:                          # airspace flown over
                    ow = self.regions[w].owner
                    if ow and ow != gid and ow not in seen:
                        kw = self.bloc_key(ow)
                        if kw != own and kw != hostile and s.airspace_respect > 0:
                            viol = viol + ((ow, s.airspace_respect),)
                            seen.add(ow)
                            pen += s.violation_reluctance * s.airspace_respect
                ov = self.regions[v].owner
                if ov and ov != gid:
                    kv = self.bloc_key(ov)
                    if kv != own and kv != hostile:
                        if ov in seen:                  # upgrade an overflight to a full violation
                            viol = tuple((o, 1.0) if o == ov else (o, wgt) for o, wgt in viol)
                            pen += s.violation_reluctance * (1 - dict(viol).get(ov, 1.0))
                        else:
                            viol = viol + ((ov, 1.0),)
                            pen += s.violation_reluctance
                np_, ns = prio + step + pen, steps + step
                if v not in best or np_ < best[v][0]:
                    best[v] = (np_, ns, viol, u)
                    heapq.heappush(heap, (np_, ns, v))
        self._routes[key] = best
        return best

    def war_route(self, gid, rid, hostile):
        """(steps, violated owners, path of Region ids) for gid's march to rid; steps = INF if no way through."""
        if not self.settings.passage:
            h = self.hops_to_region(gid, rid)
            return h, (), None
        key = (gid, rid, hostile)
        hit = self._wr.get(key)
        if hit is not None:
            return hit
        best = self.routes(gid, hostile)
        if rid not in best:
            out = (INF, (), None)
        else:
            _, steps, viol, _ = best[rid]
            path, cur = [], rid
            while cur is not None:
                path.append(cur)
                cur = best[cur][3]
            out = (steps, viol, path[::-1])
        self._wr[key] = out
        return out

    def war_force(self, gid, rid, hostile):
        g = self.groups[gid]
        steps = self.war_route(gid, rid, hostile)[0]
        if steps >= INF:
            return 0.0
        return g.power * self.eff_mobilisation(g) * self.settings.decay ** steps

    def war_defence(self, gid, rid, hostile):
        return self.war_force(gid, rid, hostile) * self.settings.defence_bonus * (1 + self.fervour(gid))

    def defence_force(self, gid, theatre):
        return self.force(gid, theatre) * self.settings.defence_bonus * (1 + self.fervour(gid))

    def eff_mobilisation(self, g):
        return g.mobilisation * (1 - 0.5 * g.weariness / (1 + g.weariness))

    def eff_aggression(self, g):
        return g.aggression * (1 - g.weariness / (1 + g.weariness))

    def force(self, gid, theatre):
        g = self.groups[gid]
        return g.power * self.eff_mobilisation(g) * self.reach_factor(self.hops_to_region(gid, theatre))

    def _theatre(self, att, dfn):
        if self.settings.passage:
            R = self.routes(att, self.bloc_key(dfn))
            cands = [r for r in self.regions_of(dfn) if r in R]
            if not cands:
                return None
            cands.sort(key=lambda r: (R[r][0], self.regions[r].people != att, -self.regions[r].value))
            return cands[0]
        best, cands = INF, []
        for r in self.regions_of(dfn):
            h = self.hops_to_region(att, r)
            if h < best:
                best, cands = h, [r]
            elif h == best:
                cands.append(r)
        if not cands:
            return None
        cands.sort(key=lambda r: (self.regions[r].people != att, -self.regions[r].value))
        return cands[0]

    def _sides(self, att, dfn, engaged, theatre, draw):
        """Return (attackers, defenders) as lists of (gid, probability or 1/0)."""
        s = self.settings
        A, D = [(att, 1.0)], [(dfn, 1.0)]
        ga, gd = self.groups[att], self.groups[dfn]
        if ga.alliance:
            for m in self.alliances[ga.alliance].members:
                if m in (att, dfn) or m in engaged or self.groups[m].strategy == "Neutral":
                    continue
                A.append((m, s.offensive_help))
        if gd.alliance:
            for m in self.alliances[gd.alliance].members:
                if m in (att, dfn) or m in engaged:
                    continue
                D.append((m, s.reliability))
        # Unaligned offshore balancers come to the defence of the weaker side.
        top = self.blocs()
        top_key = top[0][0] if top else None
        # Guarantees: the pole whose sphere the defender lies in defends it; if the defender lies in no
        # sphere, the strongest rival pole may.  Nobody intervenes inside the attacker's own sphere.
        if not gd.alliance and s.guarantee > 0:
            T = self.total_power()
            akey = self.bloc_key(att)
            sph = self.group_sphere(dfn)
            guarantor = None
            if sph is None:
                for key, mem, pw in top:
                    if key not in (akey, dfn) and pw / T >= s.pole_share:
                        guarantor = key
                        break
            elif sph != akey:
                guarantor = sph
            if guarantor is not None:
                lead = self.alliances[guarantor].leader if guarantor in self.alliances else guarantor
                if (lead in self.groups and lead not in engaged and lead not in (att, dfn)
                        and self.groups[lead].strategy != "Neutral"
                        and self.war_route(lead, theatre, akey)[0] <= s.reach):
                    D.append((lead, s.guarantee))
        if self.fervour(dfn) > 0:
            have = {m for m, _ in D} | {m for m, _ in A}
            for m in gd.protectors:
                pg = self.groups.get(m)
                if (pg and pg.alive and m not in have and m not in engaged and m != att
                        and self.bloc_key(m) != self.bloc_key(att)
                        and self.war_route(m, theatre, self.bloc_key(att))[0] <= s.reach):
                    D.append((m, s.reliability))
        hk_a, hk_d = self.bloc_key(dfn), self.bloc_key(att)
        # Violations: third parties whose territory the attacking side marches through may resist, and their
        # alliance leader (or the pole whose sphere they lie in) may take it as a cause for War.
        viol = {}
        if draw:            # settle who actually marches before working out whose territory they cross
            A = [(m, 1.0) for m, pr in A if pr >= 1.0 or self.rng.random() < pr]
        if s.passage:
            for m, pr in A:
                for v, wgt in self.war_route(m, theatre, hk_a)[1]:
                    viol[v] = max(viol.get(v, 0.0), pr * wgt)
            have = {m for m, _ in D} | {m for m, _ in A}
            for v, pr in viol.items():
                gv = self.groups.get(v)
                if not gv or not gv.alive or v in engaged or v in have:
                    continue
                if s.violation_resistance > 0:
                    D.append((v, s.violation_resistance * pr))
                    have.add(v)
                if gv.alliance:
                    friend = self.alliances[gv.alliance].leader
                    chance = s.reliability
                else:
                    sp = self.group_sphere(v)
                    friend = (self.alliances[sp].leader if sp in self.alliances
                              else (sp if sp in self.groups else None)) if sp else None   # the sphere's alliance may have dissolved
                    chance = s.guarantee
                if (friend and friend in self.groups and self.groups[friend].alive and friend not in have and friend not in engaged and self.bloc_key(friend) != hk_d
                        and self.groups[friend].strategy != "Neutral"
                        and self.war_route(friend, theatre, hk_d)[0] <= s.reach):
                    D.append((friend, chance * pr))
                    have.add(friend)
        self._viol = viol
        fa = sum(pr * self.war_force(m, theatre, hk_a) for m, pr in A)
        fd = sum(pr * self.war_force(m, theatre, hk_d) for m, pr in D)
        for h in self.alive():
            if h.strategy != "Offshore balancer" or h.alliance or h.id in engaged or h.id in (att, dfn):
                continue
            if self.bloc_key(att) == top_key or fa > 1.5 * fd:
                D.append((h.id, s.reliability))
        if draw:
            A = [(m, 1.0) for m, pr in A if pr >= 1.0 or self.rng.random() < pr]
            D = [(m, 1.0) for m, pr in D if pr >= 1.0 or self.rng.random() < pr]
        return A, D

    def win_probability(self, fa, fd):
        k = self.settings.decisiveness
        if fa <= 0:
            return 0.0
        if fd <= 0:
            return 1.0
        if self.settings.deterministic:
            return 1.0 if fa > fd else 0.0
        return 1.0 / (1.0 + (fd / fa) ** k)

    def _war_phase(self, events):
        s = self.settings
        self._sph = self.spheres()
        wars = []
        engaged = set()
        order = self.alive()
        self.rng.shuffle(order)
        for g in order:
            aggr = self.eff_aggression(g)
            if not g.alive or g.id in engaged or g.strategy == "Neutral" or aggr <= 0:
                continue
            need = 0.5 + 0.35 * (1 - aggr)
            best = None
            for h in self.alive():
                if h.id == g.id or h.id in engaged:
                    continue
                if g.alliance and h.alliance == g.alliance:
                    continue
                if self.hops(g.id, h.id) > s.reach:
                    continue
                # Cheap bound first: every ally joining at full strength against the defender alone at home.
                fa_max = sum(self.groups[m].power * self.eff_mobilisation(self.groups[m])
                             for m in (self.alliances[g.alliance].members if g.alliance else [g.id]))
                fd_min = h.power * self.eff_mobilisation(h) * s.defence_bonus * (1 + self.fervour(h.id))
                if self.win_probability(fa_max, fd_min) < need:
                    continue
                theatre = self._theatre(g.id, h.id)
                if theatre is None:
                    continue
                hk_a, hk_d = self.bloc_key(h.id), self.bloc_key(g.id)
                if self.war_route(g.id, theatre, hk_a)[0] > s.reach:
                    continue
                A, D = self._sides(g.id, h.id, engaged, theatre, draw=False)
                fa = sum(pr * self.war_force(m, theatre, hk_a) for m, pr in A)
                fd = sum(pr * self.war_defence(m, theatre, hk_d) for m, pr in D)
                if fa <= 0 or self.war_force(g.id, theatre, hk_a) < s.lead_share * fa:
                    continue
                pw = self.win_probability(fa, fd)
                if pw < need:
                    continue
                score = pw * (1 + self.regions[theatre].value / 50)
                if self.regions[theatre].people == g.id:
                    score *= 1.5        # reclaiming its own people
                if best is None or score > best[0]:
                    best = (score, h.id, theatre)
            if best is None:
                continue
            if self.rng.random() >= min(1.0, s.war_rate * aggr):
                continue
            wars.append(self._fight(g.id, best[1], best[2], engaged, events))
        return wars

    def _fight(self, att, dfn, theatre, engaged, events):
        s = self.settings
        A, D = self._sides(att, dfn, engaged, theatre, draw=True)
        a_ids = [m for m, _ in A]
        d_ids = [m for m, _ in D]
        hk_a, hk_d = self.bloc_key(dfn), self.bloc_key(att)
        violated = sorted(v for v in self._viol
                          if any(v == o for m in a_ids for o, _ in self.war_route(m, theatre, hk_a)[1]))
        resisted = [v for v in violated if v in d_ids]
        _, _, route = self.war_route(att, theatre, hk_a)
        for m in a_ids:
            own_viol = self.war_route(m, theatre, hk_a)[1]
            if own_viol:                                         # violated others' territory or airspace
                self._act(m, -(0.1 if m == att else 0.05) * sum(wgt for _, wgt in own_viol))
        weights, crossers = {}, {}
        for m in a_ids:
            for v, wgt in self.war_route(m, theatre, hk_a)[1]:
                weights[v] = max(weights.get(v, 0.0), wgt)
                crossers.setdefault(v, []).append(m)
        gd0 = self.groups[dfn]
        ga0 = self.groups[att]
        eligible = []
        if gd0.alliance:
            eligible = [m for m in self.alliances[gd0.alliance].members if m not in (att, dfn) and m not in engaged]
            came = [m for m in eligible if m in d_ids]
            if came:
                gd0.cohesion = min(1.0, gd0.cohesion + 0.15 * (1 - gd0.cohesion))
            if len(came) < len(eligible):
                gd0.cohesion = max(0.0, gd0.cohesion - 0.1)
            for m in eligible:
                self._act(m, 0.1 if m in came else -0.15)       # honoured, or deserted, an attacked ally
        for m in d_ids[1:]:
            if m not in eligible:
                self._act(m, 0.1)                                # came to the defence of a Group it guarantees
        for m in a_ids[1:]:
            self._act(m, -0.05)                                  # joined an attack
            if ga0.alliance and self.groups[m].alliance == ga0.alliance:
                self.groups[m].cohesion = max(0.0, self.groups[m].cohesion - 0.05)
        bully = (not gd0.alliance) or gd0.power * 2 < ga0.power
        self._act(att, -0.15 - (0.1 if bully else 0.0))          # started a War (worse against the weak or alone)
        for m in a_ids + d_ids:
            self.groups[m].fought = True
        engaged.update(a_ids)
        engaged.update(d_ids)
        fa_each = {m: self.war_force(m, theatre, hk_a) for m in a_ids}
        fd_each = {m: self.war_defence(m, theatre, hk_d) for m in d_ids}
        fa, fd = sum(fa_each.values()), sum(fd_each.values())
        pw = self.win_probability(fa, fd)
        att_wins = self.rng.random() < pw if not s.deterministic else fa > fd
        win_ids, lose_ids = (a_ids, d_ids) if att_wins else (d_ids, a_ids)
        fw, fl = (fa, fd) if att_wins else (fd, fa)
        win_each = fa_each if att_wins else fd_each
        r = fw / fl if fl > 0 else 99.0
        loss_frac = s.severity * r / (1 + r)
        att_frac = s.attrition * s.severity / (1 + r)
        lost_total = 0.0
        losses = {}
        before = {m: self.groups[m].power for m in a_ids + d_ids}
        for m in lose_ids:
            g = self.groups[m]
            committed = g.power * self.eff_mobilisation(g)
            loss = committed * loss_frac
            g.power = max(0.5, g.power - loss)
            losses[m] = -loss
            lost_total += loss
            self.stats[m]["lost"] += 1
        for m in win_ids:
            g = self.groups[m]
            committed = g.power * self.eff_mobilisation(g)
            cost = committed * att_frac
            gain = s.spoils * lost_total * (win_each[m] / fw if fw > 0 else 0)
            g.power = max(0.5, g.power - cost + gain)
            losses[m] = gain - cost
            self.stats[m]["won"] += 1
        self.stats[att]["started"] += 1
        # war weariness at home
        if s.weariness_rate > 0:
            for m in a_ids + d_ids:
                g = self.groups[m]
                frac = (before[m] - g.power) / before[m] if before[m] > 0 else 0.0
                weight = 1.5 if m == att else (1.0 if m in a_ids else 0.25)
                if frac > 0:
                    g.weariness += s.weariness_rate * weight * frac
                    if m in lose_ids:
                        g.weariness += 0.1 * weight
                else:
                    g.weariness = max(0.0, g.weariness + s.weariness_rate * 0.5 * frac)   # spoils ease it
        ga, gd = self.groups[att], self.groups[dfn]
        for m in d_ids:
            self.groups[m].attacked = True

        def names(ids):
            return ", ".join(self.groups[m].name for m in ids)

        rname = self.regions[theatre].name
        a_txt = ga.name + (f" (with {names(a_ids[1:])})" if len(a_ids) > 1 else "")
        d_txt = gd.name + (f" (with {names(d_ids[1:])})" if len(d_ids) > 1 else "")
        verdict = "wins" if att_wins else "is repelled"
        events.append(f"WAR over {rname}: {a_txt} attacks {d_txt}. Marshaled {fa:.1f} v {fd:.1f} "
                      f"(P win {pw:.0%}); {ga.name} {verdict}. Losers lose {loss_frac:.0%} of the Power they "
                      f"marshaled, winners {att_frac:.0%}.")
        for v in violated:
            how = "territory" if weights.get(v, 1.0) >= 1.0 else "airspace"
            by = ", ".join(self.groups[m].name for m in crossers.get(v, [])) or "the attackers"
            events.append(f"  {by} cross{'es' if len(crossers.get(v, [])) == 1 else ''} {self.groups[v].name}'s {how} - "
                          + ("it resists and joins the defence." if v in resisted else "it lets them pass."))
        moved = None
        loser_main = dfn if att_wins else att
        need = s.conquest_ratio if len(self.regions_of(loser_main)) > 1 else max(s.conquest_ratio, s.last_region_ratio)
        if r >= need:
            # The winner that marshaled most takes the Region.
            taker = max(win_ids, key=lambda m: win_each[m])
            if att_wins and self.regions[theatre].owner == dfn:
                moved = (theatre, dfn, taker)
            elif not att_wins:
                # a decisive defence pushes into the attacker's nearest Region next to the taker
                cand = [x for x in self.regions_of(att) if self.hops_to_region(taker, x) <= 1]
                if cand:
                    cand.sort(key=lambda x: (self.dist[theatre].get(x, INF), -self.regions[x].value))
                    moved = (cand[0], att, taker)
        if moved:
            rid, frm, to = moved
            self._transfer(rid, to)
            self._act(to, -0.1)                                  # conquest
            self.stats[to]["gained"] += 1
            self.stats[frm]["ceded"] += 1
            events.append(f"  {self.groups[to].name} takes {self.regions[rid].name} from {self.groups[frm].name} "
                          f"(ratio {r:.1f}:1).")
            if not self.regions_of(frm):
                self._eliminate(frm, to, events)
        return dict(attacker=att, defender=dfn, theatre=theatre, attackers=a_ids, defenders=d_ids,
                    fa=fa, fd=fd, p=pw, attacker_won=att_wins, ratio=r, loss=loss_frac,
                    attrition=att_frac, moved=list(moved) if moved else None,
                    change={m: round(v, 3) for m, v in losses.items()},
                    route=route, violated=violated, resisted=resisted,
                    overflown=[v for v in violated if weights.get(v, 1.0) < 1.0],
                    crossers={v: crossers.get(v, []) for v in violated})

    def _transfer(self, rid, to):
        reg = self.regions[rid]
        reg.owner = to
        self._clear_routes()
        self._owned = None
        reg.held_since = self.turn
        reg.integration = 0.0
        if reg.people == to:
            reg.grievance = 0.0            # liberated (or reclaimed)
        else:
            reg.grievance += self.settings.harshness

    def _eliminate(self, gid, by, events):
        g = self.groups[gid]
        self._leave(gid, events)
        self.groups[by].power += g.power * self.settings.spoils
        g.power = 0.0
        g.alive = False
        g.resentment = 0.0
        if any(r.people == gid for r in self.regions.values()):
            events.append(f"  {g.name} has lost its last Region; its people are subjugated.")
        else:
            events.append(f"  {g.name} has lost its last Region and is gone.")

    # ---- unrest: grievance, uprisings, rebirth ------------------------------
    def occupied(self):
        return [r for r in self.regions.values() if r.owner and r.people and r.people != r.owner]

    def homeland_hops(self, gid, rid):
        """Steps from the occupier's homeland (its own people's Regions it holds) to a Region."""
        home = [x for x in self.regions_of(gid) if self.regions[x].people == gid]
        if not home:
            return 2
        return min(self.dist[x].get(rid, INF) for x in home)

    def garrison_force(self, rid):
        reg = self.regions[rid]
        occ = self.groups[reg.owner]
        return (occ.power * self.settings.garrison * (1 - 0.5 * occ.weariness / (1 + occ.weariness))
                * self.settings.decay ** min(self.homeland_hops(occ.id, rid), 12))

    def _sponsors(self, rid, top_threat):
        """[(gid, probability, force)] that may back an uprising in rid."""
        s = self.settings
        reg = self.regions[rid]
        occ_key = self.bloc_key(reg.owner)
        out = []
        seen = set()
        pg = self.groups.get(reg.people)
        if pg and pg.alive and pg.id != reg.owner and self.bloc_key(pg.id) != occ_key:
            h = self.hops_to_region(pg.id, rid)
            if h <= s.reach:
                out.append((pg.id, 1.0, pg.power * pg.mobilisation * 0.5 * s.decay ** h))
                seen.add(pg.id)
        if s.sponsorship > 0:
            T = self.total_power()
            for key, mem, pw in self.blocs():
                if key != occ_key and pw / T >= s.pole_share:
                    lead = self.alliances[key].leader if key in self.alliances else key
                    if lead not in seen and self.groups[lead].strategy != "Neutral":
                        h = self.hops_to_region(lead, rid)
                        if h <= s.reach:
                            lg = self.groups[lead]
                            out.append((lead, s.sponsorship, lg.power * lg.mobilisation * 0.3 * s.decay ** h))
                            seen.add(lead)
                    break
            for gid, tk in top_threat.items():
                if gid in seen or tk != occ_key or self.bloc_key(gid) == occ_key:
                    continue
                h = self.hops_to_region(gid, rid)
                if h <= s.reach:
                    g = self.groups[gid]
                    out.append((gid, s.sponsorship, g.power * g.mobilisation * 0.3 * s.decay ** h))
                    seen.add(gid)
        return out

    def rebel_base(self, rid):
        reg = self.regions[rid]
        return reg.grievance * reg.value * 0.5

    def rebellion_threat(self, rid, sponsors=None):
        """Chance of an uprising this round in an occupied Region."""
        s = self.settings
        reg = self.regions[rid]
        if s.rebellion_rate <= 0 or reg.grievance <= 0:
            return 0.0
        if sponsors is None:
            sponsors = self._sponsors(rid, self._top_threats())
        R = self.rebel_base(rid) + sum(p * f for _, p, f in sponsors)
        G = self.garrison_force(rid)
        k = s.decisiveness
        odds = 1.0 if G <= 0 else (R ** k / (R ** k + G ** k) if R > 0 else 0.0)
        return min(1.0, s.rebellion_rate * reg.grievance / (1 + reg.grievance) * odds)

    def _top_threats(self):
        out = {}
        for g in self.alive():
            if g.strategy == "Threat balancer":
                th = self._threats(g.id)
                if th:
                    out[g.id] = max(th.items(), key=lambda kv: kv[1])[0]
        return out

    def _unrest(self, events):
        s = self.settings
        uprisings = []
        occ = self.occupied()
        if not occ:
            return uprisings
        # grievance and upkeep
        for reg in occ:
            age = self.turn - reg.held_since
            dist = 1 - s.decay ** min(self.homeland_hops(reg.owner, reg.id), 12)
            pg = self.groups.get(reg.people)
            irr = 0.0
            if pg and pg.alive:
                irr = 1.0 if self.hops_to_region(pg.id, reg.id) <= 1 else 0.5
            o = self.groups[reg.owner]
            reg.grievance = reg.grievance * s.grievance_memory + s.grievance_growth * (1 + dist + irr) * (1 - reg.integration)
            # integration: calm, nearness to the homeland and benevolence build it; a surviving people's state slows it
            near = 0.5 + 0.5 * (1 - dist)
            calm = 1 / (1 + reg.grievance)
            pull = 1.0 if irr == 0 else (0.75 if irr < 1 else 0.5)
            m = o.conduct + self._swing()
            step = s.integration_rate * (0.5 + o.benevolence) * near * calm * pull * m
            reg.integration = max(0.0, min(1.0, reg.integration + step))
            if reg.integration > 0 and self.rng.random() < s.crisis_rate * (1 - o.conduct) / 2:
                reg.integration *= 0.5
                reg.grievance += 0.3
                events.append(f"INCIDENT in {reg.name}: {o.name}'s conduct (conduct {o.conduct:+.2f}) sets back "
                              f"integration to {reg.integration:.0%}.")
                self.round_log.setdefault("incidents", []).append(reg.id)
            if reg.integration >= 1.0:
                old = self.groups[reg.people].name if pg else "its people"
                reg.people = reg.owner
                reg.grievance = 0.0
                reg.integration = 0.0
                events.append(f"{reg.name} is integrated after {age} rounds: its {old} people now count as {o.name}.")
                continue
            o.power = max(0.5, o.power - s.upkeep * reg.grievance * reg.value - s.care_cost * o.benevolence * reg.value)
        if s.rebellion_rate <= 0:
            return uprisings
        top_threat = self._top_threats()
        for reg in list(self.occupied()):
            if not self.groups[reg.owner].alive:
                continue
            sp = self._sponsors(reg.id, top_threat)
            threat = self.rebellion_threat(reg.id, sp)
            if self.rng.random() >= threat:
                continue
            uprisings.append(self._uprising(reg.id, sp, threat, events))
        return uprisings

    def peaceful_chance(self, rid, sponsors=None):
        """Chance that an uprising in an occupied Region takes the form of a peaceful protest."""
        s = self.settings
        reg = self.regions[rid]
        occ = self.groups[reg.owner]
        if sponsors is None:
            sponsors = self._sponsors(rid, self._top_threats())
        base = self.rebel_base(rid)
        foreign = sum(p * f for g, p, f in sponsors if g != reg.people)
        total = base + sum(p * f for _, p, f in sponsors)
        armed = foreign / total if total > 0 else 0.0
        return max(0.0, min(0.95, s.nonviolence * (0.6 + occ.benevolence + reg.integration) * (1 - armed)))

    def _uprising(self, rid, sponsors, threat, events):
        s = self.settings
        reg = self.regions[rid]
        occ = self.groups[reg.owner]
        people = self.groups.get(reg.people)
        pname0 = people.name if people else "its"
        if self.rng.random() < self.peaceful_chance(rid, sponsors):
            b0 = occ.benevolence
            occ.benevolence = min(1.0, occ.benevolence + 0.15)
            self._act(occ.id, 0.1)                               # conceded to peaceful protest
            reg.grievance *= 0.6
            reg.integration = min(1.0, reg.integration + 0.05)
            events.append(f"PROTEST in {reg.name}: the {pname0} people rise peacefully against {occ.name}, which "
                          f"changes course and makes concessions (benevolence {b0:.2f} -> {occ.benevolence:.2f}). "
                          f"No Power is lost.")
            return dict(region=rid, people=reg.people, occupier=occ.id, rebels=0.0, garrison=0.0, p=0.0, won=False,
                        reborn=False, backers=[], threat=threat, peaceful=True)
        backers = [(g, f) for g, p, f in sponsors if p >= 1.0 or self.rng.random() < p]
        base = self.rebel_base(rid)
        R = (base + sum(f for _, f in backers)) * s.defence_bonus
        G = self.garrison_force(rid)
        pw = self.win_probability(R, G)
        won = self.rng.random() < pw if not s.deterministic else R > G
        fw, fl = (R, G) if won else (G, R)
        r = fw / fl if fl > 0 else 99.0
        for g, f in backers:
            bg = self.groups[g]
            bg.power = max(0.5, bg.power - f * 0.25)
        pname = people.name if people else "its people"
        who = f"{pname}" + (f" (backed by {', '.join(self.groups[g].name for g, _ in backers if g != reg.people)})"
                            if any(g != reg.people for g, _ in backers) else "")
        occ.fought = True
        for g2, _ in backers:
            self.groups[g2].fought = True
        reborn = False
        if won:
            loss = G * s.severity * r / (1 + r)
            occ.power = max(0.5, occ.power - loss)
            if people and not people.alive:
                people.alive = True
                aid = sum(f for g2, f in backers if g2 != people.id)
                people.power = max(1.0, base + 0.8 * reg.value + 0.5 * aid)
                people.protectors = [g2 for g2, _ in backers if g2 != people.id]
                people.alliance = None
                people.productivity = 1.0
                people.resentment = 0.0
                people.reborn = self.turn
                reborn = True
            self._transfer(rid, reg.people)
            self.stats[occ.id]["ceded"] += 1
            events.append(f"UPRISING in {reg.name}: {who} rise against {occ.name} ({R:.1f} v {G:.1f}, threat "
                          f"{threat:.0%}) and win; {reg.name} is free" + (f" - {pname} is reborn." if reborn else "."))
            if not self.regions_of(occ.id):
                self._eliminate(occ.id, reg.people, events)
        else:
            occ.power = max(0.5, occ.power - G * s.attrition * s.severity / (1 + r))
            self._act(occ.id, -0.05)                             # crushed an armed uprising
            reg.grievance *= 0.5
            reg.integration *= 0.5
            events.append(f"UPRISING in {reg.name}: {who} rise against {occ.name} ({R:.1f} v {G:.1f}, threat "
                          f"{threat:.0%}) and are crushed.")
        return dict(region=rid, people=reg.people, occupier=occ.id, rebels=R, garrison=G, p=pw, won=won,
                    reborn=reborn, backers=[g for g, _ in backers], threat=threat, peaceful=False)

    # ---- the home front: war weariness and upheaval -----------------------
    def _home_front(self, events):
        s = self.settings
        out = []
        for g in self.alive():
            g.weariness *= (1 - s.weariness_recovery)
            if g.weariness <= s.upheaval_threshold or s.weariness_rate <= 0:
                continue
            p = min(0.6, 0.5 * (g.weariness - s.upheaval_threshold) / s.upheaval_threshold)
            if self.rng.random() >= p:
                continue
            w0 = g.weariness
            p_peace = max(0.0, min(0.95, s.nonviolence * 1.4 * s.upheaval_threshold / w0))
            if self.rng.random() < p_peace:
                old = g.strategy
                g.strategy = DOVISH.get(old, old)
                g.aggression = min(g.aggression, STRATEGIES[g.strategy]["aggression"])
                g.weariness *= 0.3
                g.conduct = max(g.conduct, self.disposition(g))  # a new government, a fresh start
                change = (f"changes course from {old} to {g.strategy}" if g.strategy != old
                          else f"stays {old} but turns cautious")
                events.append(f"PROTEST at home in {g.name}: war-weary people (weariness {w0:.2f}) peacefully bring in "
                              f"a new government, which {change}. No Power is lost.")
                out.append(dict(group=g.id, weariness=w0, left=None, peaceful=True, old=old, new=g.strategy))
                continue
            g.power = max(0.5, g.power * 0.85)
            g.aggression = max(0.02, g.aggression * 0.6)
            g.weariness *= 0.3
            g.conduct = self.disposition(g)                      # a new regime starts from its disposition
            left = None
            if g.alliance and self.alliances[g.alliance].leader != g.id and g.cohesion < 0.5:
                left = self.alliances[g.alliance].name
                self._leave(g.id, events)
            events.append(f"UPHEAVAL in {g.name}: war-weary people (weariness {w0:.2f}) violently bring down its "
                          f"government; it loses 15% of its Power and turns cautious"
                          + (f", and walks out of the {left}." if left else "."))
            out.append(dict(group=g.id, weariness=w0, left=left, peaceful=False))
        return out

    # ---- restive followers ------------------------------------------------
    def _cohesion(self, events=None):
        s = self.settings
        if s.cohesion_rate <= 0 or not self.alliances:
            return
        T = self.total_power()
        blocs = self.blocs()
        for al in self.alliances.values():
            rivals = [k for k, mem, pw in blocs if k != al.id and pw / T >= s.pole_share]
            for m in al.members:
                g = self.groups[m]
                threat = 0.0
                for k in rivals:
                    lead = self.alliances[k].leader if k in self.alliances else k
                    if self.hops(m, lead) <= s.reach:
                        threat = 1.0
                        break
                if m == al.leader:
                    continue
                lead_c = self.groups[al.leader].conduct
                mood = (g.conduct + lead_c) / 2 + 0.3 * threat + self._swing()
                if mood >= 0:
                    g.cohesion = min(1.0, g.cohesion + s.cohesion_rate * mood * (1 - g.cohesion))
                else:
                    g.cohesion = max(0.0, g.cohesion + s.cohesion_rate * mood * g.cohesion * 2)
            mean_c = sum(self.groups[m].conduct for m in al.members) / len(al.members)
            if self.rng.random() < s.crisis_rate * (1 - mean_c) / 2:
                for m in al.members:
                    self.groups[m].cohesion *= 0.5
                worst = min(al.members, key=lambda m: self.groups[m].conduct)
                if events is not None:
                    events.append(f"CRISIS in the {al.name}: quarrels over {self.groups[worst].name}'s conduct "
                                  f"({self.groups[worst].conduct:+.2f}) halve its members' cohesion.")
                self.round_log.setdefault("crises", []).append(al.id)

    def _resentment(self, events):
        s = self.settings
        self._cohesion(events)
        out = []
        if s.follower_resentment <= 0:
            return out
        T = self.total_power()
        for al in list(self.alliances.values()):
            if al.id not in self.alliances:
                continue
            bloc = sum(self.groups[m].power for m in al.members)
            lead = self.groups[al.leader]
            dom = lead.power / bloc if bloc > 0 else 0
            for m in list(al.members):
                if m == al.leader or al.id not in self.alliances:
                    continue
                g = self.groups[m]
                if dom > s.resentment_threshold:
                    g.resentment += (s.follower_resentment * (dom - s.resentment_threshold) / (1 - s.resentment_threshold)
                                     * (1 - g.cohesion))
                else:
                    g.resentment *= 0.9
                # resentment must build past a threshold before it turns into defection
                if self.rng.random() >= min(0.9, max(0.0, g.resentment - 0.5) * 0.4):
                    continue
                left = al.name
                lead_name = lead.name
                self._leave(m, events)
                g.spurned[al.id] = self.turn + 25
                g.spurned[lead.id] = self.turn + 25      # the grudge is against the dominant leader
                g.resentment = 0.0
                rival = None
                for key, mem, pw in self.blocs(exclude=m):
                    if (key != al.id and key != lead.id and lead.id not in mem
                            and pw / T >= s.pole_share and pw >= 0.5 * bloc):
                        rival = key
                        break
                dest = "to independence"
                if (rival and g.strategy != "Neutral" and self.hops(m, self.alliances[rival].leader
                                                                     if rival in self.alliances else rival) <= s.reach
                        and self._join(m, rival, events, f"defecting from the {left}")):
                    dest = f"over to the {self.bloc_name(self.groups[m].alliance)}"
                events.append(f"{g.name} resents {lead_name}'s dominance of the {left} "
                              f"({dom:.0%} of its Power) and breaks away {dest}.")
                out.append(dict(group=m, left=left, to=self.groups[m].alliance))
        return out

    # ---- growth -----------------------------------------------------------
    def _growth(self):
        d = self.settings.drift
        for g in self.alive():
            if d > 0:
                g.productivity = min(3.0, max(0.3, g.productivity * math.exp(self.rng.gauss(0, d))))
            cap = self.capacity(g.id)
            if cap <= 0:
                continue
            g.power += g.growth * g.power * (1 - g.power / cap)
            g.power = max(0.5, g.power)

    # ---- step -------------------------------------------------------------
    def step(self):
        events = []
        self.turn += 1
        self.round_log = dict(uprisings=[], breakaways=[], upheavals=[], crises=[], incidents=[])
        self._clear_routes()
        self._viol = {}
        self._conduct_drift()
        self._growth()
        upheavals = self._home_front(events)
        uprisings = self._unrest(events)
        breakaways = self._resentment(events)
        self._diplomacy(events)
        for g in self.groups.values():
            g.attacked = False
        wars = self._war_phase(events)
        self._update_leaders()
        self.round_log.update(uprisings=uprisings, breakaways=breakaways, upheavals=upheavals)
        self._record(wars, events)
        return self.history[-1]

    def run(self, turns):
        for _ in range(turns):
            self.step()

    # ---- measurement ------------------------------------------------------
    def spheres(self):
        """{region id: pole bloc key} for Regions where one pole supplies >= sphere_share of the Power reaching it."""
        s = self.settings
        T = self.total_power()
        acc = {}
        for g in self.alive():
            k = g.alliance or g.id
            acc[k] = acc.get(k, 0.0) + g.power
        poles = {k for k, p in acc.items() if p / T >= s.pole_share}
        out = {}
        reach = {}
        for g in self.alive():
            mine = self.regions_of(g.id)
            if not mine:
                continue
            k = g.alliance or g.id
            for rid in self.regions:
                h = min(self.dist[r].get(rid, INF) for r in mine)
                if h <= s.reach:
                    d = reach.setdefault(rid, {})
                    d[k] = d.get(k, 0.0) + g.power * s.decay ** h
        for rid, d in reach.items():
            owner = self.regions[rid].owner
            ok = (self.groups[owner].alliance or owner) if owner else None
            if ok in poles:
                out[rid] = ok          # a pole's own territory is its own sphere
                continue
            tot = sum(d.values())
            k, v = max(d.items(), key=lambda kv: kv[1])
            if k in poles and tot > 0 and v / tot >= s.sphere_share:
                out[rid] = k
        return out

    def group_sphere(self, gid, sph=None):
        """The pole whose sphere holds most of a Group's Region value (None if none, or if it is that pole's member)."""
        sph = self._sph if sph is None else sph
        val = {}
        tot = 0.0
        for rid in self.regions_of(gid):
            v = self.regions[rid].value
            tot += v
            k = sph.get(rid)
            if k:
                val[k] = val.get(k, 0.0) + v
        if not val:
            return None
        k, v = max(val.items(), key=lambda kv: kv[1])
        if v < tot / 2 or k == self.bloc_key(gid):
            return None
        return k

    def classify(self, weight: dict):
        """System label for Power weights {gid: Power} (global, or present in one zone)."""
        s = self.settings
        T = sum(weight.values()) or 1.0
        acc = {}
        for gid, w in weight.items():
            if w <= 0:
                continue
            k = self.groups[gid].alliance or gid
            acc[k] = acc.get(k, 0.0) + w
        blocs = sorted(acc.items(), key=lambda kv: -kv[1])
        shares = [p / T for _, p in blocs]
        poles = [(k, p) for k, p in blocs if p / T >= s.pole_share]
        n = len(poles)
        pivots = []
        if n >= 2:
            # Blocs outside the poles strong enough to tip the top two either way.
            gap = poles[0][1] - poles[1][1]
            pivots = [k for k, p in blocs[n:] if p >= gap and p / T >= s.balancer_share]
        if n == 0:
            label = "Diffuse"
        elif n == 1:
            label = "Hegemony" if shares[0] >= 0.5 else "Unipolar"
        elif n == 2:
            label = "Lopsided bipolar" if poles[1][1] < 0.5 * poles[0][1] else "Bipolar"
            if pivots:
                label += " with balancer" + ("s" if len(pivots) > 1 else "")
        elif n == 3:
            label = "Tripolar"
        else:
            label = "Multipolar"

        def con(sh):
            m = len(sh)
            if m < 2:
                return 1.0
            hhi = sum(x * x for x in sh)
            return math.sqrt(max(0.0, (hhi - 1 / m) / (1 - 1 / m)))
        return dict(label=label, poles=n, pole_keys=[k for k, _ in poles], pivot_keys=pivots,
                    top_share=shares[0] if shares else 0.0, con_blocs=con(shares),
                    con_groups=con([w / T for w in weight.values() if w > 0]),
                    balance=poles[1][1] / poles[0][1] if n >= 2 else 0.0, n_blocs=len(blocs),
                    shares={k: p / T for k, p in blocs})

    def polarity(self):
        pol = self.classify({g.id: g.power for g in self.alive()})
        pol["n_alive"] = len(self.alive())
        pol.pop("shares", None)
        return pol

    def zone_presence(self, zone_regions):
        """{gid: Power present in a zone}: full Power for Groups holding Regions there, Power x decay^steps
        for outside Groups within reach; and the set of insiders."""
        out, inside = {}, set()
        for g in self.alive():
            mine = self.regions_of(g.id)
            if not mine:
                continue
            h = min(self.dist[r].get(z, INF) for r in mine for z in zone_regions)
            if h == 0:
                inside.add(g.id)
            if h <= self.settings.reach:
                out[g.id] = g.power * self.settings.decay ** h
        return out, inside

    def regional(self):
        res = []
        for z in self.zones:
            pres, inside = self.zone_presence(z["regions"])
            pol = self.classify(pres)
            tot = sum(pres.values()) or 1.0
            pol["penetration"] = sum(v for k, v in pres.items() if k not in inside) / tot
            pol["name"] = z["name"]
            res.append(pol)
        return res

    def roles(self, pol=None):
        pol = pol or self.polarity()
        T = self.total_power()
        blocs = self.blocs()
        top_key = blocs[0][0] if blocs else None
        poles = set(pol["pole_keys"])
        pivots = set(pol.get("pivot_keys", []))
        out = {}
        for g in self.groups.values():
            if not g.alive:
                out[g.id] = "Subjugated" if any(r.people == g.id for r in self.regions.values()) else "Gone"
                continue
            k = g.alliance or g.id
            if k in pivots and (k == g.id or self.alliances[k].leader == g.id):
                out[g.id] = "Holds the balance"
            elif k in pivots:
                out[g.id] = f"Balancer bloc ({self.groups[self.alliances[k].leader].name})"
            elif k in poles and (k == g.id or self.alliances[k].leader == g.id):
                out[g.id] = "Pole"
            elif g.alliance:
                leader = self.groups[self.alliances[g.alliance].leader].name
                if k not in poles:
                    out[g.id] = f"Minor bloc ({leader})"
                elif k == top_key:
                    out[g.id] = f"Bandwagoning with {leader}"
                else:
                    out[g.id] = f"Balancing with {leader}"
            elif not g.alliance and self.group_sphere(g.id):
                out[g.id] = f"In {self.bloc_name(self.group_sphere(g.id))}'s sphere"
            elif g.reborn >= 0 and self.turn - g.reborn < 10:
                out[g.id] = "Reborn"
            elif g.strategy == "Offshore balancer":
                out[g.id] = "Offshore"
            else:
                out[g.id] = "Unaligned"
        held = {}
        for r in self.regions.values():
            if r.owner and r.people and r.people != r.owner:
                held[r.owner] = held.get(r.owner, 0) + 1
        for gid, n in held.items():
            if gid in out and out[gid] not in ("Gone", "Subjugated"):
                out[gid] += f", occupier of {n}"
        for g in self.alive():
            if g.weariness >= 0.5 * self.settings.upheaval_threshold:
                out[g.id] += ", war-weary"
        return out

    def _record(self, wars, events):
        pol = self.polarity()
        self._sph = self.spheres()
        snap = dict(
            spheres=dict(self._sph),
            in_sphere={g.id: self.group_sphere(g.id) for g in self.alive()},
            turn=self.turn,
            power={g.id: g.power for g in self.groups.values()},
            alive={g.id: g.alive for g in self.groups.values()},
            productivity={g.id: g.productivity for g in self.groups.values()},
            alliance={g.id: g.alliance for g in self.groups.values()},
            alliances={a.id: dict(name=a.name, leader=a.leader, members=list(a.members), colour=a.colour)
                       for a in self.alliances.values()},
            owners={r.id: r.owner for r in self.regions.values()},
            wars=wars, events=events, polarity=pol, roles=self.roles(pol), regional=self.regional(),
        )
        top_threat = self._top_threats() if self.occupied() else {}
        snap["unrest"] = {r.id: dict(people=r.people, grievance=round(r.grievance, 4),
                                     threat=round(self.rebellion_threat(r.id, self._sponsors(r.id, top_threat)), 4))
                          for r in self.occupied()}
        snap["people"] = {r.id: r.people for r in self.regions.values()}
        snap["resentment"] = {g.id: round(g.resentment, 4) for g in self.alive() if g.resentment > 0}
        snap["cohesion"] = {g.id: round(g.cohesion, 4) for g in self.alive() if g.alliance}
        snap["weariness"] = {g.id: round(g.weariness, 4) for g in self.alive() if g.weariness > 0}
        snap["aggression"] = {g.id: round(g.aggression, 4) for g in self.alive()}
        snap["strategy"] = {g.id: g.strategy for g in self.groups.values()}
        snap["conduct"] = {g.id: round(g.conduct, 3) for g in self.alive()}
        snap["crises"] = list(self.round_log.get("crises", [])) if self.turn else []
        snap["incidents"] = list(self.round_log.get("incidents", [])) if self.turn else []
        snap["benevolence"] = {g.id: round(g.benevolence, 3) for g in self.alive()}
        snap["upheavals"] = list(self.round_log.get("upheavals", [])) if self.turn else []
        for r in self.occupied():
            snap["unrest"][r.id]["integration"] = round(r.integration, 4)
        snap["uprisings"] = list(self.round_log["uprisings"]) if self.turn else []
        snap["breakaways"] = list(self.round_log["breakaways"]) if self.turn else []
        snap["stats"] = round_stats(snap, self)
        self.history.append(snap)


# --------------------------------------------------------------------------
# Running statistics
# --------------------------------------------------------------------------

def _mean_cohesion(snap):
    """Mean cohesion of alliance followers (leaders excluded); None when no alliance has followers."""
    vals = []
    for a in snap["alliances"].values():
        for m in a["members"]:
            if m != a["leader"]:
                vals.append(snap.get("cohesion", {}).get(m, 0.0))
    return sum(vals) / len(vals) if vals else None


def round_stats(snap, world=None):
    """Per-round counts: Wars, Groups fighting, Groups bandwagoning, Groups alive, and unrest."""
    alive = [g for g, a in snap["alive"].items() if a]
    fighting = set()
    for w in snap["wars"]:
        fighting.update(w["attackers"])
        fighting.update(w["defenders"])
    armed = 0
    for u in snap.get("uprisings", []):
        if u.get("peaceful"):
            continue                       # a peaceful protest is not War
        armed += 1
        fighting.add(u["occupier"])        # an armed uprising is: the occupier and every backer fought
        fighting.update(u.get("backers", []))
    fighting &= set(alive)
    bandwagoning = sum(1 for g in alive if snap["roles"].get(g, "").startswith("Bandwagoning"))
    ups = snap.get("uprisings", [])
    unrest = snap.get("unrest", {})
    self_rule = 1.0
    if world is not None:
        tot = sum(r.value for r in world.regions.values() if r.owner) or 1.0
        self_rule = sum(r.value for r in world.regions.values() if r.owner and r.people == r.owner) / tot
    return dict(wars=len(snap["wars"]), armed=armed, fighting=len(fighting), bandwagoning=bandwagoning, alive=len(alive),
                occupied=len(unrest), mean_threat=(sum(u["threat"] for u in unrest.values()) / len(unrest)) if unrest else 0.0,
                uprisings=len(ups), liberations=sum(1 for u in ups if u["won"]), reborn=sum(1 for u in ups if u["reborn"]),
                breakaways=len(snap.get("breakaways", [])), self_rule=self_rule,
                subjugated=sum(1 for v in snap["roles"].values() if v == "Subjugated"),
                integration=(sum(u.get("integration", 0.0) for u in unrest.values()) / len(unrest)) if unrest else None,
                cohesion=_mean_cohesion(snap),
                weariness=(sum(snap.get("weariness", {}).values()) / len(alive)) if alive else 0.0,
                upheavals=len(snap.get("upheavals", [])),
                protests=sum(1 for u in ups if u.get("peaceful")),
                home_protests=sum(1 for u in snap.get("upheavals", []) if u.get("peaceful")),
                crises=len(snap.get("crises", [])), incidents=len(snap.get("incidents", [])),
                violations=sum(len(x.get("violated", [])) for x in snap["wars"]),
                resisted=sum(len(x.get("resisted", [])) for x in snap["wars"]),
                conduct=(sum(snap.get("conduct", {}).values()) / len(snap["conduct"])) if snap.get("conduct") else 0.0)


def running_stats(history, upto=None):
    """Averages over rounds 1..upto (turn 0 is the starting position, not a round).

    pacifism = mean share of living Groups not fighting any War (or armed uprising) in a round;
    freedom  = mean share of living Groups not bandwagoning (submission = 1 - freedom)."""
    upto = len(history) - 1 if upto is None else upto
    rounds = [h["stats"] for h in history[1:upto + 1]]
    n = len(rounds)
    if not n:
        return dict(rounds=0, wars_per_round=0.0, armed_per_round=0.0, peaceful_rounds=0, pacifism=1.0, freedom=1.0, submission=0.0,
                    bandwagoning_per_round=0.0, uprisings=0, liberations=0, reborn=0, breakaways=0,
                    uprisings_per_round=0.0, self_rule=1.0, occupied=0.0, mean_threat=0.0,
                    integration=None, cohesion=None, weariness=0.0, upheavals=0, protests=0, home_protests=0,
                    crises=0, incidents=0, conduct=0.0, violations=0, resisted=0)
    pac = sum(1 - r["fighting"] / r["alive"] for r in rounds if r["alive"]) / n
    free = sum(1 - r["bandwagoning"] / r["alive"] for r in rounds if r["alive"]) / n
    return dict(rounds=n, wars_per_round=sum(r["wars"] for r in rounds) / n,
                peaceful_rounds=sum(1 for r in rounds if r["wars"] == 0 and r.get("armed", 0) == 0),
                armed_per_round=sum(r.get("armed", 0) for r in rounds) / n, pacifism=pac, freedom=free,
                submission=1 - free, bandwagoning_per_round=sum(r["bandwagoning"] for r in rounds) / n,
                uprisings=sum(r.get("uprisings", 0) for r in rounds),
                liberations=sum(r.get("liberations", 0) for r in rounds),
                reborn=sum(r.get("reborn", 0) for r in rounds),
                breakaways=sum(r.get("breakaways", 0) for r in rounds),
                uprisings_per_round=sum(r.get("uprisings", 0) for r in rounds) / n,
                self_rule=sum(r.get("self_rule", 1.0) for r in rounds) / n,
                occupied=sum(r.get("occupied", 0) for r in rounds) / n,
                mean_threat=sum(r.get("mean_threat", 0.0) for r in rounds) / n,
                integration=_avg([r.get("integration") for r in rounds]),
                cohesion=_avg([r.get("cohesion") for r in rounds]),
                weariness=sum(r.get("weariness", 0.0) for r in rounds) / n,
                upheavals=sum(r.get("upheavals", 0) for r in rounds),
                protests=sum(r.get("protests", 0) for r in rounds),
                home_protests=sum(r.get("home_protests", 0) for r in rounds),
                crises=sum(r.get("crises", 0) for r in rounds),
                incidents=sum(r.get("incidents", 0) for r in rounds),
                violations=sum(r.get("violations", 0) for r in rounds),
                resisted=sum(r.get("resisted", 0) for r in rounds),
                conduct=sum(r.get("conduct", 0.0) for r in rounds) / n)


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


# --------------------------------------------------------------------------
# Many runs
# --------------------------------------------------------------------------

def run_many(scenario, settings: Settings, runs: int, turns: int, progress=None, cancelled=lambda: False):
    """Run the same scenario with seeds settings.seed .. settings.seed+runs-1 and summarise the endings."""
    gids = [g["id"] for g in scenario["groups"]]
    per = {gid: dict(survived=0, share=0.0, largest=0, pole=0) for gid in gids}
    labels = {}
    zlabels = {}
    wars = 0
    pacifism = freedom = 0.0
    unrest_tot = dict(uprisings=0, liberations=0, reborn=0, breakaways=0, upheavals=0, protests=0, home_protests=0,
                      self_rule=0.0)
    poles_sum = 0
    done = 0
    for i in range(runs):
        if cancelled():
            break
        st = copy.copy(settings)
        st.seed = settings.seed + i
        w = World(scenario, st)
        w.run(turns)
        last = w.history[-1]
        T = w.total_power()
        pol = last["polarity"]
        labels[pol["label"]] = labels.get(pol["label"], 0) + 1
        for z in last.get("regional", []):
            d = zlabels.setdefault(z["name"], {})
            d[z["label"]] = d.get(z["label"], 0) + 1
        poles_sum += pol["poles"]
        wars += sum(len(h["wars"]) for h in w.history)
        rs = running_stats(w.history)
        pacifism += rs["pacifism"]
        freedom += rs["freedom"]
        for k in ("uprisings", "liberations", "reborn", "breakaways", "upheavals", "protests", "home_protests"):
            unrest_tot[k] += rs[k]
        unrest_tot["self_rule"] += rs["self_rule"]
        alive = [g for g in w.groups.values() if g.alive]
        biggest = max(alive, key=lambda g: g.power).id if alive else None
        for gid in gids:
            g = w.groups[gid]
            if g.alive:
                per[gid]["survived"] += 1
                per[gid]["share"] += g.power / T
            if gid == biggest:
                per[gid]["largest"] += 1
            if last["roles"].get(gid) == "Pole":
                per[gid]["pole"] += 1
        done += 1
        if progress:
            progress(done, runs)
    n = max(1, done)
    for v in per.values():
        v["share"] /= n
    return dict(runs=done, turns=turns, per=per, labels=labels, zones=zlabels, wars=wars / n, poles=poles_sum / n,
                pacifism=pacifism / n, freedom=freedom / n, unrest={k: v / n for k, v in unrest_tot.items()})
