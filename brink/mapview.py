"""The map: Regions as coastline-clipped Voronoi cells coloured by holder (or
bloc), Group names with alliance tags, sea lanes, and this turn's Wars."""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPixmap,
                         QPolygonF)
from PyQt6.QtWidgets import QSizePolicy, QToolTip, QWidget

from . import geo

SEA = QColor("#cfe0ee")
SEA_DARK = QColor("#1c2a38")
UNHELD = QColor("#c8c8c8")


def _pale(c: QColor, f=0.55):
    return QColor(int(c.red() + (255 - c.red()) * f), int(c.green() + (255 - c.green()) * f),
                  int(c.blue() + (255 - c.blue()) * f))


class MapView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.world = None
        self.snap = None
        self.mode = "groups"           # or "blocs"
        self.show_region_names = False
        self.show_links = True
        self.show_wars = True
        self.show_zones = False
        self._W = self._H = 0
        self._idx = []
        self._borders = []
        self._sea_links = []
        self._rids = []
        self._pix = None
        self._rect = QRectF()

    # ---- geometry ---------------------------------------------------------
    def set_world(self, world):
        self.world = world
        sc = world.scenario
        m = sc.get("map", {})
        aspect = float(m.get("aspect", 1.5))
        radius = float(m.get("land_radius", 0.08))
        self._rids = [r["id"] for r in sc["regions"]]
        sites = [(r["x"], r["y"]) for r in sc["regions"]]
        width = 640
        self._W, self._H, self._idx = geo.raster(sites, aspect, radius, width, int(m.get("seed", 7)))
        self._borders = geo.borders(self._W, self._H, self._idx)
        sea = []
        for r in world.regions.values():
            for o in r.links:
                if r.id < o and world.is_sea(r.id, o):      # the same land/sea split the War routes use
                    sea.append((r.id, o))
        self._sea_links = sea
        self._base = bytes(255 if i < 0 else i for i in self._idx)
        self._zone_of = {rid: z["name"] for z in world.zones for rid in z["regions"]}
        self.snap = None
        self._pix = None

    def show_snapshot(self, snap):
        self.snap = snap
        self._compose()
        self.update()

    def set_zones(self, on):
        self.show_zones = on
        self._compose()
        self.update()

    def set_mode(self, mode):
        self.mode = mode
        self._compose()
        self.update()

    def _region_colour(self, rid):
        snap, w = self.snap, self.world
        owner = snap["owners"].get(rid)
        if owner is None:
            return UNHELD
        g = w.groups[owner]
        c = QColor(g.colour)
        if self.mode == "blocs":
            aid = snap["alliance"].get(owner)
            if aid:
                return QColor(snap["alliances"][aid]["colour"])
            return _pale(c, 0.6)
        if self.mode == "unrest":
            u = snap.get("unrest", {}).get(rid)
            if not u:
                return _pale(c, 0.78)
            t = min(1.0, u["threat"] / 0.3)        # 30% a round or more = full red
            lo, hi = QColor("#f3dc6b"), QColor("#b3001b")
            return QColor(int(lo.red() + (hi.red() - lo.red()) * t), int(lo.green() + (hi.green() - lo.green()) * t),
                          int(lo.blue() + (hi.blue() - lo.blue()) * t))
        if self.mode == "integration":
            u = snap.get("unrest", {}).get(rid)
            if not u:
                return _pale(c, 0.78)
            t = min(1.0, u.get("integration", 0.0))
            lo, hi = QColor("#c0182c"), QColor("#2e9e4f")
            return QColor(int(lo.red() + (hi.red() - lo.red()) * t), int(lo.green() + (hi.green() - lo.green()) * t),
                          int(lo.blue() + (hi.blue() - lo.blue()) * t))
        if self.mode == "spheres":
            key = snap.get("spheres", {}).get(rid)
            if not key:
                return QColor("#e4e4e4")
            col = QColor(snap["alliances"][key]["colour"]) if key in snap["alliances"] else QColor(w.groups[key].colour)
            mine = (snap["alliance"].get(owner) or owner) == key
            return col if mine else _pale(col, 0.5)
        return c

    def _compose(self):
        if not self.world or not self.snap:
            self._pix = None
            return
        W, H = self._W, self._H
        base = QImage(self._base, W, H, W, QImage.Format.Format_Indexed8)
        table = [SEA.rgba()] * 256
        for i, rid in enumerate(self._rids):
            table[i] = self._region_colour(rid).rgba()
        base.setColorTable(table)
        img = base.convertToFormat(QImage.Format.Format_ARGB32)
        over = bytearray(W * H)
        owners = self.snap["owners"]
        alli = self.snap["alliance"]
        zone_of = self._zone_of if self.show_zones else {}
        for k, a, b in self._borders:
            if b < 0:
                over[k] = 3
                continue
            if zone_of and zone_of.get(self._rids[a]) != zone_of.get(self._rids[b]):
                over[k] = 4
                continue
            oa, ob = owners.get(self._rids[a]), owners.get(self._rids[b])
            if oa != ob:
                if self.mode == "blocs" and oa and ob and alli.get(oa) and alli.get(oa) == alli.get(ob):
                    over[k] = 1
                else:
                    over[k] = 2
            else:
                over[k] = 1
        ov = QImage(bytes(over), W, H, W, QImage.Format.Format_Indexed8)
        ov.setColorTable([QColor(0, 0, 0, 0).rgba(), QColor(0, 0, 0, 45).rgba(),
                          QColor(20, 20, 30, 220).rgba(), QColor(40, 70, 100, 230).rgba(),
                          QColor(150, 20, 160, 255).rgba()] + [0] * 251)
        p = QPainter(img)
        p.drawImage(0, 0, ov)
        p.end()
        self._pix = QPixmap.fromImage(img)

    # ---- painting ---------------------------------------------------------
    def _map_rect(self):
        if not self._W:
            return QRectF(self.rect())
        m = 4
        aw, ah = self.width() - 2 * m, self.height() - 2 * m
        s = min(aw / self._W, ah / self._H)
        w, h = self._W * s, self._H * s
        return QRectF(m, m, w, h)            # hug the top-left corner, next to nothing wasted

    def _pt(self, rid):
        r = self.world.regions[rid]
        rc = self._rect
        return QPointF(rc.left() + r.x * rc.width(), rc.top() + r.y * rc.height())

    def _halo_text(self, p, centre, text, font, colour=QColor("#111"), halo=QColor(255, 255, 255, 210)):
        path = QPainterPath()
        fm = QFontMetricsF(font)
        w = fm.horizontalAdvance(text)
        path.addText(centre.x() - w / 2, centre.y() + fm.ascent() / 2 - 1, font, text)
        p.setPen(QPen(halo, 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawPath(path)

    def _place(self, c, text, font, placed, wide=False):
        """Nudge a label so it neither overlaps earlier labels nor leaves the map."""
        fm = QFontMetricsF(font)
        w, h = fm.horizontalAdvance(text) + 4, fm.height() * (1.2 if wide else 1.9)
        rc = self._rect
        best = None
        dys = (0, 0.5, -0.5, 1, -1, 1.5, -1.5) + ((2, -2, 2.5, -2.5, 3, -3, 4, -4) if wide else ())
        dxs = (0, 0.2, -0.2) + ((0.45, -0.45, 0.7, -0.7) if wide else ())
        for dy in dys:
            for dx in dxs:
                x = min(max(c.x() + dx * w, rc.left() + w / 2 + 2), rc.right() - w / 2 - 2)
                y = min(max(c.y() + dy * h * 0.5, rc.top() + h / 3), rc.bottom() - h * 0.75)
                box = QRectF(x - w / 2, y - h / 3, w, h)
                if not any(box.intersects(o) for o in placed):
                    placed.append(box)
                    return QPointF(x, y)
                if best is None:
                    best = (QPointF(x, y), box)
        placed.append(best[1])
        return best[0]

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pal = self.palette()
        p.fillRect(self.rect(), pal.color(pal.ColorRole.Window))
        if not self._pix:
            p.setPen(pal.color(pal.ColorRole.WindowText))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No scenario loaded")
            return
        self._rect = rc = self._map_rect()
        p.fillRect(rc, SEA)
        p.drawPixmap(rc, self._pix, QRectF(self._pix.rect()))
        w, snap = self.world, self.snap
        scale = rc.width() / 640

        if self.show_links:
            pen = QPen(QColor(40, 70, 110, 150), max(1.0, 1.3 * scale), Qt.PenStyle.DashLine)
            p.setPen(pen)
            for a, b in self._sea_links:
                p.drawLine(self._pt(a), self._pt(b))

        if self.show_region_names:
            f = QFont(self.font())
            f.setPointSizeF(max(6.0, 7.0 * scale))
            p.setFont(f)
            for rid in self._rids:
                c = self._pt(rid) + QPointF(0, 11 * scale)
                self._halo_text(p, c, w.regions[rid].name, f, QColor("#333"), QColor(255, 255, 255, 150))

        # Group labels at the holder's Region nearest its value-weighted centre.
        total = sum(snap["power"][g] for g in snap["power"] if snap["alive"].get(g)) or 1
        held = {}
        for rid, o in snap["owners"].items():
            if o:
                held.setdefault(o, []).append(rid)
        placed = []
        for gid, rids in sorted(held.items(), key=lambda kv: -snap["power"][kv[0]]):
            g = w.groups[gid]
            vs = [w.regions[r].value for r in rids]
            mx = sum(w.regions[r].x * v for r, v in zip(rids, vs)) / sum(vs)
            my = sum(w.regions[r].y * v for r, v in zip(rids, vs)) / sum(vs)
            anchor = min(rids, key=lambda r: (w.regions[r].x - mx) ** 2 + (w.regions[r].y - my) ** 2)
            c = self._pt(anchor)
            share = snap["power"][gid] / total
            f = QFont(self.font())
            f.setBold(True)
            f.setPointSizeF(max(6.5, (6.5 + 18 * math.sqrt(share)) * scale))
            p.setFont(f)
            label = g.short or g.name
            c = self._place(c, label, f, placed)
            self._halo_text(p, c, label, f)
            aid = snap["alliance"].get(gid)
            role = snap["roles"].get(gid, "")
            tag = ""
            colour = None
            if aid:
                al = snap["alliances"][aid]
                tag = "".join(wd[0] for wd in al["name"].split() if wd[0].isalnum())[:4].upper()
                if al["leader"] == gid:
                    tag = "★ " + tag
                colour = QColor(al["colour"])
            elif role == "Pole":
                tag, colour = "★ pole", QColor("#444")
            if tag:
                ft = QFont(self.font())
                ft.setPointSizeF(max(6.0, 7.0 * scale))
                ft.setBold(True)
                p.setFont(ft)
                fm = p.fontMetrics()
                tw = fm.horizontalAdvance(tag) + 8
                th = fm.height() + 1
                box = QRectF(c.x() - tw / 2, c.y() + f.pointSizeF() * 0.9, tw, th)
                p.setPen(QPen(QColor(255, 255, 255, 220), 1))
                p.setBrush(colour)
                p.drawRoundedRect(box, 4, 4)
                p.setPen(QColor("white"))
                p.drawText(box, Qt.AlignmentFlag.AlignCenter, tag)

        if self.show_zones:
            fz = QFont(self.font())
            fz.setPointSizeF(max(8.0, 11 * scale))
            fz.setBold(True)
            fz.setItalic(True)
            for z in w.zones:
                xs = [w.regions[r].x for r in z["regions"]]
                ys = [w.regions[r].y for r in z["regions"]]
                c = QPointF(rc.left() + sum(xs) / len(xs) * rc.width(), rc.top() + sum(ys) / len(ys) * rc.height())
                lab = z["name"].upper()
                c = self._place(c, lab, fz, placed, wide=True)
                self._halo_text(p, c, lab, fz, QColor(150, 20, 160), QColor(255, 255, 255, 200))

        if self.show_wars:
            for war in snap["wars"]:
                self._draw_war(p, war, scale)
            for up in snap.get("uprisings", []):
                self._draw_uprising(p, up, scale)

        p.setPen(QColor(0, 0, 0, 90))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rc)

    def _draw_war(self, p, war, scale):
        w = self.world
        th = war["theatre"]
        end = self._pt(th)
        att = war["attacker"]
        owners = self.snap["owners"]
        # attacker's Region nearest the theatre (owners as they were before any transfer)
        before = dict(owners)
        if war.get("moved"):
            rid, frm, to = war["moved"]
            before[rid] = frm
        own = [r for r, o in before.items() if o == att and r != th] or [r for r, o in before.items() if o == att]
        if not own:
            return
        col = QColor("#c0182c") if war["attacker_won"] else QColor("#555555")
        width = max(2.0, min(7.0, 1.5 + math.sqrt(war["fa"]) * 0.6)) * scale
        route = war.get("route") or []
        if len(route) >= 2:
            # follow the actual route: solid on land and sea, dotted on air legs
            violated = set(war.get("violated", []))
            for rid in route[1:-1]:
                if before.get(rid) in violated:                # marched through a third party's Region
                    c = self._pt(rid)
                    rr = 8 * scale + 3
                    p.setPen(QPen(QColor("#c0182c"), 2.2))
                    p.setBrush(QColor(255, 255, 255, 170))
                    p.drawEllipse(c, rr, rr)
                    p.drawLine(QPointF(c.x() - rr * 0.7, c.y() + rr * 0.7), QPointF(c.x() + rr * 0.7, c.y() - rr * 0.7))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(len(route) - 1):
                a_, b_ = route[i], route[i + 1]
                pa, pb = self._pt(a_), self._pt(b_)
                air = w.is_air(a_, b_)
                style = Qt.PenStyle.DotLine if air else Qt.PenStyle.SolidLine
                p.setPen(QPen(QColor(255, 255, 255, 200), width + 2.5, style, Qt.PenCapStyle.RoundCap))
                p.drawLine(pa, pb)
                p.setPen(QPen(col, width, style, Qt.PenCapStyle.RoundCap))
                p.drawLine(pa, pb)
            ctrl = self._pt(route[-2])
        else:
            src = min(own, key=lambda r: w.dist[r].get(th, 10 ** 6))
            start = self._pt(src)
            if (start - end).manhattanLength() < 2:
                return
            dx, dy = end.x() - start.x(), end.y() - start.y()
            L = math.hypot(dx, dy)
            nx, ny = -dy / L, dx / L
            ctrl = QPointF((start.x() + end.x()) / 2 + nx * L * 0.18, (start.y() + end.y()) / 2 + ny * L * 0.18)
            path = QPainterPath(start)
            path.quadTo(ctrl, end)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 200), width + 2.5, cap=Qt.PenCapStyle.RoundCap))
            p.drawPath(path)
            p.setPen(QPen(col, width, cap=Qt.PenCapStyle.RoundCap))
            p.drawPath(path)
        # arrowhead along the final tangent
        tx, ty = end.x() - ctrl.x(), end.y() - ctrl.y()
        tl = math.hypot(tx, ty) or 1
        tx, ty = tx / tl, ty / tl
        a = 9 * scale + width
        head = QPolygonF([end, QPointF(end.x() - tx * a - ty * a * 0.55, end.y() - ty * a + tx * a * 0.55),
                          QPointF(end.x() - tx * a + ty * a * 0.55, end.y() - ty * a - tx * a * 0.55)])
        p.setPen(QPen(QColor(255, 255, 255, 220), 1))
        p.setBrush(col)
        p.drawPolygon(head)
        if war.get("moved"):
            c = self._pt(war["moved"][0])
            r = 7 * scale + 3
            star = QPolygonF()
            for i in range(10):
                ang = -math.pi / 2 + i * math.pi / 5
                rr = r if i % 2 == 0 else r * 0.45
                star.append(QPointF(c.x() + rr * math.cos(ang), c.y() + rr * math.sin(ang)))
            p.setPen(QPen(QColor("#222"), 1))
            p.setBrush(QColor("#ffd23f"))
            p.drawPolygon(star)

    def _draw_uprising(self, p, up, scale):
        c = self._pt(up["region"]) + QPointF(0, -14 * scale)
        r = 9 * scale + 3
        if up.get("peaceful"):
            # a peaceful protest: a green disc, no burst
            p.setPen(QPen(QColor("#1b5e20"), 1.4))
            p.setBrush(QColor("#7bd389"))
            p.drawEllipse(c, r * 0.85, r * 0.85)
            f = QFont(self.font())
            f.setBold(True)
            f.setPointSizeF(max(6.0, 7.5 * scale))
            p.setFont(f)
            p.setPen(QColor("#1b5e20"))
            p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, "P")
            return
        burst = QPolygonF()
        for i in range(16):
            ang = -math.pi / 2 + i * math.pi / 8
            rr = r if i % 2 == 0 else r * 0.55
            burst.append(QPointF(c.x() + rr * math.cos(ang), c.y() + rr * math.sin(ang)))
        p.setPen(QPen(QColor("#222"), 1.2))
        p.setBrush(QColor("#ff7a00") if up["won"] else QColor(255, 255, 255, 230))
        p.drawPolygon(burst)
        f = QFont(self.font())
        f.setBold(True)
        f.setPointSizeF(max(6.0, 7.5 * scale))
        p.setFont(f)
        p.setPen(QColor("#222"))
        p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, "!")

    # ---- hover ------------------------------------------------------------
    def region_at(self, pos):
        rc = self._rect
        if not self._W or not rc.contains(pos):
            return None
        px = int((pos.x() - rc.left()) / rc.width() * self._W)
        py = int((pos.y() - rc.top()) / rc.height() * self._H)
        if not (0 <= px < self._W and 0 <= py < self._H):
            return None
        i = self._idx[py * self._W + px]
        return self._rids[i] if i >= 0 else None

    def mouseMoveEvent(self, ev):
        if not self.snap:
            return
        rid = self.region_at(ev.position())
        if rid is None:
            QToolTip.hideText()
            return
        w, snap = self.world, self.snap
        r = w.regions[rid]
        o = snap["owners"].get(rid)
        lines = [f"<b>{r.name}</b> &nbsp;(value {r.value:g})"]
        if o:
            g = w.groups[o]
            total = sum(snap["power"][x] for x in snap["power"] if snap["alive"].get(x)) or 1
            lines.append(f"held by <b>{g.name}</b> &mdash; {g.strategy}")
            lines.append(f"Power {snap['power'][o]:.1f} ({snap['power'][o] / total:.1%} of all)")
            aid = snap["alliance"].get(o)
            if aid:
                lines.append(f"in the {snap['alliances'][aid]['name']}")
            lines.append(f"role: {snap['roles'].get(o, '')}")
            extra = []
            if o in snap.get("conduct", {}):
                extra.append(f"conduct {snap['conduct'][o]:+.2f}")
            if o in snap.get("cohesion", {}):
                extra.append(f"cohesion {snap['cohesion'][o]:.2f}")
            if snap.get("weariness", {}).get(o, 0) >= 0.005:
                extra.append(f"war weariness {snap['weariness'][o]:.2f}")
            if extra:
                lines.append(", ".join(extra))
        people = snap.get("people", {}).get(rid)
        u = snap.get("unrest", {}).get(rid)
        if u:
            pn = w.groups[people].name if people in w.groups else "?"
            lines.append(f"<span style='color:#b3001b'>occupied: home of the {pn} people; grievance "
                         f"{u['grievance']:.2f}, integration {u.get('integration', 0.0):.0%}, rebellion threat "
                         f"{u['threat']:.0%} a round</span>")
        nb = ", ".join(w.regions[x].name for x in r.links)
        lines.append(f"<span style='color:#666'>next to: {nb}</span>")
        QToolTip.showText(ev.globalPosition().toPoint(), "<br>".join(lines), self)
