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

### Saudi-dialect voice (ElevenLabs)

`output/silverhaven-925-explainer-saudi-voice.mp4` (54 s) uses the ElevenLabs voice **Mansour**
(white Saudi dialect, model eleven_v4). The original take is kept in `edu/voiceover-mansour-saudi.mp3`;
it was split into the 10 lines of `edu/script.py` at the pauses between sentences, then the animation
was re-timed to it. The subtitles in `edu/script.py` are in the same dialect.

## Trust reel: customer reviews (ElevenLabs female voice, white Saudi dialect)

`output/silverhaven-reviews-trust-reel.mp4` (52 s), built from `trust/src/design-reviews.jpg`.
The design is dimmed and the camera moves card by card. Each review card lights up with a glow and a
star sparkle while the voiceover reads that customer's review word for word (only reviews visible in the design).
Then all cards light up ("5 نجوم من الرياض للدمام للطائف"), then the Tabby offer on the phone, then the end card.

- Voice: ElevenLabs **Mona** (white Saudi dialect, eleven_v4). Original take: `trust/voiceover-mona-saudi.mp3`.
- `trust/render_trust.py <vo_dir> <out.mp4>`: card positions, timeline, subtitles (customer name in gold), music and SFX.

### Short cut for TikTok / Instagram Reels (under 30 s)

`output/silverhaven-reviews-reel-tiktok-28s.mp4` (29.6 s): hook → Batool → Yousef → 5-star social proof → Tabby → CTA,
cut from the same Mona take (no new generation). Rendered with `render_trust.py <vo_dir> <out> --short`: tighter
pacing, and subtitles raised to y=1420 so TikTok/Reels caption and button overlays don't cover them.

## Fixes to the store's own reviews reel

`output/silverhaven-reviews-reel-fixed.mp4` is `fix/original-reviews-reel.mp4` (15 s) with two changes, same audio:
- **Full gold stars from the first frame** (`fix/stars.py`): rating stars that were still grey or filling are
  detected (star outline match, rows of stars on the white cards, not touching text) and repainted gold.
- **CTA and link lifted out of the TikTok/Reels overlay zone** (`fix/fix_video.py`): during the existing camera
  move into the ending (frames 329–355) the scene shrinks to 86% toward the top; the margins are filled
  by mirroring and blurring the frame's own edges.

`python3 fix/fix_video.py fix/original-reviews-reel.mp4 output/silverhaven-reviews-reel-fixed.mp4`

## Merged version: store video + cinematic card spotlight

`output/silverhaven-reviews-reel-merged.mp4` (15 s, the store's own voiceover and music):
- 0–2.9 s and 11.25 s–end: the store video (`output/silverhaven-reviews-reel-fixed.mp4`: full stars, lifted CTA).
- 3.2–10.95 s: camera spotlight on `trust/src/design-reviews.jpg`, synced to the moments each card appears in the
  store video (Batool 3.2 s, Yousef 5.1 s, Osamah 8.1 s, all cards 10.1 s), with the store's own title and logo
  overlaid in the same font. Short crossfades at the joins, navy tint matched to the store video.

`python3 merge/render_merge.py output/silverhaven-reviews-reel-fixed.mp4 output/silverhaven-reviews-reel-merged.mp4`
(reuses the spotlight/sparkle code from `trust/render_trust.py`).

## Bracelets ad: "أي سوار يناسب ذوقك؟"

`output/silverhaven-bracelets-ad-25s.mp4` (25.5 s, 1080×1920, 30 fps) is built from three product photos in
`bracelets/src/`: the tennis bracelet, the two-tone hearts bracelet and the two-tone pavé link bracelet.

| Time | Scene |
|---|---|
| 0–1.5 s | Hook: three punch-in detail cuts (one per bracelet) on the beat, with a flash and an impact sound |
| 1.5–3 s | Question: "أي سوار يناسب ذوقك؟" / "3 تصاميم فضة عيار 925" |
| 3–8 s | 1 · سوار التنس الكلاسيكي: pan down the stones, then pull out |
| 8–13 s | 2 · سوار القلوب: wide shot pushing in along the hearts |
| 13–18 s | 3 · سوار الروابط المرصّع: pan up the links, then pull out |
| 18–21.5 s | Split screen 1 / 2 / 3: "رقمك المفضل؟ اكتبه لنا بالتعليقات" (to get comments) |
| 21.5–25.5 s | End card: logo, فضة عيار 925 أصلية, تسوّق الآن, silverhaven-sa.com, Tabby |

Effects: sparkle glints placed automatically on the bracelet's own highlights (the shop's background lights
are skipped), a light sweep over the metal, a whip blur between products, and a gold number badge for each
product. Synthesized 120 BPM music (cuts land on the beat) plus sound effects. All text sits inside the
TikTok / Reels / Snap safe zone.
The product text only states what the photos show (zircon stones, gold and silver tones).

```bash
python3 bracelets/render_ad.py output/silverhaven-bracelets-ad-25s.mp4
python3 bracelets/render_ad.py out.mp4 --stills sheet.jpg          # contact sheet
python3 bracelets/render_ad.py out.mp4 --stills f.jpg 6.0 23.5     # full-size frames at given times
```

### v2: full production brief (`bracelets/render_v2.py`, `bracelets/PRODUCTION.md`)

Fast TikTok/Reels concept with a navy / silver / white finish: macro stone hook with a speed-ramp pull-out,
beat-synced detail cuts, product scenes with the bracelet on the left third and text on the right (match cuts),
a 1·2·3 comment trigger, and an end card. Original 120 BPM score, normalised to −14 LUFS.
Outputs: `output/silverhaven-bracelets-ad-v2-28s.mp4`, `output/silverhaven-bracelets-ad-v2-9s.mp4`,
`output/silverhaven-bracelets-ad-v2-cover.jpg`. The shot list, concept scoring, storyboard, caption and QC are in `bracelets/PRODUCTION.md`.
