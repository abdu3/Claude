"""Silver Haven — "لا تختارين قبل تشوفين الأخيرة" bracelets reel.

usage: python3 render.py <src_dir> <out_dir> [main|short|cover|stills]...

src_dir holds the raw phone clips (VID_20261107_*.mp4, any prefix).
Edit decisions (cuts, zooms, speed, titles) live in the TIMELINES below.
"""
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "fonts")
W, H, FPS = 1080, 1920, 30

NAVY = (11, 26, 51)
SILVER = (205, 211, 220)
WHITE = (255, 255, 255)

AR_XB = os.path.join(FONTS, "Tajawal-Arabic-ExtraBold.woff")
AR_B = os.path.join(FONTS, "Tajawal-Arabic-Bold.ttf")
AR_R = os.path.join(FONTS, "Tajawal-Arabic-Regular.ttf")
LAT = os.path.join(FONTS, "CormorantGaramond-SemiBold.woff")
LAT_SANS = os.path.join(FONTS, "Tajawal-Latin-Bold.ttf")

# clip id -> (file stem, bracelet centre in the 1080x1920 frame)
CLIPS = {
    "A": ("225753", (0.60, 0.41)),  # oval pavé links + yellow-tone links
    "B": ("225802", (0.59, 0.51)),  # rectangle pavé links
    "C": ("304f88f7", (0.50, 0.53)),  # oval coloured stones, two-tone frames
    "E": ("225840", (0.64, 0.49)),  # two-tone hearts
    "F": ("225844", (0.55, 0.48)),  # same hearts, second take
    "G": ("225902", (0.62, 0.45)),  # marquise pavé with yellow X stations
}


# ------------------------------------------------------------------ helpers
def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def prog(t, a, b):
    return min(max((t - a) / (b - a), 0.0), 1.0)


def font(path, size):
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)


def find_clip(src, stem):
    hits = [p for p in glob.glob(os.path.join(src, "*.mp4")) if stem in os.path.basename(p)]
    assert hits, stem
    return hits[0]


def read_frames(path, start, dur):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", path, "-t", f"{dur:.3f}",
           "-an", "-vf", f"fps={FPS},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = len(raw) // (W * H * 3)
    return np.frombuffer(raw[: n * W * H * 3], np.uint8).reshape(n, H, W, 3)


# ------------------------------------------------------------------ grade
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
_r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.47) / (H / 2)) ** 2)
VIG = (1 - 0.42 * np.clip(_r / 1.25, 0, 1) ** 2.4)[..., None]
NAVY_F = np.array(NAVY, np.float32) / 255
SHADOW_TINT = np.array([-0.018, -0.004, 0.034], np.float32)


def grade(img):
    """Silver Haven look: neutral highlights (metal keeps its real colour),
    navy-cooled shadows, gentle contrast, slightly calmer skin, navy vignette."""
    x = img.astype(np.float32) / 255
    lum = (x @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
    x = lum + (x - lum) * 0.88  # calmer saturation (skin/background), hue untouched
    x = x * 0.97 + 0.0  # tiny exposure pull to keep sparkle highlights from clipping
    s = x * x * (3 - 2 * x)
    x = x * 0.62 + s * 0.38  # soft S-curve
    x = x + SHADOW_TINT * (1 - lum) ** 3
    x = x * VIG + NAVY_F * (1 - VIG) * 0.7
    return (np.clip(x, 0, 1) * 255).astype(np.uint8)


def crop_zoom(frame, cx, cy, zoom, bias=0.08):
    """crop a 9:16 window of size W/zoom around the bracelet centre and upscale."""
    cw, ch = W / zoom, H / zoom
    x0 = cx * W - cw / 2
    y0 = cy * H - ch / 2 - bias * ch  # bracelet sits a bit low -> room for titles on top
    x0 = min(max(x0, 0), W - cw)
    y0 = min(max(y0, 0), H - ch)
    im = Image.fromarray(frame).resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))
    if zoom > 1.3:
        im = im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=45 + int(25 * (zoom - 1.3)), threshold=2))
    return np.asarray(im)


