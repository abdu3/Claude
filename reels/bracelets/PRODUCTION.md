# Silver Haven: bracelets ad v2, production file

Deliverables (in `../output/`):

| File | What | Specs |
|---|---|---|
| `silverhaven-bracelets-ad-v2-28s.mp4` | Main ad | 28.0 s · 1080×1920 · 9:16 · 30 fps · H.264 High 4.1 · AAC 48 kHz stereo 192 kb/s · −14.3 LUFS, −1.1 dBTP |
| `silverhaven-bracelets-ad-v2-9s.mp4` | Short cut (Stories / Snap / bumper) | 9.0 s · same specs · −15.1 LUFS, −1.4 dBTP |
| `silverhaven-bracelets-ad-v2-cover.jpg` | Cover | 1080×1920; headline and products sit inside the 4:5 grid crop (y 285–1635) |

Rebuild: `python3 render_v2.py main|short|cover <out>` (see the header of `render_v2.py`).

---

## 1. Source material analysis

**What was supplied:** three still photos (4K, 2160×3840, 9:16), no video files. Each photo is treated as a
"plate": every shot below is a framed region of a photo with a camera move. Since stills have no
timestamps, shots are given as a region (frame coordinates on a 1080×1920 grid) and a zoom.

| File | Resolution | Ratio | Content | Lighting / focus |
|---|---|---|---|---|
| `bracelet-tennis.jpg` | 2160×3840 | 9:16 | Tennis bracelet with round stones in 4-prong settings, held vertically across the fingers | Excellent: sharp stones with real fire, clean silver; clasp at the bottom slightly soft |
| `bracelet-hearts.jpg` | 2160×3840 | 9:16 | Heart links alternating gold tone and silver, laid diagonally on the palm | Very good: polished reflections; clasp and bottom heart out of focus |
| `bracelet-links.jpg` | 2160×3840 | 9:16 | White links with a row of zircon, alternating with gold-tone rectangular links + extender chain | Good: links sharp; extender and its tag blurred (the stamp cannot be read) |

Native zoom limit: ×2 is 1:1 with the source; ×3.0–3.6 is still clean on the stones (checked at native
resolution), so it is used only for the macro shots.

### Shot list

| # | File | Region (x, y) / zoom | Rating | Role in the ad |
|---|---|---|---|---|
| T1 | tennis | single stone (708–742, 752) ×3.15→2.9 | ★★★★★ | **Hook**: macro of one stone, natural fire |
| T2 | tennis | whole bracelet in hand (640, 880) ×1.2 | ★★★★☆ | Hook reveal after the speed-ramped pull-out |
| T3 | tennis | prongs (655, 840–862) ×3.3 | ★★★★★ | Fast detail cut (4 prongs visible) |
| T4 | tennis | pan along the stones y 470→1010 ×2.0 | ★★★★★ | Product 1 scene |
| H1 | hearts | gold + silver heart pair (497–505, 560–625) ×3.0 | ★★★★★ | Detail cut: the two tones together |
| H2 | hearts | polished highlight (605–610, 1040–1065) ×3.0 | ★★★★☆ | Fast detail cut |
| H3 | hearts | pan along the hearts y 440→950 ×2.0 | ★★★★☆ | Product 2 scene |
| H4 | hearts | wide diagonal (590, 900) ×1.2, softened | ★★★☆☆ | Background for the "ثلاث أساور" title card |
| L1 | links | pavé link (636–640, 690–760) ×3.0 | ★★★★★ | Detail cut: row of zircon |
| L2 | links | white/gold junction (650, 845–870) ×2.8 | ★★★★☆ | Fast detail cut (a natural match to H1) |
| L3 | links | pan up the links y 1130→660 ×2.0 | ★★★★☆ | Product 3 scene |

**Rejected:** extender chain and tag (blurred, so the 925 stamp is unreadable and not used as proof);
both clasp areas (soft focus); the bokeh-only parts of the frames (no product); the top of the hearts photo (cropped heart).

