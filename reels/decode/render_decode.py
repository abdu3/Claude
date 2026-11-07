"""«نفكّ شفرة 925» — 30 s vertical reel: "فضة أصلية… ليش مو 100٪؟" decoded step by step.

usage: python3 render_decode.py <layers_dir> <out.mp4> [--stills sheet.jpg]
  layers_dir : output of ../layers.py on ../src/design-925.jpg
Voiceover: voiceover-mona-decode925.mp3 (ElevenLabs, Mona, white Saudi dialect). It is cut at its pauses
into the lines below and re-spaced; every scene is timed from those cuts.
"""
import os, sys, math, re, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "fonts")
W, H, FPS, SR = 1080, 1920, 30, 48000
LAY, OUT = sys.argv[1], sys.argv[2]
STILLS = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--stills" else None
VO_MP3 = os.path.join(HERE, "voiceover-mona-decode925.mp3")

# ------------------------------------------------------------------ voiceover lines (start, end in the take)
#  id, t_in, t_out, gap after (s)
VO = [
    ("real",    0.19, 1.30, 0.30),   # فضة أصلية…
    ("why100",  1.79, 3.60, 0.40),   # طيب ليش مو مية بالمية؟
    ("secret",  4.08, 5.21, 0.26),   # السر في هالرقم:
    ("n925",    5.64, 7.40, 0.36),   # تسعمية وخمسة وعشرين
    ("pure",    7.75, 10.65, 0.30),  # يعني اثنين وتسعين ونص بالمية فضة نقية
    ("alloy",  11.01, 13.26, 0.45),  # وسبعة ونص بالمية معادن ثانية
    ("ask",    13.70, 14.57, 0.32),  # ليش نضيفها؟
    ("soft",   14.93, 16.63, 0.22),  # لأن الفضة النقية ليّنة
    ("hard",   16.86, 20.97, 0.40),  # وهالإضافة تزيد صلابتها وتخليها أنسب لصناعة الحُلي
    ("name",   21.38, 23.68, 0.40),  # وهذي تُعرف بفضة الاسترليني
    ("now",    24.07, 24.53, 0.20),  # الحين،
    ("see",    24.75, 26.83, 0.26),  # إذا شفتي تسعمية وخمسة وعشرين…
    ("know",   27.12, 28.07, 0.30),  # تعرفين وش يعني
    ("save",   28.40, 30.66, 0.00),  # احفظي المعلومة قبل تختارين قطعتك
]
PAD, START, END_HOLD = 0.06, 0.12, 1.0
LT = {}           # id -> (t0, t1) in the final video
t = START
for k, a, b, g in VO:
    LT[k] = (t, t + (b - a)); t += (b - a) + g
TOTAL = t + END_HOLD
# scenes: (id, first line, last line)
SC = [("hook", "real", "why100"), ("num", "secret", "n925"), ("pure", "pure", "pure"), ("alloy", "alloy", "alloy"),
      ("why", "ask", "hard"), ("name", "name", "name"), ("end", "now", "save")]
SCENES = []
for i, (sid, a, b) in enumerate(SC):
    t0 = 0.0 if i == 0 else LT[a][0] - 0.22
    SCENES.append([sid, t0, None])
for i in range(len(SCENES)):
    SCENES[i][2] = SCENES[i + 1][1] if i + 1 < len(SCENES) else TOTAL

# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, t0, t1): return clamp((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t0)
def eo(x): return 1 - (1 - x) ** 3
def eio(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def eb(x, s=1.7): x -= 1; return x * x * ((s + 1) * x + s) + 1
def lerp(a, b, x): return a + (b - a) * x

SILVER = (242, 240, 236)     # BGR
SILVER_D = (196, 192, 188)
GUN = (128, 118, 108)        # the 7.5%: a distinct cool gunmetal grey
INK = (36, 20, 10)

# ------------------------------------------------------------------ sprites
class Sprite:
    def __init__(self, color, alpha, crop=True):
        if crop:
            ys, xs = np.where(alpha > 0.01)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            color, alpha = color[y0:y1, x0:x1], alpha[y0:y1, x0:x1]
        self.c = np.ascontiguousarray(color.astype(np.float32))
        self.a = np.ascontiguousarray(alpha.astype(np.float32))
        self.h, self.w = self.a.shape

def load_layer(name):
    im = cv2.imread(f"{LAY}/{name}.png", cv2.IMREAD_UNCHANGED).astype(np.float32)
    return Sprite(im[..., :3], im[..., 3] / 255.0)

def put(canvas, sp, cx, cy, op=1.0, scale=1.0, rot=0.0, shine=None, mask=None):
    """draw sprite centred at (cx, cy); shine = position of a diagonal light sweep in canvas px"""
    if op <= 0.003 or scale <= 0.01: return
    M = cv2.getRotationMatrix2D((sp.w / 2, sp.h / 2), rot, scale)
    M[0, 2] += cx - sp.w / 2; M[1, 2] += cy - sp.h / 2
    cs = np.array([[0, 0, 1], [sp.w, 0, 1], [0, sp.h, 1], [sp.w, sp.h, 1]], np.float32) @ M.T
    X0, Y0 = max(int(cs[:, 0].min()) - 1, 0), max(int(cs[:, 1].min()) - 1, 0)
    X1, Y1 = min(int(cs[:, 0].max()) + 2, W), min(int(cs[:, 1].max()) + 2, H)
    if X1 <= X0 or Y1 <= Y0: return
    M[0, 2] -= X0; M[1, 2] -= Y0
    c = cv2.warpAffine(sp.c, M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_CUBIC)
    a = np.clip(cv2.warpAffine(sp.a if mask is None else sp.a * mask, M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR), 0, 1) * op
    if shine is not None:
        ys, xs = np.mgrid[Y0:Y1, X0:X1].astype(np.float32)
        c = c + (np.exp(-(((xs + ys * 0.55) - shine) / 45.0) ** 2) * 120)[..., None]
    r = canvas[Y0:Y1, X0:X1]
    r += (np.clip(c, 0, 255) - r) * a[..., None]

# ------------------------------------------------------------------ text (mixed Arabic / Latin, RTL) with soft shadow
_fc = {}
def font(name, size):
    k = (name, size)
    if k not in _fc: _fc[k] = ImageFont.truetype(os.path.join(FONTS, name), size, layout_engine=ImageFont.Layout.RAQM)
    return _fc[k]

def _run_img(txt, f, rtl):
    kw = dict(direction="rtl", language="ar") if rtl else {}
    b = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), txt, font=f, **kw)
    asc, desc = f.getmetrics()
    im = Image.new("L", (b[2] - b[0] + 8, asc + desc + 16), 0)
    ImageDraw.Draw(im).text((4 - b[0], 8), txt, font=f, fill=255, **kw)
    return np.array(im)

