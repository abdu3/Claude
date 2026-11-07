"""Merged reviews reel: the store's own video (hook + ending + voiceover) with Claude's cinematic
card-spotlight middle built on the reviews design.

usage: python3 render_merge.py <store_fixed.mp4> <out.mp4> [--stills strip.jpg]

Timeline (seconds, synced to card pop-ins detected in the store video, so it follows the voiceover):
  0.00 – 2.90   store video (hook: bubble, question, Batool's card, phone enters)
  2.90 – 3.20   crossfade
  3.20 – 10.95  reviews design: Batool -> Yousef (5.10) -> Osamah (8.10) -> all cards light (10.10)
  10.95 – 11.25 crossfade
  11.25 – end   store video (ending with CTA, already lifted out of the overlay zone)
Audio: the store video's own track, plus very soft sparkle ticks on each card.
"""
import os, sys, math, subprocess
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
TRUST = os.path.join(HERE, "..", "trust", "render_trust.py")
SRC, OUT = sys.argv[1], sys.argv[2]
STILLS = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--stills" else None

# reuse the card geometry, dimmed design, spotlight and sparkle from the trust reel
_argv = sys.argv; sys.argv = ["render_trust.py", "-", "-"]
_ns = {"__file__": TRUST, "__name__": "trust_lib"}
exec(open(TRUST).read().split("# ------------------------------------------------------------------ timeline")[0], _ns)
sys.argv = _argv
light, sparkle, CEN, DIM = _ns["light"], _ns["sparkle"], _ns["CEN"], _ns["DIM"]
ORDER_ALL, eio, eo, eb, prog, clamp = _ns["ORDER_ALL"], _ns["eio"], _ns["eo"], _ns["eb"], _ns["prog"], _ns["clamp"]

def apply_cam(f, s, cx, cy):
    hw, hh = 1080 / (2 * s), 1920 / (2 * s)
    cx, cy = clamp(cx, hw, 1080 - hw), clamp(cy, hh, 1920 - hh)
    if abs(s - 1) < 1e-3: return f
    M = np.array([[s, 0, 540 - cx * s], [0, s, 960 - cy * s]], np.float32)
    return cv2.warpAffine(f, M, (1080, 1920), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

W, H, FPS, SR = 1080, 1920, 30, 48000
T_IN0, T_IN1 = 2.90, 3.20          # crossfade store -> design
T_OUT0, T_OUT1 = 10.95, 11.25      # crossfade design -> store ending
POPS = {"batool": 3.20, "yousef": 5.10, "osama": 8.10}
T_ALL = 10.10

# ---------------------------------------------------------------- read the store video
dec = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                     capture_output=True, check=True).stdout
STORE = np.frombuffer(dec, np.uint8).reshape(-1, H, W, 3)
N = len(STORE)

# brighter, navy-tinted base for the design so it matches the store video's background tone
NAVY = np.median(STORE[200, 400:600, 900:1060].reshape(-1, 3), 0).astype(np.float32)
DIM = cv2.GaussianBlur(_ns["IMG"], (0, 0), 6) * 0.42 + NAVY * 0.38

# store title "خلينا عملاءنا يتكلمون" + logo, as a white overlay with alpha from brightness
band = STORE[200, 0:310].astype(np.float32)
OV_A = np.clip((band.mean(2) - 95) / 110, 0, 1)
OV_A[:, :40] = 0
OV_C = band
SHADOW = cv2.GaussianBlur(OV_A, (0, 0), 7) * 0.65

def overlay_title(f, op):
    if op <= 0: return
    top = f[0:310]
    # soft navy gradient so the title reads over the moving design
    grad = np.clip(1 - np.arange(310) / 310, 0, 1)[:, None, None] ** 1.2 * 0.75 * op
    top[:] = top * (1 - grad) + np.array([48, 28, 18], np.float32) * grad
    sh = np.roll(np.roll(SHADOW, 6, 0), 3, 1)[..., None] * op
    top[:] = top * (1 - sh)
    a = OV_A[..., None] * op
    top[:] = top * (1 - a) + OV_C * a