**Hook candidates:** T1 (strongest: stone fire in the first frame), L1, H1. T1 opens, and L1/H1 carry the 3–6 s curiosity cuts.

**Edit opportunities:** the three bracelets all run vertically → **match cuts** on the bracelet column
(it stays on the same screen column, the left third, across product scenes); **speed ramp** on the hook
pull-out and the product pans (slow → fast → slow, with motion blur only during the fast part);
glints on real highlights only; one light sweep over the metal per scene.

---

## 2. Three concepts, scored (1–10)

| | Stopping power | Retention | Fit with the material | Engagement / purchase | Total |
|---|---|---|---|---|---|
| **A. Quiet luxury cinematic**: slow moves, macro, music only | 6 | 6 | 9 | 6 | 27 |
| **B. Fast TikTok/Reels**: macro hook, beat-synced cuts, "which number is yours?" | **9** | **8** | **8** | **9** | **34** |
| **C. Natural UGC**: handheld feel, voice, "look what I found" | 7 | 7 | 3 | 7 | 24 |

- A suits 4K stills, but 28 seconds of slow moves on 3 photos loses viewers by the middle.
- C needs real video (hand movement, natural sound, a voice); with stills it would look fake.
- **B wins on the actual material:** 4K resolution gives 11 distinct shots from 3 photos, enough for fast cuts,
  and the comparison of three designs builds in a "pick a number" mechanic that drives comments.
  It is executed with A's finish (navy grade, restrained type, measured transitions).

---

## 3. Script and storyboard (main ad, 28 s, 120 BPM, cut every 0.5 s or a multiple)

| Time | Shot | Camera / motion | On-screen text | Transition | Sound | Marketing goal |
|---|---|---|---|---|---|---|
| 0.0–2.1 | T1 | Macro on one stone ×3.15, slow push; glint burst at 1.0 s | «استني..» then «شوفي هاللمعة» (right side, clear of the stone) | Opens on a soft light flash | Soft impact + sparkle | Stop the scroll on the product's strongest detail |
| 2.1–3.0 | T1→T2 | **Speed-ramp** pull-out ×2.9→×1.2 revealing the whole bracelet | (text out) | Ramp | Whoosh + sparkle | Pay off the curiosity: here is the whole piece |
| 3.0–4.0 | H1 | Macro drift down | none | Hard cut on the beat | Rising pulse | Curiosity: a second, different design |
| 4.0–5.0 | L1 | Macro drift up | none | Cut on the beat | Pulse | Third design: the zircon row |
| 5.0–5.5 | T3 | Prongs | none | Cut | Pulse | Acceleration, quality detail |
| 5.5–6.0 | H2 | Heart polish | none | Cut | Pulse | |
| 6.0–6.5 | L2 | White/gold junction | none | Match on the two tones | Riser starts | |
| 6.5–8.0 | H4 | Wide, softened, navy | «ثلاث أساور» / silver rule / «وحدة منها لك» | Impact cut | Impact + tick | Frame the choice: personal, not a list |
| 8.0–11.5 | T4 | Pan down the stones with a speed ramp, bracelet on the left third | ① «تنس كلاسيكي» / «زركون بتركيب 4 مخالب» | **Drop**: the beat comes in | Kick, hat, sparkle | Desire + proof visible in the shot |
| 11.5–15.0 | H3 | Pan along the hearts, same column (**match cut**) | ② «قلوب بلونين» / «ذهبي وفضي بالتناوب» | Match cut | Sparkle | Desire: playful, two tones |
| 15.0–18.0 | L3 | Pan up the links, same column (**match cut**) | ③ «روابط مرصّعة» / «فضي مرصّع وروابط ذهبية» | Match cut | Sparkle | Desire: the dressiest of the three |
| 18.0–24.0 | 3 panels | Panels 1 · 2 · 3 rise on the beats, then a light sweep | «فضة عيار 925» / «تنلبس يومياً.. وتليق بمناسباتك» / «أي رقم يشبهك؟» / «قوليه لنا بالتعليقات» | Slide up | Soft whoosh ×3, half-time, soft impact | Brand value + comment trigger |
| 24.0–28.0 | End card | Navy, logo rises, light sweep | «اكتشفي التشكيلة كاملة» / silverhaven-sa.com / «وتقدرين تقسّطينها مع تابي» | Fade through navy | Soft impact + sparkle, music fades | CTA: visit the store; Tabby lowers the barrier |