# ------------------------------------------------------------------ sprites
def star_sprite(size=220):
    c = size / 2
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) - c
    r = np.sqrt(x * x + y * y) + 1e-3
    a = np.exp(-(y / 3.2) ** 2) * np.exp(-np.abs(x) / (size * 0.18))
    a += np.exp(-(x / 3.2) ** 2) * np.exp(-np.abs(y) / (size * 0.18))
    d1, d2 = (x + y) / 1.414, (x - y) / 1.414
    a += 0.35 * (np.exp(-(d1 / 2.4) ** 2) + np.exp(-(d2 / 2.4) ** 2)) * np.exp(-r / (size * 0.08))
    a += np.exp(-(r / 9) ** 2)
    return np.clip(a, 0, 1)


STAR = star_sprite()


def add_glint(canvas, px, py, amt, scale=1.0, rot=0.0):
    if amt <= 0.01:
        return
    s = int(220 * scale)
    if s < 8:
        return
    st = Image.fromarray((STAR * 255).astype(np.uint8)).rotate(rot, Image.BICUBIC).resize((s, s), Image.BICUBIC)
    a = np.asarray(st, np.float32)[..., None] / 255 * amt
    x0, y0 = int(px - s / 2), int(py - s / 2)
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + s, W), min(y0 + s, H)
    if xa >= xb or ya >= yb:
        return
    reg = canvas[ya:yb, xa:xb].astype(np.float32)
    aa = a[ya - y0:yb - y0, xa - x0:xb - x0]
    col = np.array([235, 242, 255], np.float32)
    canvas[ya:yb, xa:xb] = np.clip(255 - (255 - reg) * (1 - aa) + 0 * col, 0, 255).astype(np.uint8)


def brightest(canvas, box=(260, 520, 900, 1500)):
    x0, y0, x1, y1 = box
    small = canvas[y0:y1:8, x0:x1:8].astype(np.float32).mean(axis=2)
    # prefer neutral (silver) highlights over bokeh: penalise chroma
    sub = canvas[y0:y1:8, x0:x1:8].astype(np.float32)
    chroma = sub.max(axis=2) - sub.min(axis=2)
    score = small - 1.5 * chroma
    iy, ix = np.unravel_index(np.argmax(score), score.shape)
    return x0 + ix * 8, y0 + iy * 8


# ------------------------------------------------------------------ text
_cache = {}


def text_img(txt, fpath, size, fill=WHITE, rtl=True, shadow=True, tracking=0):
    key = (txt, fpath, size, fill, rtl, shadow, tracking)
    if key in _cache:
        return _cache[key]
    f = font(fpath, size)
    pad = 40
    if tracking and not rtl:
        widths = [f.getlength(ch, features=["lnum"]) for ch in txt]
        tw = int(sum(widths) + tracking * (len(txt) - 1))
    else:
        tw = int(f.getlength(txt, direction="rtl" if rtl else None)) if rtl else int(f.getlength(txt))
    asc, desc = f.getmetrics()
    th = asc + desc
    im = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if tracking and not rtl:
        x = pad
        for ch, wch in zip(txt, widths):
            d.text((x, pad), ch, font=f, fill=fill, features=["lnum"])
            x += wch + tracking
    else:
        d.text((pad, pad), txt, font=f, fill=fill, direction="rtl" if rtl else None,
               features=None if rtl else ["lnum"])
    if shadow:
        a = im.split()[3].filter(ImageFilter.GaussianBlur(10))
        sh = Image.new("RGBA", im.size, NAVY + (0,))
        sh.putalpha(a.point(lambda v: int(v * 0.75)))
        im = Image.alpha_composite(sh, im)
    arr = np.asarray(im).astype(np.float32)
    _cache[key] = arr
    return arr


def paste(canvas, arr, cx, cy, op=1.0):
    if op <= 0.005:
        return
    h, w = arr.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if xa >= xb or ya >= yb:
        return
    src = arr[ya - y0:yb - y0, xa - x0:xb - x0]
    a = src[..., 3:4] / 255 * op
    reg = canvas[ya:yb, xa:xb].astype(np.float32)
    canvas[ya:yb, xa:xb] = (reg * (1 - a) + src[..., :3] * a).astype(np.uint8)


def hline(canvas, cx, cy, half, op, thick=3, col=SILVER):
    if op <= 0 or half < 1:
        return
    x0, x1 = int(cx - half), int(cx + half)
    reg = canvas[int(cy):int(cy) + thick, x0:x1].astype(np.float32)
    canvas[int(cy):int(cy) + thick, x0:x1] = (reg * (1 - op) + np.array(col) * op).astype(np.uint8)


