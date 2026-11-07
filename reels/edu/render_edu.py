"""Educational animated explainer: "what does 925 mean?" with Arabic voiceover.

usage: python3 render_edu.py <layers_dir> <vo_dir> <out.mp4> [--stills strip.jpg]
  layers_dir : output of ../layers.py      vo_dir : output of tts.py
"""
import os, sys, json, math, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "fonts")
sys.path.insert(0, HERE)
from script import LINES

W, H, FPS, SR = 1080, 1920, 30, 48000
LAY, VO, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
STILLS = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "--stills" else None

SILVER = (236, 234, 230)       # BGR
SILVER_D = (190, 186, 182)
COPPER = (70, 122, 205)
DIM = (120, 86, 58)
RED = (96, 96, 235)
GREEN = (120, 205, 120)

# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, t0, t1): return clamp((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t0)
def eo(x): return 1 - (1 - x) ** 3
def eio(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def eb(x, s=1.7): x -= 1; return x * x * ((s + 1) * x + s) + 1

# ------------------------------------------------------------------ sprites
class Sprite:
    def __init__(self, color, alpha):
        ys, xs = np.where(alpha > 0.01)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        self.c = np.ascontiguousarray(color[y0:y1, x0:x1].astype(np.float32))
        self.a = np.ascontiguousarray(alpha[y0:y1, x0:x1].astype(np.float32))
        self.h, self.w = self.a.shape

def load_layer(name):
    im = cv2.imread(f"{LAY}/{name}.png", cv2.IMREAD_UNCHANGED).astype(np.float32)
    return Sprite(im[..., :3], im[..., 3] / 255.0)

def put(canvas, sp, cx, cy, op=1.0, scale=1.0, rot=0.0, shine=None, tint=None):
    """draw sprite centred at (cx,cy)"""
    if op <= 0.003 or scale <= 0.01: return
    M = cv2.getRotationMatrix2D((sp.w / 2, sp.h / 2), rot, scale)
    M[0, 2] += cx - sp.w / 2; M[1, 2] += cy - sp.h / 2
    cs = np.array([[0, 0, 1], [sp.w, 0, 1], [0, sp.h, 1], [sp.w, sp.h, 1]], np.float32) @ M.T
    X0, Y0 = max(int(cs[:, 0].min()) - 1, 0), max(int(cs[:, 1].min()) - 1, 0)
    X1, Y1 = min(int(cs[:, 0].max()) + 2, W), min(int(cs[:, 1].max()) + 2, H)
    if X1 <= X0 or Y1 <= Y0: return
    M[0, 2] -= X0; M[1, 2] -= Y0
    c = cv2.warpAffine(sp.c, M, (X1 - X0, Y1 - Y0)); a = cv2.warpAffine(sp.a, M, (X1 - X0, Y1 - Y0)) * op
    if tint is not None: c = c * 0 + np.array(tint, np.float32)
    if shine is not None:
        ys, xs = np.mgrid[Y0:Y1, X0:X1].astype(np.float32)
        c = c + (np.exp(-(((xs + ys * 0.55) - shine) / 40.0) ** 2) * 110)[..., None]
    r = canvas[Y0:Y1, X0:X1]
    r += (np.minimum(c, 255) - r) * a[..., None]

# ------------------------------------------------------------------ text (mixed Arabic / Latin, RTL)
_fc = {}
def font(name, size):
    k = (name, size)
    if k not in _fc: _fc[k] = ImageFont.truetype(os.path.join(FONTS, name), size, layout_engine=ImageFont.Layout.RAQM)
    return _fc[k]

def _run_img(txt, f, fill, rtl):
    kw = dict(direction="rtl", language="ar") if rtl else {}
    b = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), txt, font=f, **kw)
    asc, desc = f.getmetrics()
    im = Image.new("RGBA", (b[2] - b[0] + 8, asc + desc + 16), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - b[0], 8), txt, font=f, fill=fill[::-1] + (255,), **kw)
    return np.array(im)

