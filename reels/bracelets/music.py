"""Original synthesized music + SFX for the Silver Haven bracelets reel.

Everything here is generated from scratch with numpy (no samples, no
third-party music), so the track is free to use commercially.

Usage: python3 music.py main  out.wav
       python3 music.py short out.wav
"""
import sys
import wave
import numpy as np

SR = 44100
BPM = 120
BEAT = 60 / BPM
rng = np.random.default_rng(925)


def t_arr(dur):
    return np.arange(int(dur * SR)) / SR


def fft_filter(x, lo=None, hi=None):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    if hi:
        m *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, n)


def note(n):  # midi -> Hz
    return 440 * 2 ** ((n - 69) / 12)


def add(buf, sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= buf.shape[1]:
        return
    sig = sig[: buf.shape[1] - i]
    l = np.cos((pan + 1) * np.pi / 4)
    r = np.sin((pan + 1) * np.pi / 4)
    buf[0, i:i + len(sig)] += sig * gain * l * 1.414
    buf[1, i:i + len(sig)] += sig * gain * r * 1.414


# ---------------- instruments ----------------
def kick():
    t = t_arr(0.45)
    f = 45 + 85 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * 7)
    s[:80] += rng.normal(0, 0.3, 80) * np.linspace(1, 0, 80)
    return s


def clap():
    t = t_arr(0.25)
    n = fft_filter(rng.normal(0, 1, len(t)), 900, 5000)
    env = np.exp(-t * 18)
    for d in (0.0, 0.012, 0.024):
        env += 0.6 * np.exp(-np.maximum(t - d, 0) * 120) * (t >= d)
    return n * env * 0.5


def hat(open_=False):
    t = t_arr(0.18 if open_ else 0.05)
    n = fft_filter(rng.normal(0, 1, len(t)), 7000, None)
    return n * np.exp(-t * (18 if open_ else 70)) * 0.4


def bell(freq, dur=0.9):
    t = t_arr(dur)
    s = (np.sin(2 * np.pi * freq * t) * np.exp(-t * 5)
         + 0.35 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t * 8)
         + 0.18 * np.sin(2 * np.pi * freq * 3.01 * t) * np.exp(-t * 12))
    s[:60] *= np.linspace(0, 1, 60)
    return s


def pad(freqs, dur):
    t = t_arr(dur)
    s = np.zeros_like(t)
    for fq in freqs:
        for det in (-0.0035, 0, 0.0035):
            for h, a in ((1, 1), (2, 0.25), (3, 0.08)):
                s += a * np.sin(2 * np.pi * fq * (1 + det) * h * t + rng.uniform(0, 6))
    att, rel = 0.35, 0.5
    env = np.minimum(1, t / att) * np.minimum(1, (dur - t) / rel).clip(0, 1)
    return s * env / (len(freqs) * 3)


def sub(freq, dur):
    t = t_arr(dur)
    env = np.minimum(1, t / 0.02) * np.minimum(1, (dur - t) / 0.05).clip(0, 1)
    return np.sin(2 * np.pi * freq * t) * env


def whoosh(dur=0.5):
    t = t_arr(dur)
    n = rng.normal(0, 1, len(t))
    out = np.zeros_like(t)
    # sweep band by crossfading three bands
    bands = [fft_filter(n, 300, 1200), fft_filter(n, 1200, 4000), fft_filter(n, 4000, 10000)]
    x = t / dur
    w = [np.clip(1 - 2 * x, 0, 1), 1 - abs(2 * x - 1), np.clip(2 * x - 1, 0, 1)]
    for b, ww in zip(bands, w):
        out += b * ww
    env = np.sin(np.pi * x) ** 2
    return out * env * 0.5


def impact():
    t = t_arr(1.4)
    f = 38 + 60 * np.exp(-t * 15)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
    s += fft_filter(rng.normal(0, 1, len(t)), None, 1500) * np.exp(-t * 9) * 0.35
    return s * 0.9


def riser(dur=1.0):
    t = t_arr(dur)
    x = t / dur
    n = fft_filter(rng.normal(0, 1, len(t)), 2500, None) * x ** 2
    f = 300 + 900 * x ** 2
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * x ** 3 * 0.25
    return (n * 0.45 + s)


def sparkle(dur=0.9):
    out = np.zeros(int(dur * SR))
    for k in range(7):
        fq = note(rng.choice([93, 96, 98, 100, 103, 105]))
        b = bell(fq, 0.5) * 0.18
        i = int(k * 0.055 * SR)
        out[i:i + len(b)] += b[: len(out) - i]
    return out


def reverb(buf, seconds=1.8, mix=0.18):
    n_ir = int(seconds * SR)
    t = np.arange(n_ir) / SR
    out = np.zeros_like(buf)
    for ch in range(2):
        ir = rng.normal(0, 1, n_ir) * np.exp(-t * 3.5)
        ir = fft_filter(ir, 200, 7000)
        ir /= np.sqrt((ir ** 2).sum())
        n = buf.shape[1] + n_ir
        size = 1 << int(np.ceil(np.log2(n)))
        wet = np.fft.irfft(np.fft.rfft(buf[ch], size) * np.fft.rfft(ir, size), size)[: buf.shape[1]]
        out[ch] = buf[ch] + wet * mix
    return out


