"""Silver Haven bracelets ad v2: fast TikTok / Reels cut with a cinematic finish, built from three 4K product photos.

usage:
  python3 render_v2.py main  <out.mp4>          # 28 s main ad
  python3 render_v2.py short <out.mp4>          # 9 s cut
  python3 render_v2.py cover <out.jpg>          # cover image
  python3 render_v2.py sheet <main|short> <out.jpg> [t ...]   # contact sheet / storyboard frames

Brand look: deep navy, silver, white. The product's own colours are not shifted (the gold-tone links stay
as photographed); the grade only tints the shadows toward navy and adds a little clarity.
Every "shot" is a framed region of one of the photos (see PRODUCTION.md for the shot list).
Text stays inside x 150-930, y 180-1480 (TikTok / Reels / Snap safe zone) and next to the bracelet, not on it.
"""
import os, sys, math, re, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "fonts")
W, H, FPS, SR = 1080, 1920, 30, 48000
BEAT = 0.5                                   # 120 BPM

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, t0, t1): return clamp((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t0)
def eo(x): return 1 - (1 - x) ** 3
def eio(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def ramp(x): return eio(eio(x))              # speed ramp: long slow ends, very fast middle
def eb(x, s=1.5): x -= 1; return x * x * ((s + 1) * x + s) + 1

# ------------------------------------------------------------------ colour: navy / silver / white
NAVY = np.array([58, 33, 16], np.float32)            # BGR  #10213A
NAVY_D = np.array([30, 16, 7], np.float32)           # BGR  #07101E
SILVER = (212, 208, 202)                              # BGR  (cool silver)
WHITE = (246, 246, 246)

def grade(im):
    f = im.astype(np.float32) / 255
    lum = f.mean(2, keepdims=True)
    f = np.clip((f - 0.5) * 1.06 + 0.5, 0, 1)                                    # gentle contrast
    sh = (1 - lum) ** 2.2                                                         # shadows only
    f = f + sh * (np.array([0.035, 0.008, -0.02], np.float32))                    # navy split-tone in the darks
    f8 = (np.clip(f, 0, 1) * 255).astype(np.float32)
    blur = cv2.GaussianBlur(f8, (0, 0), 3)
    return np.clip(f8 + 0.35 * (f8 - blur), 0, 255)                              # a little clarity on metal edges

PH = {n: grade(cv2.imread(os.path.join(HERE, "src", f"bracelet-{n}.jpg"))) for n in ("tennis", "hearts", "links")}
SMALL = {n: cv2.resize(v, (W, H), interpolation=cv2.INTER_AREA) for n, v in PH.items()}

POLY = {   # bracelet centre line, frame coords (1080x1920)
    "tennis": [(668, 300), (672, 445), (662, 645), (655, 852), (650, 1060), (655, 1270), (662, 1400)],
    "hearts": [(420, 240), (440, 320), (480, 420), (497, 540), (525, 650), (548, 780), (572, 915),
               (610, 1050), (622, 1140), (668, 1260), (705, 1350)],
    "links":  [(598, 410), (612, 520), (638, 700), (650, 850), (665, 1000), (672, 1150), (690, 1300), (692, 1400)],
}
def bx(name, y):
    p = POLY[name]
    for (x0, y0), (x1, y1) in zip(p, p[1:]):
        if y <= y1: return x0 + (x1 - x0) * clamp((y - y0) / (y1 - y0))
    return p[-1][0]

def find_glints(name, n=18):
    g = cv2.cvtColor(SMALL[name].astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    th = g - cv2.morphologyEx(g, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)))
    near = np.zeros((H, W), np.uint8)
    cv2.polylines(near, [np.array(POLY[name], np.int32)], False, 255, 90)
    score = (th + 0.35 * g) * (near > 0) * (g > 170)
    mx = cv2.dilate(score, np.ones((41, 41), np.uint8))
    ys, xs = np.where((score == mx) & (score > 0))
    pts = sorted(zip(score[ys, xs], xs, ys), reverse=True)[:n]
    rng = np.random.default_rng(len(name) + 3)
    return [(float(x), float(y), rng.uniform(0, 2 * math.pi), rng.uniform(0.9, 1.6)) for _, x, y in pts]
GLINTS = {n: find_glints(n) for n in PH}

# ------------------------------------------------------------------ camera
def fit(s, cx, cy):
    hw, hh = W / (2 * s), H / (2 * s)
    return s, clamp(cx, hw, W - hw), clamp(cy, hh, H - hh)

def view(name, s, cx, cy):
    s, cx, cy = fit(s, cx, cy); hw, hh = W / (2 * s), H / (2 * s)
    src = PH[name]; k = s / 2
    x0, y0 = int(max(0, (cx - hw) * 2 - 6)), int(max(0, (cy - hh) * 2 - 6))
    x1, y1 = int(min(src.shape[1], (cx + hw) * 2 + 6)), int(min(src.shape[0], (cy + hh) * 2 + 6))
    roi = src[y0:y1, x0:x1]
    sig = 0.42 * (1 / k - 1) if k < 1 else 0
    if sig > 0.15: roi = cv2.GaussianBlur(roi, (0, 0), sig)
    M = np.array([[k, 0, W / 2 - cx * s + x0 * k], [0, k, H / 2 - cy * s + y0 * k]], np.float32)
    interp = cv2.INTER_CUBIC if k > 1 else cv2.INTER_LINEAR
    return cv2.warpAffine(roi, M, (W, H), flags=interp, borderMode=cv2.BORDER_REFLECT), (s, cx, cy)

def side(name, s, y, sx=330):
    """camera centre that puts the bracelet (at frame height y) on screen column sx: the left third"""
    return (s, bx(name, y) + (W / 2 - sx) / s, y)

def path(keys, lt, ease=eio):
    if lt <= keys[0][0]: return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if lt <= t1:
            e = ease(prog(lt, t0, t1)); return tuple(a + (b - a) * e for a, b in zip(v0, v1))
    return keys[-1][1]

def shot(name, cam_at, t, dt=1 / FPS):
    """render a camera path; adds motion blur only when the camera actually moves fast (speed ramp)"""
    c0, c1 = fit(*cam_at(t - dt / 2)), fit(*cam_at(t + dt / 2))
    f, cam = view(name, *cam_at(t))
    vy = abs(c1[2] - c0[2]) * cam[0]; vz = abs(c1[0] - c0[0]) / cam[0] * 900
    L = int(min(22, max(vy, vz) * 0.4))
    if L >= 3:
        k = np.full((L, 1), 1 / L, np.float32); f = cv2.filter2D(f, -1, k)
    return f, cam

# ------------------------------------------------------------------ light
def glint_sprite(size=120):
    c = size / 2; yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) - c
    r = np.hypot(xx, yy) + 1e-3
    rays = np.exp(-np.abs(yy) / 1.5) * np.exp(-np.abs(xx) / (size * 0.22)) + \
           np.exp(-np.abs(xx) / 1.5) * np.exp(-np.abs(yy) / (size * 0.22))
    d1, d2 = (xx + yy) / 1.414, (xx - yy) / 1.414
    rays += 0.4 * (np.exp(-np.abs(d1) / 1.2) * np.exp(-np.abs(d2) / (size * 0.08)) +
                   np.exp(-np.abs(d2) / 1.2) * np.exp(-np.abs(d1) / (size * 0.08)))
    a = np.clip(rays + np.exp(-(r / 5) ** 2) + 0.3 * np.exp(-(r / 15) ** 2), 0, 1.4)
    return a[..., None] * np.array([255, 251, 248], np.float32)      # neutral-cool white, no gold cast
