"""Ad reel for three Silver Haven bracelets, built from three product photos.

usage: python3 render_ad.py <out.mp4> [--stills sheet.jpg]

Timeline (120 BPM, cuts land on beats):
  0.0-3.0   hook: three punch-in detail cuts, then the question "أي سوار يناسب ذوقك؟"
  3.0-8.0   1  tennis bracelet   (pan down the stones, pull out)
  8.0-13.0  2  hearts bracelet   (wide, push in along the hearts)
  13.0-18.0 3  pavé link bracelet (pan up the links, pull out)
  18.0-21.5 split screen 1 | 2 | 3  "رقمك المفضل؟ اكتبه بالتعليقات"
  21.5-25.5 end card: logo, 925, shop now, link, Tabby
Text stays inside y 180-1480 and x 150-930, clear of TikTok / Reels / Snap overlays.
"""
import os, sys, math, re, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "fonts")
W, H, FPS, SR = 1080, 1920, 30, 48000
BEAT = 0.5
OUT = sys.argv[1]
STILLS = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--stills" else None

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, t0, t1): return clamp((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t0)
def eo(x): return 1 - (1 - x) ** 3
def eio(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def eb(x, s=1.7): x -= 1; return x * x * ((s + 1) * x + s) + 1

# ------------------------------------------------------------------ photos (2160x3840) + light grade
def grade(im):
    f = im.astype(np.float32) / 255
    f = np.clip((f - 0.5) * 1.08 + 0.5 + 0.01, 0, 1)            # a touch of contrast
    g = f.mean(2, keepdims=True); f = np.clip(g + (f - g) * 1.06, 0, 1)   # gentle saturation
    return (f * 255).astype(np.float32)

PH = {n: grade(cv2.imread(os.path.join(HERE, "src", f"bracelet-{n}.jpg"))) for n in ("tennis", "hearts", "links")}
SMALL = {n: cv2.resize(v, (W, H), interpolation=cv2.INTER_AREA) for n, v in PH.items()}

# bracelet centre line in frame coordinates (1080x1920), read off the photos
POLY = {
    "tennis": [(668, 300), (672, 445), (662, 645), (655, 852), (650, 1060), (655, 1270), (662, 1400)],
    "hearts": [(420, 240), (440, 320), (480, 420), (497, 540), (525, 650), (548, 780), (572, 915),
               (610, 1050), (622, 1140), (668, 1260), (705, 1350)],
    "links":  [(598, 410), (612, 520), (638, 700), (650, 850), (665, 1000), (672, 1150), (690, 1300), (692, 1400)],
}

def find_glints(name, n=16):
    """bright specular points on the bracelet itself (not the shop's bokeh lights)"""
    g = cv2.cvtColor(SMALL[name].astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    th = g - cv2.morphologyEx(g, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)))
    near = np.zeros((H, W), np.uint8)
    cv2.polylines(near, [np.array(POLY[name], np.int32)], False, 255, 90)
    score = (th + 0.35 * g) * (near > 0) * (g > 170)
    mx = cv2.dilate(score, np.ones((41, 41), np.uint8))
    ys, xs = np.where((score == mx) & (score > 0))
    pts = sorted(zip(score[ys, xs], xs, ys), reverse=True)[:n]
    rng = np.random.default_rng(len(name))
    return [(float(x), float(y), rng.uniform(0, 2 * math.pi), rng.uniform(0.9, 1.6)) for _, x, y in pts]

GLINTS = {n: find_glints(n) for n in PH}

# ------------------------------------------------------------------ camera: (scale, cx, cy) in frame coords
def view(name, s, cx, cy):
    hw, hh = W / (2 * s), H / (2 * s)
    cx, cy = clamp(cx, hw, W - hw), clamp(cy, hh, H - hh)
    src = PH[name]; k = s / 2                                    # frame px -> output px is s; source is 2x frame
    x0, y0 = int(max(0, (cx - hw) * 2 - 6)), int(max(0, (cy - hh) * 2 - 6))
    x1, y1 = int(min(src.shape[1], (cx + hw) * 2 + 6)), int(min(src.shape[0], (cy + hh) * 2 + 6))
    roi = src[y0:y1, x0:x1]
    sig = 0.42 * (1 / k - 1) if k < 1 else 0
    if sig > 0.15: roi = cv2.GaussianBlur(roi, (0, 0), sig)
    M = np.array([[k, 0, W / 2 - cx * s + x0 * k], [0, k, H / 2 - cy * s + y0 * k]], np.float32)
    return cv2.warpAffine(roi, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT), (s, cx, cy)

def path(keys, lt):
    if lt <= keys[0][0]: return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if lt <= t1:
            e = eio(prog(lt, t0, t1)); return tuple(a + (b - a) * e for a, b in zip(v0, v1))
    return keys[-1][1]

# ------------------------------------------------------------------ sprites
def glint_sprite(size=120):
    c = size / 2; yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) - c
    r = np.hypot(xx, yy) + 1e-3
    rays = np.exp(-np.abs(yy) / 1.6) * np.exp(-np.abs(xx) / (size * 0.22)) + \
           np.exp(-np.abs(xx) / 1.6) * np.exp(-np.abs(yy) / (size * 0.22))
    d1, d2 = (xx + yy) / 1.414, (xx - yy) / 1.414
    rays += 0.45 * (np.exp(-np.abs(d1) / 1.3) * np.exp(-np.abs(d2) / (size * 0.08)) +
                    np.exp(-np.abs(d2) / 1.3) * np.exp(-np.abs(d1) / (size * 0.08)))
    a = np.clip(rays + np.exp(-(r / 5.5) ** 2) + 0.35 * np.exp(-(r / 16) ** 2), 0, 1.4)
    col = np.array([255, 250, 246], np.float32)                  # BGR, a hint of warmth
    return a[..., None] * col