class Text:
    """white-silver text sprite + a blurred navy shadow under it (contrast on the textured stone)"""
    def __init__(self, txt, size=72, color=SILVER, bold=True, latin_font="Tajawal-Latin-Bold.ttf", latin_scale=1.0, latin_only=False):
        ar = font("Tajawal-Arabic-Bold.ttf" if bold else "Tajawal-Arabic-Regular.ttf", size)
        la = font(latin_font, int(size * latin_scale))
        runs = [txt] if latin_only else [r for r in re.split(r"([A-Za-z0-9][A-Za-z0-9.%,]*(?: [A-Za-z][A-Za-z]*)*%?)", txt) if r.strip()]
        imgs = []
        for r in runs:
            is_lat = bool(re.match(r"[A-Za-z0-9]", r.strip()))
            imgs.append(_run_img(r.strip(), la if is_lat else ar, not is_lat))
        space = int(size * 0.26)
        h = max(i.shape[0] for i in imgs); w = sum(i.shape[1] for i in imgs) + space * (len(imgs) - 1)
        a = np.zeros((h, w), np.uint8); x = w
        for i in imgs:                       # first run in reading order goes on the right
            x -= i.shape[1]; y = (h - i.shape[0]) // 2
            a[y:y + i.shape[0], x:x + i.shape[1]] = np.maximum(a[y:y + i.shape[0], x:x + i.shape[1]], i)
            x -= space
        p = 30
        a = np.pad(a.astype(np.float32) / 255, p)
        col = np.zeros(a.shape + (3,), np.float32) + np.array(color, np.float32)
        # subtle top-to-bottom metallic gradient
        g = np.linspace(1.04, 0.86, a.shape[0])[:, None, None]
        self.fg = Sprite(np.clip(col * g, 0, 255), a, crop=False)
        sh = np.clip(cv2.GaussianBlur(a, (0, 0), 9) * 1.3, 0, 1) * 0.85
        sh = np.roll(sh, 5, axis=0)
        self.sh = Sprite(np.zeros(a.shape + (3,), np.float32) + np.array(INK, np.float32), sh, crop=False)
        self.w, self.h = self.fg.w, self.fg.h

def ptext(cv, tx, cx, cy, op=1.0, scale=1.0, shine=None):
    put(cv, tx.sh, cx, cy, op=op, scale=scale)
    put(cv, tx.fg, cx, cy, op=op, scale=scale, shine=shine)

# ------------------------------------------------------------------ assets
PLATE = cv2.imread(f"{LAY}/plate.png")
_m = np.zeros(PLATE.shape[:2], np.uint8); cv2.ellipse(_m, (700, 1085), (150, 100), -30, 0, 360, 255, -1)
_fill = cv2.inpaint(PLATE, _m, 15, cv2.INPAINT_TELEA).astype(np.float32)   # drop the ring's cast shadow
_tex = PLATE[1450:1650, 400:700].astype(np.float32); _tex -= cv2.GaussianBlur(_tex, (0, 0), 10)
_fill[985:1185, 550:850] += _tex
_w = cv2.GaussianBlur(_m.astype(np.float32) / 255, (0, 0), 18)[..., None]
PLATE = PLATE.astype(np.float32) * (1 - _w) + cv2.GaussianBlur(_fill, (0, 0), 0.6) * _w
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1 - 0.5 * np.clip((np.hypot((XX - W / 2) / (W / 2), (YY - H * 0.45) / (H / 2)) - 0.4) / 0.8, 0, 1))[..., None]
BG = PLATE * 0.8 * VIG
L = {n: load_layer(n) for n in ["logo", "ring", "n9", "n2", "n5"]}