GLINT = glint_sprite()

def add_sprite(f, spr, x, y, amt, scale=1.0):
    if amt <= 0.01: return
    if abs(scale - 1) > 0.02: spr = cv2.resize(spr, None, fx=scale, fy=scale)
    h, w = spr.shape[:2]; x0, y0 = int(x - w / 2), int(y - h / 2)
    sx, sy = max(0, -x0), max(0, -y0); X0, Y0 = max(0, x0), max(0, y0)
    X1, Y1 = min(W, x0 + w), min(H, y0 + h)
    if X1 <= X0 or Y1 <= Y0: return
    f[Y0:Y1, X0:X1] += spr[sy:sy + Y1 - Y0, sx:sx + X1 - X0] * amt

def glints(f, name, cam, t, gain=0.85, burst=0.0, ox=0, oy=0):
    s, cx, cy = cam
    for i, (x, y, ph, sp) in enumerate(GLINTS[name]):
        tw = max(0.0, math.sin(t * sp * 2.4 + ph)) ** 10
        amt = gain * (0.8 * tw + burst * (0.55 + 0.45 * ((i * 7) % 5) / 4))
        add_sprite(f, GLINT, ox + W / 2 + s * (x - cx), oy + H / 2 + s * (y - cy), amt, scale=min(1.3, 0.5 + 0.3 * s / 2))

YY, XX = np.ogrid[0:H, 0:W]
def sweep(f, p, angle=0.35, width=160, gain=95):
    if p <= 0 or p >= 1: return f
    pos = (XX + YY * angle) - (-600 + p * (W + H * angle + 1200))
    band = np.exp(-(pos / width) ** 2).astype(np.float32)
    f += (band * np.clip((f.mean(2) - 140) / 90, 0, 1) * gain)[..., None]
    return f

_vg = np.hypot((np.arange(W) - W / 2) / (W * 0.62), (np.arange(H)[:, None] - H / 2) / (H * 0.62))
VIG = (1 - 0.30 * np.clip(_vg - 0.35, 0, 1) ** 1.4)[..., None].astype(np.float32)
def vignette(f): return f * VIG

