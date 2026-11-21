#!/usr/bin/env python3
"""Draws the animated GIFs of the lessons into docs/lessons/gifs/.

Needs Pillow (pip install pillow). Run from anywhere:
    python3 docs/lessons/make_gifs.py              # every GIF
    python3 docs/lessons/make_gifs.py gitops       # only the ones named
    GIF_SHEETS=/some/dir python3 ...               # also save one still per caption, to review quickly
Each GIF is a timeline: draw(c, t) paints the frame at t seconds, and the caption list explains each step.
Change a caption or a timing, rerun, and commit the GIF together with the change.
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H, S, FPS = 960, 540, 2, 14  # logical size, supersampling (smooth edges), frames per second
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gifs")

BG, INK, MUTED, LINE, WHITE = (250, 249, 246), (31, 35, 40), (101, 109, 118), (208, 215, 222), (255, 255, 255)
GRAY_BG = (238, 240, 243)
BLUE, BLUE_BG = (47, 111, 235), (222, 234, 255)
GREEN, GREEN_BG = (26, 140, 76), (219, 243, 228)
RED, RED_BG = (207, 52, 52), (252, 226, 226)
AMBER, AMBER_BG = (190, 120, 0), (255, 239, 204)
PURPLE, PURPLE_BG = (110, 64, 230), (236, 230, 255)
TEAL, TEAL_BG = (0, 120, 120), (222, 242, 240)
ORANGE, ORANGE_BG = (215, 85, 30), (253, 231, 218)
TERM, TERM_INK = (24, 28, 33), (215, 220, 226)

# shortcut: Segoe UI on Windows, DejaVu on Linux; DejaVu is a little wider, so layouts keep slack and the
# caption check below fails loudly if a caption no longer fits. Bundle one font if GIFs must match exactly.
FONTS = {
    "sans": ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "bold": ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "mono": ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"],
}
_fonts = {}


def font(kind, size):
    if (kind, size) not in _fonts:
        path = next((p for p in FONTS[kind] if os.path.exists(p)), None)
        _fonts[kind, size] = ImageFont.truetype(path, size * S) if path else ImageFont.load_default(size * S)
    return _fonts[kind, size]


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def seg(t, a, b):
    """0 before a, 1 after b, linear in between."""
    return clamp((t - a) / (b - a))


def ease(p):
    return p * p * (3 - 2 * p)


def pulse(t, a, b, edge=0.25):
    """0 -> 1 -> 0 over [a, b]: a highlight that fades in and out."""
    return ease(seg(t, a, a + edge)) * (1 - ease(seg(t, b - edge, b)))


def mix(a, b, p):
    p = clamp(p)
    return tuple(round(a[i] + (b[i] - a[i]) * p) for i in range(3))


def along(pts, p):
    """The point at fraction p of the way along a polyline."""
    lens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    d = clamp(p) * sum(lens)
    for i, seg_len in enumerate(lens):
        if d <= seg_len or i == len(lens) - 1:
            f = d / seg_len if seg_len else 0
            return pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f
        d -= seg_len


def frac_to(pts, k):
    """Fraction of the polyline's length used to reach point k."""
    lens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    return sum(lens[:k]) / sum(lens)


class Canvas:
    """Draws in logical 960x540 coordinates on a 2x image, shrunk at the end for smooth edges."""

    def __init__(self):
        self.im = Image.new("RGB", (W * S, H * S), BG)
        self.d = ImageDraw.Draw(self.im)

    def box(self, x, y, w, h, fill=None, outline=None, r=10, width=2):
        self.d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], radius=r * S, fill=fill,
                                 outline=outline, width=round(width * S) if outline else 0)

    def line(self, pts, color, width=2):
        self.d.line([(px * S, py * S) for px, py in pts], fill=color, width=round(width * S), joint="curve")

    def dashed(self, x, y, w, h, color, width=2, dash=9, gap=6):
        for x1, y1, x2, y2 in ((x, y, x + w, y), (x + w, y, x + w, y + h), (x + w, y + h, x, y + h), (x, y + h, x, y)):
            length, n = math.dist((x1, y1), (x2, y2)), 0.0
            while n < length:
                a, b = n / length, min(n + dash, length) / length
                self.line([(x1 + (x2 - x1) * a, y1 + (y2 - y1) * a), (x1 + (x2 - x1) * b, y1 + (y2 - y1) * b)], color, width)
                n += dash + gap

    def circle(self, cx, cy, r, fill=None, outline=None, width=2):
        self.d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=fill, outline=outline,
                       width=round(width * S) if outline else 0)

    def text(self, x, y, s, size=16, color=INK, kind="sans", anchor="mm"):
        self.d.text((x * S, y * S), s, font=font(kind, size), fill=color, anchor=anchor)

    def tw(self, s, size=16, kind="sans"):
        return self.d.textlength(s, font=font(kind, size)) / S

    def arrow(self, x1, y1, x2, y2, color, width=3, head=11, p=1.0):
        if p <= 0:
            return
        ex, ey = x1 + (x2 - x1) * p, y1 + (y2 - y1) * p
        ang = math.atan2(ey - y1, ex - x1)
        self.line([(x1, y1), (ex - head * 0.7 * math.cos(ang), ey - head * 0.7 * math.sin(ang))], color, width)
        tip = [(ex, ey)] + [(ex - head * math.cos(ang + s), ey - head * math.sin(ang + s)) for s in (-0.45, 0.45)]
        self.d.polygon([(px * S, py * S) for px, py in tip], fill=color)

    def frame(self):
        return self.im.resize((W, H), Image.Resampling.LANCZOS)


# ---------- shared pieces ----------

def dot(c, x, y, color=BLUE, r=7):
    c.circle(x, y, r + 2, WHITE)
    c.circle(x, y, r, color)


POD_COLORS = {"run": (GREEN, GREEN_BG), "start": (AMBER, AMBER_BG), "dead": (RED, RED_BG),
              "new": (BLUE, BLUE_BG), "off": (MUTED, GRAY_BG)}


def pod(c, cx, cy, label, state="run", a=1.0, bg=WHITE, w=84, h=38, size=13):
    if a <= 0.01:
        return
    edge, fill = POD_COLORS[state]
    c.box(cx - w / 2, cy - h / 2, w, h, mix(bg, fill, a), mix(bg, edge, a), r=8)
    c.text(cx, cy, label, size, mix(bg, INK, a), "bold")
    if state == "dead":
        k, d = mix(bg, RED, a), h / 2 - 7
        c.line([(cx - d, cy - d), (cx + d, cy + d)], k, 3)
        c.line([(cx - d, cy + d), (cx + d, cy - d)], k, 3)


