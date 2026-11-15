"""Brink model tests:  python3 -m unittest test_model"""
import copy
import unittest

from brink import scenarios as SC
from brink.model import Settings, World, run_many


def tiny(strategies=("Pole", "Bandwagoner", "Balancer"), powers=(30, 10, 10)):
    regions = [dict(id=f"r{i}", name=f"R{i}", x=i / 4, y=0.5, value=40, links=[f"r{i + 1}"] if i < 3 else [])
               for i in range(4)]
    groups = [dict(id=f"g{i}", name=f"G{i}", power=p, strategy=st, regions=[f"r{i}"])
              for i, (st, p) in enumerate(zip(strategies, powers))]
    groups[-1]["regions"].append("r3")
    return dict(name="tiny", regions=regions, groups=groups, alliances=[], map={})


class TestModel(unittest.TestCase):
    def test_deterministic_with_seed(self):
        a = World(SC.europe_1815(), Settings(seed=7))
        b = World(SC.europe_1815(), Settings(seed=7))
        a.run(40)
        b.run(40)
        self.assertEqual([h["power"] for h in a.history], [h["power"] for h in b.history])

    def test_scenarios_run(self):
        for f in SC.BUILTINS.values():
            sc = f()
            w = World(sc)
            w.run(30)
            self.assertEqual(len(w.history), 31)
            self.assertTrue(w.history[-1]["regional"])
            for g in w.groups.values():
                self.assertGreaterEqual(g.power, 0)

    def test_distance_decay(self):
        w = World(tiny())
        self.assertEqual(w.hops("g0", "g2"), 2)
        self.assertAlmostEqual(w.force("g0", "r2"), 30 * w.groups["g0"].mobilisation * w.settings.decay ** 2)

    def test_war_losses_follow_ratio(self):
        st = Settings(seed=1, deterministic=True, severity=0.5, attrition=0.0, spoils=0.0, conquest_ratio=99,
                      last_region_ratio=99, guarantee=0)
        w = World(tiny(("Expansionist", "Neutral", "Neutral"), (40, 10, 10)), st)
        p0 = w.groups["g1"].power
        war = w._fight("g0", "g1", "r1", set(), [])
        self.assertTrue(war["attacker_won"])
        r = war["fa"] / war["fd"]
        self.assertAlmostEqual(war["loss"], 0.5 * r / (1 + r))
        self.assertAlmostEqual(w.groups["g1"].power, p0 - p0 * w.groups["g1"].mobilisation * war["loss"])

    def test_conquest_and_elimination(self):
        st = Settings(seed=1, deterministic=True, conquest_ratio=1.1, last_region_ratio=1.1, guarantee=0)
        w = World(tiny(("Expansionist", "Neutral", "Neutral"), (80, 5, 10)), st)
        w._fight("g0", "g1", "r1", set(), [])
        self.assertEqual(w.regions["r1"].owner, "g0")
        self.assertFalse(w.groups["g1"].alive)

    def test_bandwagoner_joins_strongest(self):
        st = Settings(seed=1, inertia=0.0, war_rate=0.0)
        w = World(tiny(("Pole", "Bandwagoner", "Neutral"), (60, 10, 10)), st)
        w.step()
        self.assertIsNotNone(w.groups["g1"].alliance)
        self.assertEqual(w.alliances[w.groups["g1"].alliance].leader, "g0")

    def test_labels(self):
        st = Settings(seed=1, inertia=1.0, war_rate=0.0)
        w = World(tiny(("Pole", "Pole", "Neutral"), (40, 35, 25)), st)
        pol = w.polarity()
        self.assertEqual(pol["label"], "Tripolar")
        w = World(tiny(("Pole", "Pole", "Neutral"), (45, 40, 10)), st)
        self.assertEqual(w.polarity()["label"], "Bipolar with balancer")
        self.assertEqual(w.history[0]["roles"]["g2"], "Holds the balance")
        w = World(tiny(("Pole", "Neutral", "Neutral"), (70, 4, 4)), st)
        self.assertEqual(w.polarity()["label"], "Hegemony")

    def test_spheres(self):
        w = World(tiny(("Pole", "Neutral", "Neutral"), (70, 4, 4)), Settings(seed=1))
        sph = w.spheres()
        self.assertEqual(sph.get("r0"), "g0")
        self.assertEqual(sph.get("r1"), "g0")
        self.assertEqual(w.group_sphere("g1", sph), "g0")

    def test_conquest_subjugates_and_uprising_rebirths(self):
        st = Settings(seed=1, deterministic=True, conquest_ratio=1.1, last_region_ratio=1.1, guarantee=0,
                      harshness=3.0, garrison=0.0, nonviolence=0.0)
        w = World(tiny(("Expansionist", "Neutral", "Neutral"), (80, 5, 10)), st)
        w._fight("g0", "g1", "r1", set(), [])
        self.assertEqual(w.roles()["g1"], "Subjugated")
        self.assertEqual(w.regions["r1"].people, "g1")
        self.assertGreater(w.regions["r1"].grievance, 0)
        self.assertGreater(w.rebellion_threat("r1"), 0)
        up = w._uprising("r1", [], 0.5, [])          # no garrison: the rebels must win
        self.assertTrue(up["won"] and up["reborn"])
        self.assertTrue(w.groups["g1"].alive)
        self.assertEqual(w.regions["r1"].owner, "g1")
        self.assertEqual(w.regions["r1"].grievance, 0.0)

    def test_integration(self):
        def occupied_world(benevolence, conduct):
            st = Settings(seed=1, deterministic=True, conquest_ratio=1.1, last_region_ratio=1.1, guarantee=0,
                          rebellion_rate=0.0, integration_rate=0.05, unpredictability=0.0, crisis_rate=0.0)
            sc = tiny(("Expansionist", "Neutral", "Neutral"), (80, 5, 10))
            sc["groups"][0]["benevolence"] = benevolence
            w = World(sc, st)
            w._fight("g0", "g1", "r1", set(), [])
            w.groups["g0"].conduct = conduct
            return w
        harsh, kind = occupied_world(0.0, -0.5), occupied_world(1.0, 0.8)
        for _ in range(5):
            harsh.turn += 1
            kind.turn += 1
            harsh._unrest([])
            kind._unrest([])
        self.assertEqual(harsh.regions["r1"].integration, 0.0)      # bad conduct: no integration
        self.assertGreater(kind.regions["r1"].integration, harsh.regions["r1"].integration)
        self.assertLess(kind.regions["r1"].grievance, harsh.regions["r1"].grievance)
        for _ in range(200):
            kind.turn += 1
            kind._unrest([])
            if kind.regions["r1"].people == "g0":
                break
        self.assertEqual(kind.regions["r1"].people, "g0")      # integrated: now the occupier's people

    def test_cohesion_damps_resentment(self):
        st = Settings(seed=3, inertia=1.0, war_rate=0.0, follower_resentment=0.5, resentment_threshold=0.5,
                      cohesion_rate=0.0)
        sc = tiny(("Pole", "Bandwagoner", "Neutral"), (90, 5, 5))
        sc["alliances"] = [dict(name="Bloc", leader="g0", members=["g0", "g1"])]
        w = World(sc, st)
        w.groups["g1"].cohesion = 1.0
        w.rng.random = lambda: 0.999                          # never break away during the test
        w._resentment([])
        self.assertEqual(w.groups["g1"].resentment, 0.0)

    def test_dominant_leader_breeds_breakaways(self):
        st = Settings(seed=3, inertia=1.0, war_rate=0.0, follower_resentment=1.0, resentment_threshold=0.5,
                      cohesion_rate=0.0)
        sc = tiny(("Pole", "Bandwagoner", "Neutral"), (90, 5, 5))
        sc["alliances"] = [dict(name="Bloc", leader="g0", members=["g0", "g1"])]
        w = World(sc, st)
        for _ in range(30):
            w._resentment([])
            if w.groups["g1"].alliance is None:
                break
        self.assertIsNone(w.groups["g1"].alliance)
        self.assertFalse(w._join("g1", "g0", [], "test"))      # g0 leads no alliance now; and g1 holds a grudge

    def test_war_weariness(self):
        st = Settings(seed=1, deterministic=True, conquest_ratio=99, last_region_ratio=99, guarantee=0, spoils=0.0,
                      nonviolence=0.0)
        w = World(tiny(("Expansionist", "Expansionist", "Neutral"), (20, 30, 10)), st)
        w._fight("g0", "g1", "r1", set(), [])          # the weaker attacker loses
        self.assertGreater(w.groups["g0"].weariness, w.groups["g1"].weariness)
        a0 = w.eff_aggression(w.groups["g0"])
        self.assertLess(a0, w.groups["g0"].aggression)
        w.groups["g0"].weariness = 5.0
        w.rng.random = lambda: 0.0                       # make the upheaval certain
        p0, ag0 = w.groups["g0"].power, w.groups["g0"].aggression
        ups = w._home_front([])
        self.assertEqual([u["group"] for u in ups], ["g0"])
        self.assertLess(w.groups["g0"].power, p0)
        self.assertLess(w.groups["g0"].aggression, ag0)

    def test_bloc_renamed_when_namesake_leaves(self):
        st = Settings(seed=1, inertia=1.0, war_rate=0.0)
        regions = [dict(id=f"r{i}", name=f"R{i}", x=i / 5, y=0.5, value=40, links=[f"r{i + 1}"] if i < 3 else [])
                   for i in range(4)]
        groups = [dict(id=f"g{i}", name=f"G{i}", power=p, strategy="Bandwagoner", regions=[f"r{i}"])
                  for i, p in enumerate((30, 20, 10, 5))]
        w = World(dict(name="t", regions=regions, groups=groups, alliances=[], map={}), st)
        ev = []
        w._join("g1", "g0", ev, "test")               # G0 heads a new 'G0 bloc'
        aid = w.groups["g0"].alliance
        w._join("g2", aid, ev, "test")
        self.assertEqual(w.alliances[aid].name, "G0 bloc")
        w._leave("g0", ev)                            # the namesake walks out
        self.assertEqual(w.alliances[aid].name, "G1 bloc")
        w._join("g3", "g0", ev, "test")               # G0 founds again and keeps its own name
        names = sorted(a.name for a in w.alliances.values())
        self.assertEqual(names, ["G0 bloc", "G1 bloc"])

    def test_peaceful_forms_change_strategy_not_power(self):
        st = Settings(seed=1, deterministic=True, conquest_ratio=1.1, last_region_ratio=1.1, guarantee=0,
                      harshness=3.0, nonviolence=1.0)
        w = World(tiny(("Expansionist", "Neutral", "Neutral"), (80, 5, 10)), st)
        w._fight("g0", "g1", "r1", set(), [])
        w.rng.random = lambda: 0.0                      # every chance comes up
        p0, b0, g0 = w.groups["g0"].power, w.groups["g0"].benevolence, w.regions["r1"].grievance
        up = w._uprising("r1", [], 0.5, [])
        self.assertTrue(up["peaceful"])
        self.assertEqual(w.groups["g0"].power, p0)                 # no Power lost
        self.assertEqual(w.regions["r1"].owner, "g0")              # still occupied
        self.assertGreater(w.groups["g0"].benevolence, b0)         # the occupier changes course
        self.assertLess(w.regions["r1"].grievance, g0)
        w.groups["g0"].weariness = 0.7                              # just past the threshold
        ups = w._home_front([])
        self.assertTrue(ups and ups[0]["peaceful"])
        self.assertEqual(w.groups["g0"].strategy, "Threat balancer")   # Expansionist -> Threat balancer
        self.assertEqual(w.groups["g0"].power, p0)

    def test_conduct_follows_behaviour(self):
        st = Settings(seed=1, deterministic=True, conquest_ratio=99, last_region_ratio=99, guarantee=0,
                      reliability=1.0)
        sc = tiny(("Expansionist", "Bandwagoner", "Neutral"), (40, 20, 10))
        sc["alliances"] = [dict(name="Pact", leader="g1", members=["g1", "g2"])]
        w = World(sc, st)
        c_att, c_ally = w.groups["g0"].conduct, w.groups["g2"].conduct
        w._fight("g0", "g1", "r1", set(), [])
        self.assertLess(w.groups["g0"].conduct, c_att)                # starting a War costs reputation
        self.assertGreater(w.groups["g2"].conduct, c_ally)            # defending an ally earns it

    def test_cohesion_erodes_under_bad_conduct(self):
        st = Settings(seed=1, inertia=1.0, war_rate=0.0, unpredictability=0.0, crisis_rate=0.0, cohesion_rate=0.1)
        sc = tiny(("Pole", "Bandwagoner", "Neutral"), (30, 20, 10))
        sc["alliances"] = [dict(name="Pact", leader="g0", members=["g0", "g1"])]
        good, bad = World(sc, st), World(sc, st)
        for w, c in ((good, 0.8), (bad, -0.8)):
            w.groups["g0"].conduct = w.groups["g1"].conduct = c
            w.groups["g1"].cohesion = 0.5
            w._cohesion([])
        self.assertGreater(good.groups["g1"].cohesion, 0.5)
        self.assertLess(bad.groups["g1"].cohesion, 0.5)

    def _line(self, owners, alliances=(), **kw):
        """Five Regions in a row r0-r1-r2-r3-r4, all on land, held by the given Groups."""
        regions = [dict(id=f"r{i}", name=f"R{i}", x=0.1 + i * 0.1, y=0.5, value=20,
                        links=[f"r{i + 1}"] if i < 4 else []) for i in range(5)]
        gids = sorted(set(owners))
        groups = [dict(id=g, name=g.upper(), power=20, strategy="Expansionist",
                       regions=[f"r{i}" for i, o in enumerate(owners) if o == g]) for g in gids]
        sc = dict(name="line", regions=regions, groups=groups, alliances=list(alliances),
                  map=dict(aspect=1.0, land_radius=0.08))
        return World(sc, Settings(seed=1, **kw))

    def test_enemy_bloc_cannot_be_crossed(self):
        # a attacks e; e's ally d holds the Region between them, so a cannot reach e's Region r3 at all
        w = self._line(["a", "a", "d", "e", "e"], [dict(name="Pact", leader="e", members=["e", "d"])])
        self.assertIsNone(w._theatre("a", "e"))
        # the same map with d neutral instead: the route crosses d and violates it
        w = self._line(["a", "a", "d", "e", "e"])
        theatre = w._theatre("a", "e")
        self.assertEqual(theatre, "r3")
        steps, viol, path = w.war_route("a", theatre, w.bloc_key("e"))
        self.assertEqual(path, ["r1", "r2", "r3"])
        self.assertEqual(viol, (("d", 1.0),))

    def test_air_link_overflies(self):
        w = self._line(["a", "d", "d", "e", "e"], air_range=0.35, air_cost=1.5, airspace_respect=0.5,
                       violation_reluctance=5.0)
        steps, viol, path = w.war_route("a", "r3", w.bloc_key("e"))
        self.assertEqual(path, ["r0", "r3"])                       # flies straight over d
        self.assertEqual(viol, (("d", 0.5),))                      # an airspace violation, half weight
        self.assertAlmostEqual(steps, 1.5)

    def test_eras(self):
        from brink.model import era_of
        self.assertEqual(era_of(Settings.from_dict(SC.cold_war()["settings"])), "Air age")
        self.assertEqual(era_of(Settings.from_dict(SC.europe_1815()["settings"])), "Age of sail")

    def test_run_many(self):
        res = run_many(SC.europe_1815(), Settings(seed=1), 3, 10)
        self.assertEqual(res["runs"], 3)
        self.assertEqual(sum(res["labels"].values()), 3)

    def test_random_world_connected(self):
        sc = SC.random_world(9, 25, 6)
        w = World(sc)
        some = next(iter(w.regions))
        self.assertEqual(len(w.dist[some]), len(w.regions))
        self.assertTrue(all(w.regions_of(g) for g in w.groups))


if __name__ == "__main__":
    unittest.main()