def scrim(f, cx, cy, rx, ry, op):
    """soft navy glow behind a text block so white type reads without a hard box"""
    if op <= 0: return f
    m = np.exp(-(((XX - cx) / rx) ** 2 + ((YY - cy) / ry) ** 2) ** 1.2).astype(np.float32)[..., None] * 0.5 * op
    return f + (NAVY * 0.6 - f) * m

def navy_bg():
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    return (NAVY * (1 - g) + NAVY_D * g) * np.ones((1, W, 1), np.float32)
BG = navy_bg()

# ------------------------------------------------------------------ type
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

def with_shadow(rgba, r=None, k=0.6):
    h, w = rgba.shape[:2]; p = max(12, int(h * 0.25))
    big = np.zeros((h + 2 * p, w + 2 * p, 4), np.float32); big[p:p + h, p:p + w] = rgba
    sh = cv2.GaussianBlur(big[..., 3], (0, 0), r or max(4, h * 0.08)) * k
    a = big[..., 3] / 255; alpha = a + (1 - a) * sh / 255
    out = np.zeros_like(big); out[..., 3] = alpha * 255
    out[..., :3] = np.where(alpha[..., None] > 1e-3, big[..., :3] * a[..., None] / np.maximum(alpha[..., None], 1e-3), 0)
    return out

def text(txt, size=56, color=WHITE, bold=True, shadow=True):
    ar = font("Tajawal-Arabic-Bold.ttf" if bold else "Tajawal-Arabic-Regular.ttf", size)
    la = font("Tajawal-Latin-Bold.ttf", size)
    runs = [r for r in re.split(r"([A-Za-z0-9][A-Za-z0-9.%,\-]*%?|\.+)", txt) if r.strip()]   # dots: Latin font (Tajawal Arabic has none)
    imgs = [_run(r.strip(), la if re.match(r"[A-Za-z0-9.]", r.strip()) else ar, color,
                 not re.match(r"[A-Za-z0-9.]", r.strip())) for r in runs]
    gaps = [0 if re.fullmatch(r"\.+", r.strip()) else int(size * 0.26) for r in runs[1:]]   # dots hug the word
    h = max(i.shape[0] for i in imgs); w = sum(i.shape[1] for i in imgs) + sum(gaps)
    out = np.zeros((h, w, 4), np.uint8); x = w
    for j, i in enumerate(imgs):
        x -= i.shape[1]; y = h - i.shape[0]
        out[y:y + i.shape[0], x:x + i.shape[1]] = np.maximum(out[y:y + i.shape[0], x:x + i.shape[1]], i)
        if j < len(gaps): x -= gaps[j]
    out = out.astype(np.float32)
    return with_shadow(out) if shadow else out