# ring shadow sprite (soft dark ellipse under it)
_sh = np.zeros((120, 260), np.float32); cv2.ellipse(_sh, (130, 60), (95, 26), 0, 0, 360, 1, -1)
RING_SH = Sprite(np.zeros((120, 260, 3), np.float32) + 8, cv2.GaussianBlur(_sh, (0, 0), 14) * 0.75, crop=False)

# the "925" group in design coordinates (original positions); ring sits on the 5
GC = np.array([536.0, 965.0])
POS = {"n9": None, "n2": None, "n5": None}
def _centre(name):
    im = cv2.imread(f"{LAY}/{name}.png", cv2.IMREAD_UNCHANGED)[..., 3]
    ys, xs = np.where(im > 2); return np.array([(xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2])
for k in ["n9", "n2", "n5", "ring"]: POS[k] = _centre(k)

def group(cv, cx, cy, s, op=1.0, digits_op=None, ring=True, ring_op=None, rise=None, shine=None, ring_shine=None, ring_rot=0.0):
    """draw 925 (+ ring) as in the design, scaled by s about its centre and placed at (cx, cy)"""
    for i, k in enumerate(["n9", "n2", "n5"]):
        p = POS[k] - GC
        o = op if digits_op is None else digits_op[i]
        dy = 0 if rise is None else rise[i]
        put(cv, L[k], cx + p[0] * s, cy + p[1] * s + dy, op=o, scale=s, shine=shine)
    if ring:
        p = POS["ring"] - GC
        ro = op if ring_op is None else ring_op
        put(cv, RING_SH, cx + (p[0] + 4) * s, cy + (p[1] + 70) * s, op=ro * 0.7, scale=s * 0.9)
        put(cv, L["ring"], cx + p[0] * s, cy + p[1] * s, op=ro, scale=s, shine=ring_shine, rot=ring_rot)

T = {
    "real": Text("فضة أصلية", 92),
    "why": Text("ليش مو", 92),
    "q": Text("؟", 92),
    "100": Text("100%", 150, latin_font="PlayfairDisplay-Bold.ttf"),
    "secret": Text("السر في 925", 84, latin_font="PlayfairDisplay-Bold.ttf"),
    "pure_lbl": Text("فضة نقية", 66),
    "alloy_lbl": Text("معادن أخرى", 58, (214, 210, 206)),
    "ask": Text("ليش نضيفها؟", 104),
    "soft_lbl": Text("ليّنة", 48, (200, 196, 192), bold=False),
    "firm_lbl": Text("متماسكة", 48, (200, 196, 192), bold=False),
    "hard": Text("لزيادة الصلابة", 88),
    "name_ar": Text("فضة استرليني", 84),
    "name_en": Text("Sterling Silver", 66, (226, 222, 218), latin_font="PlayfairDisplay-Regular.ttf"),
    "known": Text("الحين تعرفين معنى 925", 72, latin_font="PlayfairDisplay-Bold.ttf"),
    "save": Text("احفظيها قبل تختارين قطعتك", 54, (222, 218, 214)),
    "url": Text("silverhaven-sa.com", 40, (200, 196, 192), latin_font="PlayfairDisplay-Regular.ttf", latin_only=True),
}
_num = {}
def num(txt, size=120, color=SILVER):
    k = (txt, size, color)
    if k not in _num: _num[k] = Text(txt, size, color, latin_font="PlayfairDisplay-Bold.ttf")
    return _num[k]

SFX = set()   # (kind, time) collected while rendering
def sfx(kind, t_abs): SFX.add((kind, round(t_abs, 3)))

# ------------------------------------------------------------------ hand-drawn strokes
def stroke(cv, pts, p, color=SILVER_D, th=5, head=False, op=1.0):
    """draw the first p (0..1) of a polyline, optional arrow head at the drawn end"""
    if p <= 0: return
    pts = np.asarray(pts, np.float32)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1); cum = np.concatenate([[0], np.cumsum(seg)])
    L_ = cum[-1] * p; n = np.searchsorted(cum, L_)
    part = pts[:max(n, 1)]
    if n < len(pts):
        f = (L_ - cum[n - 1]) / max(seg[n - 1], 1e-6); part = np.vstack([part, pts[n - 1] + (pts[n] - pts[n - 1]) * f])
    layer = cv.copy()
    cv2.polylines(layer, [np.round(part * 8).astype(np.int32)], False, color, th, cv2.LINE_AA, shift=3)
    if head and len(part) > 2:
        e = part[-1]; d = e - part[max(len(part) - 6, 0)]; d /= max(np.linalg.norm(d), 1e-6)
        nrm = np.array([-d[1], d[0]])
        for s_ in (1, -1):
            q = e - d * 26 + nrm * 14 * s_
            cv2.line(layer, tuple(np.round(e * 8).astype(int)), tuple(np.round(q * 8).astype(int)), color, th, cv2.LINE_AA, shift=3)
    cv[:] = cv * (1 - op) + layer * op

