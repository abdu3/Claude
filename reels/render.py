"""Render Silver Haven 925 reels (1080x1920, 30fps) from the layered design.

usage: python3 render.py <layers_dir> <out_dir> [reel ...]
  reels: reveal | tour | hook   (default: all)
"""
import os, sys, math, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
HERE = os.path.dirname(os.path.abspath(__file__))
LAY = sys.argv[1]
OUT = sys.argv[2]

# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, t0, t1): return clamp((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t0)
def ease_out(x): return 1 - (1 - x) ** 3
def ease_io(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def ease_back(x, s=1.6): x -= 1; return x * x * ((s + 1) * x + s) + 1
def smooth(e0, e1, x): x = np.clip((x - e0) / (e1 - e0 + 1e-6), 0, 1); return x * x * (3 - 2 * x)

# ---------------------------------------------------------------- layers
def load_rgba(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED).astype(np.float32)
    return im[..., :3], im[..., 3] / 255.0

class Layer:
    def __init__(self, color, alpha, pad=24):
        ys, xs = np.where(alpha > 0.01)
        y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, alpha.shape[0])
        x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, alpha.shape[1])
        self.x0, self.y0 = x0, y0
        self.c = np.ascontiguousarray(color[y0:y1, x0:x1])
        self.a = np.ascontiguousarray(alpha[y0:y1, x0:x1])
        self.h, self.w = self.a.shape
        self.cx, self.cy = x0 + self.w / 2, y0 + self.h / 2

def L(name):
    c, a = load_rgba(f"{LAY}/{name}.png"); return Layer(c, a)

PLATE = cv2.imread(f"{LAY}/plate.png").astype(np.float32)
ORIG = cv2.imread(os.path.join(HERE, "src", "design-925.jpg")).astype(np.float32)
NAMES = ["logo", "ring", "n9", "n2", "n5", "yaani", "arrow_l", "txt_l", "arrow_r", "txt_r", "arrow_up", "oval", "caption"]
LY = {n: L(n) for n in NAMES}
_, RING_A = load_rgba(f"{LAY}/ring.png")

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)

def draw(canvas, ly, op=1.0, scale=1.0, dx=0.0, dy=0.0, anchor=None, wipe=None, shine=None, blur=0):
    """Composite a layer. wipe(xs, ys) -> mask in canvas coords; shine = band position (px)."""
    if op <= 0.003: return
    ax, ay = anchor if anchor else (ly.cx, ly.cy)
    # crop -> canvas: p = (q + origin - anchor) * s + anchor + d
    M = np.array([[scale, 0, (ly.x0 - ax) * scale + ax + dx],
                  [0, scale, (ly.y0 - ay) * scale + ay + dy]], np.float32)
    cs = np.array([[0, 0, 1], [ly.w, 0, 1], [0, ly.h, 1], [ly.w, ly.h, 1]], np.float32) @ M.T
    X0, Y0 = int(max(math.floor(cs[:, 0].min()), 0)), int(max(math.floor(cs[:, 1].min()), 0))
    X1, Y1 = int(min(math.ceil(cs[:, 0].max()), W)), int(min(math.ceil(cs[:, 1].max()), H))
    if X1 <= X0 or Y1 <= Y0: return
    M2 = M.copy(); M2[0, 2] -= X0; M2[1, 2] -= Y0
    size = (X1 - X0, Y1 - Y0)
    if abs(scale - 1) < 1e-4 and float(M2[0, 2]).is_integer() and float(M2[1, 2]).is_integer():
        ox, oy = int(M2[0, 2]), int(M2[1, 2])
        c = np.zeros((size[1], size[0], 3), np.float32); a = np.zeros((size[1], size[0]), np.float32)
        sx0, sy0 = max(-ox, 0), max(-oy, 0)
        sx1, sy1 = min(ly.w, size[0] - ox), min(ly.h, size[1] - oy)
        c[sy0 + oy:sy1 + oy, sx0 + ox:sx1 + ox] = ly.c[sy0:sy1, sx0:sx1]
        a[sy0 + oy:sy1 + oy, sx0 + ox:sx1 + ox] = ly.a[sy0:sy1, sx0:sx1]
    else:
        c = cv2.warpAffine(ly.c, M2, size, flags=cv2.INTER_LINEAR)
        a = cv2.warpAffine(ly.a, M2, size, flags=cv2.INTER_LINEAR)
    if blur > 0.3:
        k = int(blur * 3) | 1
        c = cv2.GaussianBlur(c, (k, k), blur); a = cv2.GaussianBlur(a, (k, k), blur)
    a = a * op
    xs, ys = XX[Y0:Y1, X0:X1], YY[Y0:Y1, X0:X1]
    if wipe is not None: a = a * wipe(xs, ys)
    if shine is not None:
        band = np.exp(-(((xs + ys * 0.55) - shine) / 38.0) ** 2)
        c = c + (band * 120.0)[..., None]
    region = canvas[Y0:Y1, X0:X1]
    region += (np.minimum(c, 255) - region) * a[..., None]