TOP_SCRIM = np.clip(1 - np.arange(H) / 700, 0, 1)[:, None, None] ** 1.6


def scrim(canvas, amt):
    if amt <= 0:
        return
    a = (TOP_SCRIM * 0.72 * amt).astype(np.float32)
    canvas[:] = (canvas.astype(np.float32) * (1 - a) + np.array(NAVY, np.float32) * a).astype(np.uint8)


def title_block(canvas, t, t0, t1, lines, y=300):
    """lines: list of (text, fontpath, size, rtl, color). Each line rises + fades in, staggered."""
    if not (t0 - 0.01 <= t <= t1 + 0.3):
        return
    out = prog(t, t1 - 0.18, t1)
    yy_ = y
    for i, (txt, fp, size, rtl, col, gap) in enumerate(lines):
        e = ease_out(prog(t, t0 + i * 0.09, t0 + i * 0.09 + 0.32))
        op = e * (1 - out)
        arr = text_img(txt, fp, size, col, rtl, tracking=(10 if not rtl else 0))
        paste(canvas, arr, W / 2, yy_ + (1 - e) * 36, op)
        yy_ += gap


# ------------------------------------------------------------------ timelines
# shot: (t0, t1, clip, src_start, speed, zoom0, zoom1, flags)
# flags: "flash" white flash at cut, "punch" scale punch-in at cut
MAIN_SHOTS = [
    # HOOK 0-3  — three macro flashes, then a pull-back on the hearts
    (0.0, 0.5, "G", 0.9, 1.0, 1.95, 1.80, "flash"),
    (0.5, 1.0, "B", 1.6, 1.0, 1.90, 1.75, "flash punch"),
    (1.0, 1.5, "C", 2.2, 1.0, 1.90, 1.75, "flash punch"),
    (1.5, 3.0, "E", 0.6, 1.0, 1.70, 1.30, "punch"),
    # 01 — A
    (3.0, 4.5, "A", 0.3, 1.0, 1.25, 1.40, "punch"),
    (4.5, 6.0, "A", 1.8, 1.0, 1.85, 1.95, "punch"),
    # 02 — B
    (6.0, 7.5, "B", 0.2, 1.0, 1.25, 1.42, "punch"),
    (7.5, 9.0, "B", 1.9, 1.0, 1.90, 2.00, "punch"),
    # 03 — C (skip the shaky start)
    (9.0, 10.5, "C", 1.0, 1.0, 1.28, 1.45, "punch"),
    (10.5, 12.0, "C", 3.0, 1.0, 1.85, 1.95, "punch"),
    # 04 — hearts (two takes)
    (12.0, 13.5, "E", 1.2, 1.0, 1.30, 1.45, "punch"),
    (13.5, 15.0, "F", 0.0, 0.85, 1.80, 1.95, "punch"),
    # 05 — the last one: slow-motion reveal
    (15.0, 19.0, "G", 0.0, 0.74, 1.30, 1.75, "flash"),
    # BRAND — recap of macro details on the beat
    (19.0, 19.5, "A", 2.6, 1.0, 1.95, 1.85, "punch"),
    (19.5, 20.0, "B", 2.8, 1.0, 1.95, 1.85, "punch"),
    (20.0, 20.5, "C", 4.0, 1.0, 1.95, 1.85, "punch"),
    (20.5, 21.0, "E", 2.0, 1.0, 1.95, 1.85, "punch"),
]
MAIN_END = (21.0, 24.5, "G", 2.2)  # end card start, end, bg clip, bg src time

L_NUM = 120  # number size


def num_title(n, label):
    return [(n, LAT, L_NUM, False, SILVER, 132), (label, AR_B, 66, True, WHITE, 0)]