def curly_arrow(x0, y0, x1, y1, loop=True, n=120):
    """a hand-drawn arrow path from (x0,y0) to (x1,y1) with a small loop, like the design's arrows"""
    u = np.linspace(0, 1, n)
    x = x0 + (x1 - x0) * u; y = y0 + (y1 - y0) * u
    d = np.array([x1 - x0, y1 - y0], np.float32); d /= np.linalg.norm(d); nrm = np.array([-d[1], d[0]])
    bend = np.sin(u * math.pi) * 40
    x += nrm[0] * bend; y += nrm[1] * bend
    if loop:
        w = np.exp(-((u - 0.45) / 0.08) ** 2)
        ang = (u - 0.37) / 0.16 * 2 * math.pi
        x += w * 26 * np.sin(ang); y += w * 26 * (1 - np.cos(ang)) * -0.8
    return np.stack([x, y], 1)

def ellipse_pts(cx, cy, rx, ry, turns=1.85, start=-200, wob=0.05, n=260):
    a = np.radians(start) + np.linspace(0, 2 * math.pi * turns, n)
    r = 1 + wob * np.sin(a * 1.3 + 0.7) + 0.03 * np.linspace(0, 1, n)
    return np.stack([cx + rx * r * np.cos(a), cy + ry * r * np.sin(a) * (1 + 0.04 * np.linspace(-1, 1, n))], 1)

def sparkle(cv, cx, cy, r, op=1.0):
    if op <= 0 or r <= 1: return
    layer = cv.copy()
    pts = []
    for k in range(8):
        a = k * math.pi / 4 - math.pi / 2; rr = r if k % 2 == 0 else r * 0.22
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    cv2.fillPoly(layer, [np.round(np.array(pts) * 8).astype(np.int32)], (255, 255, 255), cv2.LINE_AA, shift=3)
    cv[:] = cv * (1 - op) + layer * op

def glow(cv, cx, cy, r, amt):
    if amt <= 0: return
    x0, y0, x1, y1 = int(max(cx - 3 * r, 0)), int(max(cy - 3 * r, 0)), int(min(cx + 3 * r, W)), int(min(cy + 3 * r, H))
    d2 = ((XX[y0:y1, x0:x1] - cx) ** 2 + (YY[y0:y1, x0:x1] - cy) ** 2) / (r * r)
    cv[y0:y1, x0:x1] += (np.exp(-d2) * amt)[..., None] * np.array([1.0, 0.97, 0.93], np.float32)