# wipe helpers -------------------------------------------------------------
def wipe_dir(ly, p, ux, uy, soft=0.12):
    """reveal along direction (ux,uy) across the layer's box; p in 0..1"""
    n = math.hypot(ux, uy); ux, uy = ux / n, uy / n
    corners = [(ly.x0, ly.y0), (ly.x0 + ly.w, ly.y0), (ly.x0, ly.y0 + ly.h), (ly.x0 + ly.w, ly.y0 + ly.h)]
    pr = [x * ux + y * uy for x, y in corners]; lo, hi = min(pr), max(pr)
    edge = lo + (hi - lo) * (p * (1 + soft))
    return lambda xs, ys: 1 - smooth(edge - (hi - lo) * soft, edge, xs * ux + ys * uy)

def wipe_angle(cx, cy, p, start=math.pi / 2, sx=1.0, sy=1.0, soft=0.25):
    """clockwise angular reveal around (cx,cy), starting at angle `start` (radians, screen coords)"""
    span = 2 * math.pi
    def f(xs, ys):
        ang = (np.arctan2((ys - cy) / sy, (xs - cx) / sx) - start) % span
        edge = p * (span + soft)
        return 1 - smooth(edge - soft, edge, ang)
    return f

# ---------------------------------------------------------------- lighting
def light_map(t, cx, cy, r=900, k=0.55):
    small = np.mgrid[0:H // 8, 0:W // 8].astype(np.float32) * 8
    d = np.hypot(small[1] - cx, small[0] - cy) / r
    m = 1 - k + k * np.exp(-d * d)
    return cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]

VIG = (1 - 0.35 * smooth(0.55, 1.25, np.hypot((XX - W / 2) / (W / 2), (YY - H / 2) / (H / 2) * 0.9)))[..., None]

def camera(frame, s, cx, cy, shake=(0, 0)):
    hw, hh = W / (2 * s), H / (2 * s)
    cx = clamp(cx, hw, W - hw); cy = clamp(cy, hh, H - hh)
    M = np.array([[s, 0, W / 2 - cx * s + shake[0]], [0, s, H / 2 - cy * s + shake[1]]], np.float32)
    if abs(s - 1) < 1e-4 and shake == (0, 0): return frame
    return cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def keyframes(t, keys):
    """keys: list of (time, value-tuple); eased interpolation between consecutive keys"""
    if t <= keys[0][0]: return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            e = ease_io(prog(t, t0, t1))
            return tuple(a + (b - a) * e for a, b in zip(v0, v1))
    return keys[-1][1]

