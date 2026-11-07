"""Trust-building reel from the "5 نجوم بكلام عملائنا" reviews design, timed to a voiceover.

usage: python3 render_trust.py <vo_dir> <out.mp4> [--stills strip.jpg]
  vo_dir holds NN_<id>.wav per line + lines.json (same layout as ../edu).
"""
import os, sys, json, math, re, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "fonts")
W, H, FPS, SR = 1080, 1920, 30, 48000
VO, OUT = sys.argv[1], sys.argv[2]
STILLS = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--stills" else None
SHORT = "--short" in sys.argv   # tighter pacing for a 20-30 s TikTok / Reels cut

# ------------------------------------------------------------------ script (subtitle per voiceover line)
LINES = [
    ("hook",   "وش يقولون عملاءنا عن سيلفر هافن؟"),
    ("batool", ("بتول", "حلوة وشكلها يجنن")),
    ("yousef", ("يوسف، الرياض", "خواتم العقيق اليماني فخمة جداً")),
    ("noura",  ("نورة", "سلاسل الفضة جميلة جداً")),
    ("mohd",   ("محمد، الرياض", "مرة عجبني خواتم الفضة الإسترليني")),
    ("osama",  ("أسامة، الدمام", "أشكركم، فخم وتعامل كويس")),
    ("all",    "تقييمات 5 نجوم من الرياض للدمام للطائف"),
    ("tabby",  "قسّط مشترياتك على دفعات مع تابي"),
    ("cta",    "سيلفر هافن، فضة عيار 925"),
]

# ------------------------------------------------------------------ geometry of the design (1080x1920)
CARDS = {   # quad corners TL, TR, BR, BL
    "batool": [(200, 228), (425, 183), (428, 405), (180, 447)],
    "buthaina": [(400, 222), (660, 225), (662, 445), (393, 452)],
    "maha": [(640, 235), (865, 262), (862, 490), (630, 465)],
    "fatima": [(880, 290), (1080, 320), (1080, 560), (868, 520)],
    "osama": [(45, 505), (302, 545), (298, 733), (25, 700)],
    "khulood": [(735, 650), (960, 678), (960, 875), (718, 850)],
    "yousef": [(90, 780), (400, 805), (395, 1000), (75, 975)],
    "noura": [(125, 1035), (380, 1055), (375, 1270), (112, 1250)],
    "rawan": [(930, 925), (1080, 930), (1080, 1180), (915, 1150)],
    "mohd": [(640, 1350), (930, 1325), (920, 1610), (625, 1635)],
    "saud": [(965, 1300), (1080, 1270), (1080, 1555), (945, 1560)],
    "phone": [(345, 505), (815, 515), (790, 1385), (318, 1370)],
    "headline": [(40, 1495), (620, 1495), (620, 1725), (40, 1725)],
    "logo": [(40, 40), (165, 40), (165, 140), (40, 140)],
}
ORDER_ALL = ["buthaina", "maha", "fatima", "khulood", "rawan", "saud", "batool", "yousef", "noura", "mohd", "osama"]

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, t0, t1): return clamp((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t0)
def eo(x): return 1 - (1 - x) ** 3
def eio(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def eb(x, s=1.7): x -= 1; return x * x * ((s + 1) * x + s) + 1

IMG = cv2.imread(os.path.join(HERE, "src", "design-reviews.jpg")).astype(np.float32)
DIM = cv2.GaussianBlur(IMG, (0, 0), 5) * 0.32
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)

def quad_mask(q, feather=7, grow=4):
    m = np.zeros((H, W), np.uint8)
    pts = np.array(q, np.float32); c = pts.mean(0); pts = c + (pts - c) * (1 + grow / 120)
    cv2.fillPoly(m, [pts.astype(np.int32)], 255, cv2.LINE_AA)
    return cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), feather)

MASK = {k: quad_mask(v, 10 if k in ("phone", "headline") else 6) for k, v in CARDS.items()}
BBOX = {k: (int(min(p[0] for p in v)) - 80, int(min(p[1] for p in v)) - 80,
            int(max(p[0] for p in v)) + 80, int(max(p[1] for p in v)) + 80) for k, v in CARDS.items()}