# ---------------- arrangement ----------------
CHORDS = [  # (root midi for sub, pad notes) Am - F - C - G
    (45, [57, 60, 64, 71]),
    (41, [57, 60, 65, 69]),
    (48, [55, 60, 64, 67]),
    (43, [55, 59, 62, 67]),
]
ARP = [0, 2, 1, 3, 2, 1, 3, 2]  # index into pad notes, +12 octave


def build(total, sections, sfx):
    """sections: list of (t0, t1, mode) mode in full|light|half|none."""
    buf = np.zeros((2, int(total * SR)))
    duck = np.ones(buf.shape[1])
    k = kick()
    bar = 4 * BEAT
    # pad + sub + arp per bar
    nbars = int(np.ceil(total / bar))
    for b in range(nbars):
        t0 = b * bar
        root, notes = CHORDS[b % 4]
        mode = mode_at(sections, t0 + 0.01)
        if mode == "none":
            continue
        add(buf, pad([note(n) for n in notes], bar + 0.4), t0, 0.16, -0.1)
        add(buf, pad([note(n + 12) for n in notes[1:3]], bar + 0.4), t0, 0.05, 0.3)
        for e in range(8):  # 8th note arp
            te = t0 + e * BEAT / 2
            if te >= total:
                break
            m = mode_at(sections, te)
            if m in ("full", "light", "half"):
                fq = note(notes[ARP[e]] + 12)
                add(buf, bell(fq), te, 0.11 if m != "half" else 0.08, -0.4 if e % 2 else 0.4)
        if mode in ("full", "half"):
            add(buf, sub(note(root - 12), bar), t0, 0.32)
    # drums
    nbeats = int(total / BEAT)
    for i in range(nbeats):
        tb = i * BEAT
        m = mode_at(sections, tb + 0.001)
        if m == "full" or (m == "half" and i % 2 == 0) or (m == "light" and i % 2 == 0):
            add(buf, k, tb, 0.85 if m != "light" else 0.55)
            a = int(tb * SR)
            L = min(int(0.25 * SR), len(duck) - a)
            duck[a:a + L] = np.minimum(duck[a:a + L], 1 - 0.55 * np.exp(-np.arange(L) / SR * 14))
        if m == "full" and i % 2 == 1:
            add(buf, clap(), tb, 0.45, 0.05)
        if m == "half" and i % 4 == 2:
            add(buf, clap(), tb, 0.4, 0.05)
        if m in ("full", "light"):
            add(buf, hat(), tb + BEAT / 2, 0.35, 0.25)
            if m == "full":
                add(buf, hat(), tb + BEAT / 4, 0.12, -0.25)
                add(buf, hat(), tb + 3 * BEAT / 4, 0.12, -0.25)
    buf *= duck  # sidechain feel on everything (kick added before, mild)
    for kind, at, g in sfx:
        s = {"whoosh": whoosh, "impact": impact, "riser": riser, "sparkle": sparkle}[kind]()
        if kind == "riser":
            at = at - len(s) / SR
        add(buf, s, at, g, 0.0 if kind != "sparkle" else 0.2)
    buf = reverb(buf)
    # fade out tail
    fo = int(1.2 * SR)
    buf[:, -fo:] *= np.linspace(1, 0, fo) ** 1.5
    buf = np.tanh(buf * 1.1) / np.tanh(1.1)
    buf /= np.abs(buf).max() / 0.89
    return buf


def mode_at(sections, t):
    for a, b, m in sections:
        if a <= t < b:
            return m
    return "none"


def write(buf, path):
    pcm = (buf.T * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    which, out = sys.argv[1], sys.argv[2]
    if which == "main":
        total = 24.5
        sections = [(0, 3, "light"), (3, 14.0, "full"), (14.0, 15.0, "none_drums"),
                    (15.0, 19.0, "half"), (19.0, 21.0, "full"), (21.0, 24.5, "pad")]
        # map custom modes
        sections = [(a, b, {"none_drums": "pad", "pad": "pad"}.get(m, m)) for a, b, m in sections]
        sfx = [("impact", 0.0, 0.55), ("sparkle", 0.05, 0.6),
               ("whoosh", 2.75, 0.5), ("whoosh", 5.75, 0.3), ("whoosh", 8.75, 0.3),
               ("whoosh", 11.75, 0.3), ("riser", 15.0, 0.5), ("impact", 15.0, 0.6),
               ("sparkle", 15.4, 0.7), ("whoosh", 18.75, 0.45), ("whoosh", 20.75, 0.5),
               ("impact", 21.0, 0.5), ("sparkle", 21.6, 0.6)]
    else:
        total = 8.5
        sections = [(0, 1.5, "light"), (1.5, 6.5, "full"), (6.5, 8.5, "pad")]
        sfx = [("impact", 0.0, 0.55), ("sparkle", 0.05, 0.6), ("whoosh", 1.25, 0.45),
               ("whoosh", 6.25, 0.5), ("impact", 6.5, 0.5), ("sparkle", 6.9, 0.6)]
    # "pad" mode: pad + arp off? keep pads only
    write(build(total, sections, sfx), out)
    print("wrote", out)
