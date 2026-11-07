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