def life(t, born, died=None, starting=0.7, fade=0.7):
    """A pod's (state, opacity) at t: starting, then running; once dead it stays red 1 s, then fades out."""
    if t < born:
        return None, 0
    if died is not None and t >= died:
        return "dead", 1 - seg(t, died + 1.0, died + 1.0 + fade)
    return ("start" if t < born + starting else "run"), ease(seg(t, born, born + 0.25))


def mark(c, cx, cy, ok=True, r=13, a=1.0, bg=BG):
    if a <= 0.01:
        return
    c.circle(cx, cy, r, mix(bg, GREEN if ok else RED, a))
    w = mix(bg, WHITE, a)
    if ok:
        c.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.48, cy - r * 0.36)], w, 3)
    else:
        d = r * 0.4
        c.line([(cx - d, cy - d), (cx + d, cy + d)], w, 3)
        c.line([(cx - d, cy + d), (cx + d, cy - d)], w, 3)


def spinner(c, cx, cy, t, r=10, color=BLUE, bg=BG):
    for i in range(8):
        ang = i / 8 * 2 * math.pi
        fade = ((i / 8 - t * 1.5) % 1)
        c.circle(cx + r * math.cos(ang), cy + r * math.sin(ang), 2.6, mix(bg, color, 1 - fade))


def browser(c, x, y, w, h, url, a=1.0, bg=BG, hot=False):
    c.box(x, y, w, h, mix(bg, WHITE, a), mix(bg, LINE, a), r=8)
    c.box(x, y, w, 22, mix(bg, GRAY_BG, a), None, r=8)
    for i, col in enumerate((RED, AMBER, GREEN)):
        c.circle(x + 12 + i * 12, y + 11, 3.5, mix(bg, col, a))
    c.box(x + 10, y + 32, w - 20, 24, mix(bg, BLUE_BG if hot else GRAY_BG, a), None, r=6)
    c.text(x + 17, y + 44, url, 12, mix(bg, INK, a), "mono", "lm")
    c.text(x + w / 2, y + h - 15, "browser", 12, mix(bg, MUTED, a))


def wrap(c, s, size, maxw):
    lines, cur = [], ""
    for word in s.split():
        trial = (cur + " " + word).strip()
        if cur and c.tw(trial, size) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def chrome(c, t, title, tag, caps):
    """Title on top; at the bottom, the caption of the current step."""
    c.text(32, 38, title, 25, INK, "bold", "lm")
    c.text(928, 38, tag, 14, MUTED, "sans", "rm")
    i = next((k for k, cap in enumerate(caps) if cap[0] <= t < cap[1]), len(caps) - 1)
    start, text = caps[i][0], caps[i][2]
    label = caps[i][3] if len(caps[i]) > 3 else str(i + 1)
    fade = ease(seg(t, start, start + 0.35)) if start > 0 else 1
    c.box(24, 462, 912, 62, INK, r=12)
    c.circle(58, 493, 17, BLUE)
    c.text(58, 493, label, 17 if len(label) == 1 else 12, WHITE, "bold")
    lines = wrap(c, text, 19, 820)
    size, ys = (19, [493]) if len(lines) == 1 else (17, [481, 505])
    if size == 17:
        lines = wrap(c, text, 17, 820)
    for y, s in zip(ys, lines):
        c.text(88, y, s, size, mix(INK, WHITE, fade), "sans", "lm")


def check_layout(name, seconds, title, tag, caps):
    """Self-check: captions tile the timeline and fit in two lines; the title fits beside its tag."""
    c = Canvas()
    assert caps[0][0] == 0 and abs(caps[-1][1] - seconds) < 1e-9, f"{name}: captions must cover 0..{seconds}"
    for cap, nxt in zip(caps, caps[1:]):
        assert cap[1] == nxt[0], f"{name}: gap or overlap after {cap[2]!r}"
    for cap in caps:
        assert len(wrap(c, cap[2], 17, 820)) <= 2, f"{name}: caption too long: {cap[2]!r}"
    assert 32 + c.tw(title, 25, "bold") + 24 + c.tw(tag, 14) < 928, f"{name}: title and tag overlap"


# ---------- overview ----------

NODES_OV = [(244, "lab-control-plane", "control plane: the brain"), (463, "lab-worker", "worker: runs your apps"),
            (682, "lab-worker2", "worker: runs your apps")]
PODS_OV = [(523, 262, "echo"), (619, 262, "echo"), (523, 306, "echo"), (619, 306, "Prometheus"),
           (742, 262, "echo"), (838, 262, "Argo CD"), (742, 306, "Grafana"), (838, 306, "echo"),
           (742, 350, "Alertmanager")]
PROM_OV, ENVOY_OV = (619, 306), (349, 351)