# ---------------------------------------------------------------- end card
def text_img(txt, font, size, fill=(236, 236, 240), tracking=0):
    f = ImageFont.truetype(os.path.join(HERE, "fonts", font), size,
                           layout_engine=ImageFont.Layout.RAQM)
    kw = dict(direction="rtl", language="ar") if any("؀" <= ch <= "ۿ" for ch in txt) else {}
    if tracking: kw["features"] = ["-kern"]
    box = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), txt, font=f, **kw)
    im = Image.new("RGBA", (box[2] - box[0] + 40, box[3] - box[1] + 40), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((20 - box[0], 20 - box[1]), txt, font=f, fill=fill + (255,), **kw)
    arr = np.array(im).astype(np.float32)
    return arr[..., [2, 1, 0]], arr[..., 3] / 255.0

def rtl_join(parts, gap=18):
    """compose [(text, font, size), ...] given in reading order, laid out right-to-left"""
    imgs = [text_img(t, f, z) for t, f, z in parts]
    h = max(a.shape[0] for _, a in imgs); w = sum(a.shape[1] for _, a in imgs) - gap * (len(imgs) - 1)
    C = np.zeros((h, w, 3), np.float32); A = np.zeros((h, w), np.float32)
    x = w
    for c, a in imgs:
        ih, iw = a.shape; x -= iw; y = (h - ih) // 2
        C[y:y + ih, x:x + iw] = np.where(a[..., None] > 0, c, C[y:y + ih, x:x + iw])
        A[y:y + ih, x:x + iw] = np.maximum(A[y:y + ih, x:x + iw], a); x += gap
    return C, A

def placed(color, alpha, cx, cy):
    full_c = np.zeros((H, W, 3), np.float32); full_a = np.zeros((H, W), np.float32)
    h, w = alpha.shape; x0, y0 = int(cx - w / 2), int(cy - h / 2)
    full_c[y0:y0 + h, x0:x0 + w] = color; full_a[y0:y0 + h, x0:x0 + w] = alpha
    return Layer(full_c, full_a, pad=4)

END = {
    "tag": placed(*rtl_join([("فضة عيار", "Tajawal-Arabic-Bold.ttf", 76), ("925", "PlayfairDisplay-Regular.ttf", 84),
                             ("أصلية", "Tajawal-Arabic-Bold.ttf", 76)]), W / 2, 1150),
    "sub": placed(*text_img("تسوّق الآن من سيلفر هافن", "Tajawal-Arabic-Regular.ttf", 46, (190, 196, 210)), W / 2, 1250),
    "url": placed(*text_img("silverhaven-sa.com", "PlayfairDisplay-Regular.ttf", 50, (215, 220, 230)), W / 2, 1400),
}
_lc, _la = load_rgba(f"{LAY}/logo.png")
END["line"] = placed(np.full((3, 360, 3), 200, np.float32), np.ones((3, 360), np.float32) * 0.6, W / 2, 1325)

def end_card(canvas, t, t0, logo_from=None):
    """darken + big logo + tagline, starting at t0"""
    p = ease_io(prog(t, t0, t0 + 0.9))
    if p > 0:
        bl = cv2.GaussianBlur(canvas, (0, 0), 1 + 14 * p)
        canvas[:] = bl * (1 - 0.82 * p)
    lg = LY["logo"]
    # logo travels from its corner spot to the centre while growing
    sx, sy = logo_from if logo_from else (lg.cx, lg.cy)
    e = ease_io(prog(t, t0 + 0.1, t0 + 1.2))
    draw(canvas, lg, op=1.0 if logo_from else e, scale=1 + 3.2 * e,
         dx=(W / 2 - sx) * e, dy=(830 - sy) * e, anchor=(lg.cx, lg.cy),
         shine=-400 + 3600 * prog(t, t0 + 1.4, t0 + 2.6))
    for i, k in enumerate(["tag", "sub", "line", "url"]):
        q = ease_out(prog(t, t0 + 0.9 + 0.18 * i, t0 + 1.6 + 0.18 * i))
        draw(canvas, END[k], op=q, dy=30 * (1 - q))

# ---------------------------------------------------------------- reel 1: layered reveal (15s)
def reel_reveal(t):
    D = 15.0
    lx, ly_ = keyframes(t, [(0, (300, 700)), (6, (760, 1000)), (12, (520, 900))])
    c = PLATE * light_map(t, lx, ly_) * VIG
    c = c * ease_out(prog(t, 0, 1.2))
    shake = (0, 0)
    # logo
    draw(c, LY["logo"], op=ease_out(prog(t, 0.6, 1.4)) * (1 - prog(t, 12.9, 13.0)))
    # ring lands
    pr = prog(t, 1.0, 2.0)
    if pr > 0:
        draw(c, LY["ring"], op=ease_out(min(pr * 1.6, 1)), scale=1 + 0.6 * (1 - ease_out(pr)),
             dy=-140 * (1 - ease_out(pr)), blur=6 * (1 - pr),
             shine=(-300 + 2600 * prog(t, 3.6, 4.6)) if t > 3.6 else None)
        if 2.0 <= t < 2.3:
            k = (2.3 - t) / 0.3; shake = (6 * k * math.sin(t * 90), 6 * k * math.cos(t * 77))
    # digits rise (their alpha has a hole where the ring sits, so the ring stays on top)
    for i, n in enumerate(["n9", "n2", "n5"]):
        q = prog(t, 2.1 + 0.22 * i, 2.9 + 0.22 * i)
        if q > 0:
            draw(c, LY[n], op=ease_out(min(q * 2, 1)), dy=90 * (1 - ease_back(q)),
                 shine=(-300 + 2600 * prog(t, 3.6, 4.6)) if t > 3.6 else None)
    # يعني
    q = prog(t, 4.3, 5.1)
    if q > 0: draw(c, LY["yaani"], wipe=wipe_dir(LY["yaani"], ease_io(q), -1, 0))
    # left: arrow then label
    q = prog(t, 5.3, 6.1)
    if q > 0: draw(c, LY["arrow_l"], wipe=wipe_dir(LY["arrow_l"], ease_io(q), -0.4, 1))
    q = prog(t, 5.9, 6.8)
    if q > 0: draw(c, LY["txt_l"], op=ease_out(q), dx=-30 * (1 - ease_out(q)), wipe=wipe_dir(LY["txt_l"], ease_io(q), -1, 0))
    # right: arrow then label
    q = prog(t, 6.8, 7.5)
    if q > 0: draw(c, LY["arrow_r"], wipe=wipe_dir(LY["arrow_r"], ease_io(q), 0.6, 1))
    q = prog(t, 7.3, 8.2)
    if q > 0: draw(c, LY["txt_r"], op=ease_out(q), dx=30 * (1 - ease_out(q)), wipe=wipe_dir(LY["txt_r"], ease_io(q), -1, 0))
    # up arrow, oval, caption
    q = prog(t, 8.5, 9.2)
    if q > 0: draw(c, LY["arrow_up"], wipe=wipe_dir(LY["arrow_up"], ease_io(q), 0.2, -1))
    q = prog(t, 9.1, 10.4)
    if q > 0: draw(c, LY["oval"], wipe=wipe_angle(705, 622, ease_io(q), start=math.radians(80), sx=3.2, sy=1))
    q = prog(t, 9.9, 10.9)
    if q > 0: draw(c, LY["caption"], op=ease_out(q), wipe=wipe_dir(LY["caption"], ease_io(q), -1, 0))
    # shine sweep across everything at the reveal
    if 11.4 < t < 12.8:
        sp = -400 + 3400 * prog(t, 11.4, 12.8)
        band = np.exp(-(((XX + YY * 0.55) - sp) / 60.0) ** 2)[..., None]
        bright = np.clip((ORIG.mean(2, keepdims=True) - 120) / 80, 0, 1)
        c += band * bright * 90
    if t >= 13.0:
        end_card(c, t, 13.0)
    # camera
    s, cx, cy = keyframes(t, [(0, (1.45, 640, 1040)), (3.4, (1.32, 600, 1030)), (5.2, (1.1, 540, 1080)),
                              (8.2, (1.1, 540, 1080)), (9.4, (1.3, 680, 820)), (10.8, (1.25, 690, 800)),
                              (12.0, (1.0, 540, 960)), (13.0, (1.0, 540, 960)), (15, (1.04, 540, 960))])
    if t >= 13.0: s, cx, cy = 1.0, 540, 960
    return camera(c, s, cx, cy, shake), D

# ---------------------------------------------------------------- reel 2: macro camera tour (12s)
def reel_tour(t):
    D = 12.0
    c = ORIG.copy()
    # gentle travelling light over the stone
    lx, ly_ = keyframes(t, [(0, (200, 800)), (12, (900, 1100))])
    c *= light_map(t, lx, ly_, r=1100, k=0.22)
    # ring sparkle sweeps
    for t0 in (0.4, 3.6, 10.2):
        if t0 < t < t0 + 1.2:
            draw(c, LY["ring"], shine=500 + 1200 * prog(t, t0, t0 + 1.2))
    if 5.2 < t < 6.6:
        sp = 600 + 900 * prog(t, 5.2, 6.6)
        band = np.exp(-(((XX + YY * 0.55) - sp) / 50.0) ** 2)[..., None]
        bright = np.clip((ORIG.mean(2, keepdims=True) - 120) / 80, 0, 1)
        c += band * bright * 80
    if t >= 10.0:
        end_card(c, t, 10.0)
        s, cx, cy = 1.0, 540, 960
    else:
        s, cx, cy = keyframes(t, [(0, (3.0, 700, 1050)), (1.6, (2.6, 690, 1045)), (3.2, (1.55, 540, 975)),
                                  (4.2, (1.55, 540, 975)), (5.4, (2.1, 705, 625)), (6.6, (2.1, 705, 625)),
                                  (7.6, (2.4, 230, 1230)), (8.4, (2.4, 230, 1230)), (9.0, (2.4, 860, 1230)),
                                  (9.5, (2.4, 860, 1230)), (10.0, (1.0, 540, 960))])
    return camera(c, s, cx, cy), D

# ---------------------------------------------------------------- reel 3: fast hook (8s, loop-friendly)
def reel_hook(t):
    D = 8.0
    c = PLATE * light_map(t, 600, 950, k=0.5) * VIG
    flash = 0.0
    # 925 + ring slam in together (the 5 has a hole where the ring sits)
    q = prog(t, 0.15, 0.6)
    if q > 0:
        sh = (-300 + 2600 * prog(t, 1.1, 1.9)) if t > 1.1 else None
        for n in ["n9", "n2", "n5", "ring"]:
            draw(c, LY[n], op=min(q * 3, 1), scale=1 + 0.9 * (1 - ease_out(q)), anchor=(540, 965),
                 blur=4 * (1 - q), shine=sh)
        flash = max(flash, 1 - prog(t, 0.6, 0.85)) if t >= 0.6 else 0
    q = prog(t, 1.4, 1.9)
    if q > 0: draw(c, LY["yaani"], op=ease_out(q), scale=1 + 0.3 * (1 - ease_back(q)))
    for n, nt, d in [("arrow_l", "txt_l", (-0.4, 1)), ("arrow_r", "txt_r", (0.6, 1))]:
        q = prog(t, 2.0, 2.45)
        if q > 0: draw(c, LY[n], wipe=wipe_dir(LY[n], ease_io(q), *d))
        q = prog(t, 2.3, 2.8)
        if q > 0: draw(c, LY[nt], op=ease_out(q), scale=1 + 0.25 * (1 - ease_back(q)))
    q = prog(t, 2.9, 3.25)
    if q > 0: draw(c, LY["arrow_up"], wipe=wipe_dir(LY["arrow_up"], ease_io(q), 0.2, -1))
    q = prog(t, 3.15, 3.9)
    if q > 0: draw(c, LY["oval"], wipe=wipe_angle(705, 622, ease_io(q), start=math.radians(80), sx=3.2, sy=1))
    q = prog(t, 3.5, 4.1)
    if q > 0: draw(c, LY["caption"], op=ease_out(q), scale=1 + 0.2 * (1 - ease_back(q)))
    draw(c, LY["logo"], op=ease_out(prog(t, 3.8, 4.4)))
    if flash > 0: c += flash * 140
    if t >= 6.2:
        end_card(c, t, 6.2, logo_from=(LY["logo"].cx, LY["logo"].cy))
    s, cx, cy = keyframes(t, [(0, (1.25, 540, 1000)), (1.9, (1.18, 540, 1050)), (2.9, (1.1, 540, 1000)),
                              (4.2, (1.0, 540, 960)), (6.2, (1.06, 540, 960))])
    if t >= 6.2: s, cx, cy = 1.0, 540, 960
    return camera(c, s, cx, cy), D

REELS = {"reveal": reel_reveal, "tour": reel_tour, "hook": reel_hook}

def render(name, fn):
    _, D = fn(0)
    path = os.path.join(OUT, f"silverhaven-925-{name}.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-shortest", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(D * FPS))
    for i in range(n):
        f, _ = fn(i / FPS)
        p.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
    p.stdin.close(); p.wait()
    print("wrote", path)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if len(sys.argv) > 3 and sys.argv[3] == "--stills":
        for name in sys.argv[4:]:
            fn = REELS[name]; _, D = fn(0)
            ts = np.linspace(0, D - 0.05, 10)
            tiles = [cv2.resize(np.clip(fn(t)[0], 0, 255).astype(np.uint8), (270, 480)) for t in ts]
            cv2.imwrite(os.path.join(OUT, f"strip-{name}.jpg"), np.vstack([np.hstack(tiles[:5]), np.hstack(tiles[5:])]))
        sys.exit()
    for name in (sys.argv[3:] or REELS):
        render(name, REELS[name])