def blit(canvas, rgba, cx, cy, op=1.0, scale=1.0, right=None):
    """right=x aligns the block's right edge to x (Arabic is right-aligned)"""
    if op <= 0.003: return
    if abs(scale - 1) > 1e-3: rgba = cv2.resize(rgba, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    h, w = rgba.shape[:2]
    if right is not None: cx = right - w / 2
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    sx0, sy0 = max(0, -x0), max(0, -y0); x0c, y0c = max(0, x0), max(0, y0)
    x1c, y1c = min(W, x0 + w), min(H, y0 + h)
    if x1c <= x0c or y1c <= y0c: return
    src = rgba[sy0:sy0 + (y1c - y0c), sx0:sx0 + (x1c - x0c)]
    a = src[..., 3:] / 255 * op
    r = canvas[y0c:y1c, x0c:x1c]; r += (src[..., [2, 1, 0]] - r) * a

def wipe(rgba, p):
    """reveal a text block from right to left (reading direction)"""
    if p >= 1: return rgba
    out = rgba.copy(); w = out.shape[1]; edge = int(w * (1 - eo(p)))
    ramp_ = np.clip((np.arange(w) - edge) / 40, 0, 1).astype(np.float32)
    out[..., 3] *= ramp_[None]; return out

def hline(f, x1, x0, y, p, op=1.0, col=SILVER):
    """thin silver rule drawn right-to-left"""
    if p <= 0: return
    xe = int(x1 - (x1 - x0) * eo(p))
    f[y:y + 3, xe:x1] += (np.array(col, np.float32) - f[y:y + 3, xe:x1]) * 0.9 * op

def badge(num, r=40):
    S = 4; size = 2 * r + 10
    m = np.zeros((size * S, size * S), np.uint8); ring = m.copy()
    cv2.circle(m, (size * S // 2,) * 2, r * S, 255, -1, cv2.LINE_AA)
    cv2.circle(ring, (size * S // 2,) * 2, r * S, 255, 2 * S, cv2.LINE_AA)
    m = cv2.resize(m, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)
    ring = cv2.resize(ring, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    g = np.linspace(1.10, 0.80, size, dtype=np.float32)[:, None]
    out = np.zeros((size, size, 4), np.float32)
    for c, v in enumerate(SILVER[::-1]): out[..., c] = np.clip(v * g + 255 * 0.15 * ring, 0, 255)
    out[..., 3] = m
    n = _run(str(num), font("PlayfairDisplay-Bold.ttf", int(r * 1.45)), tuple(int(v) for v in NAVY), False).astype(np.float32)
    ys, xs = np.where(n[..., 3] > 0); n = n[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    nh, nw = n.shape[:2]; y0, x0 = (size - nh) // 2, (size - nw) // 2
    a = n[..., 3:] / 255; reg = out[y0:y0 + nh, x0:x0 + nw, :3]; reg += (n[..., :3] - reg) * a
    return with_shadow(out, r=8)

def logo_rgba():
    d = cv2.imread(os.path.join(HERE, "..", "src", "design-925.jpg"))[35:140, 40:165].astype(np.float32)
    d = cv2.resize(d, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    d = cv2.addWeighted(d, 1.6, cv2.GaussianBlur(d, (0, 0), 2.2), -0.6, 0)
    a = np.clip((d.mean(2) - 55) / 150, 0, 1) * 255
    return np.dstack([np.full(a.shape + (3,), 246, np.float32), a]).astype(np.float32)
LOGO = logo_rgba()

def round_mask(w, h, r):
    m = np.zeros((h, w), np.uint8)
    cv2.rectangle(m, (r, 0), (w - r, h), 255, -1); cv2.rectangle(m, (0, r), (w, h - r), 255, -1)
    for x, y in ((r, r), (w - r, r), (r, h - r), (w - r, h - r)): cv2.circle(m, (x, y), r, 255, -1, cv2.LINE_AA)
    return (m.astype(np.float32) / 255)[..., None]

# ------------------------------------------------------------------ copy (Saudi dialect, only provable claims)
T = dict(
    wait=text("استني..", 104), look=text("شوفي هاللمعة", 66, SILVER),
    three=text("ثلاث أساور", 96), one=text("وحدة منها لك", 70, SILVER),
    silver925=text("فضة عيار 925", 84), daily=text("تنلبس يومياً.. وتليق بمناسباتك", 44, SILVER, bold=False),
    which=text("أي رقم يشبهك؟", 66), comment=text("قوليه لنا بالتعليقات", 44, SILVER, bold=False),
    discover=text("اكتشفي التشكيلة كاملة", 70), tabby=text("وتقدرين تقسّطينها مع تابي", 42, SILVER, bold=False),
    choose=text("أي وحدة تختارين؟", 76), nums=text("1 أو 2 أو 3", 60, SILVER),
    cover1=text("وحدة منها لك", 104), cover2=text("ثلاث أساور فضة عيار 925", 50, SILVER, bold=False),
)
T["url"] = with_shadow(_run("silverhaven-sa.com", font("PlayfairDisplay-Regular.ttf", 50), SILVER, False).astype(np.float32))
PRODUCTS = [
    dict(name="tennis", num=1, title="تنس كلاسيكي", sub="زركون بتركيب 4 مخالب"),
    dict(name="hearts", num=2, title="قلوب بلونين", sub="ذهبي وفضي بالتناوب"),
    dict(name="links", num=3, title="روابط مرصّعة", sub="فضي مرصّع وروابط ذهبية"),
]
for p in PRODUCTS: p["T"], p["S"], p["B"] = text(p["title"], 72), text(p["sub"], 42, SILVER, bold=False), badge(p["num"])
PB = {p["name"]: p for p in PRODUCTS}

SFX = []
def cue(kind, t, at, lt):
    if abs(lt - at) < 0.5 / FPS: SFX.append((kind, t))

# ------------------------------------------------------------------ scenes (each takes global t and local lt)
def sc_hook(t, lt, d, pull_at=2.1):
    """extreme macro on one tennis stone, glint burst, text, then speed-ramp pull-out to the whole bracelet"""
    cam = lambda x: path([(0.0, (3.15, 736, 752)), (pull_at, (2.9, 742, 752)), (pull_at + 0.6, (1.22, 640, 880)),
                          (d, (1.18, 640, 880))], x - (t - lt), ease=ramp)
    f, c = shot("tennis", lambda x: cam(x), t)
    glints(f, "tennis", c, t, gain=1.0, burst=1.1 * math.exp(-((lt - 1.0) / 0.18) ** 2) + 0.9 * math.exp(-((lt - pull_at - 0.62) / 0.2) ** 2))
    f = f + 255 * 0.35 * (1 - prog(lt, 0, 0.1))                              # open on a soft flash
    cue("impact", t, 0.0, lt); cue("sparkle", t, 0.95, lt); cue("whoosh", t, pull_at - 0.05, lt); cue("sparkle", t, pull_at + 0.6, lt)
    o = 1 - prog(lt, pull_at - 0.25, pull_at)
    f = scrim(f, 760, 900, 300, 200, 0.7 * eo(prog(lt, 0.1, 0.4)) * o)
    q = eb(prog(lt, 0.15, 0.45)); blit(f, T["wait"], 0, 850, op=clamp(q * 1.6) * o, scale=max(q, .01), right=935)
    blit(f, wipe(T["look"], prog(lt, 0.95, 1.35)), 0, 965, op=o, right=935)
    cue("tick", t, 0.15, lt); cue("tick", t, 0.95, lt)
    return vignette(f)

def sc_macro(name, a, b, t, lt, d):
    """a short detail cut: slow drift from camera a to camera b"""
    f, c = shot(name, lambda x: path([(0, a), (d, b)], x - (t - lt), ease=lambda u: u), t)
    glints(f, name, c, t, gain=1.0, burst=0.7 * math.exp(-((lt - 0.15) / 0.15) ** 2))
    return vignette(f)

def sc_title(t, lt, d):
    """chapter card over a softened wide shot: ثلاث أساور / وحدة منها لك"""
    f, c = view("hearts", 1.18 + 0.05 * lt, 590, 900)
    glints(f, "hearts", c, t, gain=0.6)
    e = eo(prog(lt, 0, 0.25)); f = cv2.GaussianBlur(f, (0, 0), 0.5 + 7 * e); f = f + (NAVY - f) * 0.5 * e
    q = eb(prog(lt, 0.0, 0.3)); blit(f, T["three"], W / 2, 860, op=clamp(q * 1.6), scale=max(q, .01))
    hline(f, 740, 340, 940, prog(lt, 0.35, 0.7))
    blit(f, wipe(T["one"], prog(lt, 0.5, 0.95)), W / 2, 1010)
    cue("impact", t, 0.0, lt); cue("tick", t, 0.5, lt)
    return vignette(f)

def text_block(f, p, lt, d, y=720):
    """number, title, rule, proof line: stacked on the right, bracelet stays clear on the left third"""
    k = min(1.0, d / 2.4)                    # short cuts play the same build faster
    lt = lt / k; d = d / k
    out = 1 - prog(lt, d - 0.25, d - 0.02)
    f = scrim(f, 760, y + 110, 330, 230, eo(prog(lt, 0.0, 0.35)) * out)
    q = prog(lt, 0.1, 0.4); blit(f, p["B"], 0, y, op=clamp(q * 2) * out, scale=max(eb(q), .01), right=930)
    blit(f, wipe(p["T"], prog(lt, 0.45, 0.85)), 0, y + 100, op=out, right=936)
    hline(f, 930, 600, y + 160, prog(lt, 0.7, 1.0), op=out)
    blit(f, wipe(p["S"], prog(lt, 0.95, 1.35)), 0, y + 215, op=out, right=936)
    return f

def sc_product(name, t, lt, d, keys):
    p = PB[name]
    f, c = shot(name, lambda x: path(keys, x - (t - lt), ease=ramp), t)
    glints(f, name, c, t, gain=0.95, burst=0.8 * math.exp(-((lt - d * 0.55) / 0.2) ** 2))
    f = sweep(f, prog(lt, 0.4, 1.4))
    f = text_block(f, p, lt, d)
    cue("tick", t, 0.1, lt); cue("sparkle", t, d * 0.55, lt)
    return vignette(f)

PW, PH_, PY = 300, 900, 840
PX = {"tennis": 880, "hearts": 540, "links": 200}                # 1 on the right: Arabic reading order
PCAM = {"tennis": (1.3, 662, 860), "hearts": (1.3, 560, 790), "links": (1.3, 645, 900)}
PMASK = round_mask(PW, PH_, 30)
PRING = np.clip(round_mask(PW, PH_, 30) - cv2.erode(round_mask(PW, PH_, 30), np.ones((5, 5), np.uint8))[..., None], 0, 1)

def panels(f, t, lt, stagger=0.5, y=PY, badges_at=0.25):
    for j, name in enumerate(("tennis", "hearts", "links")):
        q = eo(prog(lt, stagger * j, stagger * j + 0.45))
        if q <= 0: continue
        cue("whoosh_soft", t, stagger * j, lt)
        s, cx, cy = PCAM[name]
        pv, c = view(name, s + 0.03 * lt, cx, cy)
        glints(pv, name, c, t, gain=0.8)
        pv = sweep(pv, prog(lt, 2.6 + 0.15 * j, 3.4 + 0.15 * j))
        crop = pv[H // 2 - PH_ // 2:H // 2 + PH_ // 2, W // 2 - PW // 2:W // 2 + PW // 2]
        x0 = int(PX[name] - PW / 2); y0 = int(y - PH_ / 2 + 700 * (1 - q))
        ys0, ys1 = max(0, y0), min(H, y0 + PH_)
        if ys1 <= ys0: continue
        m = PMASK[ys0 - y0:ys1 - y0] * clamp(q * 1.4); r = f[ys0:ys1, x0:x0 + PW]
        r += (crop[ys0 - y0:ys1 - y0] - r) * m
        r += (np.array(SILVER, np.float32) - r) * PRING[ys0 - y0:ys1 - y0] * 0.55 * q
        bq = prog(lt, stagger * j + badges_at, stagger * j + badges_at + 0.35)
        if bq > 0:
            blit(f, PB[name]["B"], PX[name], y + PH_ / 2, op=clamp(bq * 2), scale=max(eb(bq), .01))
            cue("tick", t, stagger * j + badges_at, lt)
    return f

def sc_brand(t, lt, d):
    f = BG.copy()
    f = panels(f, t, lt)
    q = eo(prog(lt, 1.5, 1.9)); blit(f, T["silver925"], W / 2, 235 + 25 * (1 - q), op=q)
    hline(f, 700, 380, 300, prog(lt, 1.8, 2.2))
    blit(f, wipe(T["daily"], prog(lt, 3.5, 3.95)), W / 2, 345)
    q = eb(prog(lt, 2.5, 2.85)); blit(f, T["which"], W / 2, 1385, op=clamp(q * 1.6), scale=max(q, .01))
    blit(f, wipe(T["comment"], prog(lt, 3.0, 3.4)), W / 2, 1460)
    cue("impact_soft", t, 1.5, lt); cue("tick", t, 2.5, lt); cue("tick", t, 3.5, lt)
    out = eio(prog(lt, d - 0.35, d)); return f * (1 - out) + BG * out

def sc_cta(t, lt, d, lines=("discover", "url", "tabby")):
    f = BG.copy()
    bgp, c = view("tennis", 1.04 + 0.02 * lt, 600, 900)
    f += (cv2.GaussianBlur(bgp, (0, 0), 22) * 0.55 - f) * 0.22
    glints(f, "tennis", c, t, gain=0.3)
    q = eo(prog(lt, 0.05, 0.7)); blit(f, LOGO, W / 2, 660 + 25 * (1 - q), op=q, scale=0.84 + 0.05 * q)
    ys = {"discover": 1000, "url": 1105, "tabby": 1215, "choose": 1000, "nums": 1100}
    for j, k in enumerate(lines):
        q = eo(prog(lt, 0.5 + 0.35 * j, 0.95 + 0.35 * j)); blit(f, T[k], W / 2, ys[k] + 25 * (1 - q), op=q)
    if "url" in lines: hline(f, 760, 320, 1160, prog(lt, 1.0, 1.5))
    f = sweep(f, prog(lt, 1.6, 2.5), gain=50)
    cue("impact_soft", t, 0.0, lt); cue("sparkle", t, 0.3, lt)
    return vignette(f)

# ------------------------------------------------------------------ edits (scene list: start, duration, fn)
MAIN = [   # 28 s; every cut lands on a beat
    (0.0, 3.0, lambda t, lt, d: sc_hook(t, lt, d)),
    (3.0, 1.0, lambda t, lt, d: sc_macro("hearts", (3.0, 497, 560), (3.0, 505, 625), t, lt, d)),
    (4.0, 1.0, lambda t, lt, d: sc_macro("links", (3.0, 640, 760), (3.0, 636, 690), t, lt, d)),
    (5.0, 0.5, lambda t, lt, d: sc_macro("tennis", (3.3, 655, 840), (3.2, 655, 862), t, lt, d)),
    (5.5, 0.5, lambda t, lt, d: sc_macro("hearts", (3.0, 605, 1040), (3.1, 610, 1065), t, lt, d)),
    (6.0, 0.5, lambda t, lt, d: sc_macro("links", (2.8, 650, 845), (2.9, 652, 870), t, lt, d)),
    (6.5, 1.5, lambda t, lt, d: sc_title(t, lt, d)),
    (8.0, 3.5, lambda t, lt, d: sc_product("tennis", t, lt, d,
        [(0, side("tennis", 2.0, 470)), (1.2, side("tennis", 2.0, 560)), (2.3, side("tennis", 2.0, 960)), (d, side("tennis", 2.1, 1010))])),
    (11.5, 3.5, lambda t, lt, d: sc_product("hearts", t, lt, d,
        [(0, side("hearts", 2.0, 440)), (1.2, side("hearts", 2.0, 520)), (2.3, side("hearts", 2.0, 900)), (d, side("hearts", 2.1, 950))])),
    (15.0, 3.0, lambda t, lt, d: sc_product("links", t, lt, d,
        [(0, side("links", 2.0, 1130)), (1.0, side("links", 2.0, 1070)), (2.0, side("links", 2.0, 700)), (d, side("links", 2.1, 660))])),
    (18.0, 6.0, lambda t, lt, d: sc_brand(t, lt, d)),
    (24.0, 4.0, lambda t, lt, d: sc_cta(t, lt, d)),
]
SHORT = [  # 9 s
    (0.0, 2.5, lambda t, lt, d: sc_hook(t, lt, d, pull_at=1.6)),
    (2.5, 1.0, lambda t, lt, d: sc_product("tennis", t, lt, d, [(0, side("tennis", 2.0, 640)), (d, side("tennis", 2.05, 760))])),
    (3.5, 1.0, lambda t, lt, d: sc_product("hearts", t, lt, d, [(0, side("hearts", 2.0, 600)), (d, side("hearts", 2.05, 720))])),
    (4.5, 1.0, lambda t, lt, d: sc_product("links", t, lt, d, [(0, side("links", 2.0, 900)), (d, side("links", 2.05, 780))])),
    (5.5, 3.5, lambda t, lt, d: sc_cta(t, lt, d, lines=("choose", "nums"))),
]

def render(edit, t):
    st, d, fn = next(s for s in reversed(edit) if s[0] <= t + 1e-9)
    return fn(t, t - st, d)

def total(edit): return edit[-1][0] + edit[-1][1]

# ------------------------------------------------------------------ audio: original 120 BPM score (generated here, no licence needed)
def tone(f, d, r=0.25, amp=0.3, att=0.004, harm=(1.0,)):
    n = int(d * SR); tt = np.arange(n) / SR
    w = sum(h * np.sin(2 * math.pi * f * (k + 1) * tt) / (k + 1) for k, h in enumerate(harm))
    return (amp * np.minimum(tt / att, 1) * np.exp(-tt / r) * w).astype(np.float32)

def noise(d, seed, lp=1):
    x = np.random.default_rng(seed).standard_normal(int(d * SR)).astype(np.float32)
    return np.convolve(x, np.ones(lp) / lp, "same").astype(np.float32) if lp > 1 else x

def build_audio(edit, path):
    TOT = total(edit); n = int((TOT + 0.1) * SR); tt = np.arange(n) / SR
    L, R = np.zeros(n, np.float32), np.zeros(n, np.float32)
    def put(buf, sig, t0, g=1.0):
        st = int(t0 * SR)
        if st >= n or st + len(sig) <= 0: return
        a = max(0, -st); st = max(0, st); m = min(len(sig) - a, n - st); buf[st:st + m] += sig[a:a + m] * g
    def both(sig, t0, g=1.0, pan=0.0): put(L, sig, t0, g * (1 - pan) ** .5); put(R, sig, t0, g * (1 + pan) ** .5)
    is_main = TOT > 20
    drop = 8.0 if is_main else 2.5            # beat comes in fully here
    half = (18.0, 24.0) if is_main else (99, 99)
    end = 24.0 if is_main else 5.5
    chords = [[220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [261.6, 329.6, 392.0], [196.0, 246.9, 293.7]]   # Am F C G
    bar = 4 * BEAT
    for b in range(int(TOT / bar) + 1):
        ch = chords[b % 4]; t0 = b * bar
        sn = int((bar + 0.8) * SR); st = np.arange(sn) / SR
        env = np.minimum(st / 0.3, 1) * np.clip((bar + 0.8 - st) / 0.8, 0, 1)
        pad = sum(np.sin(2 * math.pi * f * st) + 0.25 * np.sin(2 * math.pi * f * 2.004 * st) for f in ch)
        both((0.024 * env * pad).astype(np.float32), t0)
        if t0 >= drop - 1e-6 and t0 < end: both(tone(ch[0] / 2, bar, r=0.8, amp=0.13, att=0.01), t0)
        for k in range(8):                                     # bell-like pluck arpeggio
            if t0 + k * BEAT / 2 >= TOT - 1.5: break
            f = ch[[0, 1, 2, 1, 2, 0, 1, 2][k]] * 2
            both(tone(f, 0.6, r=0.16, amp=0.03, harm=(1, .4, .15)), t0 + k * BEAT / 2, pan=0.3 if k % 2 else -0.3)
    m = int(.3 * SR); ar = np.arange(m) / SR
    kick = (np.sin(2 * math.pi * np.cumsum(55 + 80 * np.exp(-ar / .03)) / SR) * np.exp(-ar / .11) * 0.42).astype(np.float32)
    hat = noise(0.05, 3); hat = (hat - np.convolve(hat, np.ones(6) / 6, "same")) * np.exp(-np.arange(len(hat)) / SR / .01) * 0.05
    snap = (noise(0.18, 4, 2) * np.exp(-np.arange(int(.18 * SR)) / SR / .04) * 0.09).astype(np.float32)
    for k in range(int(TOT / BEAT)):
        tb = k * BEAT
        if tb >= end: break
        pre = tb < drop
        if pre and (k % 2 or tb < 1.0): continue           # intro: sparse pulse only, the hook carries the sound
        if half[0] <= tb < half[1] and k % 2: continue      # half-time under the brand section
        both(kick, tb, g=0.7 if pre else 1.0)
        if not pre: both(hat.astype(np.float32), tb + BEAT / 2, pan=0.3)
        if not pre and k % 2 and not (half[0] <= tb < half[1]): both(snap, tb)
    music = np.stack([L, R], 1)
    music *= (np.minimum(tt / 0.03, 1) * np.clip((TOT + 0.1 - tt) / 1.6, 0, 1))[:, None]
    sfx = np.zeros(n, np.float32)
    def add(sig, t0, g=1.0): put(sfx, sig.astype(np.float32), t0, g)
    rs = int(1.2 * SR)
    riser = noise(1.2, 21, 3) * np.linspace(0, 1, rs) ** 2.5 * 0.06                   # into the drop
    add(riser, drop - 1.2)
    seen = set()
    for kind, t0 in SFX:
        key = (kind, round(t0, 1))
        if key in seen: continue
        seen.add(key)
        if kind in ("impact", "impact_soft"):
            m = int(0.9 * SR); e = np.exp(-np.arange(m) / SR / (0.22 if kind == "impact" else 0.3))
            boom = np.sin(2 * math.pi * np.cumsum(42 + 70 * np.exp(-np.arange(m) / SR / .05)) / SR) * e
            add(boom * (0.42 if kind == "impact" else 0.26) + noise(0.9, 7, 8) * e * 0.03, t0)
        if kind == "sparkle":
            for j, fq in enumerate([2637, 3136, 3951, 4699, 5274]):
                add(tone(fq, 0.8, r=0.22, amp=0.028, harm=(1, .3)), t0 + 0.035 * j)
        if kind == "tick": add(tone(1760, 0.12, r=0.025, amp=0.06), t0)
        if kind in ("whoosh", "whoosh_soft"):
            d = 0.45 if kind == "whoosh" else 0.35; m = int(d * SR)
            w = noise(d, 11 + int(t0 * 10), 24) * np.sin(np.linspace(0, math.pi, m)) ** 2
            add(w * (0.22 if kind == "whoosh" else 0.12), t0 - d * 0.4)
    mix = music + sfx[:, None]
    mix /= max(1.0, np.abs(mix).max() / 0.9)
    raw = path + ".raw.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s16le", raw], input=mix.astype(np.float32).tobytes(), check=True)
    # social loudness: -14 LUFS integrated, -1.5 dBTP
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", str(SR), path], check=True)
    os.remove(raw)

def encode(edit, out):
    TOT = total(edit); tv, ta = out + ".v.mp4", out + ".a.wav"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-level", "4.1",
                          "-pix_fmt", "yuv420p", "-g", "60", tv], stdin=subprocess.PIPE)
    for k in range(int(round(TOT * FPS))):
        p.stdin.write(np.clip(render(edit, k / FPS), 0, 255).astype(np.uint8).tobytes())
    p.stdin.close(); p.wait()
    build_audio(edit, ta)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tv, "-i", ta, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000", "-shortest", "-movflags", "+faststart", out], check=True)
    os.remove(tv); os.remove(ta); print("wrote", out, TOT, "s")

def cover(out):
    f = BG.copy()
    f = panels(f, 0.0, 2.4, y=1010)
    blit(f, LOGO, W / 2, 200, scale=0.42)
    blit(f, T["cover1"], W / 2, 400)
    hline(f, 720, 360, 475, 1.0)
    blit(f, T["cover2"], W / 2, 530)
    blit(f, T["which"], W / 2, 1600)
    cv2.imwrite(out, np.clip(vignette(f), 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 95])
    print("wrote", out)

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode in ("main", "short"): encode(MAIN if mode == "main" else SHORT, sys.argv[2])
    elif mode == "cover": cover(sys.argv[2])
    elif mode == "sheet":
        edit = MAIN if sys.argv[2] == "main" else SHORT; out = sys.argv[3]
        ts = [float(x) for x in sys.argv[4:]] or [s[0] + s[1] * 0.7 for s in edit]
        tiles = [cv2.resize(np.clip(render(edit, t), 0, 255).astype(np.uint8), (270, 480)) for t in ts]
        while len(tiles) % 6: tiles.append(np.zeros((480, 270, 3), np.uint8))
        cv2.imwrite(out, np.vstack([np.hstack(tiles[i:i + 6]) for i in range(0, len(tiles), 6)]))
