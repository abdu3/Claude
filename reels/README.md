# Silver Haven — 925 reels

Three vertical reels (1080×1920, 30 fps, H.264, silent AAC track) generated from the
"925 يعني" design in `src/design-925.jpg`.

| File | Length | Idea |
|---|---|---|
| `output/silverhaven-925-reveal.mp4` | 15 s | Layer-by-layer story: ring lands → 925 rises → يعني → 92.5% / 7.5% arrows draw → Sterling Silver oval draws → light sweep → end card |
| `output/silverhaven-925-tour.mp4` | 12 s | Macro camera tour over the original design: ring close-up → 925 → oval → 92.5% → 7.5% → pull out → end card |
| `output/silverhaven-925-hook.mp4` | 8 s | Fast hook for the first 2 seconds: 925 + ring slam in with a flash, labels pop, end card |

End card: logo, "فضة عيار 925 أصلية", "تسوّق الآن من سيلفر هافن", silverhaven-sa.com.

Audio is silent on purpose: add trending/licensed music inside Instagram, TikTok or Snapchat.

## Regenerate

```bash
pip install opencv-python-headless pillow numpy   # Pillow needs libraqm for Arabic
python3 layers.py src/design-925.jpg /tmp/layers  # split design into plate + element layers
python3 render.py /tmp/layers output              # all reels (or: ... output reveal tour hook)
python3 render.py /tmp/layers output --stills reveal   # contact-sheet preview
```

Fonts: Tajawal and Playfair Display (SIL Open Font License, see `fonts/`).

## Educational explainer with Arabic voiceover

`output/silverhaven-925-explainer-voiceover.mp4` (66 s): "ما معنى 925 على الفضة؟"
Scenes: hook with magnifier → 925 → a 1000-cell grid (925 silver + 75 copper) with counters →
why pure silver bends and 925 doesn't → Sterling Silver name → look for the 925 stamp → brand end card.
Arabic subtitles, light synthesized background music (ducked under the voice) and sound effects.

- `edu/script.py`: narration (subtitle text plus fully vowelled text for the TTS engine). Edit here.
- `edu/tts.py`: offline Arabic TTS (espeak-ng + MBROLA ar2): `apt-get install espeak-ng mbrola mbrola-ar2`
- `edu/render_edu.py`: animation, audio mix and mux. Scene lengths follow the voiceover automatically.

```bash
python3 layers.py src/design-925.jpg /tmp/layers
python3 edu/tts.py /tmp/vo
python3 edu/render_edu.py /tmp/layers /tmp/vo output/silverhaven-925-explainer-voiceover.mp4
```

To use a human recording instead: record each line from `edu/script.py` as a WAV, put the files in the
vo folder under the same names (`00_hook.wav`, `01_what.wav`, …), and update the durations in `lines.json`
(or re-run a small ffprobe loop); the animation re-times itself to the new audio.
