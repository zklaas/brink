"""QPainter charts: line chart and stacked-share chart, each series with its own colour."""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QSizePolicy, QToolTip, QWidget


def nice_ticks(lo, hi, n=5):
    if hi <= lo:
        hi = lo + 1
    step = 10 ** math.floor(math.log10((hi - lo) / n))
    for m in (1, 2, 2.5, 5, 10):
        if (hi - lo) / (step * m) <= n:
            step *= m
            break
    t = math.ceil(lo / step) * step
    out = []
    while t <= hi + 1e-9:
        out.append(round(t, 10))
        t += step
    return out


class _Base(QWidget):
    turnClicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.series = []          # (label, colour, values)
        self.title = self.xlabel = self.ylabel = ""
        self.marker = None        # turn shown on the map
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._plot = QRectF()
        self._n = 0
        self._lo, self._hi = 0.0, 1.0
        self.fmt = "{:.2f}"

    def set_marker(self, t):
        self.marker = t
        self.update()

    def _frame(self, p, lo, hi, n, percent=False):
        pal = self.palette()
        fg = pal.color(pal.ColorRole.WindowText)
        fm = p.fontMetrics()
        left, top, right, bottom = 56, 28, 16, 40
        legend_w = 0
        if len(self.series) > 1:
            legend_w = min(230, max(fm.horizontalAdvance(s[0]) for s in self.series) + 30)
        r = QRectF(left, top, max(10, self.width() - left - right - legend_w), max(10, self.height() - top - bottom))
        self._plot = r
        self._n = n
        self._lo, self._hi = lo, hi
        p.setPen(fg)
        if self.title:
            f = QFont(p.font())
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(0, 4, self.width(), 20), Qt.AlignmentFlag.AlignHCenter, self.title)
            p.setFont(self.font())
        grid = QColor(fg)
        grid.setAlpha(40)
        for t in nice_ticks(lo, hi):
            y = r.bottom() - (t - lo) / (hi - lo) * r.height()
            p.setPen(QPen(grid, 1))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.setPen(fg)
            lab = f"{t:.0%}" if percent else f"{t:g}"
            p.drawText(QRectF(0, y - 8, left - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, lab)
        for t in nice_ticks(0, max(1, n - 1), 8):
            x = r.left() + t / max(1, n - 1) * r.width()
            p.drawText(QRectF(x - 30, r.bottom() + 2, 60, 16), Qt.AlignmentFlag.AlignHCenter, f"{t:g}")
        p.drawText(QRectF(r.left(), r.bottom() + 18, r.width(), 18), Qt.AlignmentFlag.AlignHCenter, self.xlabel)
        p.save()
        p.translate(12, r.center().y())
        p.rotate(-90)
        p.drawText(QRectF(-r.height() / 2, -10, r.height(), 20), Qt.AlignmentFlag.AlignHCenter, self.ylabel)
        p.restore()
        p.setPen(QPen(fg, 1))
        p.drawLine(r.bottomLeft(), r.bottomRight())
        p.drawLine(r.bottomLeft(), r.topLeft())
        if legend_w:
            y = top
            for label, col, _ in self.series:
                if y > self.height() - 20:
                    break
                p.fillRect(QRectF(r.right() + 12, y + 2, 12, 8), QColor(col))
                p.setPen(fg)
                p.drawText(QRectF(r.right() + 28, y - 2, legend_w - 30, 16), Qt.AlignmentFlag.AlignVCenter,
                           fm.elidedText(label, Qt.TextElideMode.ElideRight, legend_w - 30))
                y += 17
        return r, fg

    def _x(self, k):
        r = self._plot
        return r.left() + k / max(1, self._n - 1) * r.width()

    def _y(self, v):
        r = self._plot
        return r.bottom() - (min(max(v, self._lo), self._hi) - self._lo) / (self._hi - self._lo) * r.height()

    def _draw_marker(self, p, fg):
        if self.marker is None or self._n < 2:
            return
        x = self._x(self.marker)
        c = QColor(fg)
        c.setAlpha(120)
        p.setPen(QPen(c, 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(x, self._plot.top()), QPointF(x, self._plot.bottom()))

    def _k_at(self, pos):
        r = self._plot
        if not self.series or not r.contains(pos):
            return None
        return max(0, min(self._n - 1, round((pos.x() - r.left()) / r.width() * max(1, self._n - 1))))

    def mousePressEvent(self, ev):
        k = self._k_at(ev.position())
        if k is not None:
            self.turnClicked.emit(k)

    def mouseMoveEvent(self, ev):
        k = self._k_at(ev.position())
        if k is None:
            return
        rows = []
        for label, _, s in sorted(self.series, key=lambda t: -(t[2][k] if k < len(t[2]) and t[2][k] is not None else -1e9))[:14]:
            if k < len(s) and s[k] is not None:
                rows.append(f"{label}: {self.fmt.format(s[k])}")
        QToolTip.showText(ev.globalPosition().toPoint(), f"{self.xlabel} {k}\n" + "\n".join(rows), self)


class LineChart(_Base):
    def set_data(self, series, title="", xlabel="Turn", ylabel="", ymin=None, ymax=None, fmt="{:.2f}", percent=False):
        self.series, self.title, self.xlabel, self.ylabel = series, title, xlabel, ylabel
        self.ymin, self.ymax, self.fmt, self.percent = ymin, ymax, fmt, percent
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        p.fillRect(self.rect(), pal.color(pal.ColorRole.Base))
        if not self.series:
            p.setPen(pal.color(pal.ColorRole.WindowText))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data yet")
            return
        vals = [v for _, _, s in self.series for v in s if v is not None]
        lo = self.ymin if self.ymin is not None else min(vals)
        hi = self.ymax if self.ymax is not None else max(vals)
        if hi - lo < 1e-9:
            hi = lo + 1
        n = max(len(s) for _, _, s in self.series)
        r, fg = self._frame(p, lo, hi, n, getattr(self, "percent", False))
        for label, col, s in self.series:
            path = QPainterPath()
            first = True
            for k, v in enumerate(s):
                if v is None:
                    first = True
                    continue
                pt = QPointF(self._x(k), self._y(v))
                if first:
                    path.moveTo(pt)
                    first = False
                else:
                    path.lineTo(pt)
            p.setPen(QPen(QColor(col), 2))
            p.drawPath(path)
        self._draw_marker(p, fg)


class StackedChart(_Base):
    """Shares that add to 1 at every turn, stacked bottom to top."""

    def set_data(self, series, title="", xlabel="Turn", ylabel="Share of all Power"):
        self.series, self.title, self.xlabel, self.ylabel = series, title, xlabel, ylabel
        self.fmt = "{:.1%}"
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        p.fillRect(self.rect(), pal.color(pal.ColorRole.Base))
        if not self.series:
            p.setPen(pal.color(pal.ColorRole.WindowText))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data yet")
            return
        n = max(len(s) for _, _, s in self.series)
        r, fg = self._frame(p, 0.0, 1.0, n, percent=True)
        base = [0.0] * n
        edge = QColor(pal.color(pal.ColorRole.Base))
        for label, col, s in self.series:
            top = [base[k] + (s[k] or 0.0) for k in range(n)]
            poly = QPolygonF([QPointF(self._x(k), self._y(top[k])) for k in range(n)] +
                             [QPointF(self._x(k), self._y(base[k])) for k in reversed(range(n))])
            p.setPen(QPen(edge, 0.6))
            p.setBrush(QColor(col))
            p.drawPolygon(poly)
            base = top
        self._draw_marker(p, fg)