# the logo is light-on-dark artwork: reveal only its bright strokes, not a box
MASK["logo"] = MASK["logo"] * np.clip((IMG.mean(2) - 80) / 90, 0, 1)
CEN = {k: tuple(np.array(v, np.float32).mean(0)) for k, v in CARDS.items()}

def light(canvas, key, amount, pop=0.0, glow=0.0):
    """reveal a card from the dimmed base: amount 0..1, pop = extra scale, glow = halo strength"""
    if amount <= 0.003: return
    x0, y0, x1, y1 = [max(0, v) for v in BBOX[key]]; x1, y1 = min(x1, W), min(y1, H)
    cx, cy = CEN[key]
    if pop > 0.001:
        s = 1 + pop
        M = np.array([[s, 0, cx - cx * s], [0, s, cy - cy * s]], np.float32)
        pad = int(max(x1 - x0, y1 - y0) * pop) + 4
        X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
        Ms = M.copy(); Ms[0, 2] -= X0; Ms[1, 2] -= Y0
        col = cv2.warpAffine(IMG, Ms, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR)
        msk = cv2.warpAffine(MASK[key], Ms, (X1 - X0, Y1 - Y0))
        x0, y0, x1, y1 = X0, Y0, X1, Y1
    else:
        col, msk = IMG[y0:y1, x0:x1], MASK[key][y0:y1, x0:x1]
    if glow > 0:
        halo = cv2.GaussianBlur(msk, (0, 0), 22) * glow
        canvas[y0:y1, x0:x1] += halo[..., None] * np.array([60, 170, 230], np.float32) * 0.55
    a = (msk * amount)[..., None]
    r = canvas[y0:y1, x0:x1]
    r += (col - r) * a

# gold star sparkle that travels across a card's star row
STAR_ROW = {"batool": ((235, 372), (365, 342)), "yousef": ((170, 925), (300, 935)), "noura": ((178, 1185), (312, 1197)),
            "mohd": ((720, 1532), (850, 1517)), "osama": ((100, 650), (215, 665))}
def sparkle(canvas, key, p):
    if key not in STAR_ROW or not 0 < p < 1: return
    (ax, ay), (bx, by) = STAR_ROW[key]
    x, y = ax + (bx - ax) * p, ay + (by - ay) * p
    r = 46
    X0, Y0 = int(x - r), int(y - r)
    d = np.hypot(XX[Y0:Y0 + 2 * r, X0:X0 + 2 * r] - x, YY[Y0:Y0 + 2 * r, X0:X0 + 2 * r] - y)
    core = np.exp(-(d / 9) ** 2) + 0.5 * np.exp(-(np.abs(XX[Y0:Y0 + 2 * r, X0:X0 + 2 * r] - x) / 2.0) ** 2) * np.exp(-(d / 30) ** 2) \
        + 0.5 * np.exp(-(np.abs(YY[Y0:Y0 + 2 * r, X0:X0 + 2 * r] - y) / 2.0) ** 2) * np.exp(-(d / 30) ** 2)
    canvas[Y0:Y0 + 2 * r, X0:X0 + 2 * r] += core[..., None] * np.array([150, 230, 255], np.float32) * math.sin(p * math.pi)

# ------------------------------------------------------------------ text
_fc = {}
def font(name, size):
    if (name, size) not in _fc:
        _fc[(name, size)] = ImageFont.truetype(os.path.join(FONTS, name), size, layout_engine=ImageFont.Layout.RAQM)
    return _fc[(name, size)]

def _run(txt, f, fill, rtl):
    kw = dict(direction="rtl", language="ar") if rtl else {}
    b = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), txt, font=f, **kw)
    asc, desc = f.getmetrics()
    im = Image.new("RGBA", (b[2] - b[0] + 8, asc + desc + 16), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - b[0], 8), txt, font=f, fill=fill[::-1] + (255,), **kw)
    return np.array(im)