def g_overview(c, t):
    a1, a2, a3, a4 = (ease(seg(t, s, s + 1)) for s in (0, 2.5, 5, 7.5))
    trips = [(13.2, (523, 262)), (15.0, (742, 262))]
    hot = any(0 < seg(t, s, s + 1.6) < 0.35 for s, _ in trips)
    c.box(24, 70, 912, 380, mix(BG, GRAY_BG, a1), mix(BG, LINE, a1))
    c.text(40, 89, "Windows (your PC)", 15, mix(BG, INK, a1), "bold", "lm")
    browser(c, 40, 112, 154, 88, "echo.localtest.me", a1, GRAY_BG, hot)
    if a2:
        c.box(210, 100, 714, 340, mix(GRAY_BG, TEAL_BG, a2), mix(GRAY_BG, TEAL, a2))
        c.text(226, 117, "WSL2: a real Linux (Ubuntu) inside Windows", 14, mix(GRAY_BG, TEAL, a2), "bold", "lm")
    if a3:
        c.box(224, 132, 686, 296, mix(TEAL_BG, BLUE_BG, a3), mix(TEAL_BG, BLUE, a3))
        c.text(240, 149, "Docker Engine: runs containers", 14, mix(TEAL_BG, BLUE, a3), "bold", "lm")
    if a4:
        c.dashed(234, 162, 666, 256, mix(BLUE_BG, PURPLE, a4))
        c.text(250, 178, 'kind cluster "lab": 3 containers that act as servers', 13, mix(BLUE_BG, PURPLE, a4), "bold", "lm")
        for x, name, sub in NODES_OV:
            c.box(x, 192, 209, 218, mix(BLUE_BG, WHITE, a4), mix(BLUE_BG, LINE, a4))
            c.text(x + 12, 210, name, 14, mix(WHITE, INK, a4), "bold", "lm")
            c.text(x + 12, 229, sub, 12, mix(WHITE, MUTED, a4), "sans", "lm")
        x = 256
        for name in ("API", "etcd", "scheduler"):
            w = c.tw(name, 12) + 16
            c.box(x, 244, w, 24, mix(WHITE, PURPLE_BG, a4), None, r=6)
            c.text(x + w / 2, 256, name, 12, mix(WHITE, PURPLE, a4), "bold")
            x += w + 6
        c.box(256, 282, 74, 26, WHITE, mix(WHITE, INK, a4), r=6, width=1.5)
        c.text(293, 295, "port 80", 12, mix(WHITE, INK, a4), "mono")
        c.box(256, 326, 185, 50, mix(WHITE, BLUE_BG, a4), mix(WHITE, BLUE, a4))
        c.text(348, 351, "Envoy: the front door", 13, mix(WHITE, INK, a4), "bold")
    if 17 <= t < 20.5:  # Prometheus collects from every pod
        fade = pulse(t, 17, 20.5, 0.4)
        targets = [p[:2] for p in PODS_OV if p[2] != "Prometheus"] + [ENVOY_OV]
        for x, y in targets:
            c.line([(x, y), PROM_OV], mix(WHITE, (240, 160, 120), fade), 2)
        for k, (x, y) in enumerate(targets):
            px, py = along([(x, y), PROM_OV], ((t - 17) * 0.9 + k * 0.13) % 1)
            dot(c, px, py, mix(WHITE, ORANGE, fade), 5)
    for k, (x, y, label) in enumerate(PODS_OV):
        state, a = life(t, 10.5 + 0.22 * k, starting=0.5)
        if state:
            pod(c, x, y, label, state, a, w=90, h=36, size=12 if label != "Alertmanager" else 11)
    state, a = life(t, 21.8, starting=0.8)
    if state:
        pod(c, 523, 350, "echo", "new" if state == "start" else state, a, w=90, h=36, size=12)
    for start, target in trips:
        p = seg(t, start, start + 1.6)
        if 0 < p < 1:
            path = [(194, 156), (293, 295), ENVOY_OV, target]
            c.line(path, (160, 190, 245), 2)
            dot(c, *along(path, ease(p)))
    if t >= 20:
        g = ease(seg(t, 20, 20.6))
        c.box(786, 14, 142, 44, mix(BG, INK, g), None)
        c.text(857, 36, "GitHub: the code", 13, mix(BG, WHITE, g), "bold")
        c.arrow(857, 58, 838, 243, PURPLE, 3, p=ease(seg(t, 20.3, 21.3)))
        if t >= 21.3:
            c.text(846, 86, "Argo CD pulls main", 12, mix(GRAY_BG, PURPLE, seg(t, 21.3, 21.8)), "bold", "rm")


CAPS_OVERVIEW = [
    (0, 2.5, "Everything runs on this one PC. Start from the outside: Windows, with your browser."),
    (2.5, 5, "WSL2 runs a real Linux (Ubuntu) inside Windows. Lesson 1."),
    (5, 7.5, "Docker runs inside that Linux. It starts containers: sealed boxes, each holding one app. Lesson 1."),
    (7.5, 10.5, "kind starts 3 containers that act as servers. Together they form a Kubernetes cluster. Lesson 2."),
    (10.5, 13, "Kubernetes runs your apps as pods on the two workers, and replaces any pod that dies. Lesson 2."),
    (13, 17, "You open echo.localtest.me: the request enters on port 80, and Envoy picks an echo pod. Lesson 3."),
    (17, 20, "Prometheus collects numbers from every pod; Grafana draws them; Alertmanager warns you. Lesson 4."),
    (20, 23.5, "Argo CD copies what GitHub says into the cluster; ./lab check tests every change on your PC first. "
               "Lessons 5 and 6."),
    (23.5, 27, "That is the whole lab. Each lesson zooms into one layer, and lesson 7 shows how to debug it."),
]


# ---------- lesson 1: containers ----------

LAYERS = [("settings", PURPLE_BG), ("the program", BLUE_BG), ("base files", GREEN_BG)]
SLOTS_C = [455, 615, 775]


def slot_state(k, t):
    born = 6.6 + 1.1 * k
    if k == 1 and t >= 10.2:
        if t < 12.6:
            return "dead", 1 - seg(t, 11.3, 12.2)
        born = 12.6
    if t < born:
        return None, 0
    if t < born + 0.7:
        return "ghost", seg(t, born, born + 0.7)
    return "run", 1


def g_containers(c, t):
    a1, a2, a3 = ease(seg(t, 0, 1)), ease(seg(t, 2, 3)), ease(seg(t, 4, 5))
    c.box(24, 70, 912, 380, mix(BG, GRAY_BG, a1), mix(BG, LINE, a1))
    c.text(40, 89, "Windows (your PC)", 15, mix(BG, INK, a1), "bold", "lm")
    if a2:
        c.box(52, 104, 856, 334, mix(GRAY_BG, TEAL_BG, a2), mix(GRAY_BG, TEAL, a2))
        c.text(68, 121, "WSL2: a real Linux (Ubuntu 24.04) inside Windows", 14, mix(GRAY_BG, TEAL, a2), "bold", "lm")
    if not a3:
        return
    c.box(76, 138, 808, 288, mix(TEAL_BG, BLUE_BG, a3), mix(TEAL_BG, BLUE, a3))
    c.text(92, 155, "Docker Engine", 14, mix(TEAL_BG, BLUE, a3), "bold", "lm")
    c.box(100, 178, 210, 228, mix(BLUE_BG, WHITE, a3), mix(BLUE_BG, LINE, a3))
    c.text(205, 199, "image", 15, mix(WHITE, INK, a3), "bold")
    c.text(205, 220, "agnhost:2.53", 13, mix(WHITE, MUTED, a3), "mono")
    for i, (name, fill) in enumerate(LAYERS):
        drop = ease(seg(t, 4.6 + 0.4 * (2 - i), 5.0 + 0.4 * (2 - i)))
        y = 252 + i * 38 - (1 - drop) * 30
        if drop:
            c.box(118, y, 174, 32, mix(WHITE, fill, drop), mix(WHITE, LINE, drop), r=6)
            c.text(205, y + 16, name, 13, mix(WHITE, INK, drop), "bold")
    c.text(205, 386, "a frozen recipe (read-only)", 12, mix(WHITE, MUTED, ease(seg(t, 5.6, 6.2))))
    for k, cx in enumerate(SLOTS_C):
        state, p = slot_state(k, t)
        if state == "ghost":
            q = ease(p)
            x0, y0 = 118 + (cx - 70 - 118) * q, 252 + (190 - 252) * q
            w0, h0 = 174 + (140 - 174) * q, 108 + (200 - 108) * q
            c.box(x0, y0, w0, h0, mix(BLUE_BG, WHITE, 0.5), BLUE, r=8)
            c.text(x0 + w0 / 2, y0 + h0 / 2, "copying...", 12, BLUE, "bold")
        elif state:
            a = p
            edge = GREEN if state == "run" else RED
            c.box(cx - 70, 190, 140, 200, mix(BLUE_BG, WHITE, a), mix(BLUE_BG, edge, a))
            c.text(cx, 210, f"container {k + 1}", 14, mix(WHITE, INK, a), "bold")
            for i, (name, fill) in enumerate(LAYERS):
                c.box(cx - 52, 230 + i * 24, 104, 20, mix(WHITE, fill, a), None, r=5)
            c.text(cx, 314, "+ its own scratch space", 11, mix(WHITE, MUTED, a))
            if state == "run":
                c.circle(cx - 30, 352, 6, mix(WHITE, GREEN, a))
                c.text(cx - 18, 352, "running", 13, mix(WHITE, GREEN, a), "bold", "lm")
            else:
                c.text(cx, 352, "deleted", 13, mix(WHITE, RED, a), "bold")
                d = 46
                c.line([(cx - d, 236), (cx + d, 296)], mix(WHITE, RED, a), 3)
                c.line([(cx - d, 296), (cx + d, 236)], mix(WHITE, RED, a), 3)