GLINT = glint_sprite()

def add_sprite(f, spr, x, y, amt, scale=1.0):
    if amt <= 0.01: return
    if abs(scale - 1) > 0.02: spr = cv2.resize(spr, None, fx=scale, fy=scale)
    h, w = spr.shape[:2]; x0, y0 = int(x - w / 2), int(y - h / 2)
    sx, sy = max(0, -x0), max(0, -y0); X0, Y0 = max(0, x0), max(0, y0)
    X1, Y1 = min(W, x0 + w), min(H, y0 + h)
    if X1 <= X0 or Y1 <= Y0: return
    f[Y0:Y1, X0:X1] += spr[sy:sy + Y1 - Y0, sx:sx + X1 - X0] * amt

def glints(f, name, cam, t, gain=1.0, burst=0.0):
    s, cx, cy = cam
    for i, (x, y, ph, sp) in enumerate(GLINTS[name]):
        tw = max(0.0, math.sin(t * sp * 2.4 + ph)) ** 8
        amt = gain * (0.85 * tw + burst * (0.6 + 0.4 * ((i * 7) % 5) / 4))
        add_sprite(f, GLINT, W / 2 + s * (x - cx), H / 2 + s * (y - cy), amt, scale=0.55 + 0.35 * s / 2)

def sweep(f, p, angle=0.35, width=170, gain=120):
    """a band of light slides across the frame, boosting only highlights (metal, stones)"""
    if p <= 0 or p >= 1: return f
    yy, xx = np.ogrid[0:H, 0:W]
    pos = (xx + yy * angle) - (-600 + p * (W + H * angle + 1200))
    band = np.exp(-(pos / width) ** 2).astype(np.float32)
    luma = f.mean(2)
    f += (band * np.clip((luma - 135) / 90, 0, 1) * gain)[..., None]
    return f

VIG = None
def vignette(f, k=0.28):
    global VIG
    if VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.hypot((xx - W / 2) / (W * 0.62), (yy - H / 2) / (H * 0.62))
        VIG = (1 - k * np.clip(d - 0.35, 0, 1) ** 1.4)[..., None].astype(np.float32)
    return f * VIG

GRAD = np.clip((np.arange(H, dtype=np.float32) - 1000) / 480, 0, 1) ** 1.2
GRAD = (1 - 0.8 * GRAD)[:, None, None]
def lower_dark(f, o): return f * (1 - (1 - GRAD) * o)