MAIN_TITLES = [
    (0.12, 2.9, [("لا تختارين", AR_XB, 100, True, WHITE, 116),
                 ("قبل تشوفين الأخيرة", AR_XB, 100, True, WHITE, 0)]),
    (3.05, 5.9, num_title("01", "حلقات مرصّعة بلونين")),
    (6.05, 8.9, num_title("02", "مستطيلات تلمع مع كل حركة")),
    (9.05, 11.9, num_title("03", "أحجار بيضاوية بلون ناعم")),
    (12.05, 14.9, num_title("04", "قلوب صغيرة بلونين")),
    (15.15, 18.9, [("05", LAT, L_NUM, False, SILVER, 140), ("والأخيرة", AR_XB, 92, True, WHITE, 0)]),
    (19.02, 20.95, [("فضة ٩٢٥", AR_XB, 112, True, WHITE, 112),
                    ("تنلبس كل يوم وتكمّل إطلالة المناسبات", AR_B, 52, True, SILVER, 0)]),
]
MAIN_GLINTS = [(1.7, 0.55), (4.7, 0.5), (7.7, 0.5), (10.7, 0.5), (13.7, 0.5), (16.0, 0.8), (17.6, 0.7)]

SHORT_SHOTS = [
    (0.0, 0.75, "G", 0.9, 1.0, 1.95, 1.80, "flash"),
    (0.75, 1.5, "B", 1.6, 1.0, 1.90, 1.75, "flash punch"),
    (1.5, 2.5, "A", 0.6, 1.0, 1.45, 1.65, "punch"),
    (2.5, 3.5, "B", 0.6, 1.0, 1.45, 1.65, "punch"),
    (3.5, 4.5, "C", 1.4, 1.0, 1.45, 1.65, "punch"),
    (4.5, 5.5, "E", 0.8, 1.0, 1.45, 1.65, "punch"),
    (5.5, 6.5, "G", 0.6, 0.8, 1.45, 1.75, "flash"),
]
SHORT_END = (6.5, 8.5, "G", 2.2)
SHORT_TITLES = [
    (0.08, 1.45, [("أي وحدة لك؟", AR_XB, 112, True, WHITE, 118),
                  ("٥ تصاميم فضة ٩٢٥", AR_B, 62, True, SILVER, 0)]),
    (1.55, 2.45, [("01", LAT, L_NUM, False, SILVER, 0)]),
    (2.55, 3.45, [("02", LAT, L_NUM, False, SILVER, 0)]),
    (3.55, 4.45, [("03", LAT, L_NUM, False, SILVER, 0)]),
    (4.55, 5.45, [("04", LAT, L_NUM, False, SILVER, 0)]),
    (5.55, 6.45, [("05", LAT, L_NUM, False, SILVER, 0)]),
]
SHORT_GLINTS = [(0.15, 0.5), (5.8, 0.6)]


# ------------------------------------------------------------------ end card
_blur_bg = {}


