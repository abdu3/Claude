"""Split the flat 925 design into a clean background plate + per-element alpha layers."""
import cv2, numpy as np, sys, os
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
img = cv2.imread(src)
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
bg = cv2.medianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 41).astype(np.float32)
bg_big = cv2.medianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 151).astype(np.float32)
diff = g - bg
# element boxes (x0,y0,x1,y1)
BOX = {
 "logo":   (40, 35, 165, 140),
 "oval":   (375, 525, 1040, 745),
 "arrow_up": (690, 720, 750, 845),
 "num":    (268, 828, 805, 1102),
 "ring":   (600, 960, 820, 1160),
 "yaani":  (260, 1100, 705, 1215),
 "arrow_l": (150, 1035, 320, 1255),
 "txt_l":  (70, 1255, 370, 1310),
 "arrow_r": (770, 1105, 870, 1210),
 "txt_r":  (710, 1250, 1030, 1305),
}
H, W = g.shape
full = np.zeros((H, W), np.float32)
alphas = {}
for k, (x0, y0, x1, y1) in BOX.items():
    a = np.zeros((H, W), np.float32)
    if k == "ring":
        f = img.astype(np.float32)
        chroma = f[..., 0] - f[..., 2]          # stone is blue, silver is neutral grey
        e = np.zeros((H, W), np.uint8)
        cv2.ellipse(e, (690, 1042), (120, 72), -56, 0, 360, 255, -1)
        a = np.clip((26 - chroma) / 10, 0, 1) * (cv2.GaussianBlur(e, (0, 0), 2) / 255.0)
        a = a.astype(np.float32)
    else:
        base = bg_big if k in ("num", "yaani") else bg
        sub = np.clip((g - base - 22) / 30, 0, 1)
        a[y0:y1, x0:x1] = sub[y0:y1, x0:x1]
        a = cv2.GaussianBlur(a, (0, 0), 0.6)
    alphas[k] = a
    full = np.maximum(full, a)
# remove the ring area from the "num" layer so they animate separately
alphas["num"] = alphas["num"] * (1 - alphas["ring"])
# split 925 into single digits, the oval into stroke + caption
for name, (x0, x1) in {"n9": (0, 452), "n2": (452, 622), "n5": (622, W)}.items():
    a = np.zeros_like(alphas["num"]); a[:, x0:x1] = alphas["num"][:, x0:x1]; alphas[name] = a
cap = np.zeros_like(alphas["oval"]); cap[598:678, 468:948] = 1
alphas["caption"] = alphas["oval"] * cap
alphas["oval"] = alphas["oval"] * (1 - cap)
# background plate: inpaint everything that is an element
low = np.zeros((H, W), np.uint8)
for k, (x0, y0, x1, y1) in BOX.items():
    base = bg_big if k in ("num", "yaani") else bg
    low[y0:y1, x0:x1] |= ((g - base)[y0:y1, x0:x1] > 9).astype(np.uint8)
low = cv2.morphologyEx(low, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
ring_zone = np.zeros((H, W), np.uint8); cv2.ellipse(ring_zone, (690, 1042), (124, 76), -56, 0, 360, 1, -1)
m = (cv2.dilate(((full > 0.05) | (low > 0) | (ring_zone > 0)).astype(np.uint8), np.ones((7, 7), np.uint8)) * 255)
plate = cv2.inpaint(img, m, 9, cv2.INPAINT_TELEA)
# re-texture the inpainted areas: high-frequency stone detail from a clean area,
# low-frequency lighting from the inpainted plate
f = plate.astype(np.float32)
src_y = 1360
hf = np.zeros_like(f)
tex = img[src_y:, :].astype(np.float32)
th = tex.shape[0]
for y in range(0, H, th):
    seg = tex[: min(th, H - y)]
    hf[y:y + seg.shape[0]] = seg - cv2.GaussianBlur(seg, (0, 0), 12)
lf = cv2.GaussianBlur(f, (0, 0), 12)
wm = cv2.GaussianBlur(cv2.dilate(m, np.ones((25, 25), np.uint8)).astype(np.float32) / 255, (0, 0), 10)[..., None]
plate = np.clip(f * (1 - wm) + (lf + hf) * wm, 0, 255).astype(np.uint8)
cv2.imwrite(f"{out}/plate.png", plate)
for k, a in alphas.items():
    rgba = np.dstack([img, (a * 255).astype(np.uint8)])
    cv2.imwrite(f"{out}/{k}.png", rgba)
cv2.imwrite(f"{out}/_mask.png", (full * 255).astype(np.uint8))
print("ok")
