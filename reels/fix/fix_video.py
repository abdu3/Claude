"""Fix the customer-reviews reel: full gold stars from the first frame, and lift the closing
scene (CTA button + link) out of the TikTok / Reels overlay zone.

usage: python3 fix_video.py <in.mp4> <out.mp4>
"""
import sys, os, subprocess, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stars import fix_stars

SRC, OUT = sys.argv[1], sys.argv[2]
W, H, FPS = 1080, 1920, 30
LIFT_START, LIFT_END, SCALE = 329, 355, 0.86      # frames of the existing camera move into the ending

def eio(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2

def lift(frame, p):
    s = 1 - (1 - SCALE) * eio(p)
    if s > 0.999: return frame
    sw, sh = int(round(W * s)), int(round(H * s))
    small = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_AREA)
    x0 = (W - sw) // 2
    # fill the freed margins by mirroring the frame's own edges, then blur that fill only
    padded = cv2.copyMakeBorder(small, 0, H - sh, x0, W - sw - x0, cv2.BORDER_REFLECT_101)
    bg = cv2.GaussianBlur(padded, (0, 0), 22).astype(np.float32)
    # the mirrored strip under the frame would echo the gold button: fade it towards the navy tone
    navy = bg[sh - 40:sh, :].mean((0, 1))
    k = np.clip((np.arange(H) - sh) / max(H - sh, 1), 0, 1)[:, None, None] * 0.85
    gray = bg.mean(2, keepdims=True)
    bg = bg * (1 - k) + (navy * 0.9 + 0 * gray) * k
    m = np.zeros((H, W), np.float32); m[:sh, x0:x0 + sw] = 1
    m = cv2.erode(m, np.ones((25, 25), np.uint8)); m = cv2.GaussianBlur(m, (0, 0), 10)[..., None]
    return (padded.astype(np.float32) * m + bg * (1 - m)).astype(np.uint8)

dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
tmp = OUT + ".v.mp4"
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                        "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
i, fixed = 0, 0
while True:
    buf = dec.stdout.read(W * H * 3)
    if len(buf) < W * H * 3: break
    f = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    f, n = fix_stars(f); fixed += n > 0
    if i >= LIFT_START:
        f = lift(f, min(1.0, (i - LIFT_START) / (LIFT_END - LIFT_START)))
    enc.stdin.write(f.tobytes()); i += 1
enc.stdin.close(); enc.wait(); dec.wait()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-i", SRC, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy",
                "-movflags", "+faststart", OUT], check=True)
os.remove(tmp)
print(f"wrote {OUT}: {i} frames, stars fixed in {fixed}")