def text(txt, size=64, color=SILVER, bold=True, latin="Tajawal-Latin-Bold.ttf"):
    """returns Sprite; splits into Arabic and Latin/number runs, lays runs out right-to-left"""
    import re
    ar = font("Tajawal-Arabic-Bold.ttf" if bold else "Tajawal-Arabic-Regular.ttf", size)
    la = font(latin, int(size * 1.0))
    runs = [r for r in re.split(r"([A-Za-z0-9][A-Za-z0-9.%,]*(?: [A-Za-z][A-Za-z]*)*%?)", txt) if r.strip()]
    imgs = []
    for r in runs:
        is_lat = bool(re.match(r"[A-Za-z0-9]", r.strip()))
        imgs.append(_run_img(r.strip(), la if is_lat else ar, color, not is_lat))
    space = int(size * 0.28)
    h = max(i.shape[0] for i in imgs); w = sum(i.shape[1] for i in imgs) + space * (len(imgs) - 1)
    out = np.zeros((h, w, 4), np.uint8); x = w
    for i in imgs:                       # first run in reading order goes on the right
        x -= i.shape[1]; y = h - i.shape[0]
        out[y:y + i.shape[0], x:x + i.shape[1]] = np.maximum(out[y:y + i.shape[0], x:x + i.shape[1]], i)
        x -= space
    o = out.astype(np.float32)
    return Sprite(o[..., [2, 1, 0]], o[..., 3] / 255.0)

def latin(txt, size, color=SILVER, f="PlayfairDisplay-Bold.ttf"):
    o = _run_img(txt, font(f, size), color, False).astype(np.float32)
    return Sprite(o[..., [2, 1, 0]], o[..., 3] / 255.0)

# ------------------------------------------------------------------ assets
PLATE = cv2.imread(f"{LAY}/plate.png")
_m = np.zeros(PLATE.shape[:2], np.uint8); cv2.ellipse(_m, (700, 1085), (150, 100), -30, 0, 360, 255, -1)
_fill = cv2.inpaint(PLATE, _m, 15, cv2.INPAINT_TELEA).astype(np.float32)   # drop the ring's cast shadow
_tex = PLATE[1450:1650, 400:700].astype(np.float32); _tex -= cv2.GaussianBlur(_tex, (0, 0), 10)
_fill[985:1185, 550:850] += _tex
_w = cv2.GaussianBlur(_m.astype(np.float32) / 255, (0, 0), 18)[..., None]
PLATE = PLATE.astype(np.float32) * (1 - _w) + cv2.GaussianBlur(_fill, (0, 0), 0.6) * _w
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1 - 0.45 * np.clip((np.hypot((XX - W / 2) / (W / 2), (YY - H * 0.45) / (H / 2)) - 0.45) / 0.8, 0, 1))[..., None]
BG = PLATE * 0.78 * VIG
L = {n: load_layer(n) for n in ["logo", "ring", "n9", "n2", "n5", "oval", "caption"]}

SUBS = [text(s, 52) for _, s, _ in LINES]
T = {
    "title": text("ما معنى 925 على الفضة؟", 70),
    "parts1000": text("1000 جزء", 64),
    "pure": text("92.5% فضة نقية", 60),
    "alloy": text("7.5% نحاس ومعادن", 60, COPPER),
    "soft": text("فضة نقية 999 ليّنة", 56),
    "strong": text("فضة 925 قوية وثابتة", 56),
    "sterling_ar": text("الفضة الإسترلينية", 84),
    "stamp": text("ختم 925", 64),
    "q": latin("?", 260, SILVER_D),
    "n925": latin("925", 140, (170, 168, 165)),
    "tag": text("فضة عيار 925", 76),
    "sub": text("تسوّق الآن من سيلفر هافن", 46, (205, 200, 195), bold=False),
    "url": latin("silverhaven-sa.com", 50, (225, 222, 218), "PlayfairDisplay-Regular.ttf"),
}
DIG = {d: latin(d, 330, SILVER, "PlayfairDisplay-Regular.ttf") for d in "925"}
CNT = {}
def counter(n, size=150, color=SILVER):
    k = (n, size, color)
    if k not in CNT: CNT[k] = latin(str(n), size, color, "Tajawal-Latin-Bold.ttf")
    return CNT[k]