# ------------------------------------------------------------------ composition bar (fills right-to-left)
BX0, BX1, BY, BH = 130, 950, 1010, 70
def comp_bar(cv, silver_frac, alloy_frac, op=1.0, alloy_glow=0.0):
    if op <= 0: return
    layer = cv.copy()
    def rrect(img, x0, x1, col, th=-1):
        r = BH // 2
        if x1 - x0 < 2: return
        x0i, x1i = int(x0), int(x1)
        cv2.rectangle(img, (x0i + r, BY - r), (max(x1i - r, x0i + r), BY + r), col, th, cv2.LINE_AA) if th < 0 else None
        cv2.circle(img, (x0i + r, BY), r, col, th, cv2.LINE_AA); cv2.circle(img, (max(x1i - r, x0i + r), BY), r, col, th, cv2.LINE_AA)
    # track
    tr = layer.copy(); rrect(tr, BX0, BX1, (60, 38, 22)); layer[:] = layer * 0.35 + tr * 0.65
    full = BX1 - BX0
    clip = np.zeros((H, W), np.uint8)
    cv2.rectangle(clip, (BX0 + BH // 2, BY - BH // 2), (BX1 - BH // 2, BY + BH // 2), 1, -1)
    cv2.circle(clip, (BX0 + BH // 2, BY), BH // 2, 1, -1, cv2.LINE_AA); cv2.circle(clip, (BX1 - BH // 2, BY), BH // 2, 1, -1, cv2.LINE_AA)
    y0, y1 = BY - BH // 2 - 1, BY + BH // 2 + 2
    xs = XX[y0:y1]; ys = YY[y0:y1]
    xs_split = BX1 - full * 0.925
    sil = (xs >= BX1 - full * silver_frac).astype(np.float32)
    grad = (1.06 - 0.2 * (ys - (BY - BH / 2)) / BH)[..., None]
    silver = np.array(SILVER, np.float32) * grad
    al = ((xs < xs_split - 3) & (xs >= xs_split - 3 - (xs_split - BX0) * alloy_frac)).astype(np.float32)
    stripes = (((xs + ys) // 9) % 2 == 0).astype(np.float32)[..., None]
    gun = np.array(GUN, np.float32) * (0.92 + 0.16 * stripes) + alloy_glow * 70
    m = clip[y0:y1].astype(np.float32)
    reg = layer[y0:y1]
    reg[:] = reg * (1 - (sil * m)[..., None]) + silver * (sil * m)[..., None]
    reg[:] = reg * (1 - (al * m)[..., None]) + gun * (al * m)[..., None]
    if 0.02 < silver_frac < 0.999:   # bright leading edge while filling
        ex = BX1 - full * silver_frac
        reg += (np.exp(-((xs - ex) / 6) ** 2) * m * 90)[..., None]
    cv[:] = cv * (1 - op) + layer * op

# ------------------------------------------------------------------ soft line → firm ring diagram
def morph_line(cv, cx, cy, p, op=1.0, wobble_t=0.0):
    """p=0: a sagging, wobbly line (soft silver); p=1: a closed, perfectly round ring"""
    if op <= 0: return
    n = 140; u = np.linspace(0, 1, n)
    lx = cx - 230 + 460 * u
    ly = cy + 70 * np.sin(u * math.pi) + 9 * np.sin(u * 19 + wobble_t * 6) * (1 - p)
    a = -math.pi / 2 + u * 2 * math.pi
    rx, ry = cx + 120 * np.cos(a), cy + 120 * np.sin(a)
    q = eio(p)
    pts = np.stack([lerp(lx, rx, q), lerp(ly, ry, q)], 1)
    layer = cv.copy()
    th = int(lerp(14, 20, q))
    cv2.polylines(layer, [np.round(pts * 8).astype(np.int32)], p > 0.98, SILVER, th, cv2.LINE_AA, shift=3)
    cv2.polylines(layer, [np.round((pts - [0, th * 0.25]) * 8).astype(np.int32)], p > 0.98, (255, 255, 255), 3, cv2.LINE_AA, shift=3)
    cv[:] = cv * (1 - op) + layer * op

# ------------------------------------------------------------------ scenes
def scene(cv, sid, t, lt, D):
    """t: absolute time, lt: time since scene start, D: scene length"""
    if sid == "hook":
        # ring close-up from the design with a light sweep
        z = 2.7 + 0.12 * lt
        p = eo(prog(lt, 0.0, 0.7))
        glow(cv, 540, 930, 330, 26 * p)
        put(cv, RING_SH, 548, 1150, op=0.8 * p, scale=2.4)
        put(cv, L["ring"], 540, 930, op=p, scale=z, rot=-4 + 3 * math.sin(lt * 0.9), shine=-500 + 1900 * prog(lt, 0.3, 1.9))
        a, b = LT["real"]; q = eo(prog(t, a - 0.05, a + 0.35))
        ptext(cv, T["real"], 520, 390 + 30 * (1 - q), op=q)
        a, b = LT["why100"]
        q = eo(prog(t, a - 0.05, a + 0.3))
        # "ليش مو 100%؟" laid out right-to-left: [؟][100%][ليش مو]
        k = eb(prog(t, a + 0.8, a + 1.2), 2.4)
        s100 = 0.55 + 0.45 * k
        w_why, w_q, w_100 = T["why"].w - 60, T["q"].w - 60, T["100"].w - 60
        total = w_why + w_q + w_100 * 1.0 + 30
        xr = 520 + total / 2
        ptext(cv, T["why"], xr - w_why / 2, 1440, op=q)
        x100 = xr - w_why - 18 - w_100 / 2
        ptext(cv, T["100"], x100, 1418, op=q * clamp(0.4 + k), scale=s100)
        ptext(cv, T["q"], x100 - w_100 / 2 - 8 - w_q / 2, 1440, op=q)
        sfx("boom", a + 0.8)
    elif sid == "num":
        # ring slides aside and settles on the 5 while 925 rises behind it
        a, b = LT["secret"]
        m = eio(prog(lt, 0.0, 1.0))
        s = 1.42; gx, gy = 532, 900
        rp = POS["ring"] - GC
        rx, ry = lerp(540, gx + rp[0] * s, m), lerp(930, gy + rp[1] * s, m)
        ds = [eb(prog(lt, 0.35 + 0.12 * i, 0.95 + 0.12 * i)) for i in range(3)]
        group(cv, gx, gy, s, digits_op=[clamp(d) for d in ds], ring=False, rise=[90 * (1 - d) for d in ds],
              shine=-400 + 2600 * prog(t, LT["n925"][0], LT["n925"][1] + 0.4))
        put(cv, RING_SH, rx + 6, ry + 95 * lerp(2.4 / 1.42, 1, m), op=0.7, scale=lerp(2.4, s * 0.9, m))
        put(cv, L["ring"], rx, ry, scale=lerp(2.8, s, m), rot=lerp(-4, 0, m))
        q = eo(prog(t, a - 0.1, a + 0.3)); ptext(cv, T["secret"], 520, 380 + 30 * (1 - q), op=q)
        u = eio(prog(t, LT["n925"][0] - 0.1, LT["n925"][0] + 0.7))
        stroke(cv, [(840 - 640 * x, 1225 + 6 * math.sin(x * 7)) for x in np.linspace(0, 1, 60)], u, SILVER_D, 6)
        if u > 0: sfx("draw", LT["n925"][0] - 0.1)
    elif sid in ("pure", "alloy"):
        m = eio(prog(lt, 0.0, 0.8)) if sid == "pure" else 1.0
        s = lerp(1.42, 0.62, m); gx, gy = lerp(532, 540, m), lerp(900, 470, m)
        group(cv, gx, gy, s)
        a, b = LT["pure"]
        fill = eio(prog(t, a + 0.55, a + 2.4)) * 0.925
        alloy = eio(prog(t, LT["alloy"][0] + 0.15, LT["alloy"][0] + 0.9))
        comp_bar(cv, fill, alloy, op=eo(prog(t, a - 0.2, a + 0.2)), alloy_glow=0.6 * math.sin(math.pi * prog(t, LT["alloy"][0] + 0.6, LT["alloy"][0] + 1.6)))
        val = fill * 100
        lab = "92.5%" if fill >= 0.9249 else f"{val:.1f}%"
        xs = (BX1 + (BX1 - (BX1 - BX0) * 0.925)) / 2
        q = eo(prog(t, a + 0.45, a + 0.75))
        dim = 1.0 if sid == "pure" else 0.95
        ptext(cv, num(lab, 116), xs, 860, op=q * dim)
        if fill >= 0.9249: sfx("click", a + 2.4)
        ql = eo(prog(t, a + 1.4, a + 1.9)); ptext(cv, T["pure_lbl"], xs, 1128 + 20 * (1 - ql), op=ql * dim)
        if sid == "alloy":
            c0 = LT["alloy"][0]
            # arrow from the label up to the 7.5% segment
            stroke(cv, curly_arrow(300, 1330, 170, 1065), eio(prog(t, c0 + 0.3, c0 + 1.1)), SILVER_D, 5, head=True)
            if t >= c0 + 0.3: sfx("draw", c0 + 0.3)
            qa = eb(prog(t, c0 + 0.8, c0 + 1.3))
            ptext(cv, num("7.5%", 96, (226, 222, 218)), 470, 1300, op=clamp(qa), scale=max(qa, .01))
            ptext(cv, T["alloy_lbl"], 470, 1395, op=eo(prog(t, c0 + 1.1, c0 + 1.5)))
            if t >= c0 + 0.8: sfx("click", c0 + 0.8)
    elif sid == "why":
        a, b = LT["ask"]; s0, s1 = LT["soft"]; h0, h1 = LT["hard"]
        # "ليش نضيفها؟" beat on a near-empty screen, then the ring close-up and the diagram
        q = eo(prog(t, a - 0.15, a + 0.3)) * (1 - eio(prog(t, s0 - 0.1, s0 + 0.3)))
        ptext(cv, T["ask"], 520, 900, op=q, scale=0.95 + 0.05 * q)
        r = eo(prog(t, s0 - 0.1, s0 + 0.6))
        z = 2.3 + 0.25 * prog(t, s0, h1)
        glow(cv, 540, 640, 300, 22 * r)
        put(cv, RING_SH, 548, 830, op=0.75 * r, scale=2.1)
        put(cv, L["ring"], 540, 640, op=r, scale=z, rot=-3 + 4 * prog(t, s0, h1), shine=-600 + 2100 * prog(t, h0 + 0.8, h0 + 2.6))
        mp = prog(t, h0 + 0.2, h0 + 1.8)
        mo = eo(prog(t, s0 + 0.2, s0 + 0.7))
        morph_line(cv, 520, 1135, mp, op=mo, wobble_t=t)
        ptext(cv, T["soft_lbl"], 520, 1300, op=mo * (1 - eio(prog(mp, 0.3, 0.7))))
        ptext(cv, T["firm_lbl"], 520, 1300, op=mo * eio(prog(mp, 0.5, 0.9)))
        if mp >= 1: sparkle(cv, 520 + 85, 1135 - 85, 26 * eb(prog(t, h0 + 1.8, h0 + 2.2)), op=1 - prog(t, h0 + 2.4, h0 + 3.0))
        qh = eb(prog(t, h0 + 1.0, h0 + 1.5))
        ptext(cv, T["hard"], 520, 1430, op=clamp(qh), scale=max(qh, .01))
        if t >= h0 + 1.0: sfx("pop", h0 + 1.0)
        if t >= h0 + 1.8: sfx("ding", h0 + 1.8)
    elif sid == "name":
        a, b = LT["name"]
        # back to the design's composition: ring on the 5, a silver oval drawn around the name
        q = eo(prog(lt, 0.0, 0.7))
        group(cv, 536, 1010, 1.0 + 0.04 * prog(lt, 0, D), op=q, ring_shine=-400 + 1600 * prog(t, b - 0.6, b + 0.8))
        glow(cv, 380 + 380 * prog(lt, 0, D), 700, 420, 14)   # light moves slowly across
        ox, oy = 520, 600
        stroke(cv, ellipse_pts(ox, oy, 360, 128), eio(prog(t, a - 0.05, a + 1.2)), SILVER_D, 5)
        if t >= a: sfx("draw", a - 0.05)
        qa = eo(prog(t, a + 0.35, a + 0.85)); ptext(cv, T["name_ar"], ox, oy - 30, op=qa)
        qe = eo(prog(t, a + 1.25, a + 1.75)); ptext(cv, T["name_en"], ox, oy + 50, op=qe)
        stroke(cv, curly_arrow(700, 860, 690, 760), eio(prog(t, a + 1.0, a + 1.6)), SILVER_D, 5, head=True)
    elif sid == "end":
        n0 = LT["now"][0]; k0 = LT["know"][0]; v0 = LT["save"][0]
        rec = eio(prog(lt, 0.0, 1.4))
        # 925 recedes, the ring comes forward
        s = lerp(1.0, 0.92, rec); gx, gy = 536, lerp(1010, 800, rec)
        group(cv, gx, gy, s, op=lerp(1.0, 0.26, rec), ring=False, shine=-400 + 2600 * prog(t, LT["see"][0] + 1.0, LT["see"][1] + 0.2))
        rp = POS["ring"] - GC
        rx, ry = lerp(536 + rp[0], 540, rec), lerp(1010 + rp[1], 1000, rec)
        rs = lerp(1.0, 2.0, rec)
        glow(cv, rx, ry, 280, 24 * rec)
        put(cv, RING_SH, rx + 6, ry + 95 * rs / 1.0 * 0.95, op=0.75, scale=rs * 0.9)
        put(cv, L["ring"], rx, ry, scale=rs, rot=lerp(0, -4, rec) + 2 * math.sin(lt), shine=-500 + 2000 * prog(t, k0, k0 + 1.4))
        ql = eo(prog(lt, 0.4, 1.4))
        put(cv, L["logo"], 540, 330 - 20 * (1 - ql), op=ql, scale=2.4, shine=-300 + 2200 * prog(t, v0 + 0.5, v0 + 2.0))
        qk = eo(prog(t, LT["see"][0] + 0.9, LT["see"][0] + 1.4))
        ptext(cv, T["known"], 520, 1310 + 25 * (1 - qk), op=qk)
        sp = eb(prog(t, k0 + 0.1, k0 + 0.5))
        tw = 1 + 0.15 * math.sin(lt * 5)
        sparkle(cv, 520 - T["known"].w / 2 + 2, 1270, 22 * clamp(sp) * tw, op=clamp(sp))
        sparkle(cv, 520 - T["known"].w / 2 + 34, 1250, 11 * clamp(sp) * tw, op=clamp(sp))
        if t >= k0 + 0.1: sfx("ding", k0 + 0.1)
        qs = eo(prog(t, v0 - 0.1, v0 + 0.4)); ptext(cv, T["save"], 520, 1408 + 20 * (1 - qs), op=qs)
        # bookmark ("save") icon beside the line
        if qs > 0:
            bx, by = 520 - T["save"].w / 2 + 6, 1408
            pts = np.array([[bx - 16, by - 24], [bx + 16, by - 24], [bx + 16, by + 24], [bx, by + 12], [bx - 16, by + 24]], np.float32)
            layer = cv.copy(); cv2.fillPoly(layer, [np.round(pts * 8).astype(np.int32)], (222, 218, 214), cv2.LINE_AA, shift=3)
            cv[:] = cv * (1 - qs) + layer * qs
        ptext(cv, T["url"], 520, 1478, op=eo(prog(t, v0 + 0.6, v0 + 1.1)))

def render(si, t):
    sid, t0, t1 = SCENES[si]
    cv = BG.copy()
    if sid != "end": put(cv, L["logo"], 105, 92, op=0.95)
    scene(cv, sid, t, t - t0, t1 - t0)
    return cv

def frame(t):
    i = max(k for k, s in enumerate(SCENES) if s[1] <= t + 1e-9)
    cv = render(i, t)
    XF = 0.3
    if i > 0 and t - SCENES[i][1] < XF and SCENES[i][0] not in ("pure", "alloy", "end"):
        pv = render(i - 1, SCENES[i][1] - 1e-3)
        a = eio((t - SCENES[i][1]) / XF); cv = pv * (1 - a) + cv * a
    if t < 0.25: cv *= 0.4 + 0.6 * t / 0.25
    if t > TOTAL - 0.35: cv *= max(0.0, (TOTAL - t) / 0.35) * 0.6 + 0.4
    return cv

# ------------------------------------------------------------------ audio: re-spaced VO + curious pluck bed + SFX
def tone(f, d, a=0.004, r=0.25, amp=0.3):
    n = int(d * SR); tt = np.arange(n) / SR
    return (amp * np.minimum(tt / a, 1) * np.exp(-tt / r) * np.sin(2 * math.pi * f * tt)).astype(np.float32)

def build_audio(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", VO_MP3, "-af", "loudnorm=I=-15:TP=-1.5", "-f", "f32le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    src = np.frombuffer(raw, np.float32)
    n = int((TOTAL + 0.3) * SR)
    vo = np.zeros(n, np.float32)
    for k, a, b, g in VO:
        i0, i1 = int((a - PAD) * SR), int((b + PAD) * SR); seg = src[i0:i1].copy()
        f = int(0.03 * SR); seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
        st = int((LT[k][0] - PAD) * SR); vo[st:st + len(seg)] += seg[:n - st]
    tt = np.arange(n) / SR
    # music: 104 BPM, A-minor curious pizzicato motif + soft kick + pad; drops out on "ليش نضيفها؟"
    beat = 60 / 104
    mus = np.zeros(n, np.float32)
    motif = [440, 523.3, 659.3, 587.3, 523.3, 659.3, 783.99, 659.3]
    chords = [[220, 329.6], [174.6, 261.6], [196, 293.7], [164.8, 246.9]]
    drop0, drop1 = LT["ask"][0] - 0.1, LT["soft"][0] + 0.2
    for b in range(int(TOTAL / beat) + 1):
        tb = b * beat
        if drop0 < tb < drop1: continue
        st = int(tb * SR)
        kk = tone(55, 0.35, a=0.002, r=0.09, amp=0.32)
        if b % 2 == 0: mus[st:st + len(kk)] += kk[:max(0, n - st)]
        for h in range(2):   # eighth-note plucks
            ps = int((tb + h * beat / 2) * SR)
            if ps >= n: continue
            f = motif[(2 * b + h) % 8] * (1 if (b // 8) % 2 == 0 else 0.89)
            pl = tone(f, 0.5, r=0.11, amp=0.05) + tone(2 * f, 0.5, r=0.06, amp=0.015)
            mus[ps:ps + len(pl)] += pl[:n - ps]
    bar = 4 * beat
    for bi in range(int(TOTAL / bar) + 1):
        st, en = int(bi * bar * SR), min(int((bi + 1) * bar * SR), n)
        if st >= n: break
        seg = tt[st:en] - bi * bar
        env = np.minimum(seg / 0.6, 1) * np.clip((bar - seg) / 0.4, 0, 1)
        for f in chords[bi % 4]:
            mus[st:en] += 0.035 * env * np.sin(2 * math.pi * f * seg)
    gate = np.ones(n, np.float32)
    gate[(tt > drop0) & (tt < drop1)] = 0.15
    gate = np.convolve(gate, np.ones(int(0.12 * SR)) / int(0.12 * SR), mode="same")
    mus *= gate * np.minimum(tt / 0.4, 1) * np.clip((TOTAL + 0.3 - tt) / 1.2, 0, 1)
    lev = np.convolve(np.abs(vo), np.ones(int(0.2 * SR)) / int(0.2 * SR), mode="same")
    mus *= 1 - 0.5 * np.clip(lev / 0.04, 0, 1)
    fx = np.zeros(n, np.float32); rng = np.random.default_rng(7)
    def add(sig, t0):
        st = int(t0 * SR)
        if 0 <= st < n: fx[st:st + len(sig)] += sig[:n - st]
    for kind, t0 in sorted(SFX):
        if kind == "boom":   # muffled hit
            m = int(0.7 * SR); x = np.arange(m) / SR
            add((0.55 * np.sin(2 * math.pi * (70 - 30 * x) * x) * np.exp(-x / 0.18)).astype(np.float32), t0)
        elif kind == "click":
            add(tone(2400, 0.05, a=0.0005, r=0.012, amp=0.25) + tone(1200, 0.05, a=0.0005, r=0.02, amp=0.12), t0)
        elif kind == "pop":
            add(tone(880, 0.18, r=0.05, amp=0.2) + tone(1320, 0.18, r=0.04, amp=0.1), t0)
        elif kind == "ding":
            add(tone(1568, 1.2, r=0.4, amp=0.16) + tone(2349, 1.2, r=0.25, amp=0.07), t0)
        elif kind == "draw":   # pencil scribble: band-passed noise with a jittery envelope
            m = int(0.7 * SR); x = np.arange(m) / SR
            no = rng.standard_normal(m).astype(np.float32)
            no = np.convolve(no, np.ones(4) / 4, mode="same") - np.convolve(no, np.ones(40) / 40, mode="same")
            env = np.sin(np.pi * x / 0.7) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 9 * x)))
            add((0.11 * no * env).astype(np.float32), t0)
    for s in SCENES[1:]:   # soft whoosh at scene changes
        m = int(0.4 * SR); no = rng.standard_normal(m)
        w = np.convolve(no, np.ones(40) / 40, mode="same") * np.sin(np.linspace(0, math.pi, m)) ** 2 * 0.18
        add(w.astype(np.float32), s[1] - 0.2)
    mix = vo + mus + fx
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-ac", "2", "-c:a", "pcm_s16le", path], input=mix.astype(np.float32).tobytes(), check=True)

# ------------------------------------------------------------------ main
if STILLS:
    ts = [2.9, 6.6, 9.6, 12.5, 13.6, 15.6, 19.0, 22.8, 27.2, TOTAL - 0.4]
    tiles = [cv2.resize(np.clip(frame(x), 0, 255).astype(np.uint8), (324, 576), interpolation=cv2.INTER_AREA) for x in ts]
    cv2.imwrite(STILLS, np.vstack([np.hstack(tiles[:5]), np.hstack(tiles[5:])]))
    print({k: tuple(round(v, 2) for v in LT[k]) for k in LT}, [(s[0], round(s[1], 2)) for s in SCENES], round(TOTAL, 2))
    sys.exit()

tmpv, tmpa = OUT + ".video.mp4", OUT + ".audio.wav"
p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                      "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                      "-pix_fmt", "yuv420p", tmpv], stdin=subprocess.PIPE)
for i in range(int(round(TOTAL * FPS))):
    p.stdin.write(np.clip(frame(i / FPS), 0, 255).astype(np.uint8).tobytes())
p.stdin.close(); p.wait()
build_audio(tmpa)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmpv, "-i", tmpa, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart", OUT], check=True)
os.remove(tmpv); os.remove(tmpa)
print("wrote", OUT, round(TOTAL, 2), "s")