def end_card(canvas, t, t0, t1, src, bgclip, bgt, short=False):
    key = (bgclip, bgt)
    if key not in _blur_bg:
        fr = read_frames(find_clip(src, CLIPS[bgclip][0]), bgt, 0.1)[0]
        cx, cy = CLIPS[bgclip][1]
        im = Image.fromarray(grade(crop_zoom(fr, cx, cy, 1.5)))
        _blur_bg[key] = np.asarray(im.filter(ImageFilter.GaussianBlur(26)), np.float32)
    lt = t - t0
    e = ease_io(prog(lt, 0, 0.45))
    bg = _blur_bg[key]
    # slow push on the blurred bg
    z = 1 + 0.04 * lt
    bgi = Image.fromarray(bg.astype(np.uint8)).resize((int(W * z), int(H * z)), Image.BILINEAR)
    bx, by = (bgi.width - W) // 2, (bgi.height - H) // 2
    bg = np.asarray(bgi, np.float32)[by:by + H, bx:bx + W]
    bg = bg * 0.38 + np.array(NAVY, np.float32) * 0.62
    canvas[:] = (canvas.astype(np.float32) * (1 - e) + bg * e).astype(np.uint8)

    cy = 760
    a1 = ease_out(prog(lt, 0.25, 0.85))
    paste(canvas, text_img("SILVER HAVEN", LAT, 112, WHITE, False, tracking=14), W / 2, cy + (1 - a1) * 30, a1)
    a2 = ease_out(prog(lt, 0.45, 1.0))
    hline(canvas, W / 2, cy + 82, 200 * a2, a2 * 0.9, 2)
    paste(canvas, text_img("سيلفر هافن", AR_R, 54, SILVER, True), W / 2, cy + 140, a2)
    a3 = ease_out(prog(lt, 0.75, 1.25))
    if short:
        lines = [("اكتبي رقمك بالتعليقات", AR_XB, 76, WHITE)]
    else:
        lines = [("أي رقم عجبك؟", AR_XB, 84, WHITE), ("اكتبيه بالتعليقات", AR_B, 62, WHITE)]
    yy_ = cy + 330
    for txt, fp, sz, col in lines:
        paste(canvas, text_img(txt, fp, sz, col, True), W / 2, yy_ + (1 - a3) * 30, a3)
        yy_ += sz + 26
    a4 = ease_out(prog(lt, 1.05, 1.5))
    yy_ += 40
    if not short:
        paste(canvas, text_img("والتشكيلة كاملة في متجرنا", AR_R, 46, SILVER, True), W / 2, yy_, a4)
        yy_ += 86
    url = text_img("silverhaven-sa.com", LAT_SANS, 44, WHITE, False, shadow=False)
    # pill outline
    pw, ph = url.shape[1] - 80 + 70, 84
    if a4 > 0:
        pill = Image.new("RGBA", (pw + 8, ph + 8), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle((4, 4, pw + 4, ph + 4), radius=ph // 2,
                                               outline=SILVER + (230,), width=3)
        paste(canvas, np.asarray(pill, np.float32), W / 2, yy_ + 4, a4)
        paste(canvas, url, W / 2, yy_ + 2, a4)
    # closing glint on the logotype
    gl = prog(lt, 0.9, 1.6)
    if 0 < gl < 1:
        add_glint(canvas, W / 2 + 300, cy - 40, np.sin(np.pi * gl) * 0.9, 0.55 + 0.25 * gl, 45 * gl)
    out = prog(t, t1 - 0.35, t1)
    if out > 0:
        canvas[:] = (canvas.astype(np.float32) * (1 - out * 0.35)).astype(np.uint8)


# ------------------------------------------------------------------ render
def shot_frames(src, shot):
    t0, t1, clip, s, v, *_ = shot
    dur_src = (t1 - t0) * v + 0.2
    return read_frames(find_clip(src, CLIPS[clip][0]), s, dur_src)


def render(src, shots, titles, glints, endspec, total, out_path, audio, cover_at=None, stills=None):
    enc = None
    if out_path:
        enc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
             "-r", str(FPS), "-i", "-", "-i", audio,
             "-filter_complex", "[1:a]loudnorm=I=-14:TP=-1.5:LRA=9,afade=t=out:st=%.2f:d=0.6[a]" % (total - 0.6),
             "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
             "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}", out_path],
            stdin=subprocess.PIPE)
    n_total = int(round(total * FPS))
    cur, frames = None, None
    glint_pos = {}
    for fi in range(n_total):
        t = fi / FPS
        if stills is not None and fi not in stills:
            continue
        shot = next((s for s in shots if s[0] <= t < s[1]), None)
        e0 = endspec[0]
        if shot is None:
            shot = shots[-1]
        if shot is not cur:
            cur, frames = shot, shot_frames(src, shot)
        t0, t1, clip, s, v, z0, z1, flags = shot
        lt = t - t0
        fpos = min(lt * v * FPS, len(frames) - 1.001)
        i0 = int(fpos)
        fr = frames[i0]
        if v < 0.99:  # frame blend for smooth slow motion
            a = fpos - i0
            fr = (frames[i0].astype(np.float32) * (1 - a) + frames[i0 + 1].astype(np.float32) * a).astype(np.uint8)
        z = z0 + (z1 - z0) * ease_io(lt / (t1 - t0))
        if "punch" in flags:
            z *= 1 + 0.07 * (1 - ease_out(lt / 0.28))
        cx, cy = CLIPS[clip][1]
        canvas = grade(crop_zoom(fr, cx, cy, z)).copy()

        # glints (position picked once per glint from the brightest silver highlight)
        for g0, gd in glints:
            if g0 <= t < g0 + gd:
                if g0 not in glint_pos:
                    glint_pos[g0] = brightest(canvas)
                p = (t - g0) / gd
                px, py = glint_pos[g0]
                add_glint(canvas, px, py, np.sin(np.pi * p) ** 1.5 * 0.85, 0.35 + 0.35 * p, 60 * p)

        # titles + scrim
        active = [tt for tt in titles if tt[0] - 0.05 <= t <= tt[1] + 0.05]
        if active:
            tt = active[0]
            scrim(canvas, ease_out(prog(t, tt[0] - 0.1, tt[0] + 0.2)) * (1 - prog(t, tt[1] - 0.1, tt[1] + 0.1)))
        for tt in titles:
            title_block(canvas, t, tt[0], tt[1], tt[2], y=245)
        # silver rule under numbers
        for tt in titles:
            if tt[2][0][1] == LAT and tt[0] <= t <= tt[1]:
                e = ease_out(prog(t, tt[0] + 0.1, tt[0] + 0.45)) * (1 - prog(t, tt[1] - 0.18, tt[1]))
                hline(canvas, W / 2, 312, 60 * e, e * 0.85, 2)

        if t >= e0:
            end_card(canvas, t, e0, endspec[1], src, endspec[2], endspec[3], short=(total < 12))

        # white flash on hook cuts
        if "flash" in flags and lt < 0.12:
            f = (1 - lt / 0.12) ** 2 * 0.55
            canvas = (canvas.astype(np.float32) * (1 - f) + 255 * f).astype(np.uint8)
        if fi == 0:
            pass
        if stills is not None:
            stills[fi] = canvas.copy()
            continue
        if cover_at is not None and abs(t - cover_at) < 1e-6:
            return canvas
        enc.stdin.write(canvas.tobytes())
    if enc:
        enc.stdin.close()
        enc.wait()
        print("wrote", out_path)