CAPS_CONTAINERS = [
    (0, 2, "Your PC runs Windows."),
    (2, 4, "WSL2 adds a real Linux inside it: a light virtual machine that you open like a terminal."),
    (4, 6.5, "Docker stores images. An image is a frozen recipe: the files and the program, read-only."),
    (6.5, 10.2, "docker run makes a container: a running copy of the image, sealed off from the others."),
    (10.2, 12.6, "Delete a container and whatever it changed is gone. The image itself never changes."),
    (12.6, 15, "Start it again from the same image: you get the exact same box. That is what makes containers reliable."),
    (15, 17.5, "Containers share Linux's kernel instead of booting a whole OS, so they start in about a second."),
]


# ---------- lesson 2: kubernetes ----------

CHIPS_K = [("API server", "the front desk"), ("etcd", "the memory"), ("scheduler", "picks a node"),
           ("controllers", "fix differences")]
GLOW_K = [[(1.8, 2.7)], [(2.3, 3.1)], [(3.0, 7.0)], [(11.6, 12.8)]]
SLOTS_K = [(312, 350), (652, 350), (422, 350), (762, 350), (532, 350)]


def g_kubernetes(c, t):
    c.box(32, 84, 196, 130, WHITE, LINE)
    c.text(48, 104, "You", 16, INK, "bold", "lm")
    c.text(212, 104, "kubectl apply", 12, MUTED, "mono", "rm")
    c.box(48, 124, 164, 74, AMBER_BG, None, r=6)
    for i, s in enumerate(("kind: Deployment", "name: echo", "replicas: 5")):
        c.text(58, 141 + i * 20, s, 12, INK, "mono", "lm")
    c.box(256, 84, 672, 130, PURPLE_BG, PURPLE)
    c.text(272, 104, "lab-control-plane: the brain", 15, PURPLE, "bold", "lm")
    for i, (name, sub) in enumerate(CHIPS_K):
        x, g = 272 + i * 164, max(pulse(t, a, b) for a, b in GLOW_K[i])
        c.box(x, 124, 156, 74, mix(WHITE, AMBER_BG, g), mix(LINE, AMBER, g))
        c.text(x + 78, 150, name, 14, INK, "bold")
        c.text(x + 78, 174, sub, 12, MUTED)
    for x, name in ((256, "lab-worker"), (596, "lab-worker2")):
        c.box(x, 236, 332, 190, WHITE, LINE)
        c.text(x + 16, 258, name, 14, INK, "bold", "lm")
        c.text(x + 16, 278, "worker node (a Docker container)", 12, MUTED, "sans", "lm")
    p = ease(seg(t, 0.6, 2.0))
    if 0 < p < 1:
        x, y = along([(130, 161), (350, 161)], p)
        c.box(x - 34, y - 18, 68, 36, AMBER_BG, AMBER, r=6)
        c.text(x, y, "echo x5", 12, INK, "bold")
    pods = [(SLOTS_K[i], f"echo {i + 1}", 3.2 + 0.8 * i, 9.6 if i == 2 else None, (678, 198)) for i in range(5)]
    pods.append((SLOTS_K[2], "echo 6", 12.4, None, (842, 198)))
    running = 0
    for (x, y), label, born, died, src in pods:
        q = seg(t, born - 0.4, born)
        if 0 < q and t < born + 0.5:
            c.line([src, along([src, (x, y - 19)], q)], mix(WHITE, AMBER, 1 - seg(t, born + 0.1, born + 0.5)), 2)
        state, a = life(t, born, died)
        if state:
            pod(c, x, y, label, state, a, w=90)
            running += state == "run"
    col = GREEN if running == 5 else (RED if t > 9 else AMBER)
    c.box(32, 236, 196, 130, WHITE, LINE)
    c.text(48, 266, "wanted", 14, MUTED, "sans", "lm")
    c.text(212, 266, "5", 28, INK, "bold", "rm")
    c.line([(48, 296), (212, 296)], LINE, 1)
    c.text(48, 330, "running", 14, MUTED, "sans", "lm")
    c.text(212, 330, str(running), 28, col, "bold", "rm")


CAPS_KUBERNETES = [
    (0, 3, 'You write down what you want: "echo, 5 copies". The API server stores it in etcd, the cluster\'s memory.'),
    (3, 7.5, "The scheduler picks a worker for each copy (a pod) and spreads them out. Each pod starts, then runs."),
    (7.5, 9.6, "Wanted 5, running 5. Nothing to do."),
    (9.6, 11.6, "A pod crashes, or its node dies. Only 4 are running now."),
    (11.6, 14.5, "A controller sees that 4 is not 5 and makes a new pod. No human had to step in."),
    (14.5, 19, "This loop never stops: compare what you asked for with what runs, then fix the difference."),
]


# ---------- lesson 3: traffic ----------

ROWS_T = [("echo.*", "echo"), ("grafana.*", "Grafana"), ("argocd.*", "Argo CD"), ("prometheus.*", "Prometheus")]
ECHO_T = [(700, 140 + 44 * i) for i in range(5)]
GRAFANA_T = (694, 399)


def path_t(row, target):
    if target == "grafana":
        return [(204, 170), (340, 170), (472, 197 + 38 * row), (600, 197 + 38 * row), (600, 399), GRAFANA_T]
    return [(204, 170), (340, 170), (472, 197 + 38 * row), (645, ECHO_T[target][1])]


TRIPS_T = ([(5.9 + 0.55 * j, 1.4, 0, j % 5) for j in range(1, 10)] + [(11.3, 2.0, 1, "grafana")]
           + [(14.8 + 0.6 * k, 1.4, 0, i) for k, i in enumerate((0, 2, 3, 4))])


