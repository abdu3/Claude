"""Turn grey / half-filled rating stars into full gold stars in a frame.

Stars are found as compact, solid light-grey (or pale-gold) blobs on the white review cards that
do not touch dark text pixels; each is repainted with the gold of a completed star, keeping its
anti-aliased edge so the shape is unchanged.
"""
import cv2, numpy as np

GOLD = np.array([38, 178, 244], np.float32)       # BGR of a filled star in the video

def _star_template():
    c, pts = 100, []
    for i in range(10):
        r = 90 if i % 2 == 0 else 38; a = -np.pi / 2 + i * np.pi / 5
        pts.append((c + r * np.cos(a), c + r * np.sin(a)))
    m = np.zeros((200, 200), np.uint8); cv2.fillPoly(m, [np.array(pts, np.int32)], 255)
    return cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0][0]
STAR = _star_template()

def _is_star(mask):
    cs = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]
    if not cs: return False
    c = max(cs, key=cv2.contourArea)
    return cv2.matchShapes(c, STAR, cv2.CONTOURS_MATCH_I1, 0) < 0.25

def fix_stars(img, min_area=18, max_area=2500):
    f = img.astype(np.float32)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    lum = f.mean(2); sat = hsv[..., 1]; hue = hsv[..., 0]
    grey = (lum > 140) & (lum < 228) & (sat < 40)                          # empty star
    pale = (sat >= 40) & (sat < 150) & (hue > 8) & (hue < 32) & (lum > 120)  # star mid-fill
    gold = (sat >= 150) & (hue > 10) & (hue < 30)                          # finished star
    cand = (grey | pale).astype(np.uint8)
    dark = (lum < 120).astype(np.uint8)
    near_dark = cv2.dilate(dark, np.ones((5, 5), np.uint8))
    card = cv2.dilate((lum > 232).astype(np.uint8), np.ones((9, 9), np.uint8))  # white card around it
    n, lab, st, _ = cv2.connectedComponentsWithStats(cand, 8)
    # every star-shaped blob (grey, pale or gold) -> used to confirm rows of 5
    allm = (grey | pale | gold).astype(np.uint8)
    n2, lab2, st2, cen2 = cv2.connectedComponentsWithStats(allm, 8)
    stars = [(cen2[j][0], cen2[j][1], st2[j][4]) for j in range(1, n2)
             if min_area <= st2[j][4] <= max_area and 0.6 < st2[j][2] / max(st2[j][3], 1) < 1.6
             and _is_star(lab2[st2[j][1]:st2[j][1] + st2[j][3], st2[j][0]:st2[j][0] + st2[j][2]] == j)]
    def in_row(cx, cy, area, h):
        same = [1 for (x, y, a) in stars if abs(y - cy) < h * 0.6 and 0.6 < a / area < 1.6 and abs(x - cx) < h * 7]
        return len(same) >= 3
    out = f.copy(); hits = 0
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if not (min_area <= a <= max_area) or not (0.6 < w / max(h, 1) < 1.6) or a / (w * h) < 0.35:
            continue
        m = lab[y:y + h, x:x + w] == i
        if not _is_star(m) or not in_row(x + w / 2, y + h / 2, a, h): continue
        if near_dark[y:y + h, x:x + w][m].mean() > 0.15: continue              # anti-aliased text edge
        if card[y:y + h, x:x + w][m].mean() < 0.5: continue                    # not sitting on a card
        if gold[y:y + h, x:x + w][m].mean() > 0.6: continue                    # already gold
        # coverage from how far the pixel is from the card white -> keeps the soft edge
        X0, Y0, X1, Y1 = max(x - 3, 0), max(y - 3, 0), min(x + w + 3, img.shape[1]), min(y + h + 3, img.shape[0])
        reg = f[Y0:Y1, X0:X1]; bg = np.percentile(reg.mean(2), 95)
        mm = cv2.dilate((lab[Y0:Y1, X0:X1] == i).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        cov = np.clip((bg - reg.mean(2)) / max(bg - np.percentile(reg.mean(2)[lab[Y0:Y1, X0:X1] == i], 20), 8), 0, 1)
        cov = np.where(mm, cov, 0)[..., None]
        bgc = np.array([bg, bg, bg], np.float32) * np.array([1.0, 0.99, 0.97])
        out[Y0:Y1, X0:X1] = reg * (1 - cov) + (bgc * 0 + GOLD) * cov + reg * 0 * cov
        out[Y0:Y1, X0:X1] = np.where(mm[..., None], np.array([bg, bg, bg]) * (1 - cov) + GOLD * cov, reg)
        hits += 1
    return out.astype(np.uint8), hits