def cover(src, out_dir):
    shot = (0, 1, "G", 1.4, 1.0, 1.75, 1.75, "")
    fr = shot_frames(src, shot)[0]
    cx, cy = CLIPS["G"][1]
    canvas = grade(crop_zoom(fr, cx, cy, 1.75, bias=0.02)).copy()
    scrim(canvas, 1.0)
    paste(canvas, text_img("لا تختارين", AR_XB, 118, WHITE, True), W / 2, 270)
    paste(canvas, text_img("قبل تشوفين الأخيرة", AR_XB, 108, WHITE, True), W / 2, 395)
    hline(canvas, W / 2, 495, 90, 0.9, 3)
    paste(canvas, text_img("٥ أساور فضة ٩٢٥", AR_B, 60, SILVER, True), W / 2, 560)
    px, py = brightest(canvas)
    add_glint(canvas, px, py, 0.85, 0.5, 20)
    # bottom brand strip
    bot = np.clip((np.arange(H) - 1480) / 440, 0, 1)[:, None, None] ** 1.4 * 0.7
    canvas[:] = (canvas * (1 - bot) + np.array(NAVY) * bot).astype(np.uint8)
    paste(canvas, text_img("SILVER HAVEN", LAT, 70, WHITE, False, tracking=10), W / 2, 1640)
    p = os.path.join(out_dir, "silverhaven-bracelets-cover.jpg")
    Image.fromarray(canvas).save(p, quality=93)
    print("wrote", p)


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    work = os.environ.get("WORK", "/tmp")
    jobs = sys.argv[3:] or ["main", "short", "cover"]
    os.makedirs(out, exist_ok=True)
    if "main" in jobs:
        render(src, MAIN_SHOTS, MAIN_TITLES, MAIN_GLINTS, MAIN_END, 24.5,
               os.path.join(out, "silverhaven-bracelets-main-24s.mp4"), os.path.join(work, "music_main.wav"))
    if "short" in jobs:
        render(src, SHORT_SHOTS, SHORT_TITLES, SHORT_GLINTS, SHORT_END, 8.5,
               os.path.join(out, "silverhaven-bracelets-short-8s.mp4"), os.path.join(work, "music_short.wav"))
    if "cover" in jobs:
        cover(src, out)
    if "stills" in jobs:
        times = [0.3, 0.8, 1.2, 2.2, 3.6, 5.0, 6.6, 8.0, 9.6, 11.0, 12.6, 14.2, 15.6, 17.5, 19.3, 20.2, 21.5, 23.5]
        st = {int(round(x * FPS)): None for x in times}
        render(src, MAIN_SHOTS, MAIN_TITLES, MAIN_GLINTS, MAIN_END, 24.5, None, None, stills=st)
        ims = [Image.fromarray(st[k]).resize((270, 480)) for k in sorted(st)]
        sheet = Image.new("RGB", (270 * 6, 480 * 3))
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % 6) * 270, (i // 6) * 480))
        sheet.save(os.path.join(work, "stills.jpg"), quality=88)
        print("stills")