def text(txt, size=56, color=(245, 245, 245), bold=True):
    ar = font("Tajawal-Arabic-Bold.ttf" if bold else "Tajawal-Arabic-Regular.ttf", size)
    la = font("Tajawal-Latin-Bold.ttf", size)
    runs = [r for r in re.split(r"([A-Za-z0-9][A-Za-z0-9.%,\-]*%?)", txt) if r.strip()]
    imgs = [_run(r.strip(), la if re.match(r"[A-Za-z0-9]", r.strip()) else ar, color,
                 not re.match(r"[A-Za-z0-9]", r.strip())) for r in runs]
    sp = int(size * 0.28); h = max(i.shape[0] for i in imgs); w = sum(i.shape[1] for i in imgs) + sp * (len(imgs) - 1)
    out = np.zeros((h, w, 4), np.uint8); x = w
    for i in imgs:
        x -= i.shape[1]; y = h - i.shape[0]
        out[y:y + i.shape[0], x:x + i.shape[1]] = np.maximum(out[y:y + i.shape[0], x:x + i.shape[1]], i); x -= sp
    return out.astype(np.float32)

def blit(canvas, rgba, cx, cy, op=1.0, scale=1.0):
    if op <= 0.003: return
    if abs(scale - 1) > 1e-3:
        rgba = cv2.resize(rgba, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    h, w = rgba.shape[:2]; x0, y0 = int(cx - w / 2), int(cy - h / 2)
    sx0, sy0 = max(0, -x0), max(0, -y0); x0c, y0c = max(0, x0), max(0, y0)
    x1c, y1c = min(W, x0 + w), min(H, y0 + h)
    if x1c <= x0c or y1c <= y0c: return
    src = rgba[sy0:sy0 + (y1c - y0c), sx0:sx0 + (x1c - x0c)]
    a = src[..., 3:] / 255 * op
    r = canvas[y0c:y1c, x0c:x1c]; r += (src[..., [2, 1, 0]] - r) * a

def pill(canvas, cx, cy, w, h, op, color=(40, 22, 12), alpha=0.62):
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    m = np.zeros((h, w), np.uint8); rr = h // 2
    cv2.rectangle(m, (rr, 0), (w - rr, h), 255, -1); cv2.circle(m, (rr, rr), rr, 255, -1); cv2.circle(m, (w - rr, rr), rr, 255, -1)
    m = (cv2.GaussianBlur(m, (0, 0), 1) / 255 * alpha * op)[..., None]
    r = canvas[y0:y0 + h, x0:x0 + w]; r += (np.array(color, np.float32) - r) * m

def name_quote(name, quote, size=50):
    """customer name in gold on the right (start of an RTL line), quote in white"""
    a, b = text(name, size, (60, 196, 245)), text(quote, size)
    gap = int(size * 0.6); h = max(a.shape[0], b.shape[0])
    out = np.zeros((h, a.shape[1] + gap + b.shape[1], 4), np.float32)
    out[h - a.shape[0]:, -a.shape[1]:] = a; out[h - b.shape[0]:, :b.shape[1]] = b
    return out

SUB = {k: name_quote(*s) if isinstance(s, tuple) else text(s, 50) for k, s in LINES}
T_HOOK = text("وش يقولون عملاءنا؟", 92)
T_HOOK2 = text("عن سيلفر هافن", 64, (200, 215, 235), bold=False)
T_STARS = text("★★★★★", 80, (40, 190, 250)) if False else None
T_END1 = text("فضة عيار 925", 78)
T_END2 = text("تجربة تستاهل الخمس نجوم", 52, (205, 215, 230), bold=False)
T_URL = _run("silverhaven-sa.com", font("PlayfairDisplay-Regular.ttf", 50), (225, 222, 218), False).astype(np.float32)
T_TABBY = text("قسّطها على 4 دفعات", 60) if False else None

def star_icon(size, color=(40, 190, 250)):
    im = np.zeros((size, size, 4), np.float32); c = size / 2
    pts = []
    for i in range(10):
        r = c * (0.95 if i % 2 == 0 else 0.42); a = -math.pi / 2 + i * math.pi / 5
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    m = np.zeros((size * 4, size * 4), np.uint8)
    cv2.fillPoly(m, [(np.array(pts) * 4).astype(np.int32)], 255, cv2.LINE_AA)
    m = cv2.resize(m, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)
    im[..., 0], im[..., 1], im[..., 2] = color[2], color[1], color[0]; im[..., 3] = m
    return im
STAR = star_icon(84)

# ------------------------------------------------------------------ timeline
info = json.load(open(os.path.join(VO, "lines.json")))
LEAD, TAIL = (0.15, 0.2) if SHORT else (0.25, 0.35)
scenes, t = [], 0.0
for i, ln in enumerate(info):
    d = LEAD + ln["dur"] + TAIL + ((1.0 if SHORT else 1.8) if ln["id"] == "cta" else 0)
    scenes.append(dict(id=ln["id"], t0=t, t1=t + d, wav=ln["file"], i=i)); t += d
TOTAL = t
SC = {s["id"]: s for s in scenes}
FOCUS = {"batool": "batool", "yousef": "yousef", "noura": "noura", "mohd": "mohd", "osama": "osama"}
SFX = []

def cam_keys():
    k = [(0, (1.0, 540, 960))]
    for s in scenes:
        a, b = s["t0"], s["t1"]
        if s["id"] == "hook": k += [(b - 0.5, (1.05, 540, 960))]
        elif s["id"] in FOCUS:
            cx, cy = CEN[FOCUS[s["id"]]]
            k += [(a + 0.7, (2.05, cx, cy)), (b - 0.35, (2.15, cx, cy))]
        elif s["id"] == "all": k += [(a + 0.9, (1.0, 540, 960)), (b - 0.2, (1.04, 540, 960))]
        elif s["id"] == "tabby":
            cx, cy = CEN["phone"]; k += [(a + 0.8, (1.55, cx, cy - 40)), (b - 0.3, (1.62, cx, cy - 40))]
        elif s["id"] == "cta": k += [(a + 0.8, (1.0, 540, 960))]
    return k
KEYS = cam_keys()

def camera(t):
    if t <= KEYS[0][0]: return KEYS[0][1]
    for (t0, v0), (t1, v1) in zip(KEYS, KEYS[1:]):
        if t <= t1:
            e = eio(prog(t, t0, t1)); return tuple(a + (b - a) * e for a, b in zip(v0, v1))
    return KEYS[-1][1]

def apply_cam(f, s, cx, cy):
    hw, hh = W / (2 * s), H / (2 * s)
    cx, cy = clamp(cx, hw, W - hw), clamp(cy, hh, H - hh)
    if abs(s - 1) < 1e-3: return f
    M = np.array([[s, 0, W / 2 - cx * s], [0, s, H / 2 - cy * s]], np.float32)
    return cv2.warpAffine(f, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def frame(t):
    i = max(k for k, s in enumerate(scenes) if s["t0"] <= t + 1e-9)
    sc = scenes[i]; lt = t - sc["t0"]; sid = sc["id"]
    c = DIM.copy()
    # cards already introduced stay lit
    lit_until = {k: 0.0 for k in CARDS}
    for s in scenes[:i]:
        if s["id"] in FOCUS: lit_until[FOCUS[s["id"]]] = 1.0
    if i > SC["all"]["i"]: lit_until.update({k: 1.0 for k in ORDER_ALL})
    for k, v in lit_until.items():
        if v > 0 and k not in ("phone", "headline", "logo"): light(c, k, 0.85)
    light(c, "logo", 0.9 * eo(prog(t, 0.2, 1.0)))
    if sid == "hook":
        for j, k in enumerate(ORDER_ALL):   # quick teaser flicker of cards
            p = prog(lt, 0.3 + 0.08 * j, 0.6 + 0.08 * j) * (1 - prog(lt, 1.6 + 0.05 * j, 2.2 + 0.05 * j))
            light(c, k, 0.5 * p)
    elif sid in FOCUS:
        k = FOCUS[sid]; p = prog(lt, 0.2, 0.8)
        light(c, k, eo(p), pop=0.06 * (1 - eb(p)) + 0.02 * eo(p), glow=0.9 * eo(p))
        sparkle(c, k, prog(lt, 0.9, 2.0))
        if abs(lt - 0.2) < 1 / FPS: SFX.append(("pop", t))
    elif sid == "all":
        for j, k in enumerate(ORDER_ALL):
            p = prog(lt, 0.4 + 0.16 * j, 0.8 + 0.16 * j)
            light(c, k, eo(p), pop=0.05 * (1 - eb(p)) if p < 1 else 0)
            if abs(lt - (0.4 + 0.16 * j)) < 1 / FPS: SFX.append(("tick", t))
    if sid in ("tabby", "cta") or i > SC["tabby"]["i"]:
        p = prog(lt, 0.2, 0.9) if sid == "tabby" else 1
        light(c, "phone", eo(p), glow=0.6 * eo(p) if sid == "tabby" else 0)
    if sid == "cta":
        light(c, "headline", eo(prog(lt, 0.3, 1.0)), glow=0.4)
        # a row of five stars pops in above the headline
        for j in range(5):
            q = prog(lt, 0.9 + 0.12 * j, 1.3 + 0.12 * j)
            if q > 0:
                blit(c, STAR, 120 + 95 * j, 1440, op=clamp(q * 2), scale=max(eb(q), 0.01))
                if abs(lt - (0.9 + 0.12 * j)) < 1 / FPS: SFX.append(("tick", t))
    s, cx, cy = camera(t)
    f = apply_cam(c, s, cx, cy)
    # ---- screen-space overlays
    if sid == "hook":
        q = eb(prog(lt, 0.1, 0.6)); blit(f, T_HOOK, W / 2, 860, op=clamp(q), scale=max(q, .01))
        blit(f, T_HOOK2, W / 2, 975, op=eo(prog(lt, 0.5, 1.0)))
        for j in range(5):
            q = prog(lt, 0.7 + 0.1 * j, 1.1 + 0.1 * j)
            if q > 0: blit(f, STAR, 350 + 95 * j, 1080, op=clamp(q * 2), scale=max(eb(q), 0.01) * 0.8)
        o = 1 - prog(lt, sc["t1"] - sc["t0"] - 0.45, sc["t1"] - sc["t0"])
        if o < 1: f = f * 1  # overlays fade via scene crossfade
    if sid == "cta":
        e = prog(lt, 1.8, 2.6)
        if e > 0:
            f = cv2.GaussianBlur(f, (0, 0), 1 + 10 * eio(e)) * (1 - 0.88 * eio(e))
            blit(f, cv2.resize(_logo_rgba, None, fx=3.4, fy=3.4), W / 2, 760, op=eio(e))
            for j, (img, y) in enumerate([(T_END1, 1060), (T_END2, 1160), (T_URL, 1300)]):
                q = eo(prog(lt, 2.2 + 0.2 * j, 2.8 + 0.2 * j)); blit(f, img, W / 2, y + 30 * (1 - q), op=q)
    if sid != "cta" or lt < 1.8:
        sp = SUB[sid]; o = eo(prog(lt, 0.1, 0.4)) * (1 - prog(lt, sc["t1"] - sc["t0"] - 0.25, sc["t1"] - sc["t0"]))
        if o > 0:
            sc_ = min(1.0, (W - 110) / sp.shape[1])
            sy = 1420 if SHORT else 1700   # keep clear of TikTok / Reels caption and button overlays
            pill(f, W / 2, sy, int(min(sp.shape[1] * sc_ + 70, W - 40)), int(sp.shape[0] * sc_ + 30), o)
            blit(f, sp, W / 2, sy + 4, op=o, scale=sc_)
    return f

_lm = MASK["logo"][40:140, 40:165]
_logo_rgba = np.dstack([IMG[40:140, 40:165][..., [2, 1, 0]], np.clip(
    (IMG[40:140, 40:165].mean(2) - 70) / 120, 0, 1) * 255]).astype(np.float32)

def render_frame(t):
    i = max(k for k, s in enumerate(scenes) if s["t0"] <= t + 1e-9)
    f = frame(t); sc = scenes[i]; lt = t - sc["t0"]
    XF = 0.3
    if i > 0 and lt < XF and sc["id"] in ("hook", "cta"):
        pass
    if t < 0.3: f = f * (t / 0.3)
    return f

# ------------------------------------------------------------------ audio
def tone(f, d, r=0.25, amp=0.3):
    n = int(d * SR); tt = np.arange(n) / SR
    return (amp * np.minimum(tt / 0.004, 1) * np.exp(-tt / r) * np.sin(2 * math.pi * f * tt)).astype(np.float32)

def build_audio(path):
    n = int((TOTAL + 0.3) * SR); vo = np.zeros((n, 2), np.float32)
    for s in scenes:
        x = subprocess.run(["ffmpeg", "-v", "error", "-i", s["wav"], "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                           capture_output=True).stdout
        a = np.frombuffer(x, np.float32).reshape(-1, 2); st = int((s["t0"] + LEAD) * SR)
        vo[st:st + len(a)] += a[:n - st]
    tt = np.arange(n) / SR; music = np.zeros(n, np.float32)
    # warm, hopeful pad: C - G - Am - F with a soft pluck arpeggio
    chords = [[261.6, 329.6, 392.0], [196.0, 246.9, 293.7], [220.0, 261.6, 329.6], [174.6, 220.0, 261.6]]
    bd = 3.2
    for b in range(int(TOTAL / bd) + 2):
        st, en = int(b * bd * SR), min(int((b + 1) * bd * SR + SR), n)
        if st >= n: break
        seg = tt[st:en] - b * bd; env = np.minimum(seg / 0.8, 1) * np.clip((bd + 1 - seg), 0, 1)
        for f in chords[b % 4]: music[st:en] += 0.045 * env * np.sin(2 * math.pi * f * seg)
        for k in range(8):
            ps = st + int(k * bd / 8 * SR)
            if ps < n:
                tn = tone(chords[b % 4][k % 3] * 2, 0.6, r=0.18, amp=0.03); music[ps:ps + len(tn)] += tn[:n - ps]
    music *= np.minimum(np.minimum(tt / 1.0, 1), np.clip((TOTAL + 0.3 - tt) / 1.8, 0, 1))
    k = int(0.25 * SR); lev = np.convolve(np.abs(vo[:, 0]), np.ones(k) / k, mode="same")
    music *= 1 - 0.55 * np.clip(lev / 0.05, 0, 1)
    sfx = np.zeros(n, np.float32)
    def add(sig, t0):
        st = int(t0 * SR); sfx[st:st + len(sig)] += sig[:max(0, n - st)]
    seen = set()
    for kind, t0 in SFX:
        key = (kind, round(t0, 2))
        if key in seen: continue
        seen.add(key)
        if kind == "pop": add(tone(988, 0.25, r=0.07, amp=0.22) + tone(1480, 0.25, r=0.05, amp=0.1), t0)
        if kind == "tick": add(tone(1760, 0.15, r=0.03, amp=0.12), t0)
    for s in scenes[1:]:
        m = int(0.4 * SR); w = np.convolve(np.random.default_rng(2).standard_normal(m), np.ones(40) / 40, "same")
        add((w * np.sin(np.linspace(0, math.pi, m)) ** 2 * 0.18).astype(np.float32), s["t0"] - 0.15)
    mix = vo + (music + sfx)[:, None]; mix /= max(1.0, np.abs(mix).max() / 0.95)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s16le", path], input=mix.tobytes(), check=True)

if STILLS:
    ts = [s["t0"] + (s["t1"] - s["t0"]) * 0.75 for s in scenes] + [TOTAL - 0.1]
    tiles = [cv2.resize(np.clip(render_frame(t), 0, 255).astype(np.uint8), (216, 384)) for t in ts]
    cv2.imwrite(STILLS, np.hstack(tiles)); sys.exit()

tv, ta = OUT + ".v.mp4", OUT + ".a.wav"
p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                      "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", tv], stdin=subprocess.PIPE)
for n in range(int(TOTAL * FPS)):
    p.stdin.write(np.clip(render_frame(n / FPS), 0, 255).astype(np.uint8).tobytes())
p.stdin.close(); p.wait()
build_audio(ta)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tv, "-i", ta, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                "-movflags", "+faststart", OUT], check=True)
os.remove(tv); os.remove(ta); print("wrote", OUT, round(TOTAL, 1), "s")
