"""Brink main window."""
from __future__ import annotations

import copy
import csv
import html
import os

from PyQt6.QtCore import QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox,
                             QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout,
                             QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox,
                             QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QScrollArea, QSlider,
                             QSpinBox, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget,
                             QTextBrowser, QVBoxLayout, QWidget)

from . import scenarios as SC
from .charts import LineChart, StackedChart
from .guide import GUIDE_HTML
from .mapview import MapView
from .model import (ERAS, era_of, running_stats, SETTING_INFO, STRATEGIES, STRATEGY_ORDER, Settings, World, run_many, strategy_info)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(os.path.expanduser("~"), ".config", "brink")


def _pct(v):
    return "-" if v is None else f"{v:.0%}"


def _num(v, nd=1):
    return f"{v:.{nd}f}"


class FitBrowser(QTextBrowser):
    """A text pane that never scrolls: the font shrinks until the whole text fits."""
    SIZES = [10.5, 10.0, 9.5, 9.0, 8.5, 8.0, 7.5, 7.0, 6.5, 6.0, 5.5, 5.0]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setOpenLinks(False)
        self._html = ""

    def set_fitted(self, text):
        self._html = text
        self._fit()

    def _fit(self):
        doc = self.document()
        avail = self.viewport().height() - 4
        for size in self.SIZES:
            f = QFont(self.font())
            f.setPointSizeF(size)
            doc.setDefaultFont(f)
            self.setHtml(self._html)
            doc.setTextWidth(self.viewport().width())
            if doc.size().height() <= avail:
                break
        self.verticalScrollBar().setValue(0)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self._html:
            self._fit()


class ManyWorker(QThread):
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(dict)

    def __init__(self, scenario, settings, runs, turns):
        super().__init__()
        self.scenario, self.settings, self.runs, self.turns = scenario, settings, runs, turns
        self.cancelled = False

    def run(self):
        res = run_many(self.scenario, self.settings, self.runs, self.turns,
                       progress=lambda d, n: self.progress.emit(d, n), cancelled=lambda: self.cancelled)
        self.finished_ok.emit(res)


class RandomDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New random world")
        f = QFormLayout(self)
        self.seed = QSpinBox()
        self.seed.setRange(1, 999999)
        self.seed.setValue(QTimerSeed.next())
        self.regions = QSpinBox()
        self.regions.setRange(6, 120)
        self.regions.setValue(30)
        self.groups = QSpinBox()
        self.groups.setRange(2, 28)
        self.groups.setValue(8)
        self.aspect = QDoubleSpinBox()
        self.aspect.setRange(0.8, 2.5)
        self.aspect.setSingleStep(0.1)
        self.aspect.setValue(1.6)
        f.addRow("Map seed", self.seed)
        f.addRow("Regions", self.regions)
        f.addRow("Groups", self.groups)
        f.addRow("Map width / height", self.aspect)
        note = QLabel("Groups get random strategies and starting Power; edit them on the Groups tab.")
        note.setWordWrap(True)
        f.addRow(note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


class QTimerSeed:
    _n = 1

    @classmethod
    def next(cls):
        cls._n += 1
        return cls._n


class MainWindow(QMainWindow):
    G_COLS = ["Group", "Map name", "Colour", "Strategy", "Start Power", "Growth", "Mobilisation", "Aggression",
              "Benevolence", "Starting alliance", "Power now", "Share", "Productivity", "Alliance now", "Role",
              "Regions", "Wars won / lost", "Regions taken / lost", "Occupies", "Resentment", "Cohesion",
              "War weariness", "Aggression now", "Strategy now", "Benevolence now", "Conduct"]
    G_EDIT = 10         # columns before this are the editable setup
    SECTIONS = [("overview", "Overview"), ("blocs", "Blocs"), ("peace", "Peace & freedom"),
                ("occupation", "Occupation"), ("alliances", "Alliances"), ("home", "Home front"),
                ("regional", "Regional systems"), ("spheres", "Spheres"), ("wars", "Wars"), ("events", "Events")]
    R_COLS = ["Region", "Value", "Starting holder", "Next to", "Holder now", "People", "Grievance", "Integration",
              "Rebellion threat"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Brink")
        self.resize(1360, 860)
        self.scenario = None
        self.settings = Settings()
        self.world: World | None = None
        self.view_turn = 0
        self._filling = False
        self.worker = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)
        v.setContentsMargins(8, 6, 8, 6)
        v.addLayout(self._build_scenario_bar())
        v.addLayout(self._build_run_bar())
        self.tabs = QTabWidget()
        v.addWidget(self.tabs, 1)
        self.tabs.addTab(self._build_guide(), "Guide")
        self.tabs.addTab(self._build_map_tab(), "Map")
        self.tabs.addTab(self._build_groups_tab(), "Groups")
        self.tabs.addTab(self._build_regions_tab(), "Regions")
        self.tabs.addTab(self._build_settings_tab(), "Settings")
        self.tabs.addTab(self._build_charts_tab(), "Charts")
        self.tabs.addTab(self._build_log_tab(), "Log")
        self.tabs.addTab(self._build_many_tab(), "Many runs")
        self.tabs.currentChanged.connect(lambda _: self._refresh_view())
        self.statusBar()

        self.load_scenario(SC.europe_1815())
        self.tabs.setCurrentIndex(1)

    # ------------------------------------------------------------------ bars
    def _build_scenario_bar(self):
        h = QHBoxLayout()
        h.addWidget(QLabel("Scenario:"))
        self.sc_combo = QComboBox()
        self.sc_combo.addItems(list(SC.BUILTINS))
        self.sc_combo.setMinimumWidth(260)
        self.sc_combo.activated.connect(self._pick_builtin)
        h.addWidget(self.sc_combo)
        b = QPushButton("New random world...")
        b.clicked.connect(self._new_random)
        h.addWidget(b)
        b = QPushButton("Open...")
        b.clicked.connect(self._open)
        h.addWidget(b)
        b = QPushButton("Save setup...")
        b.setToolTip("Save the scenario as set up on the Groups / Regions / Settings tabs (turn 0).")
        b.clicked.connect(self._save_setup)
        h.addWidget(b)
        b = QPushButton("Save current state...")
        b.setToolTip("Save the world as it stands at the turn shown, as a new scenario to start from.")
        b.clicked.connect(self._save_state)
        h.addWidget(b)
        h.addStretch(1)
        self.sc_desc = QLabel()
        self.sc_desc.setStyleSheet("color: palette(mid);")
        h.addWidget(self.sc_desc)
        return h

    def _build_run_bar(self):
        h = QHBoxLayout()
        h.addWidget(QLabel("Seed"))
        self.seed = QSpinBox()
        self.seed.setRange(0, 999999)
        self.seed.setValue(1)
        self.seed.setToolTip("Random seed for diplomacy and War outcomes. Same seed + same setup = same history.")
        h.addWidget(self.seed)
        b = QPushButton("Reset")
        b.setToolTip("Back to turn 0 with the current setup and seed.")
        b.clicked.connect(self.reset)
        h.addWidget(b)
        self.step_btn = QPushButton("Step")
        self.step_btn.setShortcut(QKeySequence("Space"))
        self.step_btn.setToolTip("Play one turn (Space)")
        self.step_btn.clicked.connect(lambda: self.advance(1))
        h.addWidget(self.step_btn)
        self.run_n = QSpinBox()
        self.run_n.setRange(1, 5000)
        self.run_n.setValue(50)
        b = QPushButton("Run")
        b.clicked.connect(lambda: self.advance(self.run_n.value()))
        h.addWidget(b)
        h.addWidget(self.run_n)
        h.addWidget(QLabel("turns"))
        self.play_btn = QPushButton("Play")
        self.play_btn.setCheckable(True)
        self.play_btn.toggled.connect(self._play)
        h.addWidget(self.play_btn)
        self.speed = QComboBox()
        self.speed.addItems(["Very slow", "Slow", "Medium", "Fast"])
        self.speed.setCurrentIndex(0)          # Very slow
        self.speed.currentIndexChanged.connect(lambda _: self._play(self.play_btn.isChecked()))
        h.addWidget(self.speed)
        h.addSpacing(16)
        h.addWidget(QLabel("Turn"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self._slider_moved)
        h.addWidget(self.slider, 1)
        self.turn_lbl = QLabel("0 / 0")
        self.turn_lbl.setMinimumWidth(80)
        h.addWidget(self.turn_lbl)
        return h

    # ------------------------------------------------------------------ tabs
    def _build_guide(self):
        t = QTextBrowser()
        t.setOpenExternalLinks(True)
        t.setHtml(GUIDE_HTML)
        return t

    def _build_map_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 4, 0, 0)
        h = QHBoxLayout()
        h.addWidget(QLabel("Colour by:"))
        self.mode_groups = QRadioButton("Groups")
        self.mode_blocs = QRadioButton("Blocs (alliances)")
        self.mode_spheres = QRadioButton("Spheres of influence")
        self.mode_spheres.setToolTip("Full colour: the pole's own bloc. Pale: Regions of other Groups inside its sphere. "
                                     "Grey: in no pole's sphere.")
        self.mode_groups.setChecked(True)
        bg = QButtonGroup(w)
        self.mode_unrest = QRadioButton("Unrest")
        self.mode_unrest.setToolTip("Occupied Regions shaded by rebellion threat (yellow = low, red = 30% a round or more); "
                                    "Regions held by their own people pale.")
        self.mode_integration = QRadioButton("Integration")
        self.mode_integration.setToolTip("Occupied Regions shaded by integration with their occupier (red = none, "
                                         "green = nearly assimilated); Regions held by their own people pale.")
        for b, m in ((self.mode_groups, "groups"), (self.mode_blocs, "blocs"), (self.mode_spheres, "spheres"),
                     (self.mode_unrest, "unrest"), (self.mode_integration, "integration")):
            bg.addButton(b)
            b.toggled.connect(lambda on, m=m: on and self.map.set_mode(m))
            h.addWidget(b)
        h.addSpacing(16)
        for label, attr, on in (("Region names", "show_region_names", False), ("Sea lanes", "show_links", True),
                                ("This turn's Wars", "show_wars", True)):
            cb = QCheckBox(label)
            cb.setChecked(on)
            cb.toggled.connect(lambda val, a=attr: (setattr(self.map, a, val), self.map.update()))
            h.addWidget(cb)
        cb = QCheckBox("Zones")
        cb.setToolTip("Outline the regional zones and show each zone's own system")
        cb.toggled.connect(lambda on: self.map.set_zones(on))
        h.addWidget(cb)
        h.addStretch(1)
        v.addLayout(h)
        # The key to the map's symbols, on a line of its own so none of it is cut off.
        sym = "style='font-size:13pt; font-weight:bold; color:%s'"
        legend = QLabel(f"Key: &nbsp;<span {sym % '#c0182c'}>&#10230;</span> War won by the attacker &nbsp;&nbsp; "
                        f"<span {sym % '#555555'}>&#10230;</span> attack repelled &nbsp;&nbsp; "
                        f"<span {sym % '#d4a017'}>&#9733;</span> Region changed hands &nbsp;&nbsp; "
                        f"<span {sym % '#ff7a00'}>&#10040;</span> armed uprising (filled = won) &nbsp;&nbsp; "
                        f"<span {sym % '#2e9e4f'}>&#9679;</span> peaceful protest &nbsp;&nbsp; "
                        f"<span {sym % '#2f6db5'}>&#9632;</span> tag under a name = its alliance (&#9733; = leader) "
                        f"&nbsp;&nbsp; <span {sym % '#3d5a80'}>- - -</span> sea lane &nbsp;&nbsp; "
                        f"<span {sym % '#c0182c'}>&#8856;</span> third party's territory violated &nbsp;&nbsp; "
                        f"<span {sym % '#c0182c'}>&middot;&middot;&middot;</span> air leg of an attack")
        legend.setWordWrap(True)
        legend.setContentsMargins(4, 0, 4, 2)
        v.addWidget(legend)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)
        self.map = MapView()
        body.addWidget(self.map, 1)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.side_group = QButtonGroup(w)
        self.side_group.setExclusive(True)
        self.side_buttons = {}
        bf = QFont(self.font())
        bf.setPointSizeF(10.0)
        for i, (key, label) in enumerate(self.SECTIONS):
            b = QPushButton(label.replace("&", "&&"))
            b.setCheckable(True)
            b.setFont(bf)
            b.setFixedSize(220, 36)
            b.setStyleSheet("QPushButton { text-align: left; padding: 4px 10px; } "
                            "QPushButton:checked { font-weight: bold; }")
            self.side_group.addButton(b, i)
            self.side_buttons[key] = b
            col.addWidget(b)
        col.addStretch(1)
        body.addLayout(col)
        self.side_pane = FitBrowser()
        self.side_pane.document().setDefaultStyleSheet(
            "h3 { margin-top: 0px; margin-bottom: 4px; } h4 { margin-top: 8px; margin-bottom: 2px; } "
            "td { padding: 1px 2px; } ul { margin-top: 2px; margin-bottom: 2px; } li { margin-bottom: 2px; }")
        self.side_pane.setFixedWidth(380)
        body.addWidget(self.side_pane)
        self.side_section = "overview"
        self.side_buttons["overview"].setChecked(True)
        self.side_group.idClicked.connect(self._pick_section)
        self._sections = {}
        v.addLayout(body, 1)
        return w

    def _build_groups_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        note = QLabel("The first ten columns are the setup (edit them; the simulation resets to turn 0). "
                      "Groups with the same 'Starting alliance' name begin allied. The rest show the turn on the slider. "
                      "Double-click a colour to change it.")
        note.setWordWrap(True)
        v.addWidget(note)
        split = QSplitter(Qt.Orientation.Vertical)
        self.gtable = QTableWidget(0, len(self.G_COLS))
        self.gtable.setHorizontalHeaderLabels(self.G_COLS)
        self.gtable.verticalHeader().setVisible(False)
        self.gtable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.gtable.setSortingEnabled(False)
        self.gtable.itemChanged.connect(self._group_edited)
        self.gtable.cellDoubleClicked.connect(self._group_dbl)
        self.gtable.currentCellChanged.connect(lambda r, *_: self._show_group_info(r))
        split.addWidget(self.gtable)
        self.ginfo = QTextBrowser()
        split.addWidget(self.ginfo)
        split.setSizes([480, 200])
        v.addWidget(split, 1)
        return w

    def _build_regions_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        note = QLabel("A Region's value adds to its holder's capacity - the ceiling its Power grows toward. "
                      "Editing value or starting holder resets to turn 0. Distance between Groups is counted "
                      "in steps along 'Next to' links (land borders and sea lanes).")
        note.setWordWrap(True)
        v.addWidget(note)
        self.rtable = QTableWidget(0, len(self.R_COLS))
        self.rtable.setHorizontalHeaderLabels(self.R_COLS)
        self.rtable.verticalHeader().setVisible(False)
        self.rtable.itemChanged.connect(self._region_edited)
        v.addWidget(self.rtable, 1)
        return w

    def _build_settings_tab(self):
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        w = QWidget()
        outer.setWidget(w)
        g = QGridLayout(w)
        g.setColumnStretch(2, 1)
        self.set_widgets = {}
        row = 0
        intro = QLabel("Changes take effect from the next turn of the current run, and in every run after it. "
                       "'Save setup...' stores them with the scenario.")
        intro.setWordWrap(True)
        g.addWidget(intro, row, 0, 1, 3)
        row += 1
        g.addWidget(QLabel("<b>Era of warfare</b>"), row, 0)
        self.era_combo = QComboBox()
        self.era_combo.addItems(list(ERAS) + ["Custom"])
        self.era_combo.activated.connect(self._pick_era)
        g.addWidget(self.era_combo, row, 1)
        el = QLabel("Presets for how Wars travel: the cost of a sea crossing, and whether there is air power - its "
                    "range, its cost and how far neutral airspace is respected. Choosing one sets those settings "
                    "below; changing any of them shows 'Custom'.")
        el.setWordWrap(True)
        el.setStyleSheet("color: palette(placeholder-text);")
        g.addWidget(el, row, 2)
        row += 1
        self.passage_cb = QCheckBox("Territorial passage (Wars travel by land, sea and air links; third parties' "
                                    "territory is violated, the enemy bloc's cannot be crossed)")
        self.passage_cb.toggled.connect(lambda on: self._setting_changed("passage", on))
        g.addWidget(self.passage_cb, row, 0, 1, 3)
        row += 1
        for name, (label, lo, hi, step, nd, help_) in SETTING_INFO.items():
            if nd == 0:
                sb = QSpinBox()
                sb.setRange(int(lo), int(hi))
            else:
                sb = QDoubleSpinBox()
                sb.setDecimals(nd)
                sb.setRange(lo, hi)
                sb.setSingleStep(step)
            sb.valueChanged.connect(lambda val, n=name: self._setting_changed(n, val))
            self.set_widgets[name] = sb
            lab = QLabel(f"<b>{label}</b>")
            hl = QLabel(help_)
            hl.setWordWrap(True)
            hl.setStyleSheet("color: palette(placeholder-text);")
            g.addWidget(lab, row, 0)
            g.addWidget(sb, row, 1)
            g.addWidget(hl, row, 2)
            row += 1
        self.det_cb = QCheckBox("Deterministic Wars (the side with more marshaled Power always wins)")
        self.det_cb.toggled.connect(lambda on: self._setting_changed("deterministic", on))
        g.addWidget(self.det_cb, row, 0, 1, 3)
        row += 1
        b = QPushButton("Restore the scenario's settings")
        b.clicked.connect(self._restore_settings)
        g.addWidget(b, row, 0)
        g.setRowStretch(row + 1, 1)
        return outer

    def _build_charts_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        h = QHBoxLayout()
        h.addWidget(QLabel("Chart:"))
        self.chart_pick = QComboBox()
        self.chart_pick.addItems(["Share of Power by Group", "Share of Power by bloc", "Power by Group",
                                  "Polarity measures", "Poles and Wars", "Pacifism, freedom and self-determination", "Unrest and rebellion",
                                  "Integration, cohesion, conduct and war weariness",
                                  "Poles by zone",
                                  "Largest bloc's share by zone", "Outside powers by zone"])
        self.chart_pick.currentIndexChanged.connect(lambda _: self._refresh_charts())
        h.addWidget(self.chart_pick)
        h.addStretch(1)
        self.chart_note = QLabel()
        h.addWidget(self.chart_note)
        b = QPushButton("Export history CSV...")
        b.clicked.connect(self._export_csv)
        h.addWidget(b)
        v.addLayout(h)
        self.chart_stack = QStackedWidget()
        self.stacked = StackedChart()
        self.lines = LineChart()
        for c in (self.stacked, self.lines):
            c.turnClicked.connect(self.slider.setValue)
            self.chart_stack.addWidget(c)
        v.addWidget(self.chart_stack, 1)
        return w

    def _build_log_tab(self):
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        return self.log

    def _build_many_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        intro = QLabel("One run is one history. Run the same setup many times (seeds Seed, Seed+1, ...) to see "
                       "what tends to happen: who survives, who ends as a pole, and what kind of system results.")
        intro.setWordWrap(True)
        v.addWidget(intro)
        h = QHBoxLayout()
        h.addWidget(QLabel("Runs"))
        self.many_runs = QSpinBox()
        self.many_runs.setRange(2, 5000)
        self.many_runs.setValue(100)
        h.addWidget(self.many_runs)
        h.addWidget(QLabel("Turns each"))
        self.many_turns = QSpinBox()
        self.many_turns.setRange(1, 5000)
        self.many_turns.setValue(100)
        h.addWidget(self.many_turns)
        self.many_btn = QPushButton("Run")
        self.many_btn.clicked.connect(self._many)
        h.addWidget(self.many_btn)
        self.many_bar = QProgressBar()
        h.addWidget(self.many_bar, 1)
        v.addLayout(h)
        self.many_summary = QLabel()
        self.many_summary.setWordWrap(True)
        v.addWidget(self.many_summary)
        self.many_table = QTableWidget(0, 6)
        self.many_table.setHorizontalHeaderLabels(["Group", "Strategy", "Survived", "Mean final share",
                                                   "Largest at end", "Pole at end"])
        self.many_table.verticalHeader().setVisible(False)
        self.many_table.setSortingEnabled(True)
        self.many_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        v.addWidget(self.many_table, 1)
        return w

    # ------------------------------------------------------------- scenario
    def load_scenario(self, sc):
        self.timer.stop()
        self.play_btn.setChecked(False)
        self.scenario = copy.deepcopy(sc)
        seed = self.seed.value()
        self.settings = Settings.from_dict(sc.get("settings"))
        self.settings.seed = seed
        self._fill_settings()
        self.sc_desc.setText(sc.get("name", ""))
        i = self.sc_combo.findText(sc.get("name", ""))
        if i >= 0:
            self.sc_combo.setCurrentIndex(i)
        self.sc_desc.setToolTip(sc.get("description", ""))
        self.reset(rebuild_map=True)
        self._fill_groups_setup()
        self._fill_regions_setup()
        self.many_table.setRowCount(0)
        self.many_summary.setText("")

    def reset(self, rebuild_map=True):
        self.timer.stop()
        self.play_btn.setChecked(False)
        self.settings.seed = self.seed.value()
        self.world = World(self.scenario, self.settings)
        self.world.settings = self.settings
        if rebuild_map:
            self.map.set_world(self.world)
        else:
            self.map.world = self.world
        self.log.clear()
        self._append_log(self.world.history[0])
        self.slider.blockSignals(True)
        self.slider.setRange(0, 0)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.view_turn = 0
        self._refresh_view()

    def _pick_builtin(self, i):
        name = self.sc_combo.itemText(i)
        if name == "Random world":
            self._new_random()
            return
        self.load_scenario(SC.BUILTINS[name]())

    def _new_random(self):
        d = RandomDialog(self)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            sc = SC.random_world(d.seed.value(), d.regions.value(), d.groups.value(), d.aspect.value())
            self.load_scenario(sc)
        finally:
            QApplication.restoreOverrideCursor()

    def _open(self):
        os.makedirs(CONFIG, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, "Open scenario", os.path.join(HERE, "scenarios"),
                                              "Brink scenarios (*.json)")
        if not path:
            return
        try:
            self.load_scenario(SC.load(path))
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Brink", f"Could not open {path}:\n{e}")

    def _save_setup(self):
        sc = copy.deepcopy(self.scenario)
        st = self.settings.to_dict()
        st.pop("seed", None)
        sc["settings"] = st
        self._save_dialog(sc)

    def _save_state(self):
        w = self.world
        snap = w.history[self.view_turn]
        sc = copy.deepcopy(self.scenario)
        sc["name"] = f"{sc.get('name', 'Scenario')} - turn {snap['turn']}"
        sc["description"] = f"Saved at turn {snap['turn']} of a run of '{self.scenario.get('name', '')}' (seed {self.settings.seed})."
        for g in sc["groups"]:
            g["power"] = round(snap["power"][g["id"]], 3)
            g["regions"] = [rid for rid, o in snap["owners"].items() if o == g["id"]]
            prod = snap.get("productivity", {}).get(g["id"], 1.0)
            if abs(prod - 1) > 1e-9:
                for r in sc["regions"]:
                    if r["id"] in g["regions"]:
                        r["value"] = round(r["value"] * prod, 3)
        people = snap.get("people", {})
        cur = {r.id: r for r in w.regions.values()}
        if snap["turn"] == w.turn:
            for r in sc["regions"]:
                r["people"] = people.get(r["id"])
                u = snap.get("unrest", {}).get(r["id"])
                if u:
                    r["grievance"] = u["grievance"]
                    r["integration"] = u.get("integration", 0.0)
                    r["held_since"] = 0
        else:
            for r in sc["regions"]:
                r["people"] = people.get(r["id"])
                u = snap.get("unrest", {}).get(r["id"])
                if u:
                    r["grievance"] = u["grievance"]
                    r["integration"] = u.get("integration", 0.0)
        for g in sc["groups"]:
            gid = g["id"]
            if gid in snap.get("cohesion", {}):
                g["cohesion"] = snap["cohesion"][gid]
            if snap.get("weariness", {}).get(gid):
                g["weariness"] = snap["weariness"][gid]
            if gid in snap.get("aggression", {}):
                g["aggression"] = snap["aggression"][gid]
            if gid in snap.get("conduct", {}):
                g["conduct"] = snap["conduct"][gid]
            if gid in snap.get("strategy", {}):
                g["strategy"] = snap["strategy"][gid]
            if gid in snap.get("benevolence", {}):
                g["benevolence"] = snap["benevolence"][gid]
        keep = {g for g, a in snap["alive"].items() if a} | {p for p in people.values() if p}
        sc["groups"] = [g for g in sc["groups"] if g["id"] in keep]
        sc["alliances"] = [dict(name=a["name"], leader=a["leader"], members=list(a["members"]))
                           for a in snap["alliances"].values()]
        st = self.settings.to_dict()
        st.pop("seed", None)
        sc["settings"] = st
        self._save_dialog(sc)

    def _save_dialog(self, sc):
        os.makedirs(os.path.join(HERE, "scenarios"), exist_ok=True)
        default = os.path.join(HERE, "scenarios", "".join(c if c.isalnum() else "-" for c in sc.get("name", "scenario")).strip("-").lower() + ".json")
        path, _ = QFileDialog.getSaveFileName(self, "Save scenario", default, "Brink scenarios (*.json)")
        if not path:
            return
        if not path.endswith(".json"):
            path += ".json"
        SC.save(sc, path)
        self.statusBar().showMessage(f"Saved {path}", 6000)

    # ------------------------------------------------------------- running
    def advance(self, n):
        if n > 20:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for _ in range(n):
                snap = self.world.step()
                self._append_log(snap)
        finally:
            if n > 20:
                QApplication.restoreOverrideCursor()
        last = self.world.turn
        self.slider.blockSignals(True)
        self.slider.setRange(0, last)
        self.slider.setValue(last)
        self.slider.blockSignals(False)
        self.view_turn = last
        self._refresh_view()

    def _play(self, on):
        if on:
            self.timer.start([5000, 700, 280, 60][self.speed.currentIndex()])
            self.play_btn.setText("Pause")
        else:
            self.timer.stop()
            self.play_btn.setText("Play")

    def _tick(self):
        self.advance(1)

    def _slider_moved(self, t):
        self.view_turn = t
        self._refresh_view()

    def _append_log(self, snap):
        pol = snap["polarity"]
        lines = [f"--- Turn {snap['turn']}: {pol['label']}, {pol['poles']} pole(s), largest bloc {pol['top_share']:.0%}"]
        lines += ["  " + e for e in snap["events"]]
        self.log.appendPlainText("\n".join(lines))

    # ------------------------------------------------------------- display
    def _refresh_view(self):
        if not self.world:
            return
        snap = self.world.history[self.view_turn]
        self.turn_lbl.setText(f"{snap['turn']} / {self.world.turn}")
        idx = self.tabs.currentIndex()
        tab = self.tabs.tabText(idx)
        if tab == "Map":
            self.map.show_snapshot(snap)
            self._fill_side(snap)
        elif tab == "Groups":
            self._fill_groups_state(snap)
        elif tab == "Regions":
            self._fill_regions_state(snap)
        elif tab == "Charts":
            self._refresh_charts()
        if tab != "Map":
            self.map.snap = snap   # keep the map current for when it is shown

    def _pick_section(self, i):
        self.side_section = self.SECTIONS[i][0]
        self.side_pane.set_fitted(self._sections.get(self.side_section, ""))

    def _fill_side(self, snap):
        """Build every section of the Map tab's pane; show the chosen one; put live counts on the buttons."""
        w = self.world
        pol = snap["polarity"]
        st = snap["stats"]
        t = snap["turn"]
        rs = running_stats(w.history, t)
        total = sum(snap["power"][g] for g in snap["power"] if snap["alive"][g]) or 1
        esc = html.escape

        def table(rows, widths=None):
            return "<table width='100%' cellspacing='2'>" + "".join(rows) + "</table>"

        def row(label, val, bold=False):
            if bold:
                return f"<tr><td><b>{label}</b></td><td align='right'><b>{val}</b></td></tr>"
            return f"<tr><td>{label}</td><td align='right'>{val}</td></tr>"

        def bar(v, colour):
            pct = int(round(max(0.0, min(1.0, v)) * 100))
            return (f"<tr><td colspan='2'><table cellspacing='0' cellpadding='0' width='100%'><tr>"
                    f"<td width='{pct}%' bgcolor='{colour}' height='8'></td><td width='{100 - pct}%' bgcolor='#dddddd'>"
                    f"</td></tr></table></td></tr>")

        def note(text):
            return f"<tr><td colspan='2'><small style='color:gray'>{text}</small></td></tr>"

        def title(text):
            return f"<h3>Turn {t}: {esc(text)}</h3>"

        played = t > 0
        S = {}
        alive = st["alive"] or 1

        # Overview -------------------------------------------------------
        rows = [row("System", esc(pol["label"]), True), row("Poles", pol["poles"]),
                row("Largest bloc's share", f"{pol['top_share']:.0%}"),
                row("Balance between the top two poles", f"{pol['balance']:.2f}"),
                row("Concentration (blocs)", f"{pol['con_blocs']:.2f}"),
                row("Groups / blocs", f"{pol['n_alive']} / {pol['n_blocs']}")]
        if played:
            rows += [row("&nbsp;", ""), row("Rate of pacifism", f"{rs['pacifism']:.1%}", True), bar(rs["pacifism"], "#3a9a5b"),
                     row("Rate of freedom", f"{rs['freedom']:.1%}", True), bar(rs["freedom"], "#2f6db5"),
                     row("Rate of self-determination", f"{rs['self_rule']:.1%}", True), bar(rs["self_rule"], "#c2672b"),
                     row("&nbsp;", ""),
                     row("Wars this round", st["wars"]),
                     row("Uprisings this round (peaceful)", f"{st.get('uprisings', 0)} ({st.get('protests', 0)})"),
                     row("Breakaways this round", st.get("breakaways", 0)),
                     row("Alliance crises / occupation incidents", f"{st.get('crises', 0)} / {st.get('incidents', 0)}"),
                     row("Upheavals this round (peaceful)", f"{st.get('upheavals', 0)} ({st.get('home_protests', 0)})")]
        else:
            rows.append(note("No rounds played yet - press Step, Run or Play."))
        S["overview"] = title(pol["label"]) + table(rows)

        # Blocs --------------------------------------------------------------
        blocs = {}
        for gid, a in snap["alive"].items():
            if a:
                blocs.setdefault(snap["alliance"][gid] or gid, []).append(gid)
        rows = []
        for k, mem in sorted(blocs.items(), key=lambda kv: -sum(snap["power"][m] for m in kv[1])):
            share = sum(snap["power"][m] for m in mem) / total
            if k in snap["alliances"]:
                al = snap["alliances"][k]
                col, name = al["colour"], esc(al["name"])
                members = ", ".join(("<b>%s</b>" if m == al["leader"] else "%s") % esc(w.groups[m].name)
                                    for m in sorted(mem, key=lambda m: -snap["power"][m]))
            else:
                col, name = w.groups[k].colour, esc(w.groups[k].name)
                members = f"<i>unaligned - {esc(snap['roles'].get(k, ''))}</i>"
            pole = " &#9733;" if k in pol["pole_keys"] else ""
            rows.append(f"<tr><td><span style='color:{col}'>&#9632;</span> <b>{name}</b>{pole}<br>"
                        f"<small>{members}</small></td><td align='right' valign='top'>{share:.1%}</td></tr>")
        S["blocs"] = title("Blocs") + "<div style='color:gray'>&#9733; = pole; leader in bold</div>" + table(rows)

        # Peace & freedom ------------------------------------------------------
        if played:
            rows = [row("Rate of pacifism", f"{rs['pacifism']:.1%}", True), bar(rs["pacifism"], "#3a9a5b"),
                    note(f"share of Groups not at War (armed uprisings count as War), averaged over rounds 1-{t}; "
                         f"this round {1 - st['fighting'] / alive:.0%} ({st['fighting']} of {st['alive']} fighting)"),
                    row("Wars this round / per round", f"{st['wars']} / {rs['wars_per_round']:.2f}"),
                    row("Armed uprisings this round / per round", f"{st.get('armed', 0)} / {rs['armed_per_round']:.2f}"),
                    row("Rounds without War or armed uprising", f"{rs['peaceful_rounds']} of {rs['rounds']}"),
                    row("Neutral territory violated (resisted)", f"{rs['violations']} ({rs['resisted']})"),
                    row("&nbsp;", ""),
                    row("Rate of freedom", f"{rs['freedom']:.1%}", True), bar(rs["freedom"], "#2f6db5"),
                    note(f"share of Groups not bandwagoning, averaged; this round {1 - st['bandwagoning'] / alive:.0%} "
                         f"({st['bandwagoning']} of {st['alive']} bandwagoning)"),
                    row("Rate of submission", f"{rs['submission']:.1%}"),
                    row("Bandwagoning per round", f"{rs['bandwagoning_per_round']:.2f}"),
                    row("&nbsp;", ""),
                    row("Rate of self-determination", f"{rs['self_rule']:.1%}", True), bar(rs["self_rule"], "#c2672b"),
                    note(f"share of Region value held by its own people, averaged; this round {st.get('self_rule', 1.0):.0%}")]
            S["peace"] = title("Peace & freedom") + table(rows)
        else:
            S["peace"] = title("Peace & freedom") + "<p style='color:gray'>No rounds played yet.</p>"

        # Occupation -------------------------------------------------------------
        unrest = snap.get("unrest", {})
        n_armed = rs["uprisings"] - rs["protests"]
        armed_lib = (rs["liberations"] / n_armed) if n_armed else 0
        rows = [row("Occupied Regions now / average", f"{st.get('occupied', 0)} / {rs['occupied']:.1f}"),
                row("Rebellion threat (mean)", f"{st.get('mean_threat', 0.0):.1%}"),
                row("Integration (now / average)", f"{_pct(st.get('integration'))} / {_pct(rs['integration'])}"),
                row("Uprisings this round / total", f"{st.get('uprisings', 0)} / {rs['uprisings']}"),
                row("&nbsp;&nbsp;peaceful protests / armed", f"{rs['protests']} / {rs['uprisings'] - rs['protests']}"),
                row("Liberations", f"{rs['liberations']} ({armed_lib:.0%} of armed uprisings)"),
                row("Groups reborn / subjugated now", f"{rs['reborn']} / {st.get('subjugated', 0)}"),
                row("Incidents setting back integration", f"{st.get('incidents', 0)} / {rs['incidents']}")]
        occ = title("Occupation & rebellion") + table(rows)
        for rid in snap.get("incidents", []):
            o = snap["owners"].get(rid)
            if o:
                occ += (f"<p>&#9889; Incident in <b>{esc(w.regions[rid].name)}</b>: {esc(w.groups[o].name)}'s conduct "
                        f"({snap.get('conduct', {}).get(o, 0):+.2f}) sets back integration</p>")
        for up in snap.get("uprisings", []):
            if up.get("peaceful"):
                occ += (f"<p><span style='color:#2e9e4f'>&#9679;</span> <b>{esc(w.regions[up['region']].name)}</b> "
                        f"protested peacefully; {esc(w.groups[up['occupier']].name)} made concessions "
                        f"(benevolence now {snap.get('benevolence', {}).get(up['occupier'], 0):.2f})</p>")
                continue
            res = ("won - " + ("reborn" if up["reborn"] else "freed")) if up["won"] else "crushed"
            back = ", ".join(w.groups[b].name for b in up["backers"] if b != up["people"])
            occ += (f"<p>&#10040; <b>{esc(w.regions[up['region']].name)}</b> rose in arms against "
                    f"{esc(w.groups[up['occupier']].name)}: {res}" + (f" (backed by {esc(back)})" if back else "") + "</p>")
        hot = sorted(unrest.items(), key=lambda kv: -kv[1]["threat"])[:8]
        if hot:
            occ += ("<h4>Most at risk</h4><table width='100%' cellspacing='2'><tr><th align='left'>Region</th>"
                    "<th align='left'>people / held by (conduct)</th><th align='right'>integr.</th>"
                    "<th align='right'>threat</th></tr>")
            for rid, u in hot:
                pn = w.groups[u["people"]].name if u["people"] in w.groups else "?"
                o = snap["owners"][rid]
                occ += (f"<tr><td>{esc(w.regions[rid].name)}</td><td>{esc(pn)} / {esc(w.groups[o].name)} "
                        f"({snap.get('conduct', {}).get(o, 0):+.2f})</td>"
                        f"<td align='right'>{u.get('integration', 0.0):.0%}</td><td align='right'>{u['threat']:.0%}</td></tr>")
            occ += "</table>"
        S["occupation"] = occ

        # Alliances ------------------------------------------------------------------
        rows = [row("Cohesion of followers (now / average)", f"{_pct(st.get('cohesion'))} / {_pct(rs['cohesion'])}"),
                row("Breakaways this round / total", f"{st.get('breakaways', 0)} / {rs['breakaways']}"),
                row("Crises this round / total", f"{st.get('crises', 0)} / {rs['crises']}"),
                row("Mean conduct of all Groups", f"{st.get('conduct', 0.0):+.2f}")]
        al_html = title("Alliances") + table(rows)
        for aid in snap.get("crises", []):
            if aid in snap["alliances"]:
                al_html += (f"<p>&#9889; <b>Crisis in the {esc(snap['alliances'][aid]['name'])}</b>: "
                            f"its members' cohesion halved</p>")
        for al_id, al in snap["alliances"].items():
            bloc = sum(snap["power"][m] for m in al["members"]) or 1
            dom = snap["power"][al["leader"]] / bloc
            al_html += (f"<h4><span style='color:{al['colour']}'>&#9632;</span> {esc(al['name'])} "
                        f"<small>(leader {esc(w.groups[al['leader']].name)} holds {dom:.0%}, conduct "
                        f"{snap.get('conduct', {}).get(al['leader'], 0):+.2f})</small></h4><table width='100%' cellspacing='2'>"
                        "<tr><th align='left'>member</th><th align='right'>conduct</th><th align='right'>cohesion</th>"
                        "<th align='right'>resentment</th></tr>")
            for m in sorted(al["members"], key=lambda m: -snap["power"][m]):
                if m == al["leader"]:
                    continue
                al_html += (f"<tr><td>{esc(w.groups[m].name)}</td>"
                            f"<td align='right'>{snap.get('conduct', {}).get(m, 0):+.2f}</td>"
                            f"<td align='right'>{snap.get('cohesion', {}).get(m, 0):.2f}</td>"
                            f"<td align='right'>{snap.get('resentment', {}).get(m, 0):.2f}</td></tr>")
            al_html += "</table>"
        for b in snap.get("breakaways", []):
            to = snap["alliances"][b["to"]]["name"] if b.get("to") in snap["alliances"] else "independence"
            al_html += f"<p>&#8618; <b>{esc(w.groups[b['group']].name)}</b> broke away from the {esc(b['left'])} to {esc(to)}</p>"
        S["alliances"] = al_html

        # Home front --------------------------------------------------------------------
        rows = [row("War weariness (mean, now / average)", f"{st.get('weariness', 0.0):.2f} / {rs['weariness']:.2f}"),
                row("Upheavals this round / total", f"{st.get('upheavals', 0)} / {rs['upheavals']}"),
                row("&nbsp;&nbsp;peaceful / violent", f"{rs['home_protests']} / {rs['upheavals'] - rs['home_protests']}")]
        home = title("Home front") + table(rows)
        for uh in snap.get("upheavals", []):
            if uh.get("peaceful"):
                home += (f"<p><span style='color:#2e9e4f'>&#9679;</span> <b>{esc(w.groups[uh['group']].name)}</b>: war weariness "
                         f"{uh['weariness']:.2f} brings in a new government peacefully - {esc(uh['old'])} to "
                         f"{esc(uh['new'])}; no Power lost</p>")
                continue
            home += (f"<p>&#9888; <b>{esc(w.groups[uh['group']].name)}</b>: war weariness {uh['weariness']:.2f} violently "
                     f"brings down its government; -15% Power"
                     + (f"; it walks out of the {esc(uh['left'])}" if uh.get("left") else "") + "</p>")
        weary = sorted(snap.get("weariness", {}).items(), key=lambda kv: -kv[1])[:8]
        if weary:
            home += ("<h4>Most war-weary</h4><table width='100%' cellspacing='2'><tr><th align='left'>Group</th>"
                     "<th align='right'>weariness</th><th align='right'>aggression now</th></tr>")
            for gid, v in weary:
                home += (f"<tr><td>{esc(w.groups[gid].name)}</td><td align='right'>{v:.2f}</td>"
                         f"<td align='right'>{snap.get('aggression', {}).get(gid, 0):.2f}</td></tr>")
            home += "</table>"
        S["home"] = home

        # Regional systems ------------------------------------------------------------------
        reg = title("Regional systems") + ("<table width='100%' cellspacing='2'><tr><th align='left'>Zone</th>"
                                           "<th align='left'>System</th><th align='right'>Outside</th></tr>")
        for z in snap.get("regional", []):
            poles = ", ".join(esc(self._bloc_label(snap, k)) for k in z["pole_keys"])
            piv = ", ".join(esc(self._bloc_label(snap, k)) for k in z.get("pivot_keys", []))
            extra = f"<br><small>poles: {poles}</small>" if poles else ""
            if piv:
                extra += f"<br><small>holding the balance: {piv}</small>"
            reg += (f"<tr><td valign='top'><b>{esc(z['name'])}</b></td><td>{esc(z['label'])}{extra}</td>"
                    f"<td align='right' valign='top'>{z['penetration']:.0%}</td></tr>")
        reg += "</table><p><small style='color:gray'>Outside = share of the Power present in the zone held by Groups with no Region there.</small></p>"
        S["regional"] = reg

        # Spheres -------------------------------------------------------------------------------
        sph = snap.get("spheres", {})
        by = {}
        for rid, k in sph.items():
            by.setdefault(k, []).append(rid)
        sp = title("Spheres of influence")
        if not by:
            sp += "<p style='color:gray'>No pole holds a sphere of influence.</p>"
        for k, rids in sorted(by.items(), key=lambda kv: -len(kv[1])):
            clients = sorted({w.groups[g].name for g, kk in snap.get("in_sphere", {}).items() if kk == k})
            sp += f"<h4>{esc(self._bloc_label(snap, k))}: {len(rids)} Regions</h4>"
            if clients:
                sp += f"<p>Groups inside it: {esc(', '.join(clients))}</p>"
        S["spheres"] = sp

        # Wars ------------------------------------------------------------------------------------
        wr = title("Wars")
        if not snap["wars"]:
            last = next((h["turn"] for h in reversed(w.history[:t + 1]) if h["wars"]), None)
            wr += "<p style='color:gray'>No Wars this round" + (f"; the last was in round {last}." if last else ".") + "</p>"
        for war in snap["wars"]:
            a, d = w.groups[war["attacker"]].name, w.groups[war["defender"]].name
            allies_a = [w.groups[m].name for m in war["attackers"][1:]]
            allies_d = [w.groups[m].name for m in war["defenders"][1:]]
            res = "attacker won" if war["attacker_won"] else "attack repelled"
            wr += (f"<h4>{esc(a)} v {esc(d)} over {esc(w.regions[war['theatre']].name)}</h4>"
                   + table([row("Marshaled", f"{war['fa']:.1f} v {war['fd']:.1f}"),
                            row("Attacker's chance", f"{war['p']:.0%}"),
                            row("Result", res),
                            row("Losers lost / winners lost", f"{war['loss']:.0%} / {war['attrition']:.0%} of what they marshaled")]
                           + ([row("With the attacker", esc(", ".join(allies_a)))] if allies_a else [])
                           + ([row("With the defender", esc(", ".join(allies_d)))] if allies_d else [])
                           + ([row("Region taken", f"{esc(w.regions[war['moved'][0]].name)} to {esc(w.groups[war['moved'][2]].name)}")]
                              if war.get("moved") else [])
                           + ([row("Route", esc(" > ".join(w.regions[r].name for r in war["route"])))]
                              if war.get("route") and len(war["route"]) > 1 else [])
                           + [row(("Territory" if v not in war.get("overflown", []) else "Airspace") + " of "
                                  + esc(w.groups[v].name),
                                  "crossed by " + esc(", ".join(w.groups[m].name for m in war.get("crossers", {}).get(v, [])))
                                  + ("; resisted" if v in war.get("resisted", []) else "; let them pass"))
                              for v in war.get("violated", [])]))
        S["wars"] = wr

        # Events --------------------------------------------------------------------------------------
        ev = [e.strip() for e in snap["events"]]
        evh = title("Events")
        if not ev:
            evh += "<p style='color:gray'>Nothing happened this round.</p>"
        else:
            evh += "<ul style='margin-left:-20px'>" + "".join(f"<li>{esc(e)}</li>" for e in ev[:14]) + "</ul>"
            if len(ev) > 14:
                evh += f"<p><i>... {len(ev) - 14} more on the Log tab</i></p>"
        S["events"] = evh

        self._sections = S
        counts = {"blocs": f"{pol['n_blocs']}", "wars": f"{st['wars']}", "occupation": f"{st.get('occupied', 0)}"
                  + (f", {st.get('uprisings', 0)} rising" if st.get("uprisings") else ""),
                  "alliances": f"{len(snap['alliances'])}" + (f", {st.get('breakaways')} left" if st.get("breakaways") else "")
                  + (f", crisis" if st.get("crises") else ""),
                  "home": f"{st.get('upheavals')} upheaval" if st.get("upheavals") else "",
                  "events": f"{len(ev)}", "spheres": f"{len(by)}", "regional": f"{len(snap.get('regional', []))}"}
        for key, label in self.SECTIONS:
            c = counts.get(key, "")
            text = f"{label} ({c})" if c not in ("", None) else label
            self.side_buttons[key].setText(text.replace("&", "&&"))      # '&' would be read as a shortcut mark
        self.side_pane.set_fitted(S.get(self.side_section, ""))

    @staticmethod
    def _set_html(tb, text):
        """Replace a pane's contents without losing the reader's scroll position."""
        bar = tb.verticalScrollBar()
        pos = bar.value()
        tb.setHtml(text)
        bar.setValue(min(pos, bar.maximum()))

    def _bloc_label(self, snap, k):
        if k in snap["alliances"]:
            return snap["alliances"][k]["name"]
        return self.world.groups[k].name if k in self.world.groups else k

    # groups ----------------------------------------------------------------
    def _fill_groups_setup(self):
        self._filling = True
        sc = self.scenario
        t = self.gtable
        t.setRowCount(len(sc["groups"]))
        start_alliance = {}
        for a in sc.get("alliances", []):
            for m in a.get("members", []):
                start_alliance[m] = a.get("name", "")
        for i, g in enumerate(sc["groups"]):
            d = STRATEGIES.get(g.get("strategy", "Balancer"), STRATEGIES["Balancer"])
            vals = [g.get("name", g["id"]), g.get("short", ""), "", None, g.get("power", 10), g.get("growth", 0.08),
                    g.get("mobilisation", d["mobilisation"]), g.get("aggression", d["aggression"]),
                    g.get("benevolence", 0.3), start_alliance.get(g["id"], "")]
            for c, val in enumerate(vals):
                if c == 3:
                    cb = QComboBox()
                    cb.addItems(STRATEGY_ORDER)
                    cb.setCurrentText(g.get("strategy", "Balancer"))
                    cb.currentTextChanged.connect(lambda txt, row=i: self._strategy_edited(row, txt))
                    t.setCellWidget(i, c, cb)
                    continue
                it = QTableWidgetItem()
                if isinstance(val, (int, float)):
                    it.setData(Qt.ItemDataRole.EditRole, float(val))
                else:
                    it.setText(str(val))
                if c == 2:
                    it.setBackground(QColor(g.get("colour", "#888")))
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    it.setToolTip("Double-click to change")
                t.setItem(i, c, it)
            for c in range(self.G_EDIT, len(self.G_COLS)):
                it = QTableWidgetItem()
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                t.setItem(i, c, it)
        t.resizeColumnsToContents()
        t.setColumnWidth(2, 50)
        t.setColumnWidth(self.G_COLS.index("Role"), 230)
        t.setColumnWidth(self.G_COLS.index("Alliance now"), 150)
        self._filling = False
        self._fill_groups_state(self.world.history[self.view_turn])

    def _fill_groups_state(self, snap):
        self._filling = True
        w = self.world
        total = sum(snap["power"][g] for g in snap["power"] if snap["alive"][g]) or 1
        owners = snap["owners"]
        # cumulative war record up to this turn
        rec = {gid: [0, 0, 0, 0] for gid in w.groups}
        for h in w.history[1:snap["turn"] + 1]:
            for war in h["wars"]:
                wins = war["attackers"] if war["attacker_won"] else war["defenders"]
                loses = war["defenders"] if war["attacker_won"] else war["attackers"]
                for m in wins:
                    rec[m][0] += 1
                for m in loses:
                    rec[m][1] += 1
                if war.get("moved"):
                    rec[war["moved"][2]][2] += 1
                    rec[war["moved"][1]][3] += 1
        for i, g in enumerate(self.scenario["groups"]):
            gid = g["id"]
            alive = snap["alive"].get(gid)
            aid = snap["alliance"].get(gid)
            vals = [_num(snap["power"][gid]) if alive else "-", f"{snap['power'][gid] / total:.1%}" if alive else "-",
                    f"{snap.get('productivity', {}).get(gid, 1.0):.2f}",
                    snap["alliances"][aid]["name"] if aid else "", snap["roles"].get(gid, ""),
                    str(sum(1 for o in owners.values() if o == gid)),
                    f"{rec[gid][0]} / {rec[gid][1]}", f"{rec[gid][2]} / {rec[gid][3]}",
                    str(sum(1 for rid in snap.get("unrest", {}) if owners.get(rid) == gid) or ""),
                    f"{snap.get('resentment', {}).get(gid, 0.0):.2f}" if snap.get("resentment", {}).get(gid) else "",
                    f"{snap['cohesion'][gid]:.2f}" if gid in snap.get("cohesion", {}) else "",
                    f"{snap['weariness'][gid]:.2f}" if snap.get("weariness", {}).get(gid, 0) >= 0.005 else "",
                    f"{snap['aggression'][gid]:.2f}" if gid in snap.get("aggression", {}) else "",
                    snap.get("strategy", {}).get(gid, "") if alive else "",
                    f"{snap['benevolence'][gid]:.2f}" if gid in snap.get("benevolence", {}) else "",
                    f"{snap['conduct'][gid]:+.2f}" if gid in snap.get("conduct", {}) else ""]
            for c, val in enumerate(vals):
                it = self.gtable.item(i, self.G_EDIT + c)
                if it:
                    it.setText(val)
        self._filling = False
        self._show_group_info(self.gtable.currentRow())

    def _show_group_info(self, row):
        if row is None or row < 0 or not self.scenario or row >= len(self.scenario["groups"]):
            self.ginfo.setHtml("<p>Select a Group to see its strategy explained.</p>"
                               + "".join(f"<p><b>{n}</b>: {html.escape(STRATEGIES[n]['gist'])}</p>" for n in STRATEGY_ORDER))
            return
        g = self.scenario["groups"][row]
        txt = strategy_info(g.get("strategy", "Balancer")).split("\n\n")
        regions = ", ".join(self.world.regions[r].name for r in g.get("regions", []) if r in self.world.regions)
        self.ginfo.setHtml(f"<h3>{html.escape(g.get('name', ''))} - {html.escape(txt[0])}</h3>"
                           f"<p><i>{html.escape(txt[1])}</i></p><p>{html.escape(txt[2])}</p>"
                           f"<p><b>Starting Regions:</b> {html.escape(regions)}</p>")

    def _strategy_edited(self, row, txt):
        if self._filling:
            return
        g = self.scenario["groups"][row]
        g["strategy"] = txt
        d = STRATEGIES[txt]
        g["aggression"] = d["aggression"]
        g["mobilisation"] = d["mobilisation"]
        self._filling = True
        self.gtable.item(row, 6).setData(Qt.ItemDataRole.EditRole, d["mobilisation"])
        self.gtable.item(row, 7).setData(Qt.ItemDataRole.EditRole, d["aggression"])
        self._filling = False
        self.statusBar().showMessage(f"{g['name']} is now a {txt} (its aggression and mobilisation set to that "
                                     f"strategy's defaults). Reset to turn 0.", 8000)
        self.reset(rebuild_map=False)
        self._show_group_info(row)

    def _group_edited(self, it):
        if self._filling or it.column() >= self.G_EDIT:
            return
        row, col = it.row(), it.column()
        g = self.scenario["groups"][row]
        if col == 0:
            g["name"] = it.text().strip() or g["id"]
        elif col == 1:
            g["short"] = it.text().strip()
        elif col in (4, 5, 6, 7, 8):
            key = {4: "power", 5: "growth", 6: "mobilisation", 7: "aggression", 8: "benevolence"}[col]
            try:
                val = float(it.data(Qt.ItemDataRole.EditRole))
            except (TypeError, ValueError):
                return
            if key != "power":
                val = min(1.0, max(0.0, val))
            g[key] = val
        elif col == 9:
            self._rebuild_alliances_from_table()
        self.reset(rebuild_map=False)
        self.statusBar().showMessage("Setup changed - back to turn 0.", 5000)

    def _rebuild_alliances_from_table(self):
        by = {}
        for i, g in enumerate(self.scenario["groups"]):
            it = self.gtable.item(i, 9)
            name = it.text().strip() if it else ""
            if name:
                by.setdefault(name, []).append(g["id"])
        pw = {g["id"]: g.get("power", 0) for g in self.scenario["groups"]}
        self.scenario["alliances"] = [dict(name=n, leader=max(m, key=lambda x: pw[x]), members=m)
                                      for n, m in by.items() if len(m) >= 2]

    def _group_dbl(self, row, col):
        if col != 2:
            return
        g = self.scenario["groups"][row]
        c = QColorDialog.getColor(QColor(g.get("colour", "#888")), self, f"Colour for {g['name']}")
        if not c.isValid():
            return
        g["colour"] = c.name()
        self._filling = True
        self.gtable.item(row, 2).setBackground(c)
        self._filling = False
        self.reset(rebuild_map=False)

    # regions ---------------------------------------------------------------
    def _fill_regions_setup(self):
        self._filling = True
        sc = self.scenario
        names = {r["id"]: r.get("name", r["id"]) for r in sc["regions"]}
        holder = {}
        for g in sc["groups"]:
            for r in g.get("regions", []):
                holder[r] = g["id"]
        t = self.rtable
        t.setRowCount(len(sc["regions"]))
        links = {rid: reg.links for rid, reg in self.world.regions.items()}
        for i, r in enumerate(sc["regions"]):
            it = QTableWidgetItem(names[r["id"]])
            t.setItem(i, 0, it)
            it = QTableWidgetItem()
            it.setData(Qt.ItemDataRole.EditRole, float(r.get("value", 10)))
            t.setItem(i, 1, it)
            cb = QComboBox()
            cb.addItem("(none)", None)
            for g in sc["groups"]:
                cb.addItem(g.get("name", g["id"]), g["id"])
            cb.setCurrentIndex(max(0, cb.findData(holder.get(r["id"]))))
            cb.currentIndexChanged.connect(lambda _, row=i, box=cb: self._holder_edited(row, box.currentData()))
            t.setCellWidget(i, 2, cb)
            it = QTableWidgetItem(", ".join(names[x] for x in links.get(r["id"], [])))
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            t.setItem(i, 3, it)
            for c in range(4, len(self.R_COLS)):
                it = QTableWidgetItem()
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                t.setItem(i, c, it)
        t.resizeColumnsToContents()
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._filling = False
        self._fill_regions_state(self.world.history[self.view_turn])

    def _fill_regions_state(self, snap):
        self._filling = True
        for i, r in enumerate(self.scenario["regions"]):
            o = snap["owners"].get(r["id"])
            ppl = snap.get("people", {}).get(r["id"])
            u = snap.get("unrest", {}).get(r["id"])
            vals = [self.world.groups[o].name if o else "", self.world.groups[ppl].name if ppl in self.world.groups else "",
                    f"{u['grievance']:.2f}" if u else "", f"{u.get('integration', 0.0):.0%}" if u else "",
                    f"{u['threat']:.1%}" if u else ""]
            for c, val in enumerate(vals):
                it = self.rtable.item(i, 4 + c)
                if it:
                    it.setText(val)
        self._filling = False

    def _region_edited(self, it):
        if self._filling:
            return
        r = self.scenario["regions"][it.row()]
        if it.column() == 0:
            r["name"] = it.text().strip() or r["id"]
            self.reset(rebuild_map=True)
        elif it.column() == 1:
            try:
                r["value"] = max(0.0, float(it.data(Qt.ItemDataRole.EditRole)))
            except (TypeError, ValueError):
                return
            self.reset(rebuild_map=False)

    def _holder_edited(self, row, gid):
        if self._filling:
            return
        rid = self.scenario["regions"][row]["id"]
        for g in self.scenario["groups"]:
            if rid in g.get("regions", []):
                g["regions"].remove(rid)
        if gid:
            for g in self.scenario["groups"]:
                if g["id"] == gid:
                    g.setdefault("regions", []).append(rid)
        self.reset(rebuild_map=False)
        self.statusBar().showMessage("Starting holder changed - back to turn 0.", 5000)

    # settings ---------------------------------------------------------------
    def _fill_settings(self):
        self._filling = True
        for name, sb in self.set_widgets.items():
            sb.setValue(getattr(self.settings, name))
        self.det_cb.setChecked(self.settings.deterministic)
        self.passage_cb.setChecked(self.settings.passage)
        self.era_combo.setCurrentText(era_of(self.settings))
        self._filling = False

    def _setting_changed(self, name, val):
        if self._filling:
            return
        cur = getattr(self.settings, name)
        setattr(self.settings, name, type(cur)(val))
        if self.world:
            self.world._clear_routes()
        self._filling = True
        self.era_combo.setCurrentText(era_of(self.settings))
        self._filling = False
        self.statusBar().showMessage(f"{name} = {val} (applies from the next turn)", 4000)

    def _pick_era(self, i):
        name = self.era_combo.itemText(i)
        if name not in ERAS:
            return
        vals = dict(air_range=0.0)
        vals.update(ERAS[name])
        for k, v in vals.items():
            setattr(self.settings, k, type(getattr(self.settings, k))(v))
        if self.world:
            self.world._clear_routes()
        self._fill_settings()
        self.statusBar().showMessage(f"Era of warfare: {name} (applies from the next turn)", 5000)

    def _restore_settings(self):
        seed = self.settings.seed
        fresh = Settings.from_dict(self.scenario.get("settings"))
        for f in fresh.to_dict():
            setattr(self.settings, f, getattr(fresh, f))
        self.settings.seed = seed
        self._fill_settings()

    # charts -------------------------------------------------------------------
    def _refresh_charts(self):
        w = self.world
        hist = w.history
        which = self.chart_pick.currentIndex()
        groups = self.scenario["groups"]
        self.chart_note.setText("Click a chart to show that turn on the map.")
        if which == 0:
            series = []
            for g in groups:
                vals = []
                for h in hist:
                    tot = sum(h["power"][x] for x in h["power"] if h["alive"][x]) or 1
                    vals.append(h["power"][g["id"]] / tot if h["alive"][g["id"]] else 0.0)
                series.append((g.get("name", g["id"]), g.get("colour", "#888"), vals))
            self.stacked.set_data(series, "Share of all Power, by Group")
            self.chart_stack.setCurrentWidget(self.stacked)
            self.stacked.set_marker(self.view_turn)
        elif which == 1:
            keys = {}
            for h in hist:
                for aid, a in h["alliances"].items():
                    keys[aid] = (a["name"], a["colour"])          # latest name
            seen = {}
            for aid, (name, col) in list(keys.items()):
                seen.setdefault(name, []).append(aid)
            for name, aids in seen.items():
                if len(aids) > 1:      # the same name at different times: tell them apart by founding round
                    for aid in aids:
                        first = next(h["turn"] for h in hist if aid in h["alliances"])
                        keys[aid] = (f"{name} (from round {first})", keys[aid][1])
            series = []
            for aid, (name, col) in keys.items():
                vals = []
                for h in hist:
                    tot = sum(h["power"][x] for x in h["power"] if h["alive"][x]) or 1
                    vals.append(sum(h["power"][m] for m in h["alliances"][aid]["members"]) / tot
                                if aid in h["alliances"] else 0.0)
                series.append((name, col, vals))
            vals = []
            for h in hist:
                tot = sum(h["power"][x] for x in h["power"] if h["alive"][x]) or 1
                vals.append(sum(h["power"][x] for x in h["power"] if h["alive"][x] and not h["alliance"][x]) / tot)
            series.append(("Unaligned", "#bbbbbb", vals))
            self.stacked.set_data(series, "Share of all Power, by alliance")
            self.chart_stack.setCurrentWidget(self.stacked)
            self.stacked.set_marker(self.view_turn)
        elif which == 2:
            series = [(g.get("name", g["id"]), g.get("colour", "#888"),
                       [h["power"][g["id"]] if h["alive"][g["id"]] else None for h in hist]) for g in groups]
            self.lines.set_data(series, "Power by Group", ylabel="Power", ymin=0, fmt="{:.1f}")
            self.chart_stack.setCurrentWidget(self.lines)
            self.lines.set_marker(self.view_turn)
        elif which == 3:
            P = [h["polarity"] for h in hist]
            series = [("Largest bloc's share", "#d1495b", [p["top_share"] for p in P]),
                      ("Balance (2nd pole / 1st)", "#2f6db5", [p["balance"] for p in P]),
                      ("Concentration of blocs", "#3a9a5b", [p["con_blocs"] for p in P]),
                      ("Concentration of Groups", "#e0a030", [p["con_groups"] for p in P])]
            self.lines.set_data(series, "Polarity measures", ylabel="0 to 1", ymin=0, ymax=1)
            self.chart_stack.setCurrentWidget(self.lines)
            self.lines.set_marker(self.view_turn)
        elif which == 5:
            pac, free, pac_now, free_now = [], [], [], []
            for t, h in enumerate(hist):
                if t == 0:
                    for lst in (pac, free, pac_now, free_now):
                        lst.append(None)
                    continue
                rs = running_stats(hist, t)
                st = h["stats"]
                a = st["alive"] or 1
                pac.append(rs["pacifism"])
                free.append(rs["freedom"])
                pac_now.append(1 - st["fighting"] / a)
                free_now.append(1 - st["bandwagoning"] / a)
            selfr = [None] + [running_stats(hist, t)["self_rule"] for t in range(1, len(hist))]
            series = [("Rate of pacifism (running)", "#3a9a5b", pac), ("Rate of freedom (running)", "#2f6db5", free),
                      ("Rate of self-determination (running)", "#c2672b", selfr),
                      ("Not at War this round", "#9fd3ae", pac_now), ("Not bandwagoning this round", "#a9c4e8", free_now)]
            self.lines.set_data(series, "Pacifism, freedom and self-determination", ylabel="share of Groups", ymin=0, ymax=1, fmt="{:.0%}", percent=True)
            self.chart_stack.setCurrentWidget(self.lines)
            self.lines.set_marker(self.view_turn)
        elif which == 6:
            st = [h["stats"] for h in hist]
            series = [("Occupied Regions", "#c2672b", [x.get("occupied", 0) for x in st]),
                      ("Armed uprisings", "#ff7a00", [x.get("uprisings", 0) - x.get("protests", 0) for x in st]),
                      ("Peaceful protests", "#2e9e4f", [x.get("protests", 0) for x in st]),
                      ("Liberations", "#3a9a5b", [x.get("liberations", 0) for x in st]),
                      ("Breakaways from blocs", "#7b4fa8", [x.get("breakaways", 0) for x in st]),
                      ("Subjugated peoples", "#5d6d7e", [x.get("subjugated", 0) for x in st]),
                      ("Violent upheavals at home", "#d1495b", [x.get("upheavals", 0) - x.get("home_protests", 0) for x in st]),
                      ("Peaceful changes of government", "#88a838", [x.get("home_protests", 0) for x in st]),
                      ("Alliance crises", "#1f9eb0", [x.get("crises", 0) for x in st]),
                      ("Occupation incidents", "#b04f8f", [x.get("incidents", 0) for x in st])]
            self.lines.set_data(series, "Unrest and rebellion", ylabel="count", ymin=0, fmt="{:.0f}")
            self.chart_stack.setCurrentWidget(self.lines)
            self.lines.set_marker(self.view_turn)
        elif which == 7:
            st = [h["stats"] for h in hist]
            series = [("Integration of occupied Regions", "#3a9a5b", [x.get("integration") for x in st]),
                      ("Cohesion of alliance followers", "#2f6db5", [x.get("cohesion") for x in st]),
                      ("War weariness (mean)", "#d1495b", [x.get("weariness", 0.0) for x in st]),
                      ("Resentment (mean, followers)", "#7b4fa8",
                       [(sum(h.get("resentment", {}).values()) / max(1, sum(len(a["members"]) - 1 for a in h["alliances"].values())))
                        for h in hist])]
            series.append(("Conduct (mean, -1 to +1)", "#e0a030", [x.get("conduct", 0.0) for x in st]))
            self.lines.set_data(series, "Integration, cohesion, conduct and war weariness", ylabel="level", fmt="{:.2f}")
            self.chart_stack.setCurrentWidget(self.lines)
            self.lines.set_marker(self.view_turn)
        elif which >= 8:
            from .scenarios import PALETTE
            zones = [z["name"] for z in w.zones]
            field, title, kw = [("poles", "Poles in each zone", dict(ylabel="poles", ymin=0, fmt="{:.0f}")),
                                ("top_share", "Largest bloc's share of the Power present in each zone",
                                 dict(ylabel="share", ymin=0, ymax=1, fmt="{:.0%}")),
                                ("penetration", "Share of each zone's Power held by outside Groups",
                                 dict(ylabel="share", ymin=0, ymax=1, fmt="{:.0%}"))][which - 8]
            series = []
            for i, zn in enumerate(zones):
                vals = []
                for h in hist:
                    zz = next((z for z in h.get("regional", []) if z["name"] == zn), None)
                    vals.append(zz[field] if zz else None)
                series.append((zn, PALETTE[(i * 3) % len(PALETTE)], vals))
            self.lines.set_data(series, title, **kw)
            self.chart_stack.setCurrentWidget(self.lines)
            self.lines.set_marker(self.view_turn)
        else:
            series = [("Poles", "#7b4fa8", [h["polarity"]["poles"] for h in hist]),
                      ("Wars this turn", "#c0182c", [len(h["wars"]) for h in hist]),
                      ("Blocs", "#1f9eb0", [h["polarity"]["n_blocs"] for h in hist]),
                      ("Groups left", "#5d6d7e", [h["polarity"]["n_alive"] for h in hist])]
            self.lines.set_data(series, "Poles, blocs and Wars", ylabel="count", ymin=0, fmt="{:.0f}")
            self.chart_stack.setCurrentWidget(self.lines)
            self.lines.set_marker(self.view_turn)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export history", os.path.expanduser("~/brink-history.csv"), "CSV (*.csv)")
        if not path:
            return
        w = self.world
        gids = [g["id"] for g in self.scenario["groups"]]
        with open(path, "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow(["turn", "system", "poles", "largest_bloc_share", "balance", "concentration_blocs",
                         "wars", "groups_fighting", "groups_bandwagoning", "groups_alive",
                         "rate_of_pacifism_running", "rate_of_freedom_running", "occupied_regions",
                         "mean_rebellion_threat", "uprisings", "liberations", "reborn", "breakaways", "rate_of_self_determination",
                         "subjugated", "integration", "cohesion", "war_weariness", "upheavals", "peaceful_protests",
                         "peaceful_home_changes", "alliance_crises",
                         "occupation_incidents", "mean_conduct", "neutrality_violations",
                         "violations_resisted"] + [f"power:{w.groups[g].name}" for g in gids] + [f"alliance:{w.groups[g].name}" for g in gids])
            for h in w.history:
                p = h["polarity"]
                wr.writerow([h["turn"], p["label"], p["poles"], round(p["top_share"], 4), round(p["balance"], 4),
                             round(p["con_blocs"], 4), len(h["wars"]), h["stats"]["fighting"],
                             h["stats"]["bandwagoning"], h["stats"]["alive"],
                             round(running_stats(w.history, h["turn"])["pacifism"], 4) if h["turn"] else "",
                             round(running_stats(w.history, h["turn"])["freedom"], 4) if h["turn"] else "",
                             h["stats"].get("occupied", 0), round(h["stats"].get("mean_threat", 0.0), 4),
                             h["stats"].get("uprisings", 0), h["stats"].get("liberations", 0), h["stats"].get("reborn", 0),
                             h["stats"].get("breakaways", 0), round(h["stats"].get("self_rule", 1.0), 4),
                             h["stats"].get("subjugated", 0),
                             "" if h["stats"].get("integration") is None else round(h["stats"]["integration"], 4),
                             "" if h["stats"].get("cohesion") is None else round(h["stats"]["cohesion"], 4),
                             round(h["stats"].get("weariness", 0.0), 4), h["stats"].get("upheavals", 0),
                             h["stats"].get("protests", 0), h["stats"].get("home_protests", 0),
                             h["stats"].get("crises", 0), h["stats"].get("incidents", 0),
                             round(h["stats"].get("conduct", 0.0), 4), h["stats"].get("violations", 0),
                             h["stats"].get("resisted", 0)]
                            + [round(h["power"][g], 3) if h["alive"][g] else "" for g in gids]
                            + [h["alliances"][h["alliance"][g]]["name"] if h["alliance"][g] else "" for g in gids])
        self.statusBar().showMessage(f"Wrote {path}", 6000)

    # many runs ----------------------------------------------------------------
    def _many(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancelled = True
            return
        st = copy.copy(self.settings)
        st.seed = self.seed.value()
        self.worker = ManyWorker(copy.deepcopy(self.scenario), st, self.many_runs.value(), self.many_turns.value())
        self.worker.progress.connect(lambda d, n: (self.many_bar.setMaximum(n), self.many_bar.setValue(d)))
        self.worker.finished_ok.connect(self._many_done)
        self.many_btn.setText("Cancel")
        self.worker.start()

    def _many_done(self, res):
        self.many_btn.setText("Run")
        n = max(1, res["runs"])
        labels = ", ".join(f"{k} {v / n:.0%}" for k, v in sorted(res["labels"].items(), key=lambda kv: -kv[1]))
        zl = "".join(f"<br>&nbsp;&nbsp;<b>{html.escape(zn)}</b>: " + ", ".join(
            f"{k} {v / n:.0%}" for k, v in sorted(d.items(), key=lambda kv: -kv[1])) for zn, d in res.get("zones", {}).items())
        self.many_summary.setText(f"<b>{res['runs']} runs of {res['turns']} turns.</b> System at the end: {labels}. "
                                  f"Mean poles at the end {res['poles']:.2f}; mean Wars per run {res['wars']:.1f}; "
                                  f"rate of pacifism {res['pacifism']:.1%}; rate of freedom {res['freedom']:.1%}; "
                                  f"rate of self-determination {res['unrest']['self_rule']:.1%}. Per run: {res['unrest']['uprisings']:.1f} "
                                  f"uprisings, {res['unrest']['liberations']:.1f} liberations, {res['unrest']['reborn']:.1f} "
                                  f"Groups reborn, {res['unrest']['breakaways']:.1f} breakaways, {res['unrest']['upheavals']:.1f} upheavals; "
                                  f"{res['unrest']['protests']:.1f} of the uprisings and {res['unrest']['home_protests']:.1f} "
                                  f"of the upheavals were peaceful."
                                  + (f"<br>Regional systems at the end:{zl}" if zl else ""))
        t = self.many_table
        t.setSortingEnabled(False)
        t.setRowCount(len(self.scenario["groups"]))
        for i, g in enumerate(self.scenario["groups"]):
            p = res["per"][g["id"]]
            vals = [g.get("name", g["id"]), g.get("strategy", ""), p["survived"] / n, p["share"], p["largest"] / n, p["pole"] / n]
            for c, val in enumerate(vals):
                it = QTableWidgetItem()
                if isinstance(val, float):
                    it.setData(Qt.ItemDataRole.DisplayRole, round(val * 100, 1))
                    it.setToolTip(f"{val:.1%}")
                else:
                    it.setText(val)
                if c == 0:
                    it.setForeground(QColor(g.get("colour", "#888")))
                t.setItem(i, c, it)
        t.setHorizontalHeaderLabels(["Group", "Strategy", "Survived %", "Mean final share %", "Largest at end %", "Pole at end %"])
        t.setSortingEnabled(True)
        t.resizeColumnsToContents()

    def closeEvent(self, ev):
        self.timer.stop()
        if self.worker and self.worker.isRunning():
            self.worker.cancelled = True
            self.worker.wait(3000)
        super().closeEvent(ev)


def main(argv):
    app = QApplication(argv)
    app.setApplicationName("Brink")
    app.setDesktopFileName("brink")
    icon = os.path.join(HERE, "icons", "brink.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    win = MainWindow()
    win.show()
    return app.exec()