def g_traffic(c, t):
    first = path_t(0, 0)
    f_row = frac_to(first, 2)
    p_first = f_row * ease(seg(t, 0.4, 2.6)) + (1 - f_row) * ease(seg(t, 5.5, 6.3))
    dots, hot_rows, arrivals = [], set(), {i: [6.3] if i == 0 else [] for i in range(5)}
    if 0.4 < t < 6.3:
        dots.append(along(first, p_first))
    if 2.4 < t < 5.7:
        hot_rows.add(0)
    url, hot = ("grafana.localtest.me" if 11 <= t < 14 else "echo.localtest.me"), 0.4 < t < 1.6
    for start, dur, row, target in TRIPS_T:
        pts = path_t(row, target)
        p = seg(t, start, start + dur)
        if target != "grafana":
            arrivals[target].append(start + dur)
        if 0 < p < 1:
            dots.append(along(pts, p))
            fr = frac_to(pts, 2)
            if fr - 0.18 < p < fr + 0.12:
                hot_rows.add(row)
            hot = hot or p < 0.25
    browser(c, 32, 120, 172, 100, url, hot=hot)
    c.text(284, 140, "the door", 12, MUTED)
    c.box(228, 152, 112, 36, WHITE, INK, r=6, width=1.5)
    c.text(284, 170, "localhost:80", 12, INK, "mono")
    c.box(364, 96, 216, 250, BLUE_BG, BLUE)
    c.text(472, 120, "Envoy", 17, INK, "bold")
    c.text(472, 142, "the gateway", 12, MUTED)
    c.text(380, 168, "routes (HTTPRoutes)", 11, MUTED, "sans", "lm")
    for i, (host, app) in enumerate(ROWS_T):
        h = 1.0 if i in hot_rows else 0.0
        c.box(380, 182 + i * 38, 184, 30, mix(WHITE, AMBER_BG, h), mix(LINE, AMBER, h), r=6, width=1.5)
        c.text(388, 197 + i * 38, host, 11, INK, "mono", "lm")
        c.text(556, 197 + i * 38, "-> " + app, 11, INK, "mono", "rm")
    c.box(620, 84, 308, 266, WHITE, LINE)
    c.text(636, 104, "echo: 5 pods behind one Service", 13, INK, "bold", "lm")
    for i, (x, y) in enumerate(ECHO_T):
        n = sum(1 for at in arrivals[i] if at <= t)
        down = i == 1 and t >= 14.2
        state = "dead" if down else ("new" if any(at <= t < at + 0.35 for at in arrivals[i]) else "run")
        pod(c, x, y, f"echo-{i + 1}", state, w=110, h=36)
        note = f"{n} request" + ("" if n == 1 else "s")
        c.text(772, y, note + (" - not ready" if down else ""), 12, RED if down else MUTED, "sans", "lm")
    g = pulse(t, 13.3, 14.2, 0.15)
    c.box(620, 368, 148, 62, mix(ORANGE_BG, BLUE_BG, g), mix(ORANGE, BLUE, g))
    c.text(694, 399, "Grafana", 14, INK, "bold")
    c.box(780, 368, 148, 62, PURPLE_BG, PURPLE)
    c.text(854, 399, "Argo CD", 14, INK, "bold")
    for x, y in dots:
        dot(c, x, y)


CAPS_TRAFFIC = [
    (0, 3, "You type echo.localtest.me. That name points back to your own PC, so the request enters at localhost:80."),
    (3, 5.5, "Envoy, the gateway, reads the name you typed and looks up its routes: echo.* goes to the echo pods."),
    (5.5, 11, "Each request goes to the next pod in turn (round robin). The work is shared: that is load balancing."),
    (11, 14, "Another name, same door: grafana.localtest.me is routed to Grafana instead."),
    (14, 18.5, "A pod fails its health check? Envoy stops sending it requests until it is healthy again."),
]


# ---------- lesson 4: monitoring ----------

TARGETS_M = [("echo pods", "requests, memory"), ("nodes", "CPU, disk, network"), ("Envoy", "traffic, latency"),
             ("kube-state-metrics", "pods wanted vs ready")]


def echo_avail(t):
    if t < 8.5:
        return 5
    if t < 14.5:
        return 5 - 3 * seg(t, 8.5, 9.0)
    return 2 + 3 * seg(t, 14.5, 15.0)


def g_monitoring(c, t):
    c.box(32, 84, 204, 290, WHITE, LINE)
    c.text(48, 104, "targets", 14, INK, "bold", "lm")
    c.text(48, 122, "things that expose numbers", 11, MUTED, "sans", "lm")
    for k, (name, sub) in enumerate(TARGETS_M):
        y = 140 + k * 56
        c.line([(222, y + 22), (276, 205)], (240, 205, 188), 2)
        c.box(46, y, 176, 44, GRAY_BG, None, r=8)
        c.text(58, y + 15, name, 13, INK, "bold", "lm")
        c.text(58, y + 32, sub, 11, MUTED, "sans", "lm")
    c.box(276, 120, 180, 170, ORANGE_BG, ORANGE)
    c.text(366, 146, "Prometheus", 16, INK, "bold")
    for i, s in enumerate(("asks every target", "every 30 seconds,", "keeps 3 days of it")):
        c.text(366, 178 + i * 20, s, 12, MUTED)
    c.text(366, 258, "the collector", 12, ORANGE, "bold")
    for k in range(4):
        ph = (t - k * 0.12) % 1.5
        if ph < 0.6:
            dot(c, *along([(222, 162 + k * 56), (276, 205)], ph / 0.6), ORANGE, 5)
    c.arrow(456, 200, 494, 200, ORANGE, 3)
    c.line([(366, 290), (366, 310)], LINE, 2)
    v = echo_avail(t)
    state, wait = ("OK", 0) if v >= 3 else (("Pending", seg(t, 8.85, 11.5)) if t < 11.5 else ("Firing", 1))
    col, fill = {"OK": (GREEN, GREEN_BG), "Pending": (AMBER, AMBER_BG), "Firing": (RED, RED_BG)}[state]
    c.box(276, 310, 180, 120, WHITE, LINE)
    c.text(366, 330, "alert rule", 13, INK, "bold")
    c.text(366, 352, "echo pods < 3", 12, INK, "mono")
    c.text(366, 370, "for 2 minutes", 12, INK, "mono")
    c.box(306, 384, 120, 28, fill, col, r=14)
    c.text(366, 398, state, 13, col, "bold")
    if state == "Pending":
        c.box(306, 418, 120, 5, GRAY_BG, None, r=2)
        c.box(306, 418, max(5, 120 * wait), 5, AMBER, None, r=2)
    c.box(496, 84, 432, 236, WHITE, LINE)
    c.text(512, 104, "Grafana: echo pods available", 14, INK, "bold", "lm")
    vcol = GREEN if v >= 3 else RED
    c.text(912, 104, f"{round(v)} pods", 14, vcol, "bold", "rm")
    gx0, gx1, gy = 532, 912, (lambda val: 300 - val * 29)
    c.line([(gx0, 126), (gx0, 300), (gx1, 300)], LINE, 1.5)
    for val in (0, 3, 6):
        c.text(524, gy(val), str(val), 11, MUTED, "sans", "rm")
    x = gx0
    while x < gx1:
        c.line([(x, gy(3)), (min(x + 8, gx1), gy(3))], RED, 1.5)
        x += 14
    c.text(908, gy(3) - 10, "alert line: 3", 11, RED, "sans", "rm")
    pts = [(gx0 + tt / 19 * (gx1 - gx0), gy(echo_avail(tt))) for tt in [i / 10 for i in range(int(t * 10) + 1)]]
    if len(pts) > 1:
        c.line(pts, BLUE, 3)
    c.circle(*pts[-1], 5, BLUE)
    firing = state == "Firing"
    c.arrow(456, 370, 494, 385, RED, 3, p=ease(seg(t, 11.5, 11.9)) if firing else 0)
    c.box(496, 340, 432, 90, RED_BG if firing else WHITE, RED if firing else LINE)
    bx = 540 + (2 * math.sin(t * 40) if firing else 0)
    bell = RED if firing else MUTED
    c.box(bx - 11, 368, 22, 26, bell, None, r=11)
    c.box(bx - 15, 388, 30, 5, bell, None, r=2)
    c.circle(bx, 398, 3.5, bell)
    c.text(572, 372, "Alertmanager", 14, INK, "bold", "lm")
    if firing:
        msg, mcol = "ALERT: EchoReplicasMissing (2 pods, needs 3)", RED
    elif t >= 14.7:
        msg, mcol = "resolved: echo is back to 5 pods", GREEN
    else:
        msg, mcol = "quiet: nothing to report", MUTED
    c.text(572, 396, msg, 12, mcol, "bold" if firing else "sans", "lm")