# ---------------------------------------------------------------- the design middle
CAM = [(T_IN0, (1.12, 540, 900)), (3.6, (1.7, *CEN["batool"])), (4.8, (1.74, *CEN["batool"])),
       (5.35, (1.7, *CEN["yousef"])), (7.8, (1.76, *CEN["yousef"])),
       (8.35, (1.7, *CEN["osama"])), (9.85, (1.76, *CEN["osama"])),
       (10.45, (1.0, 540, 960)), (T_OUT1, (1.03, 540, 960))]

def cam(t):
    if t <= CAM[0][0]: return CAM[0][1]
    for (t0, v0), (t1, v1) in zip(CAM, CAM[1:]):
        if t <= t1:
            e = eio(prog(t, t0, t1)); return tuple(a + (b - a) * e for a, b in zip(v0, v1))
    return CAM[-1][1]

def design_frame(t):
    c = DIM.copy()
    for k, t0 in POPS.items():
        if t < t0: continue
        p = prog(t, t0, t0 + 0.55)
        light(c, k, eo(p), pop=0.07 * (1 - eb(p)) + 0.02 * eo(p) * (1 - prog(t, T_ALL, T_ALL + 0.5)),
              glow=0.9 * eo(p) * (1 - 0.6 * prog(t, t0 + 2.2, t0 + 3.0)))
        sparkle(c, k, prog(t, t0 + 0.5, t0 + 1.5))
    for j, k in enumerate([x for x in ORDER_ALL if x not in POPS]):
        p = prog(t, T_ALL + 0.07 * j, T_ALL + 0.07 * j + 0.35)
        if p > 0: light(c, k, eo(p), pop=0.05 * (1 - eb(p)) if p < 1 else 0)
    if t > T_ALL: light(c, "phone", 0.9 * eo(prog(t, T_ALL + 0.3, T_ALL + 0.8)))
    f = apply_cam(c, *cam(t))
    overlay_title(f, 1.0)
    return f

def frame(i):
    t = i / FPS
    store = STORE[min(i, N - 1)].astype(np.float32)
    if t < T_IN0 or t >= T_OUT1: return store
    d = design_frame(t)
    if t < T_IN1: a = eio(prog(t, T_IN0, T_IN1)); return store * (1 - a) + d * a
    if t >= T_OUT0: a = eio(prog(t, T_OUT0, T_OUT1)); return d * (1 - a) + store * a
    return d

# ---------------------------------------------------------------- audio: store track + soft sparkles
def build_audio(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    def ping(f, d, r, amp):
        n = int(d * SR); tt = np.arange(n) / SR
        return (amp * np.minimum(tt / 0.004, 1) * np.exp(-tt / r) * np.sin(2 * math.pi * f * tt)).astype(np.float32)
    def add(sig, t0):
        s = int(t0 * SR); e = min(len(a), s + len(sig)); a[s:e] += sig[:e - s, None]
    for t0 in POPS.values():
        add(ping(1568, 0.5, 0.12, 0.05) + ping(2349, 0.5, 0.08, 0.025), t0 + 0.5)
    for j in range(8):
        add(ping(2093, 0.2, 0.04, 0.02), T_ALL + 0.07 * j)
    a /= max(1.0, np.abs(a).max() / 0.98)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s16le", path], input=a.tobytes(), check=True)

if STILLS:
    ts = np.arange(0, N / FPS, 0.5)
    tiles = [cv2.resize(np.clip(frame(int(t * FPS)), 0, 255).astype(np.uint8), (180, 320)) for t in ts]
    rows = [np.hstack(tiles[k:k + 10] + [np.zeros((320, 180, 3), np.uint8)] * (10 - len(tiles[k:k + 10])))
            for k in range(0, len(tiles), 10)]
    cv2.imwrite(STILLS, np.vstack(rows)); sys.exit()

tv, ta = OUT + ".v.mp4", OUT + ".a.wav"
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                        "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", tv],
                       stdin=subprocess.PIPE)
for i in range(N):
    enc.stdin.write(np.clip(frame(i), 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait()
build_audio(ta)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tv, "-i", ta, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart", OUT], check=True)
os.remove(tv); os.remove(ta)
print("wrote", OUT, N, "frames")