# ------------------------------------------------------------------ timeline from voiceover
info = json.load(open(os.path.join(VO, "lines.json")))
LEAD, TAIL = 0.35, 0.55
scenes, t = [], 0.0
for i, ln in enumerate(info):
    d = LEAD + ln["dur"] + TAIL + (1.6 if ln["id"] == "brand" else 0)
    scenes.append(dict(id=ln["id"], t0=t, t1=t + d, dur=ln["dur"], wav=ln["file"], sub=i))
    t += d
TOTAL = t
SFX = []   # (time, kind)

# grid geometry: 40 x 25 = 1000 cells, filled right-to-left (Arabic reading order)
GC, GR, CS, GAP = 40, 25, 22, 3
GX0 = (W - (GC * (CS + GAP) - GAP)) // 2
GY0 = 640
def cell_xy(i):
    r, c = divmod(i, GC); c = GC - 1 - c
    return GX0 + c * (CS + GAP), GY0 + r * (CS + GAP)

def draw_grid(cv, appear, silver_n, copper_n, op=1.0):
    """appear: 0..1 wave-in; silver_n / copper_n: number of filled cells"""
    if op <= 0: return
    layer = cv.copy()
    for i in range(1000):
        x, y = cell_xy(i)
        r, c = divmod(i, GC)
        a = clamp(appear * 1.6 - (r + (GC - 1 - c) * 0.3) / (GR + GC * 0.3) * 0.6)
        if a <= 0: continue
        s = CS * eb(a) if a < 1 else CS
        if i < silver_n: col = SILVER
        elif i >= 1000 - copper_n: col = COPPER
        else: col = None
        cx, cy = x + CS / 2, y + CS / 2; hs = s / 2
        p0, p1 = (int(cx - hs), int(cy - hs)), (int(cx + hs) - 1, int(cy + hs) - 1)
        if col: cv2.rectangle(layer, p0, p1, col, -1)
        else: cv2.rectangle(layer, p0, p1, DIM, 1)
    cv[:] = cv * (1 - op) + layer * op