CAPS_MONITORING = [
    (0, 4, 'Every 30 seconds Prometheus asks each target: "what are your numbers now?" It pulls; the apps just answer.'),
    (4, 8.5, "Each answer is stored with its time. Grafana reads them and draws graphs, like this one."),
    (8.5, 11.5, "echo drops to 2 pods, under the line. The rule waits 2 minutes first, so a short blip wakes nobody."),
    (11.5, 14.5, "Still too low after 2 minutes: the alert fires, and Alertmanager tells a human (chat, mail or pager)."),
    (14.5, 19, "The pods come back and the alert clears by itself. (This lab has no receiver yet: that is an exercise.)"),
]


# ---------- lesson 5: gitops ----------

SLOTS_G = [(682, 170), (774, 170), (866, 170), (682, 226), (774, 226)]


def argo_status(t):
    for end, s in ((4, "Synced"), (6.8, "OutOfSync"), (8.4, "Syncing"), (11.2, "Synced"), (14.4, "OutOfSync"),
                   (16.4, "Syncing")):
        if t < end:
            return s
    return "Synced"


def g_gitops(c, t):
    replicas = 3 if t < 4 else 5
    c.box(32, 84, 264, 270, WHITE, LINE)
    c.box(32, 84, 264, 40, INK, None)
    c.text(48, 104, "GitHub: main branch", 14, WHITE, "bold", "lm")
    c.text(48, 142, "apps/echo/echo.yaml", 12, MUTED, "mono", "lm")
    h = pulse(t, 4, 7.2)
    c.box(40, 244, 248, 24, mix(WHITE, AMBER_BG, h), None, r=4)
    for i, s in enumerate(("kind: Deployment", "metadata:", "  name: echo", "spec:", f"  replicas: {replicas}")):
        c.text(48, 168 + i * 22, s, 13, INK, "mono", "lm")
    c.text(48, 290, "history", 11, MUTED, "sans", "lm")
    c.text(48, 310, "- echo: 3 copies", 12, INK, "mono", "lm")
    if t >= 4:
        c.text(48, 330, "- PR merged: echo to 5 copies", 12, mix(WHITE, INK, seg(t, 4, 4.4)), "mono", "lm")
    status = argo_status(t)
    col, fill = {"Synced": (GREEN, GREEN_BG), "OutOfSync": (AMBER, AMBER_BG), "Syncing": (BLUE, BLUE_BG)}[status]
    c.box(340, 130, 236, 180, PURPLE_BG, PURPLE)
    c.text(458, 154, "Argo CD", 17, INK, "bold")
    c.text(458, 178, "compares Git with the cluster,", 12, MUTED)
    c.text(458, 196, "then makes them match", 12, MUTED)
    c.box(378, 216, 160, 34, fill, col, r=17)
    c.text(458, 233, status + ("." * (int(t * 3) % 4) if status == "Syncing" else ""), 14, col, "bold")
    c.text(318, 186, "reads", 11, MUTED)
    c.arrow(298, 200, 338, 200, PURPLE, 3)
    c.text(598, 206, "applies", 11, MUTED)
    c.arrow(578, 220, 618, 220, PURPLE, 3)
    if 4 < t < 4.7:
        dot(c, *along([(298, 200), (338, 200)], seg(t, 4, 4.7)), AMBER, 6)
    if status == "Syncing":
        dot(c, *along([(578, 220), (618, 220)], (t * 1.5) % 1), BLUE, 6)
    c.box(620, 84, 308, 270, WHITE, LINE)
    c.text(636, 104, "cluster", 14, INK, "bold", "lm")
    c.text(636, 124, "echo pods", 12, MUTED, "sans", "lm")
    running = 0
    for i, (x, y) in enumerate(SLOTS_G):
        first = -10 if i < 3 else 7.0 + 0.4 * (i - 3)  # 3 pods from the start, 2 more after the sync
        if i == 0 or t < 11.0:
            state, a = life(t, first)
        elif t < 14.6:  # the hand edit kills slots 1-4
            state, a = life(t, first, died=11.0)
        else:  # selfHeal brings them back
            state, a = life(t, 14.6 + 0.3 * (i - 1))
        if state:
            pod(c, x, y, "echo", state, a)
            running += state == "run"
    c.text(774, 300, f"Git wants {replicas}, running {running}", 15, GREEN if running == replicas else AMBER, "bold")
    hand = pulse(t, 10, 14.2, 0.3)
    if hand:
        c.box(620, 372, 308, 58, mix(BG, AMBER_BG, hand), mix(BG, AMBER, hand))
        c.text(636, 388, "someone, by hand:", 11, mix(BG, MUTED, hand), "sans", "lm")
        c.text(636, 410, "$ kubectl scale deploy/echo --replicas=1", 12, mix(BG, INK, hand), "mono", "lm")