**Short cut (9 s):** hook T1 with a ramp at 1.6 s (0–2.5) → ①②③ one second each with their names (2.5–5.5) →
end card «أي وحدة تختارين؟ / 1 أو 2 أو 3» with the logo (5.5–9).

---

## 4. Production standards applied

- **Grade:** shadows toned slightly toward navy, light contrast and clarity on metal edges. **No hue shift:** the
  gold-tone parts stay as photographed and the silver is not warmed. Glints are a neutral cool white.
- **Graphics:** navy #10213A, silver and white only; Tajawal for Arabic, Playfair for numerals and the URL;
  titles wipe in right-to-left (reading direction) with a silver rule; each number sits in a silver disc.
- **Placement:** in product scenes the bracelet is held on the left third and the text on the right, so no text
  covers the product; all text sits inside x 150–930 and y 180–1480 (clear of TikTok / Reels / Snap UI).
- **Claims:** only what the photos show (zircon, 4 prongs, two tones) plus the store's own 925 line. No prices,
  discounts or guarantees. Tabby comes from the store's earlier ad design; remove the line if it no longer applies.
- **Faithfulness:** no generated shots, no models, no added stones or reshaping. The only additions are light (glints, sweep).
- **Music:** an original track built in code (Am–F–C–G, 120 BPM), so no licence is needed. Effects: soft impact, whoosh,
  sparkle, tick, kept quiet under the music. Loudness normalised to −14 LUFS for social platforms.

---

## 5. Post caption

> ثلاث أساور فضة عيار 925.. وكل وحدة لها طابعها ✨
> ١ تنس كلاسيكي · ٢ قلوب بلونين · ٣ روابط مرصّعة
> أي رقم يشبهك؟ اكتبيه بالتعليقات 👇
> التشكيلة كاملة على silverhaven-sa.com
>
> #سيلفر_هافن #فضة_925 #اساور_فضة #اكسسوارات #هدايا #مجوهرات_فضة #السعودية

Short version (Stories/Snap): «أي وحدة تختارين؟ ١ أو ٢ أو ٣ 👀 | silverhaven-sa.com»

---

## 6. Quality review

| Check | Result |
|---|---|
| Duration / frames | Main 28.0 s = 840 frames; short 9.0 s = 270 frames |
| Black frames (ffmpeg blackdetect) | None in either version |
| Unintended cuts | None: every cut is on a beat (0.5 s grid) per the storyboard |
| Text / timing | Checked on a grid of 2 frames per second from the exported file; text never covers the bracelet in product scenes |
| Product integrity | Shape and colours as in the photos; zoom ≤ ×3.6, checked at native resolution |
| Audio | −14.3 LUFS integrated, true peak −1.1 dBTP (main) |
| Phone playback | H.264 High 4.1, yuv420p, faststart: plays natively on iOS/Android and uploads directly |
| Not done | Real-time playback on a physical phone (no device in this environment); a human voiceover |

**Assessment:** the hook is strong (stone fire in the first frame plus a curiosity line); the rhythm speeds up
from 3 s to 6.5 s, then settles into the three product scenes; the ending invites a comment and then a store
visit. The main weakness is the material itself: three photos. Short real videos (a wrist turning under the
light, a clasp closing) would lift retention and allow a true UGC version.