# ------------------------------------------------------------------ text (Tajawal Arabic + Latin, RTL via raqm)
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

def text(txt, size=56, color=(245, 245, 245), bold=True, shadow=True):
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
    out = out.astype(np.float32)
    return with_shadow(out) if shadow else out

def with_shadow(rgba, r=None):
    """soft dark halo under the glyphs so text reads over any part of a photo"""
    h, w = rgba.shape[:2]; p = max(12, int(h * 0.25))
    big = np.zeros((h + 2 * p, w + 2 * p, 4), np.float32); big[p:p + h, p:p + w] = rgba
    sh = cv2.GaussianBlur(big[..., 3], (0, 0), r or max(4, h * 0.09)) * 0.75
    a = big[..., 3:] / 255
    col = big[..., :3] * a                                             # shadow colour is black
    alpha = a[..., 0] + (1 - a[..., 0]) * sh / 255
    out = np.zeros_like(big); out[..., 3] = alpha * 255
    out[..., :3] = np.where(alpha[..., None] > 1e-3, col / np.maximum(alpha[..., None], 1e-3), 0)
    return out

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

GOLD = (92, 192, 236)            # BGR champagne gold
CREAM = (225, 232, 240)

def badge(num, r=54):
    """gold disc with a dark serif numeral"""
    S = 4; size = 2 * r + 8
    m = np.zeros((size * S, size * S), np.uint8)
    cv2.circle(m, (size * S // 2, size * S // 2), r * S, 255, -1, cv2.LINE_AA)
    m = cv2.resize(m, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)
    yy = np.linspace(1.12, 0.86, size, dtype=np.float32)[:, None]   # light from the top
    out = np.zeros((size, size, 4), np.float32)
    for c in range(3): out[..., c] = np.clip(GOLD[::-1][c] * yy, 0, 255)
    out[..., 3] = m
    n = _run(str(num), font("PlayfairDisplay-Bold.ttf", int(r * 1.5)), (28, 30, 40), False).astype(np.float32)
    ys, xs = np.where(n[..., 3] > 0); n = n[ys.min():ys.max() + 1, xs.min():xs.max() + 1]   # tight to the glyph
    nh, nw = n.shape[:2]; y0, x0 = (size - nh) // 2, (size - nw) // 2
    a = n[..., 3:] / 255
    reg = out[y0:y0 + nh, x0:x0 + nw, :3]; reg += (n[..., :3] - reg) * a
    return with_shadow(out, r=8)

def logo_rgba():
    d = cv2.imread(os.path.join(HERE, "..", "src", "design-925.jpg"))[35:140, 40:165].astype(np.float32)
    d = cv2.resize(d, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    d = cv2.addWeighted(d, 1.6, cv2.GaussianBlur(d, (0, 0), 2.2), -0.6, 0)      # unsharp after upscale
    a = np.clip((d.mean(2) - 55) / 150, 0, 1) * 255
    return np.dstack([np.full(a.shape + (3,), 245, np.float32), a]).astype(np.float32)

LOGO = logo_rgba()

# product copy: only what the photos show (stones are zircon; colours are gold/white tones)
PRODUCTS = [
    dict(name="tennis", num=1, title="سوار التنس الكلاسيكي", sub="زركون لامع بتركيب 4 مخالب", t0=3.0, t1=8.0),
    dict(name="hearts", num=2, title="سوار القلوب", sub="ذهبي وفضي بتصميم ناعم", t0=8.0, t1=13.0),
    dict(name="links", num=3, title="سوار الروابط المرصّع", sub="لونين بلمسة زركون فخمة", t0=13.0, t1=18.0),
]
for p in PRODUCTS:
    p["T"], p["S"], p["B"] = text(p["title"], 74), text(p["sub"], 46, CREAM, bold=False), badge(p["num"])

CAM = {   # (local time, (scale, cx, cy))
    "tennis": [(0.0, (2.25, 668, 420)), (3.0, (2.25, 655, 1010)), (4.6, (1.12, 610, 1090))],
    "hearts": [(0.0, (1.12, 560, 900)), (2.2, (1.95, 520, 640)), (4.6, (2.05, 640, 1120))],
    "links":  [(0.0, (2.1, 688, 1300)), (2.8, (2.1, 612, 520)), (4.6, (1.12, 640, 1060))],
}

T_Q1 = text("أي سوار يناسب ذوقك؟", 88)
T_Q2 = text("3 تصاميم فضة عيار 925", 54, GOLD)
T_PICK1 = text("رقمك المفضل؟", 84)
T_PICK2 = text("اكتبه لنا بالتعليقات", 50, CREAM, bold=False)
T_END1 = text("فضة عيار 925 أصلية", 74)
T_END2 = text("تسوّق الآن من سيلفر هافن", 50, CREAM, bold=False)
T_URL = with_shadow(_run("silverhaven-sa.com", font("PlayfairDisplay-Regular.ttf", 52), GOLD, False).astype(np.float32))
T_TABBY = text("قسّطها على دفعات مع تابي", 42, CREAM, bold=False)

TOTAL = 25.5
SFX = []   # (kind, time) collected while rendering

def motion_blur(f, amount):
    L = int(amount)
    if L < 3: return f
    k = np.zeros((L, 1), np.float32); k[:] = 1 / L
    return cv2.filter2D(f, -1, k)

# ------------------------------------------------------------------ scenes
def scene_hook(t):
    cuts = [("tennis", (2.9, 660, 860)), ("hearts", (2.7, 528, 660)), ("links", (2.8, 640, 735))]
    if t < 1.5:
        i = int(t / BEAT); lt = t - i * BEAT; name, (s, cx, cy) = cuts[i]
        s = s * (1.12 - 0.12 * eo(prog(lt, 0, 0.35)))                 # punch-in settle
        f, cam = view(name, s, cx, cy)
        glints(f, name, cam, t * 3, gain=1.2, burst=0.9 * (1 - prog(lt, 0.0, 0.3)))
        f = f + 255 * 0.55 * (1 - prog(lt, 0, 0.09))                    # flash on the cut
        if lt < 1 / FPS: SFX.append(("hit", t))
        return vignette(f)
    lt = t - 1.5
    f, cam = view("tennis", 1.06 + 0.04 * lt, 660, 900)
    glints(f, "tennis", cam, t, gain=0.9)
    if lt < 1 / FPS: SFX.append(("rise", t))
    f = cv2.GaussianBlur(f, (0, 0), 1 + 9 * eo(prog(lt, 0, 0.4))) * (1 - 0.5 * eo(prog(lt, 0, 0.4)))
    f = f + 255 * 0.4 * (1 - prog(lt, 0, 0.12))
    q = eb(prog(lt, 0.05, 0.45)); blit(f, T_Q1, W / 2, 860, op=clamp(q * 1.5), scale=max(q, .01))
    q = eo(prog(lt, 0.35, 0.75)); blit(f, T_Q2, W / 2, 985 + 30 * (1 - q), op=q)
    return vignette(f)

def scene_product(p, t):
    lt = t - p["t0"]; d = p["t1"] - p["t0"]; name = p["name"]
    s, cx, cy = path(CAM[name], lt)
    f, cam = view(name, s, cx, cy)
    glints(f, name, cam, t, gain=1.0, burst=0.8 * math.exp(-((lt - 3.1) / 0.25) ** 2))
    f = sweep(f, prog(lt, 1.0, 2.0))
    if abs(lt - 3.0) < 0.5 / FPS: SFX.append(("chime", t))
    # lower third
    o = eo(prog(lt, 0.2, 0.6)) * (1 - prog(lt, d - 0.3, d - 0.05))
    f = lower_dark(f, o)
    q = prog(lt, 0.3, 0.75)
    if q > 0:
        blit(f, p["B"], W / 2, 1255, op=clamp(q * 2) * (1 - prog(lt, d - 0.3, d - 0.05)), scale=max(eb(q), .01))
        if abs(lt - 0.3) < 0.5 / FPS: SFX.append(("pop", t))
    q = eo(prog(lt, 0.5, 0.95)); blit(f, p["T"], W / 2, 1360 + 40 * (1 - q), op=q * (1 - prog(lt, d - 0.3, d - 0.05)))
    q = eo(prog(lt, 0.75, 1.2)); blit(f, p["S"], W / 2, 1452 + 30 * (1 - q), op=q * (1 - prog(lt, d - 0.3, d - 0.05)))
    f = vignette(f)
    # whip transition: blur out at the end, blur in at the start
    mb = 140 * eio(prog(lt, d - 0.18, d)) + 140 * (1 - eo(prog(lt, 0, 0.2)))
    if lt < 1 / FPS: SFX.append(("whoosh", t - 0.15))
    return motion_blur(f, mb)

PANEL_W, PANEL_H, PANEL_Y = 330, 1000, 830
PANEL_X = {"tennis": 905, "hearts": 540, "links": 175}             # 1 on the right (RTL reading order)
PANEL_CX = {"tennis": 662, "hearts": 560, "links": 645}
PANEL_CY = {"tennis": 860, "hearts": 800, "links": 900}

def round_mask(w, h, r):
    m = np.zeros((h, w), np.uint8)
    cv2.rectangle(m, (r, 0), (w - r, h), 255, -1); cv2.rectangle(m, (0, r), (w, h - r), 255, -1)
    for x, y in ((r, r), (w - r, r), (r, h - r), (w - r, h - r)): cv2.circle(m, (x, y), r, 255, -1, cv2.LINE_AA)
    return (m.astype(np.float32) / 255)[..., None]
PMASK = round_mask(PANEL_W, PANEL_H, 34)

def scene_pick(t):
    lt = t - 18.0
    bg, _ = view("tennis", 1.0, 540, 960)
    f = cv2.GaussianBlur(bg, (0, 0), 24) * 0.22
    for j, p in enumerate(PRODUCTS):
        name = p["name"]; q = eo(prog(lt, 0.05 + 0.18 * j, 0.6 + 0.18 * j))
        if q <= 0: continue
        if abs(lt - (0.05 + 0.18 * j)) < 0.5 / FPS: SFX.append(("whoosh", t))
        s = 1.25 + 0.06 * lt
        pv, cam = view(name, s, PANEL_CX[name], PANEL_CY[name])
        glints(pv, name, cam, t, gain=0.9)
        crop = pv[H // 2 - PANEL_H // 2:H // 2 + PANEL_H // 2, W // 2 - PANEL_W // 2:W // 2 + PANEL_W // 2]
        x0 = int(PANEL_X[name] - PANEL_W / 2); y0 = int(PANEL_Y - PANEL_H / 2 + 900 * (1 - q))
        ys0, ys1 = max(0, y0), min(H, y0 + PANEL_H)
        if ys1 <= ys0: continue
        m = PMASK[ys0 - y0:ys1 - y0] * clamp(q * 1.4)
        r = f[ys0:ys1, x0:x0 + PANEL_W]; r += (crop[ys0 - y0:ys1 - y0] - r) * m
        bq = prog(lt, 0.7 + 0.18 * j, 1.1 + 0.18 * j)
        if bq > 0:
            blit(f, p["B"], PANEL_X[name], PANEL_Y + PANEL_H / 2, op=clamp(bq * 2), scale=max(eb(bq), .01))
            if abs(lt - (0.7 + 0.18 * j)) < 0.5 / FPS: SFX.append(("pop", t))
    q = eb(prog(lt, 0.9, 1.3)); blit(f, T_PICK1, W / 2, 225, op=clamp(q * 1.5), scale=max(q, .01))
    q = eo(prog(lt, 1.3, 1.7)); blit(f, T_PICK2, W / 2, 1440 + 25 * (1 - q), op=q)
    out = 1 - eio(prog(lt, 3.2, 3.5))
    return f * (0.25 + 0.75 * out)

def scene_end(t):
    lt = t - 21.5
    bg, cam = view("tennis", 1.02 + 0.03 * lt, 600, 900)
    f = cv2.GaussianBlur(bg, (0, 0), 20) * 0.2
    glints(f, "tennis", cam, t, gain=0.35)
    q = eo(prog(lt, 0.1, 0.8)); blit(f, LOGO, W / 2, 640 + 30 * (1 - q), op=q, scale=0.74 + 0.06 * q)
    if abs(lt - 0.1) < 0.5 / FPS: SFX.append(("chime", t))
    for j, (img, y) in enumerate([(T_END1, 1000), (T_END2, 1100), (T_URL, 1225), (T_TABBY, 1345)]):
        q = eo(prog(lt, 0.6 + 0.2 * j, 1.1 + 0.2 * j)); blit(f, img, W / 2, y + 30 * (1 - q), op=q)
    f = sweep(f, prog(lt, 1.6, 2.6), gain=60)
    return vignette(f, 0.2)

def render_frame(t):
    if t < 3.0: f = scene_hook(t)
    elif t < 18.0: f = scene_product(next(p for p in PRODUCTS if p["t0"] <= t < p["t1"]), t)
    elif t < 21.5: f = scene_pick(t)
    else: f = scene_end(t)
    return f

# ------------------------------------------------------------------ audio: 120 BPM elegant pop bed + sfx
def tone(f, d, r=0.25, amp=0.3, att=0.004):
    n = int(d * SR); tt = np.arange(n) / SR
    return (amp * np.minimum(tt / att, 1) * np.exp(-tt / r) * np.sin(2 * math.pi * f * tt)).astype(np.float32)

def noise(d, seed, lp=1):
    n = int(d * SR); x = np.random.default_rng(seed).standard_normal(n).astype(np.float32)
    return np.convolve(x, np.ones(lp) / lp, "same").astype(np.float32) if lp > 1 else x

def build_audio(path):
    n = int((TOTAL + 0.2) * SR); tt = np.arange(n) / SR
    L, R = np.zeros(n, np.float32), np.zeros(n, np.float32)
    def put(buf, sig, t0, g=1.0):
        st = int(t0 * SR)
        if st >= n or st + len(sig) <= 0: return
        a = max(0, -st); st = max(0, st); m = min(len(sig) - a, n - st); buf[st:st + m] += sig[a:a + m] * g
    def both(sig, t0, g=1.0, pan=0.0): put(L, sig, t0, g * (1 - pan) ** .5); put(R, sig, t0, g * (1 + pan) ** .5)
    # chords Am - F - C - G, two bars each
    chords = [[220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [261.6, 329.6, 392.0], [196.0, 246.9, 293.7]]
    bar = 4 * BEAT
    for b in range(int(TOTAL / bar) + 1):
        ch = chords[(b // 1) % 4]; t0 = b * bar
        seg_n = int((bar + 0.6) * SR); st = np.arange(seg_n) / SR
        env = np.minimum(st / 0.25, 1) * np.clip((bar + 0.6 - st) / 0.6, 0, 1)
        pad = sum(np.sin(2 * math.pi * f * st) + 0.3 * np.sin(2 * math.pi * f * 2.003 * st) for f in ch)
        both((0.028 * env * pad).astype(np.float32), t0)
        both(tone(ch[0] / 2, bar, r=0.9, amp=0.12, att=0.01), t0)                        # bass
        for k in range(8):                                                                   # pluck arpeggio
            f = ch[[0, 1, 2, 1, 2, 0, 1, 2][k]] * 2
            both(tone(f, 0.5, r=0.14, amp=0.035), t0 + k * BEAT / 2, pan=0.35 if k % 2 else -0.35)
    kick = (np.sin(2 * math.pi * np.cumsum(60 + 90 * np.exp(-np.arange(int(.3 * SR)) / SR / .03)) / SR) *
            np.exp(-np.arange(int(.3 * SR)) / SR / .12) * 0.5).astype(np.float32)
    hat = (noise(0.06, 3) * np.exp(-np.arange(int(.06 * SR)) / SR / .012) * 0.05).astype(np.float32)
    hat = hat - np.convolve(hat, np.ones(6) / 6, "same")
    clap = (noise(0.2, 4, 3) * np.exp(-np.arange(int(.2 * SR)) / SR / .05) * 0.12).astype(np.float32)
    for k in range(int(TOTAL / BEAT)):
        tb = k * BEAT
        if tb < 1.5 or tb >= 24.0: continue                     # hook uses hits; end rings out
        if 18.0 <= tb < 21.5 and k % 2: continue                # half-time feel on the split screen
        both(kick, tb)
        both(hat, tb + BEAT / 2, pan=0.3)
        if k % 2 and tb >= 3.0: both(clap, tb)
    fade = np.minimum(tt / 0.05, 1) * np.clip((TOTAL + 0.2 - tt) / 2.2, 0, 1)
    sfx = np.zeros(n, np.float32)
    def add(sig, t0, g=1.0): put(sfx, sig, t0, g)
    seen = set()
    for kind, t0 in SFX:
        key = (kind, round(t0, 1))
        if key in seen: continue
        seen.add(key)
        if kind == "hit":
            m = int(0.6 * SR); e = np.exp(-np.arange(m) / SR / 0.16)
            boom = np.sin(2 * math.pi * np.cumsum(45 + 120 * np.exp(-np.arange(m) / SR / .04)) / SR) * e * 0.55
            add((boom + noise(0.6, 7, 4) * e * 0.08).astype(np.float32), t0)
            add(tone(2637, 0.6, r=0.18, amp=0.05) + tone(3520, 0.6, r=0.12, amp=0.04), t0 + 0.02)
        if kind == "rise":
            m = int(0.5 * SR); x = noise(0.5, 9, 2) * np.linspace(0, 1, m) ** 2 * 0.08
            add(x.astype(np.float32), t0 - 0.5)
            add(tone(1318, 1.2, r=0.4, amp=0.07) + tone(1976, 1.2, r=0.35, amp=0.05), t0)
        if kind == "chime":
            for j, fq in enumerate([2093, 2637, 3136, 4186]):
                add(tone(fq, 0.9, r=0.3, amp=0.05), t0 + 0.05 * j)
        if kind == "pop": add(tone(988, 0.25, r=0.06, amp=0.16) + tone(1480, 0.25, r=0.04, amp=0.07), t0)
        if kind == "whoosh":
            m = int(0.4 * SR); w = noise(0.4, 11, 30) * np.sin(np.linspace(0, math.pi, m)) ** 2 * 0.35
            add(w.astype(np.float32), t0)
    L = (L * fade + sfx); R = (R * fade + sfx)
    mix = np.stack([L, R], 1); mix /= max(1.0, np.abs(mix).max() / 0.92)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s16le", path], input=mix.astype(np.float32).tobytes(), check=True)

if STILLS and len(sys.argv) > 4:
    for t in map(float, sys.argv[4:]): cv2.imwrite(STILLS.replace('.jpg', f'-{t}.jpg'), np.clip(render_frame(t), 0, 255).astype(np.uint8))
    sys.exit()
if STILLS:
    ts = [0.2, 0.7, 1.2, 2.6, 3.5, 5.5, 7.6, 9.0, 11.0, 14.0, 17.5, 20.5, 25.0]
    tiles = [cv2.resize(np.clip(render_frame(t), 0, 255).astype(np.uint8), (270, 480)) for t in ts]
    rows = [np.hstack(tiles[i:i + 7] + [np.zeros((480, 270, 3), np.uint8)] * (7 - len(tiles[i:i + 7]))) for i in (0, 7)]
    cv2.imwrite(STILLS, np.vstack(rows)); sys.exit()

tv, ta = OUT + ".v.mp4", OUT + ".a.wav"
p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                      "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", tv], stdin=subprocess.PIPE)
for k in range(int(TOTAL * FPS)):
    p.stdin.write(np.clip(render_frame(k / FPS), 0, 255).astype(np.uint8).tobytes())
p.stdin.close(); p.wait()
build_audio(ta)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tv, "-i", ta, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                "-movflags", "+faststart", OUT], check=True)
os.remove(tv); os.remove(ta); print("wrote", OUT, TOTAL, "s")
