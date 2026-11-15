"""The Guide tab."""
from .model import STRATEGIES, STRATEGY_ORDER

_strats = "".join(
    f"<h4>{n}</h4><p><i>{STRATEGIES[n]['gist']}</i></p><p>{STRATEGIES[n]['blurb']}</p>"
    f"<p style='color:#777'>Default aggression {STRATEGIES[n]['aggression']:.2f}, mobilisation "
    f"{STRATEGIES[n]['mobilisation']:.2f}.</p>"
    for n in STRATEGY_ORDER)

GUIDE_HTML = f"""
<h2>Brink - a balance-of-power simulation</h2>
<p>The world is made of <b>Regions</b>, each held by a <b>Group</b>. Every Group has an amount of <b>Power</b>.
Each turn a Group can use its Power to fight <b>Wars</b>, or it can make itself safer by joining an
<b>Alliance</b> - to become a <i>pole</i>, to act as a <i>balancer</i> between poles, or to <i>bandwagon</i>
with a pole that already exists. The question Brink lets you play with is the old one: does a world of
Groups that only look after themselves stay in balance, or does it slide into hegemony - and what decides
which?</p>

<h3>Getting started</h3>
<ol>
<li>Pick a scenario at the top (or <b>New random world...</b>).</li>
<li>Press <b>Step</b> (or Space) to play a turn, <b>Run</b> for many turns, or <b>Play</b> to watch.</li>
<li>Drag the <b>Turn</b> slider to look back at any earlier turn - the map, tables and side panel all follow it.
Clicking on a chart jumps there too.</li>
<li>Change the setup on the <b>Groups</b> and <b>Regions</b> tabs (strategy, Power, starting alliances, Region
values and holders). Any setup change resets to turn 0.</li>
<li>Use <b>Many runs</b> to see what <i>usually</i> happens with a setup, not just one history.</li>
</ol>

<h3>A turn</h3>
<p><b>1. Growth.</b> Each Group's Power grows toward its <i>capacity</i> - the summed value of the Regions it
holds, times its productivity: <code>Power += growth x Power x (1 - Power / capacity)</code>. A Group that
lost Power in a War recovers; one that lost Regions shrinks toward its smaller base. Productivity takes a
small random step each turn (the <i>Differential growth</i> setting), so some Groups rise and others decline -
the uneven growth that, in theories of hegemonic war, brings on power transitions.</p>
<p><b>2. Diplomacy.</b> Each Group (in random order) may reconsider its alignment. With probability
<i>Diplomatic inertia</i> it keeps what it has, unless it was attacked last turn. If it reconsiders, it
acts on its strategy (below): it may join an alliance, leave one, or stay unaligned. Joining an unaligned
Group creates a new alliance led by that Group, so a strong Group becomes a pole simply by being joined.
An alliance's leader is always its strongest member; an alliance left with one member dissolves.</p>
<p><b>3. War.</b> Each Group that is willing to fight looks at every Group within <i>Reach</i> Regions that is
not its ally, estimates the War, and attacks the most promising target if its chance of winning is at least
<code>0.5 + 0.35 x (1 - aggression)</code> - an aggressive Group needs little edge, a cautious one a lot.
Even then it attacks only with probability <i>War propensity x aggression</i>. Each Group fights at most one
War per turn.</p>

<h3>How a War is decided</h3>
<p><b>Sides.</b> The attacker brings in each of its allies with probability <i>Help in attack</i>; the defender's
allies come with probability <i>Alliance reliability</i>; unaligned Offshore balancers join the defence when
the attacker belongs to the strongest bloc or brings far more Power; and when the defender is unaligned, the
leader of the pole whose sphere of influence it lies in (or, outside every sphere, the strongest rival pole)
may step in with probability <i>Guarantees</i>, if it can reach the theatre. A Group only starts a War if its own
force is at least <i>Initiator's share</i> of its side's expected force.</p>
<p><b>Proximity.</b> The theatre is the defender's Region nearest the attacker. Each participant
<i>marshals</i> its Power times its mobilisation, and that force reaches the theatre multiplied by
<code>decay ^ distance</code>, where distance is the number of steps from its nearest Region (Boulding's
loss-of-strength gradient). The defending side's total is multiplied by the <i>Defender's advantage</i>.</p>
<p><b>Who wins.</b> With A and D the marshaled Power at the theatre, the attacker wins with probability
<code>A^k / (A^k + D^k)</code>, k = <i>Decisiveness</i> (or the larger side always wins, if Wars are set to be
deterministic).</p>
<p><b>What it costs.</b> With r = winner's marshaled Power / loser's:</p>
<ul>
<li>each loser loses <code>severity x r/(1+r)</code> of the Power it marshaled - an even fight costs a quarter
at severity 0.5, a 3:1 rout 37.5%, and a hopeless stand nearly half;</li>
<li>each winner loses <code>attrition x severity x 1/(1+r)</code> of what it marshaled - close victories are
expensive, lopsided ones cheap;</li>
<li><i>Spoils</i> - a share of what the losers lost - goes to the winners in proportion to their forces;</li>
<li>if r reaches the <i>Ratio that takes a Region</i>, the winner that marshaled most takes the contested
Region (or, after a crushing defence, a Region of the attacker's next to it). A Group with no Regions left
is gone, and its conqueror takes a share of what Power it had.</li>
</ul>

<h3>Passage: how Wars travel</h3>
<p>A War has to <b>get</b> to the theatre. Each side's force travels along the cheapest route through the map's links:
a land border counts as one step, a <b>sea lane</b> as <i>Sea crossing cost</i> steps, and - with air power - an
<b>air link</b> joins any two Regions within <i>Air range</i> as <i>Air step cost</i> steps. Force arrives multiplied by
decay^steps, and a Group can only start a War whose route is within <i>Reach</i>.</p>
<ul>
<li>Its own and its allies' Regions (and unheld ones) are crossed freely.</li>
<li>The <b>enemy bloc's</b> Regions cannot be crossed: an attacker must strike a Region it can reach from outside, so
allies screen one another and an interior Region is safe until the frontier falls.</li>
<li>A <b>third party's</b> Region can be crossed, but that <b>violates its territory</b>: when choosing a route each
violation counts as <i>Reluctance to violate</i> extra steps, so attackers go round a neutral if they reasonably can.
If they do cross, the violated Group joins the defence with probability <i>Resistance to violation</i>; its alliance
leader (with alliance reliability), or the pole whose sphere it lies in (with the guarantee chance), may follow -
a cause for War, as Belgium was in 1914. The violator's conduct suffers.</li>
<li>Flying <b>over</b> a third party's Region violates its <b>airspace</b> - weighted by <i>Respect for neutral
airspace</i> in the reluctance, the chance of resistance and the harm to conduct. Landing in its Region is always a
full violation.</li>
</ul>
<p>The <b>Era of warfare</b> menu on the Settings tab sets these link costs together: <i>Pre-modern</i> (seas hard to
cross, no air power), <i>Age of sail</i> (seas are highways), <i>Industrial</i>, <i>Air age</i> (moderate air range,
airspace partly respected) and <i>Missile age</i> (long range, airspace little respected). Untick <i>Territorial
passage</i> to go back to plain distance, ignoring whose land lies between. On the map an attack's arrow follows its
route - dotted on air legs - and a ringed slash marks a third party's Region marched through. The Wars section of
the side pane lists each War's route and violations.</p>

<h3>Poles, balancers and bandwagoners</h3>
<p>A <b>bloc</b> is an alliance, or an unaligned Group on its own. A bloc holding at least <i>Share that makes a
pole</i> of all Power is a <b>pole</b> (&#9733;). A bloc outside the poles <b>holds the balance</b> when its Power is
at least the gap between the two strongest poles - it could tip them either way - and it holds at least
<i>Share that makes a balancer</i>. The system is labelled:</p>
<ul>
<li><b>Hegemony</b> - one pole, holding half of all Power or more; <b>Unipolar</b> - one pole, less than half;</li>
<li><b>Bipolar</b> - two poles; <b>Lopsided bipolar</b> - two poles, the second with less than half the first's Power;</li>
<li>... <b>with balancer(s)</b> - a two-pole system in which one or more blocs hold the balance;</li>
<li><b>Tripolar</b> - three poles; <b>Multipolar</b> - four or more; <b>Diffuse</b> - none.</li>
</ul>
<p>Each Group's <b>role</b> is read off the result, whatever its strategy:</p>
<ul>
<li><b>Pole</b> - leads a pole, or is one alone;</li>
<li><b>Holds the balance</b> - leads (or is) a bloc that could tip the top two poles;</li>
<li><b>Bandwagoning with X</b> - a member of the strongest bloc;</li>
<li><b>Balancing with X</b> - a member of a pole that is not the strongest;</li>
<li><b>In X's sphere</b> - unaligned, with most of its Regions inside pole X's sphere of influence;</li>
<li><b>Offshore</b> - an unaligned Offshore balancer; <b>Minor bloc</b>, <b>Unaligned</b>, <b>Gone</b>.</li>
</ul>

<h3>Running statistics</h3>
<p>The side pane of the Map tab keeps a running tally over the rounds played up to the turn on the slider:</p>
<ul>
<li><b>Rate of pacifism</b> - the share of living Groups <i>not</i> fighting any War in a round, averaged over the
rounds so far (100% = no Group has ever fought). An <b>armed uprising counts as War</b>: the occupier and every
Group that backed the rebels count as fighting that round (a peaceful protest does not). Beside it: Wars and armed
uprisings this round and per round, and how many rounds passed with neither.</li>
<li><b>Rate of freedom</b> - the share of living Groups <i>not</i> bandwagoning (not sitting as followers inside the
strongest bloc), averaged over the rounds so far. Its complement is the <b>rate of submission</b>.</li>
</ul>
<p>The <b>rate of self-determination</b> is the share of all Region value held by its own people (the Group
that held it at the start), averaged over the rounds so far: freedom counts diplomatic submission (bandwagoning),
self-determination counts territorial submission (conquest and subjugation).</p>
<p>All three are charted under <i>Pacifism, freedom and self-determination</i> (running averages and each round's own value), written to the
history CSV, and averaged over runs on the Many runs tab.</p>

<h3>Occupation, rebellion and rebirth</h3>
<p>Every Region remembers its <b>people</b> - the Group that held it at the start. A Region held by anyone else is
<b>occupied</b>, and a Group that loses its last Region is not gone but <b>subjugated</b>: a people without a
state, which can come back.</p>
<p><b>Grievance.</b> A conquered Region starts with <i>Harshness of conquest</i> grievance. Each round it keeps
<i>Grievance memory</i> (95%) of its grievance and gains <code>grievance growth x (1 + distance + irredentism) x (1 - integration)</code>, where
<i>distance</i> = 1 - decay^steps from the occupier's homeland (its own people's Regions) and <i>irredentism</i> is 1
if the people's own Group still exists next door, 0.5 if it exists further off.</p>
<p><b>Integration.</b> Each occupied Region also has an integration level with its occupier, from 0 to 1. Each round
it grows by <code>integration rate x (0.5 + benevolence) x nearness x calm x pull</code>: <i>nearness</i> runs from 1
next to the homeland down to 0.5 far away, <i>calm</i> = 1/(1 + grievance), and <i>pull</i> is 0.5 while the people's
own Group survives next door, 0.75 if it survives further off, 1 if it is subjugated. Conquest starts integration
again from 0 and a crushed uprising halves it. An integrated people stops building grievance; at full integration
the Region is <b>assimilated</b> - its people become the occupier's and the threat of rebellion is gone.
<b>Benevolence</b> (a setup column on the Groups tab, 0 to 1) is how well a Group treats the Regions it occupies:
it speeds integration but costs <i>Cost of benevolence</i> x benevolence x value in Power each round.</p>
<p><b>Upkeep.</b> Holding an occupied Region costs the occupier <code>upkeep x grievance x value</code> Power each
round - imperial overstretch.</p>
<p><b>Rebellion threat.</b> Rebels can raise <code>grievance x value / 2</code>, plus help from <b>sponsors</b>:
the people's own Group if it still exists (always), the leader of the strongest pole outside the occupier's bloc,
and Threat balancers whose worst threat is the occupier's bloc (each with probability <i>Rebel sponsorship</i>,
paying a quarter of what it sends). The occupier's <b>garrison</b> is <code>garrison strength x its Power x
decay^steps from its homeland</code>. The chance of an uprising each round is <code>rebellion propensity x
grievance/(1 + grievance) x R^k/(R^k + G^k)</code>.</p>
<p><b>Uprisings</b> are fought like Wars (the rebels get the defender's advantage). If the rebels win, the
Region returns to its people - a subjugated Group is <b>reborn</b> there, with Power from the Region plus half the
aid its backers sent - and the occupier loses Power as a defeated side would. A reborn Group burns with
<b>fervour</b>: for the <i>Fervour period</i> it defends with (1 + <i>Fervour of the reborn</i>) times its usual
force, fading to nothing, and the Groups that backed its uprising may come to its defence, as allies would. If they lose, grievance is halved and the occupier pays its attrition. A Group whose own
people's Region is held by someone nearby also prefers to make War there (revanchism).</p>

<h3>Peaceful and armed forms</h3>
<p>Discontent does not always take up arms. Each uprising in an occupied Region, and each upheaval at home, first
draws whether it is <b>peaceful</b>; the <i>Nonviolence</i> setting scales the chance.</p>
<ul>
<li><b>Peaceful protest in an occupied Region</b> - chance = nonviolence x (0.6 + the occupier's benevolence +
integration) x (1 - the share of the rebels' strength that comes from foreign backers' arms), at most 95%. No one
fights and no one loses Power: the occupier changes course and makes concessions - its benevolence rises by 0.15,
the Region's grievance falls by 40% and its integration rises a little. The Region stays occupied. (Marked on the
map by a green disc.)</li>
<li><b>Armed uprising</b> - otherwise: fought as above, costing the occupier Power and perhaps freeing the Region.</li>
<li><b>Peaceful change of government at home</b> - chance = nonviolence x 1.4 x threshold / weariness, so a Group
just past the threshold usually changes peacefully and a deeply war-weary one tends to boil over. The new
government changes the Group's <b>strategy</b> to a less warlike one (Expansionist to Threat balancer, Pole to
Balancer, Balancer or Threat balancer to Offshore balancer, Bandwagoner or Offshore balancer to Neutral) and its
aggression to no more than that strategy's default. No Power is lost.</li>
<li><b>Violent upheaval</b> - otherwise: the Group loses 15% of its Power, its aggression falls by 40%, and a
weakly attached follower walks out of its alliance.</li>
</ul>
<p>The Groups tab shows each Group's <i>Strategy now</i> and <i>Benevolence now</i>, which these events change.</p>

<h3>Restive followers and cohesion</h3>
<p>Submission is not only conquest. In an alliance whose leader holds more than <i>Dominance that breeds
resentment</i> of the bloc's Power, every follower gains resentment each round in proportion to the excess, times
<b>(1 - cohesion)</b>; otherwise its resentment fades. Past a threshold, resentment turns into a chance of
<b>breaking away</b> - to independence, or over to a rival pole that is at least half as strong and within reach.
A Group that breaks away holds a grudge against that leader for 25 rounds. Set <i>Follower resentment</i> to 0 to
switch this off.</p>
<p><b>Cohesion</b> (0 to 1) is how attached a member is to its alliance. It starts at 0 on joining and grows each
round by <i>Cohesion rate</i> x (1 - cohesion), twice as fast while a rival pole is within reach (a shared threat).
Being defended when attacked raises it; allies failing to turn up lowers it, and so does being dragged into a War a
partner started. A long-standing alliance facing a common enemy can therefore live with a dominant leader.</p>

<h3>Conduct: why integration and cohesion often fail</h3>
<p>Integration and cohesion are not automatic; they depend on how Groups behave. Every Group has a <b>conduct</b>
score from -1 to +1 - a reputation built from what it does:</p>
<ul>
<li><b>Lowers it</b> (aggressive or self-interested): starting a War (-0.15, and -0.1 more for bullying an
unaligned Group or one under half its Power), joining an attack (-0.05), conquering a Region (-0.1), crushing an
armed uprising (-0.05), deserting an attacked ally (-0.15), and - for a leader - dominating its bloc beyond the
resentment threshold (-0.01 a round).</li>
<li><b>Raises it</b> (diplomatic or common-interested): coming to an attacked ally's defence (+0.1), defending a
Group it guarantees or sponsored (+0.1), conceding to a peaceful protest (+0.1), and each round at peace (+0.01).</li>
<li>Each round conduct keeps <i>Conduct memory</i> of itself and drifts the rest of the way toward the Group's
<b>disposition</b>, 0.5 - aggression (peaceable Groups drift up, aggressive ones down). A new government resets it.</li>
</ul>
<p><b>Integration</b> changes each round by <code>integration rate x (0.5 + benevolence) x nearness x calm x pull x
(occupier's conduct + a random swing)</code>: it grows under an occupier that behaves well and <b>erodes</b> under one
that does not. <b>Cohesion</b> changes by <code>cohesion rate x (mean conduct of member and leader + 0.3 if a rival
pole is within reach + a random swing)</code>, growing when that is positive and eroding when it is negative. The
random swing (<i>Unpredictability</i>) means good conduct does not always pay and bad conduct does not always fail.</p>
<p><b>Crises.</b> Each round an alliance may suffer a crisis (chance = <i>Crisis rate</i> x (1 - its members' mean
conduct)/2) that halves every member's cohesion, and an occupied Region an <b>incident</b> (chance = crisis rate x
(1 - the occupier's conduct)/2) that halves its integration and adds grievance.</p>

<h3>War weariness at home</h3>
<p>War also breeds grievance at home. Each War adds <code>war weariness x the share of its Power a Group lost</code>
- weighted 1.5 for the Group that started it, 1 for allies who joined the attack, and 0.25 for defenders, who rally
round the flag - plus 0.1 more for being on the losing side; profitable victories ease it, and a share
(<i>Recovery from weariness</i>) fades each round. A war-weary Group is less aggressive and mobilises less, so it
marshals less Power and garrisons its conquests more weakly: effective aggression = aggression x 1/(1 + w), effective
mobilisation = mobilisation x (1 - w/(2(1 + w))). Above <i>Weariness that risks upheaval</i> it risks an
<b>upheaval</b> each round: it loses 15% of its Power, a cautious government cuts its aggression by 40%, and a
follower with cohesion under 0.5 walks out of its alliance.</p>

<p>The Map's <i>Unrest</i> colouring shades occupied Regions by rebellion threat (yellow low, red 30% a round or
more), and <i>Integration</i> shades them from red (none) to green (nearly assimilated); bursts mark this round's
uprisings (filled = won). The side pane adds the <b>rate of self-determination</b> (the share of Region
value held by its own people), occupied Regions, mean threat, uprisings, liberations, rebirths and breakaways,
and lists the hottest occupied Regions. It also shows mean integration, mean cohesion of followers, mean war weariness and upheavals. New roles:
<b>Subjugated</b>, <b>Reborn</b>, and ", occupier of N" and ", war-weary" added to a role.</p>

<h3>Regional systems</h3>
<p>The world is split into <b>zones</b> (named in the scenario; a random world is split by geography). Each zone
gets its own system label, computed from the <b>Power present</b> there: a Group holding a Region in the zone
counts in full, and a Group outside it counts as Power x decay^steps to the zone's nearest Region, if within
reach. So a world can be bipolar overall while one zone is tripolar and another lies under a single bloc's
hegemony. <b>Outside powers</b> is the share of the Power present in a zone that belongs to Groups holding no
Region there - how far the zone is penetrated by outsiders. Tick <i>Zones</i> on the map to outline them; the
Charts tab plots poles, the largest bloc's share and outside powers zone by zone, and Many runs tallies how each
zone ends.</p>

<h3>Spheres of influence</h3>
<p>Every pole's Power reaches out across the map, fading with distance. A Region lies in a pole's <b>sphere of
influence</b> when that pole's bloc supplies at least <i>Share that makes a sphere</i> of all the Power able to
reach it. Spheres change behaviour: when an unaligned Group is attacked, the pole whose sphere it lies in may
defend it (<i>Guarantees</i>); a pole does not intervene in a War inside the attacker's own sphere; and a Group in
no sphere may be defended by the strongest rival pole. Colour the map by <i>Spheres of influence</i>: full colour
= the pole's own bloc, pale = other Groups' Regions inside its sphere, grey = no one's.</p>
<p>Measures (Charts tab): <i>largest bloc's share</i>; <i>balance</i> = second pole's Power / first pole's (1 =
evenly matched, 0 = fewer than two poles); <i>concentration</i> = Singer, Bremer &amp; Stuckey's CON, 0 when
everyone is equal and 1 when one holds everything, computed for blocs and for Groups.</p>

<h3>Strategies</h3>
{_strats}

<h3>The map</h3>
<p>Regions are drawn as cells round their centres, clipped by coastlines. Dashed lines are sea lanes - links
between Regions whose cells do not touch. Group names grow with their share of Power; the tag below a name
is its alliance (&#9733; = the alliance's leader, or an unaligned Group that is a pole on its own). Red arrows
are this turn's Wars that the attacker won, grey ones attacks that were repelled, and a gold star marks a
Region that changed hands. <i>Colour by blocs</i> paints every alliance in its leader's colour and leaves
unaligned Groups pale. Hover over a Region for details.</p>

<h3>Scenarios</h3>
<p><b>Four powers</b> is a made-up world built to stay multipolar: four regional powers far apart and Power
that fades fast with distance. <b>Europe after 1815</b> and <b>Cold War world</b> are stylized: their Power figures are rough illustrative
weights, not data, and each state's strategy is a caricature of its habits. Use them as starting points, not
as history. <b>Random worlds</b> make up a map, names, strategies and Power from a seed. <b>Save setup...</b>
writes the scenario as edited (JSON); <b>Save current state...</b> writes the world as it stands at the turn
on the slider, alliances and all, so you can start a new scenario from it. Saved files go in the
<code>scenarios</code> folder next to the program by default.</p>

<h3>Things to try</h3>
<ul>
<li>Set <i>Power kept per Region of distance</i> low (0.4) and then high (0.95): when distance stops mattering,
does the world consolidate faster?</li>
<li>Make every Group a Bandwagoner, then every Group a Balancer. Which world produces a hegemon?</li>
<li>In Europe after 1815, turn Britain from an Offshore balancer into a Bandwagoner and use Many runs to compare
how often a hegemony forms.</li>
<li>Raise <i>Decisiveness</i> and <i>Severity</i> to make War catastrophic, or drop <i>Alliance reliability</i>
to see what unreliable allies do to deterrence.</li>
</ul>
"""