CAPS_GITOPS = [
    (0, 4, "Git says: 3 copies of echo. The cluster runs 3. Argo CD compares both: Synced."),
    (4, 6.8, "You merge a pull request that says 5. Git and the cluster now differ: OutOfSync."),
    (6.8, 10, "Argo CD applies what Git says. Two new pods start, and it is Synced again."),
    (10, 14.4, "Someone changes the cluster by hand: kubectl scale to 1. The cluster no longer matches Git."),
    (14.4, 17.5, "selfHeal: Argo CD puts the cluster back to what Git says. Hand edits never stick."),
    (17.5, 21, "So to change anything, change Git. Its history is your undo button: revert the commit."),
]


# ---------- lesson 6: delivery ----------

STATIONS_D = [("branch", "your change", ""), ("./lab check", "on your PC", ""), ("push", "the hook checks", "once more"),
              ("CI", "GitHub checks", "on its machines"), ("review", "a human reads", "the diff"),
              ("merge", "into main", "(owner, CI green)"), ("Argo CD", "deploys it", "")]
MOVES_D = [(0, 0), (2.5, 0), (3.3, 1), (5.6, 1), (6.4, 0), (6.6, 0), (7.4, 1), (9.0, 1), (9.8, 2), (11.6, 2),
           (12.4, 3), (14.6, 3), (15.4, 4), (16.6, 4), (17.2, 5), (17.8, 5), (18.4, 6)]
MARKS_D = [(0, 2.4, True), (1, 8.2, True), (2, 11.0, True), (3, 14.0, True), (4, 16.2, True), (5, 17.4, True),
           (6, 19.0, True)]
SPIN_D = [(1, 3.3, 4.8), (1, 7.4, 8.2), (2, 9.8, 11.0), (3, 12.4, 14.0), (4, 15.4, 16.2)]
PITCH_D, BOX_D = 132, 118


def sx(k):
    return 25 + k * PITCH_D + BOX_D / 2


def g_delivery(c, t):
    last = len(STATIONS_D) - 1
    for k, (name, sub, sub2) in enumerate(STATIONS_D):
        x = 25 + k * PITCH_D
        done = any(s == k and t >= at for s, at, _ in MARKS_D)
        c.box(x, 196, BOX_D, 120, GREEN_BG if done else WHITE, GREEN if done else LINE)
        c.circle(x + 18, 214, 11, INK)
        c.text(x + 18, 214, str(k + 1), 12, WHITE, "bold")
        c.text(x + BOX_D / 2, 240, name, 14, INK, "mono" if name.startswith(".") else "bold")
        c.text(x + BOX_D / 2, 262, sub, 11, MUTED)
        if sub2:
            c.text(x + BOX_D / 2, 278, sub2, 11, MUTED)
        if k < last:
            c.arrow(x + BOX_D + 1, 256, x + PITCH_D - 1, 256, LINE, 2, head=7)
    for i in range(3):
        state, a = life(t, MARKS_D[-1][1] + 0.3 * i, starting=0.4)
        if state:
            pod(c, sx(last) - 32 + i * 32, 298, "", state, a, GREEN_BG, w=24, h=18)
    for k, at, ok in MARKS_D:
        mark(c, sx(k), 340, ok, a=ease(seg(t, at, at + 0.25)))
    if 4.8 <= t < 6.4:
        mark(c, sx(1), 340, False, a=ease(seg(t, 4.8, 5.05)) * (1 - seg(t, 6.0, 6.4)))
    for k, a, b in SPIN_D:
        if a <= t < b:
            spinner(c, sx(k), 340, t)
    for (x0, x1, label) in ((25 + PITCH_D, 25 + 3 * PITCH_D + BOX_D, "CI: every change tested, here and on GitHub"),
                            (25 + 5 * PITCH_D, 25 + 6 * PITCH_D + BOX_D, "CD: ship what passed")):
        c.line([(x0, 372), (x0, 380), (x1, 380), (x1, 372)], MUTED, 1.5)
        c.text((x0 + x1) / 2, 398, label, 13, MUTED, "bold")
    pos = 0.0
    for (t0, s0), (t1, s1) in zip(MOVES_D, MOVES_D[1:]):
        if t0 <= t < t1:
            pos = s0 + (s1 - s0) * ease(seg(t, t0, t1))
            break
    else:
        pos = MOVES_D[-1][1]
    cx = sx(0) + pos * PITCH_D
    failed = 4.8 <= t < 6.4
    c.box(cx - 46, 142, 92, 36, RED_BG if failed else BLUE_BG, RED if failed else BLUE, r=8)
    c.text(cx, 160, "fix it!" if failed else "my change", 13, RED if failed else INK, "bold")


CAPS_DELIVERY = [
    (0, 2.5, "You change files on a branch, never straight on main.", "1"),
    (2.5, 6.5, "./lab check tests the change on your PC. Red? Fix it now, before anyone else sees it.", "2"),
    (6.5, 9, "Fixed and checked again: green.", "2"),
    (9, 11.5, "git push runs ./lab check once more (a pre-push hook), then you open a PR.", "3"),
    (11.5, 14.5, "CI: GitHub runs the same check on its own machines, for every PR. Nobody can skip it.", "4"),
    (14.5, 18, "A human reads the diff. The owner merges, and main accepts it only when CI is green.", "5-6"),
    (18, 22, "Argo CD sees the new main and deploys it. CI tested the change; CD shipped it.", "7"),
]


# ---------- lesson 7: troubleshooting ----------

RUNGS_T = [("kubectl get pods -A", "what is unhealthy?"), ("kubectl get events", "what happened?"),
           ("kubectl describe pod", "the pod's whole story"), ("kubectl logs --previous", "what the app said")]
TERM_LINES = [
    (0.4, "note", "# echo.localtest.me: some requests fail. Why?"),
    (3.3, "cmd", "kubectl get pods -A"),
    (4.6, "clue", "default   echo-5c9f-x2   0/1   CrashLoopBackOff   4 restarts"),
    (7.3, "cmd", "kubectl get events --sort-by=.lastTimestamp"),
    (8.6, "clue", "Warning  BackOff  pod/echo-5c9f-x2  restarting failed container"),
    (11.3, "cmd", "kubectl describe pod echo-5c9f-x2"),
    (12.6, "out", "Last State:  Terminated   Reason: Error"),
    (12.9, "clue", "Exit Code:   1"),
    (15.3, "cmd", "kubectl logs echo-5c9f-x2 --previous"),
    (16.6, "bad", "Error: unknown flag: --http-portt"),
    (19.3, "note", "# fix the typo in Git, merge; Argo CD rolls it out"),
    (20.2, "cmd", "kubectl get pods -l app=echo"),
    (21.4, "good", "5 echo pods   1/1   Running"),
]
TERM_COLORS = {"note": (139, 148, 158), "out": TERM_INK, "clue": (255, 200, 87), "bad": (255, 123, 114),
               "good": (126, 231, 135), "cmd": TERM_INK}