def bar(cv, y, bend, op=1.0, x0=190, x1=890, color=SILVER, thick=46):
    xs = np.linspace(x0, x1, 60)
    u = (xs - x0) / (x1 - x0)
    ys = y + bend * np.sin(u * math.pi)
    pts = np.stack([xs, ys], 1).astype(np.int32)
    layer = cv.copy()
    cv2.polylines(layer, [pts], False, color, thick, cv2.LINE_AA)
    cv2.polylines(layer, [pts - [0, thick // 4]], False, (252, 252, 252), 6, cv2.LINE_AA)
    cv[:] = cv * (1 - op) + layer * op

def press_arrow(cv, x, y, op=1.0):
    layer = cv.copy()
    pts = np.array([[x - 22, y - 120], [x + 22, y - 120], [x + 22, y - 45], [x + 52, y - 45], [x, y], [x - 52, y - 45], [x - 22, y - 45]], np.int32)
    cv2.fillPoly(layer, [pts], (215, 205, 200), cv2.LINE_AA)
    cv[:] = cv * (1 - op) + layer * op

def check(cv, cx, cy, p, color=GREEN):
    pts = np.array([[cx - 50, cy], [cx - 15, cy + 38], [cx + 60, cy - 50]], np.float32)
    seg = [(pts[0], pts[1]), (pts[1], pts[2])]
    L1 = np.linalg.norm(pts[1] - pts[0]); L2 = np.linalg.norm(pts[2] - pts[1]); d = p * (L1 + L2)
    if d <= 0: return
    e1 = pts[0] + (pts[1] - pts[0]) * min(d / L1, 1)
    cv2.line(cv, tuple(pts[0].astype(int)), tuple(e1.astype(int)), color, 16, cv2.LINE_AA)
    if d > L1:
        e2 = pts[1] + (pts[2] - pts[1]) * min((d - L1) / L2, 1)
        cv2.line(cv, tuple(pts[1].astype(int)), tuple(e2.astype(int)), color, 16, cv2.LINE_AA)

def cross(cv, cx, cy, p, color=RED):
    for k, (a, b) in enumerate([((-45, -45), (45, 45)), ((45, -45), (-45, 45))]):
        q = clamp(p * 2 - k)
        if q <= 0: continue
        s = (int(cx + a[0]), int(cy + a[1])); e = (int(s[0] + (b[0] - a[0]) * q), int(s[1] + (b[1] - a[1]) * q))
        cv2.line(cv, s, e, color, 16, cv2.LINE_AA)

def subtitle(cv, sc, lt):
    sp = SUBS[sc["sub"]]
    o = eo(prog(lt, 0.15, 0.5)) * (1 - prog(lt, sc["t1"] - sc["t0"] - 0.3, sc["t1"] - sc["t0"]))
    if o <= 0: return
    cx, cy = W / 2, 1640
    pw = min(sp.w + 70, W - 40); ph = sp.h + 34
    x0, y0 = int(cx - pw / 2), int(cy - ph / 2)
    box = cv[y0:y0 + ph, x0:x0 + pw]
    m = np.zeros((ph, pw), np.uint8); cv2.rectangle(m, (ph // 2, 0), (pw - ph // 2, ph), 255, -1)
    cv2.circle(m, (ph // 2, ph // 2), ph // 2, 255, -1); cv2.circle(m, (pw - ph // 2, ph // 2), ph // 2, 255, -1)
    m = (m / 255.0 * 0.55 * o)[..., None]
    box[:] = box * (1 - m) + np.array((40, 22, 12), np.float32) * m
    sc_ = min(1.0, (W - 90) / sp.w)
    put(cv, sp, cx, cy + 4, op=o, scale=sc_)

# ------------------------------------------------------------------ scenes
def scene(cv, sid, lt, D):
    """lt: local time from scene start; D: scene length"""
    if sid == "hook":
        put(cv, T["title"], W / 2, 330, op=eo(prog(lt, 0.2, 0.8)), scale=0.9 + 0.1 * eo(prog(lt, 0.2, 0.8)))
        p = eb(prog(lt, 0.4, 1.3))
        put(cv, L["ring"], W / 2, 960, op=clamp(p), scale=2.4 * max(p, 0.01), rot=6 * math.sin(lt * 1.3))
        # magnifier sweeping in
        q = eio(prog(lt, 1.6, 3.2))
        mx, my = 1250 - 560 * q, 700 + 180 * q
        if q > 0:
            cv2.circle(cv, (int(mx), int(my)), 150, (40, 24, 14), -1, cv2.LINE_AA)
            put(cv, T["n925"], mx, my, op=prog(lt, 2.6, 3.2))
            cv2.circle(cv, (int(mx), int(my)), 150, (220, 214, 210), 14, cv2.LINE_AA)
            hx, hy = mx + 106, my + 106
            cv2.line(cv, (int(hx), int(hy)), (int(hx + 130), int(hy + 130)), (220, 214, 210), 30, cv2.LINE_AA)
        q2 = eb(prog(lt, 3.4, 4.0))
        put(cv, T["q"], 250, 760, op=clamp(q2), scale=max(q2, 0.01), rot=-12)
        if abs(lt - 3.4) < 1 / FPS: SFX.append(("pop", lt))
    elif sid == "what":
        for i, d in enumerate("925"):
            p = prog(lt, 0.1 + 0.15 * i, 0.7 + 0.15 * i)
            put(cv, DIG[d], 375 + 165 * i, 960 + 80 * (1 - eb(p)), op=eo(p),
                shine=-300 + 2600 * prog(lt, 1.0, 2.2))
        q = eio(prog(lt, 0.9, 1.7))
        if q > 0: cv2.line(cv, (int(820 - 640 * q), 1150), (820, 1150), SILVER_D, 6, cv2.LINE_AA)
    elif sid in ("grid", "silver", "alloy"):
        top = {"grid": 1, "silver": 1, "alloy": 1}[sid]
        if sid == "grid":
            draw_grid(cv, prog(lt, 0.2, 2.2), 0, 0)
            n = int(1000 * eo(prog(lt, 0.4, 2.4)))
            put(cv, counter(n), W / 2, 430, op=eo(prog(lt, 0.2, 0.6)))
            put(cv, T["parts1000"], W / 2, 1380, op=eo(prog(lt, 2.0, 2.6)))
        elif sid == "silver":
            fill = int(925 * eio(prog(lt, 0.3, 3.8)))
            draw_grid(cv, 1, fill, 0)
            put(cv, counter(fill), W / 2, 430)
            q = eb(prog(lt, 3.9, 4.5)); put(cv, T["pure"], W / 2, 1380, op=clamp(q), scale=max(q, .01))
            if abs(lt - 3.9) < 1 / FPS: SFX.append(("pop", lt))
        else:
            fill = int(75 * eio(prog(lt, 0.3, 2.6)))
            draw_grid(cv, 1, 925, fill)
            put(cv, counter(fill, color=COPPER), W / 2, 430)
            put(cv, T["pure"], W / 2, 1385, op=0.55, scale=0.8)
            q = eb(prog(lt, 2.8, 3.4)); put(cv, T["alloy"], W / 2, 1470, op=clamp(q), scale=max(q, .01))
            if abs(lt - 2.8) < 1 / FPS: SFX.append(("pop", lt))
            # summary bar
            q = eio(prog(lt, 3.8, 5.0))
            if q > 0:
                x0, x1, y = 120, 960, 1305
                xm = x1 - (x1 - x0) * 0.925
                cv2.rectangle(cv, (int(x1 - (x1 - xm) * q), y - 14), (x1, y + 14), SILVER, -1, cv2.LINE_AA)
                if q > 0.95: cv2.rectangle(cv, (x0, y - 14), (int(xm) - 4, y + 14), COPPER, -1, cv2.LINE_AA)
    elif sid == "why":
        put(cv, T["soft"], W / 2, 560, op=eo(prog(lt, 0.2, 0.7)))
        press = eio(prog(lt, 1.2, 3.0))
        ay = 760 + 150 * press
        press_arrow(cv, W / 2, int(ay) + 80 * press - 10, op=eo(prog(lt, 0.6, 1.1)))
        bar(cv, 960, 190 * press + 8 * math.sin(lt * 18) * press * (1 - prog(lt, 3.0, 3.6)), op=eo(prog(lt, 0.3, 0.8)))
        cross(cv, W / 2, 1330, prog(lt, 3.2, 3.8))
        if abs(lt - 3.2) < 1 / FPS: SFX.append(("down", lt))
    elif sid == "strong":
        put(cv, T["strong"], W / 2, 560, op=eo(prog(lt, 0.2, 0.7)))
        press = eio(prog(lt, 1.0, 2.0)) * (1 - eio(prog(lt, 3.2, 4.0)))
        press_arrow(cv, W / 2, int(830 + 70 * press), op=eo(prog(lt, 0.5, 1.0)))
        shake = 6 * math.sin(lt * 30) * press
        bar(cv, 960 + shake, 0, op=eo(prog(lt, 0.3, 0.8)))
        # sparkle on the bar
        sp = -200 + 1800 * prog(lt, 2.4, 3.4)
        if 0 < sp < 1300:
            x = int(sp)
            cv2.circle(cv, (min(x, 890), 948), 10, (255, 255, 255), -1, cv2.LINE_AA)
        check(cv, W / 2, 1300, eo(prog(lt, 2.2, 3.0)))
        if abs(lt - 2.2) < 1 / FPS: SFX.append(("ding", lt))
    elif sid == "name":
        # oval draws (angular reveal) with caption, then Arabic name below
        p = eio(prog(lt, 0.2, 1.4))
        sp = L["oval"]
        if p > 0:
            ys, xs = np.mgrid[0:sp.h, 0:sp.w].astype(np.float32)
            ang = (np.arctan2((ys - sp.h / 2), (xs - sp.w / 2) / 3.2) - math.radians(80)) % (2 * math.pi)
            m = np.clip((p * (2 * math.pi + .3) - ang) / .3, 0, 1)
            tmp = Sprite.__new__(Sprite); tmp.c, tmp.a, tmp.h, tmp.w = sp.c, sp.a * m, sp.h, sp.w
            put(cv, tmp, W / 2, 820, scale=1.45)
        put(cv, L["caption"], W / 2, 830, op=eo(prog(lt, 1.0, 1.6)), scale=1.45,
            shine=-200 + 2400 * prog(lt, 2.0, 3.2))
        q = eb(prog(lt, 1.6, 2.3)); put(cv, T["sterling_ar"], W / 2, 1120, op=clamp(q), scale=max(q, .01))
        if abs(lt - 1.6) < 1 / FPS: SFX.append(("pop", lt))
    elif sid == "stamp":
        z = 2.0 + 0.6 * eio(prog(lt, 0, D))
        put(cv, L["ring"], 470, 1000, scale=z, rot=-4, shine=-400 + 3200 * prog(lt, 1.0, 2.4))
        q = eb(prog(lt, 1.2, 1.9))
        mx, my = 760, 600
        if q > 0:
            cv2.line(cv, (560, 960), (int(560 + (mx - 560) * clamp(q)), int(960 + (my - 960) * clamp(q))), SILVER_D, 5, cv2.LINE_AA)
            r = int(140 * clamp(q))
            cv2.circle(cv, (mx, my), r, (36, 22, 12), -1, cv2.LINE_AA)
            cv2.circle(cv, (mx, my), r, SILVER, 8, cv2.LINE_AA)
            put(cv, T["n925"], mx, my, op=clamp(q), scale=max(q, .01) * 0.85)
        if abs(lt - 1.2) < 1 / FPS: SFX.append(("pop", lt))
        put(cv, T["stamp"], W / 2, 1360, op=eo(prog(lt, 2.0, 2.6)))
    elif sid == "brand":
        lg = L["logo"]; q = eio(prog(lt, 0.1, 1.2))
        put(cv, lg, W / 2, 760, op=q, scale=3.6, shine=-300 + 2600 * prog(lt, 1.4, 2.6))
        put(cv, L["ring"], W / 2, 1030, op=eo(prog(lt, 0.6, 1.3)), scale=0.9)
        for i, k in enumerate(["tag", "sub", "url"]):
            qq = eo(prog(lt, 1.0 + 0.2 * i, 1.6 + 0.2 * i))
            put(cv, T[k], W / 2, [1210, 1300, 1420][i] + 30 * (1 - qq), op=qq)

def frame(t):
    i = max(k for k, s in enumerate(scenes) if s["t0"] <= t + 1e-9)
    sc = scenes[i]; lt = t - sc["t0"]; D = sc["t1"] - sc["t0"]
    def render(s, ltime):
        cv = BG.copy()
        if s["id"] != "brand":
            put(cv, L["logo"], 105, 92)
        scene(cv, s["id"], ltime, s["t1"] - s["t0"])
        if s["id"] != "brand": subtitle(cv, s, ltime)
        return cv
    cv = render(sc, lt)
    XF = 0.4
    if i > 0 and lt < XF:   # crossfade from the previous scene's last frame
        prev = scenes[i - 1]
        pv = render(prev, prev["t1"] - prev["t0"] - 1e-3)
        a = eio(lt / XF); cv = pv * (1 - a) + cv * a
    if t < 0.4: cv *= t / 0.4
    return cv

# ------------------------------------------------------------------ audio
def tone(f, d, env_a=0.005, env_r=0.25, amp=0.3):
    n = int(d * SR); tt = np.arange(n) / SR
    env = np.minimum(tt / env_a, 1) * np.exp(-tt / env_r)
    return amp * env * np.sin(2 * math.pi * f * tt)

def build_audio(path):
    n = int((TOTAL + 0.5) * SR)
    vo = np.zeros((n, 2), np.float32)
    for s in scenes:
        x = subprocess.run(["ffmpeg", "-v", "error", "-i", s["wav"], "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                           capture_output=True).stdout
        a = np.frombuffer(x, np.float32).reshape(-1, 2); st = int((s["t0"] + LEAD) * SR)
        vo[st:st + len(a)] += a[:n - st]
    # ambient pad: Am - F - C - G, soft sines with slow swell
    music = np.zeros(n, np.float32); tt = np.arange(n) / SR
    chords = [[220, 261.6, 329.6], [174.6, 220, 261.6], [196, 261.6, 329.6], [196, 246.9, 293.7]]
    bar_d = 4.0
    for b in range(int(TOTAL / bar_d) + 2):
        st, en = int(b * bar_d * SR), min(int((b + 1) * bar_d * SR + SR), n)
        if st >= n: break
        seg = tt[st:en] - b * bar_d
        env = np.minimum(seg / 1.2, 1) * np.clip((bar_d + 1 - seg) / 1.0, 0, 1)
        for f in chords[b % 4]:
            music[st:en] += 0.05 * env * (np.sin(2 * math.pi * f * seg) + 0.3 * np.sin(2 * math.pi * 2 * f * seg))
        # sparkle arpeggio
        for k in range(4):
            ps = st + int(k * SR)
            if ps < n:
                tn = tone(chords[b % 4][k % 3] * 4, 0.9, amp=0.025, env_r=0.35)
                music[ps:ps + len(tn)] += tn[:n - ps]
    music = np.convolve(music, np.ones(8) / 8, mode="same")
    fade = np.minimum(np.minimum(tt / 1.5, 1), np.clip((TOTAL + 0.5 - tt) / 2.0, 0, 1))
    music *= fade
    # duck music under voice
    vlev = np.abs(vo[:, 0]); k = int(0.25 * SR)
    vlev = np.convolve(vlev, np.ones(k) / k, mode="same")
    duck = 1 - 0.55 * np.clip(vlev / 0.05, 0, 1)
    music *= duck
    # sfx
    sfx = np.zeros(n, np.float32)
    def add(sig, t0):
        st = int(t0 * SR); sfx[st:st + len(sig)] += sig[:max(0, n - st)]
    for s in scenes[1:]:   # whoosh on every scene change
        d = 0.45; m = int(d * SR); noise = np.random.default_rng(1).standard_normal(m)
        env = np.sin(np.linspace(0, math.pi, m)) ** 2
        w = np.convolve(noise, np.ones(30) / 30, mode="same") * env * 0.25
        add(w.astype(np.float32), s["t0"] - 0.2)
    for kind, t0 in SFX:
        if kind == "pop": add(tone(880, 0.18, env_r=0.05, amp=0.25) + tone(1320, 0.18, env_r=0.04, amp=0.12), t0)
        if kind == "ding": add(tone(1568, 1.2, env_r=0.4, amp=0.2) + tone(2093, 1.2, env_r=0.3, amp=0.1), t0)
        if kind == "down":
            m = int(0.4 * SR); tt2 = np.arange(m) / SR
            add((0.25 * np.sin(2 * math.pi * (300 - 400 * tt2) * tt2) * np.exp(-tt2 / 0.15)).astype(np.float32), t0)
    mix = vo + (music + sfx)[:, None]
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s16le", path], input=mix.astype(np.float32).tobytes(), check=True)

# ------------------------------------------------------------------ main
if STILLS:
    ts = [s["t0"] + (s["t1"] - s["t0"]) * 0.8 for s in scenes]
    tiles = [cv2.resize(np.clip(frame(t), 0, 255).astype(np.uint8), (270, 480)) for t in ts]
    cv2.imwrite(STILLS, np.vstack([np.hstack(tiles[:5]), np.hstack(tiles[5:])]))
    sys.exit()

tmpv = OUT + ".video.mp4"; tmpa = OUT + ".audio.wav"
p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                      "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                      "-pix_fmt", "yuv420p", tmpv], stdin=subprocess.PIPE)
for i in range(int(TOTAL * FPS)):
    p.stdin.write(np.clip(frame(i / FPS), 0, 255).astype(np.uint8).tobytes())
p.stdin.close(); p.wait()
build_audio(tmpa)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmpv, "-i", tmpa, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart", OUT], check=True)
os.remove(tmpv); os.remove(tmpa)
print("wrote", OUT, round(TOTAL, 1), "s")
