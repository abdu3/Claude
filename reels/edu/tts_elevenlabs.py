"""Arabic voiceover via ElevenLabs text-to-speech (drop-in replacement for tts.py).

usage: python3 tts_elevenlabs.py <vo_dir> [voice_id]
The API key is read from ELEVENLABS_API_KEY, or injected by the session's network proxy.
Writes the same files as tts.py (NN_<id>.wav + lines.json), so render_edu.py re-times itself.
"""
import os, sys, json, subprocess, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script import LINES
from tts import duration

VOICE = sys.argv[2] if len(sys.argv) > 2 else "pNInz6obpgDQGcFmaJgB"   # replace with an Arabic voice you like
MODEL = "eleven_multilingual_v2"
KEY = os.environ.get("ELEVENLABS_API_KEY", "proxy-injected")

def synth(text, out_wav, prev=None, nxt=None):
    body = {"text": text, "model_id": MODEL, "language_code": "ar",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True}}
    if prev: body["previous_text"] = prev          # keeps intonation consistent across lines
    if nxt: body["next_text"] = nxt
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_128",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"xi-api-key": KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    mp3 = urllib.request.urlopen(req, timeout=120).read()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "mp3", "-i", "-", "-af", "loudnorm=I=-16:TP=-1.5,aresample=48000",
                    "-ac", "2", out_wav], input=mp3, check=True)

if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True); info = []
    said = [s for _, _, s in LINES]
    for i, (k, _, text) in enumerate(LINES):
        f = os.path.join(out, f"{i:02d}_{k}.wav")
        synth(text, f, said[i - 1] if i else None, said[i + 1] if i + 1 < len(said) else None)
        info.append({"id": k, "file": f, "dur": duration(f)}); print(k, round(info[-1]["dur"], 2))
    json.dump(info, open(os.path.join(out, "lines.json"), "w"), ensure_ascii=False, indent=1)
