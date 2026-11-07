"""Offline Arabic TTS: espeak-ng (phonemes) -> MBROLA ar2 (diphone voice) -> ffmpeg polish."""
import subprocess, re, os, tempfile

VOICE = "/usr/share/mbrola/ar2/ar2"

def synth(text, out_wav, speed=136, pitch=1.0):
    pho = subprocess.run(["espeak-ng", "-v", "mb-ar2", "-s", str(speed), "-q", "--pho", text],
                         capture_output=True, text=True, check=True).stdout
    # ar2 has no "R" diphones (espeak's emphatic r) -> use plain r
    pho = re.sub(r"^R\t", "r\t", pho, flags=re.M)
    with tempfile.TemporaryDirectory() as d:
        p, raw = os.path.join(d, "x.pho"), os.path.join(d, "x.wav")
        open(p, "w").write(pho)
        subprocess.run(["mbrola", "-f", str(pitch), VOICE, p, raw], check=True, capture_output=True)
        # warm it up a little: band-limit, gentle compression, tiny room, 48 kHz stereo
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af",
                        "highpass=f=80,lowpass=f=7000,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,"
                        "aecho=0.8:0.5:40:0.12,loudnorm=I=-16:TP=-1.5,aresample=48000",
                        "-ac", "2", out_wav], check=True)

def duration(wav):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav],
                                capture_output=True, text=True).stdout)

if __name__ == "__main__":
    import sys, json
    sys.path.insert(0, os.path.dirname(__file__))
    from script import LINES
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    info = []
    for i, (k, sub, said) in enumerate(LINES):
        f = os.path.join(out, f"{i:02d}_{k}.wav"); synth(said, f)
        info.append({"id": k, "file": f, "dur": duration(f)})
        print(k, round(info[-1]["dur"], 2))
    json.dump(info, open(os.path.join(out, "lines.json"), "w"), ensure_ascii=False, indent=1)