def g_troubleshooting(c, t):
    for k, (cmd, sub) in enumerate(RUNGS_T):
        y = 92 + k * 84
        active, done = 3 + 4 * k <= t < 7 + 4 * k, t >= 7 + 4 * k
        c.box(32, y, 300, 70, BLUE_BG if active else WHITE, BLUE if active else LINE)
        c.circle(58, y + 35, 15, BLUE if active else (GREEN if done else MUTED))
        c.text(58, y + 35, str(k + 1), 14, WHITE, "bold")
        c.text(84, y + 25, cmd, 13, INK, "mono", "lm")
        c.text(84, y + 48, sub, 12, MUTED, "sans", "lm")
        if done:
            mark(c, 308, y + 35, a=ease(seg(t, 7 + 4 * k, 7.3 + 4 * k)), r=11, bg=WHITE)
        if k < 3:
            c.arrow(182, y + 71, 182, y + 83, LINE, 2, head=7)
    c.box(356, 84, 572, 346, TERM, None, r=12)
    for i, col in enumerate((RED, AMBER, GREEN)):
        c.circle(376 + i * 16, 102, 5, col)
    c.text(642, 102, "terminal", 12, (139, 148, 158))
    y = 132
    shown = [line for line in TERM_LINES if line[0] <= t]
    for i, (at, kind, text) in enumerate(shown):
        if kind == "cmd":
            n = round(len(text) * seg(t, at, at + 1.0))
            c.text(372, y, "$", 13, (126, 231, 135), "mono", "lm")
            c.text(388, y, text[:n], 13, TERM_INK, "mono", "lm")
            if i == len(shown) - 1 and (n < len(text) or int(t * 2.5) % 2):  # cursor on the line being typed
                cx = 388 + c.tw(text[:n], 13, "mono")
                c.box(cx + 1, y - 8, 8, 16, TERM_INK, None, r=1)
        else:
            hl = {"clue": (58, 52, 30), "good": (30, 52, 36), "bad": (64, 32, 32)}.get(kind)
            if hl:
                c.box(366, y - 11, 552, 22, mix(TERM, hl, ease(seg(t, at, at + 0.3))), None, r=4)
            c.text(372, y, text, 13, TERM_COLORS[kind], "mono", "lm")
        y += 22


CAPS_TROUBLE = [
    (0, 3, "Something is broken. Don't guess: walk down the ladder, from the big picture to the detail.", "?"),
    (3, 7, "Big picture first: what is unhealthy? One echo pod keeps crashing (CrashLoopBackOff).", "1"),
    (7, 11, "Events: what did Kubernetes see happen? It keeps restarting a container that fails.", "2"),
    (11, 15, "Describe: the pod's full story. Exit code 1 means the app stopped by itself.", "3"),
    (15, 19, "Logs: the app tells you why. A typo in a startup flag.", "4"),
    (19, 24, "Fix it in Git, not by hand: Argo CD rolls it out and all 5 pods run again.", "fix"),
]


GIFS = {
    "overview": (27, "The whole lab in one picture", "", g_overview, CAPS_OVERVIEW),
    "containers": (17.5, "Containers: one recipe, many identical boxes", "Lesson 1", g_containers, CAPS_CONTAINERS),
    "kubernetes": (19, "Kubernetes: say what you want, it keeps it true", "Lesson 2", g_kubernetes, CAPS_KUBERNETES),
    "traffic": (18.5, "Traffic: one front door, many rooms", "Lesson 3", g_traffic, CAPS_TRAFFIC),
    "monitoring": (19, "Monitoring: measure all the time, shout when it matters", "Lesson 4", g_monitoring,
                   CAPS_MONITORING),
    "gitops": (21, "GitOps: Git is the boss", "Lesson 5", g_gitops, CAPS_GITOPS),
    "delivery": (22, "CI/CD: every change takes the same road", "Lesson 6", g_delivery, CAPS_DELIVERY),
    "troubleshooting": (24, "Troubleshooting: walk the ladder, don't guess", "Lesson 7", g_troubleshooting,
                        CAPS_TROUBLE),
}


SWATCHES = [BG, INK, MUTED, LINE, WHITE, GRAY_BG, BLUE, BLUE_BG, GREEN, GREEN_BG, RED, RED_BG, AMBER, AMBER_BG,
            PURPLE, PURPLE_BG, TEAL, TEAL_BG, ORANGE, ORANGE_BG, TERM, TERM_INK, (240, 160, 120), (160, 190, 245),
            (240, 205, 188)] + list(TERM_COLORS.values())


def render(name, seconds, title, tag, draw, caps):
    check_layout(name, seconds, title, tag, caps)

    def still(t):
        c = Canvas()
        draw(c, t)
        chrome(c, t, title, tag, caps)
        return c.frame()

    # One palette for the whole GIF, taken from one still per caption: same colours keep the same index in
    # every frame, so the GIF encoder only stores the pixels that move.
    samples = [still((cap[0] + cap[1]) / 2) for cap in caps]
    sheet = Image.new("RGB", (W, H * len(samples) + 60))
    for i, im in enumerate(samples):
        sheet.paste(im, (0, H * i))
    for i, col in enumerate(SWATCHES):  # small dots must keep their colour: give every named colour a palette slot
        sheet.paste(col, (i * 30, H * len(samples), i * 30 + 30, H * len(samples) + 60))
    pal = sheet.quantize(256, dither=Image.Dither.NONE)
    if os.environ.get("GIF_SHEETS"):
        cols = 2
        rows = (len(samples) + 1) // cols
        grid = Image.new("RGB", (W * cols // 2, H * rows // 2), WHITE)
        for i, im in enumerate(samples):
            grid.paste(im.resize((W // 2, H // 2)), ((i % cols) * W // 2, (i // cols) * H // 2))
        grid.save(os.path.join(os.environ["GIF_SHEETS"], name + "-sheet.png"))
    frames = [still(n / FPS).quantize(palette=pal, dither=Image.Dither.NONE) for n in range(round(seconds * FPS))]
    path = os.path.join(OUT, name + ".gif")
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=round(1000 / FPS), loop=0, optimize=False)
    kb = os.path.getsize(path) // 1024
    assert kb < 3000, f"{name}.gif is {kb} KB: too heavy for a doc page"
    print(f"{name}.gif  {len(frames)} frames  {kb} KB")


def main():
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or list(GIFS)
    unknown = [n for n in names if n not in GIFS]
    if unknown:
        sys.exit(f"unknown GIF {unknown}; choose from {list(GIFS)}")
    for n in names:
        render(n, *GIFS[n])


if __name__ == "__main__":
    main()
