"""Cut the pose sheet (design.png) into the pet's still bodies, and find where its eyes go.

    just sprites                     # design.png -> webui/static/sprites/
    just sprites --preview out.png   # also save every pose with a dot where each eye goes

The sheet, as the designer drew it:
  - five bodies without eyes, read top row left to right then bottom row: stand, walk, sit,
    loaf, lie (POSE_ORDER); anything else on the sheet (e.g. sample eyes) is ignored
  - background transparent, or a light grey-and-white checkerboard painted on (removed here:
    whatever light, colourless area touches the sheet's edge; the bodies' dark outline stops it)

Written to the sprites folder (read by sprites.py, drawn by static/pet-view.js):
    <pose>/body.png   the body on the page's 6:5 canvas, standing on its standing point
    faces.json        per pose, where the eyes, blush and mouth go on that canvas and how big
                      they are; the page draws them there (static/pet-view.js). The nose,
                      mouth and blush drawn on the sheet are painted over with fur in body.png.
Where the eyes go is worked out from each face's nose and blush (pink spots). If a pose's eyes
look off, give the face's eye positions in the sheet's pixels with --eyes (see main()).

Needs Pillow, numpy and scipy; the just recipe brings them in for this run only.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from .sprites import POSES, SPRITES_DIR

POSE_ORDER = ["stand", "walk", "sit", "loaf", "lie"]
# Where the eyes go, from the face's blush and nose (the design draws none on the bodies):
EYE_IN = 0.3      # each eye this share of the way from its blush towards the nose
EYE_UP = 0.12     # eyes this share of the blush-to-blush distance above the blush
MOUTH_WIDTH = 0.24  # the page's mouth, as a share of the blush-to-blush distance
EYE_SIZE = 0.1    # an eye's radius, as a share of the blush-to-blush distance

BG_SAT, BG_LIGHT = 0.10, 180   # background: colour saturation below this, brightness above this
BODY_SHARE = 0.45              # the standing body's width as a share of the canvas (as the SVG pet)
GROUND = 0.96                  # standing point: 96% down the canvas
FRINGE_PX = 2                  # light, colourless pixels this close to the background are dropped

assert set(POSE_ORDER) == set(POSES)


def cut_out(path: Path) -> np.ndarray:
    """The sheet as RGBA with the background transparent."""
    img = Image.open(path)
    rgba = np.array(img.convert("RGBA")).astype(np.float32)
    if (rgba[..., 3] < 255).any():
        return rgba  # already transparent
    rgb = rgba[..., :3]
    hi, lo = rgb.max(-1), rgb.min(-1)
    pale = ((hi - lo) / np.maximum(hi, 1) < BG_SAT) & (hi > BG_LIGHT)
    labels, _ = ndimage.label(pale)
    edge = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    bg = np.isin(labels, list(edge))
    # the checkerboard's light halo around outlines
    near_bg = ndimage.binary_dilation(bg, iterations=FRINGE_PX)
    bg |= near_bg & pale
    rgba[..., 3] = np.where(bg, 0, 255)
    rgba[bg, :3] = 0
    return rgba


def pieces(rgba: np.ndarray) -> list[tuple[slice, slice, int]]:
    """Each separate drawing: (rows, cols, label), largest first."""
    solid = rgba[..., 3] > 0
    labels, n = ndimage.label(ndimage.binary_opening(solid))
    sizes = ndimage.sum(solid, labels, range(1, n + 1))
    out = [(sl[0], sl[1], i + 1, sizes[i]) for i, sl in enumerate(ndimage.find_objects(labels)) if sl and sizes[i] > 50]
    out.sort(key=lambda p: -p[3])
    return [(a, b, c) for a, b, c, _ in out], labels


def read_face(rgba: np.ndarray, rows: slice, cols: slice, mask: np.ndarray) -> dict | None:
    """A face's nose and blush (pink spots), and where the eyes go from them, in sheet pixels:
        {"eyes": [(x, y), (x, y)], "r": eye radius,
         "nose": (x, y, w, h), "blush": [(x, y, w, h), (x, y, w, h)],
         "spots": the nose's and blush's pixels, in the body's box}
    or None if the face can't be read."""
    rgb = rgba[rows, cols, :3]
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    pink = (r > 220) & (g < 200) & (b < 200) & (r - g > 40) & mask
    lab, n = ndimage.label(pink)
    blobs = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        area = int((lab[sl] == i).sum())
        if area < 40:
            continue
        cy, cx = ndimage.center_of_mass(lab == i)
        blobs.append((area, cx + cols.start, cy + rows.start, sl[1].stop - sl[1].start, sl[0].stop - sl[0].start, i))
    # The face's blush is the two largest round spots at one height, the nose the small spot
    # between them; the insides of the ears are pink too but sit higher up
    # (spots in the top third of a standing body are the insides of the ears)
    height = rows.stop - rows.start
    low = [bl for bl in blobs if bl[2] > rows.start + height / 3]
    low.sort(key=lambda b: -b[0])
    best = None
    for i in range(len(low)):
        for j in range(i + 1, len(low)):
            a, c = sorted([low[i], low[j]], key=lambda b: b[1])
            span = c[1] - a[1]
            if abs(a[2] - c[2]) > 0.25 * span or span < 60:
                continue
            noses = [nb for nb in low if a[1] < nb[1] < c[1] and nb[0] < 0.6 * min(a[0], c[0])]
            if not noses:
                continue
            nose = min(noses, key=lambda nb: abs(nb[2] - (a[2] + c[2]) / 2))
            left, right = nose[1] - a[1], c[1] - nose[1]
            if not 0.6 < left / right < 1.6:  # blush on both sides of the nose, about evenly
                continue
            score = abs(left - right) / span
            if best is None or score < best[0]:
                best = (score, a, c, nose)
    if best is None:
        return None
    _, a, c, nose = best
    # eyes: inside each blush towards the nose, above the blush
    span = c[1] - a[1]
    y = min(a[2], c[2]) - EYE_UP * span
    return {
        "eyes": [(a[1] + EYE_IN * (nose[1] - a[1]), y), (c[1] + EYE_IN * (nose[1] - c[1]), y)],
        "r": EYE_SIZE * span,
        "nose": nose[1:5],
        "blush": [a[1:5], c[1:5]],
        "spots": np.isin(lab, [a[5], c[5], nose[5]]),
    }


def erase_spots(rgba: np.ndarray, rows: slice, cols: slice, spots: np.ndarray, body: np.ndarray) -> None:
    """Paint the drawn nose and blush over with the fur around them (the page draws its own).
    The mouth's dark lines are kept."""
    box = rgba[rows, cols]
    rgb = box[..., :3]
    light = rgb.mean(-1) > 140
    pinkish = (rgb[..., 0] - rgb[..., 1] > 12)  # the spots' darker pink edges
    near = (ndimage.binary_dilation(spots, iterations=3)
            | (ndimage.binary_dilation(spots, iterations=11) & pinkish)) & body
    ring = ndimage.binary_dilation(spots, iterations=9) & ~ndimage.binary_dilation(spots, iterations=4) & body
    fur = ring & (rgb.mean(-1) > 200)
    if not fur.any():
        return
    colour = np.median(rgb[fur], axis=0)
    reddish = rgb[..., 0] - rgb[..., 1] > 40  # the nose's dark red outline (the mouth's lines are brown)
    rgb[near & (light | reddish)] = colour


def erase_mouth(rgba: np.ndarray, rows: slice, cols: slice, face: dict, body: np.ndarray) -> None:
    """Paint the drawn mouth (its dark lines and the teeth between them) over with fur; the
    page draws its own mouth where the nose was."""
    nx, ny = face["nose"][0] - cols.start, face["nose"][1] - rows.start
    span = face["blush"][1][0] - face["blush"][0][0]
    box = rgba[rows, cols]
    rgb = box[..., :3]
    h, w = rgb.shape[:2]
    y0, y1 = int(max(ny - 0.02 * span, 0)), int(min(ny + 0.4 * span, h))
    x0, x1 = int(max(nx - 0.35 * span, 0)), int(min(nx + 0.35 * span, w))
    dark = np.zeros((h, w), bool)
    dark[y0:y1, x0:x1] = rgb[y0:y1, x0:x1].mean(-1) < 150
    dark &= body
    lab, n = ndimage.label(dark)
    keep = [i for i, sl in enumerate(ndimage.find_objects(lab), 1) if sl and (lab[sl] == i).sum() > 15]
    if not keep:
        return
    ys, xs = np.nonzero(np.isin(lab, keep))
    area = np.zeros((h, w), bool)
    area[max(ys.min() - 4, 0):ys.max() + 5, max(xs.min() - 4, 0):xs.max() + 5] = True
    area &= body
    ring = ndimage.binary_dilation(area, iterations=8) & ~ndimage.binary_dilation(area, iterations=2) & body
    fur = ring & (rgb.mean(-1) > 200)
    if fur.any():
        rgb[area] = np.median(rgb[fur], axis=0)


def build(sheet: Path, out: Path, preview: Path | None, eye_override: dict) -> list[str]:
    problems: list[str] = []
    rgba = cut_out(sheet)
    found, labels = pieces(rgba)
    if len(found) < len(POSE_ORDER):
        return [f"found {len(found)} drawings, need {len(POSE_ORDER)} bodies"]
    bodies = found[:len(POSE_ORDER)]
    # reading order: top row then bottom row, each left to right
    top = min(b[0].start for b in bodies)
    mid = (top + max(b[0].stop for b in bodies)) / 2
    bodies.sort(key=lambda b: ((b[0].start + b[0].stop) / 2 > mid, b[1].start))

    # One canvas for every pose, sized from the standing body
    stand = bodies[POSE_ORDER.index("stand")]
    cw = int(round((stand[1].stop - stand[1].start) / BODY_SHARE))
    ch = int(round(cw * 5 / 6))
    tallest = max(b[0].stop - b[0].start for b in bodies)
    if tallest > ch * GROUND:
        ch = int(np.ceil(tallest / GROUND))
        cw = int(round(ch * 6 / 5))
    widest = max(b[1].stop - b[1].start for b in bodies)
    if widest > cw:
        problems.append(f"the widest pose ({widest} px) is wider than the canvas ({cw} px) and is cut")

    def blank():
        return np.zeros((ch, cw, 4), dtype=np.float32)

    def paste(canvas, rows, cols, label, ox, oy):
        part = rgba[rows, cols].copy()
        part[labels[rows, cols] != label] = 0
        y0, x0 = rows.start + oy, cols.start + ox
        ys, xs = max(0, -y0), max(0, -x0)
        ye, xe = min(part.shape[0], ch - y0), min(part.shape[1], cw - x0)
        region = canvas[y0 + ys:y0 + ye, x0 + xs:x0 + xe]
        src = part[ys:ye, xs:xe]
        a = src[..., 3:4] / 255
        region[..., :3] = src[..., :3] * a + region[..., :3] * (1 - a)
        region[..., 3:4] = np.maximum(region[..., 3:4], src[..., 3:4])

    outputs: dict[str, np.ndarray] = {}
    faces: dict[str, dict] = {}
    previews = []
    for pose, (rows, cols, label) in zip(POSE_ORDER, bodies):
        # bottom centre of the body -> the standing point
        ox = int(round(cw / 2 - (cols.start + cols.stop) / 2))
        oy = int(round(ch * GROUND - rows.stop))
        body_mask = labels[rows, cols] == label
        face = read_face(rgba, rows, cols, body_mask)
        if face:
            erase_spots(rgba, rows, cols, face["spots"], body_mask)
            erase_mouth(rgba, rows, cols, face, body_mask)
        body = blank()
        paste(body, rows, cols, label, ox, oy)
        outputs[f"{pose}/body.png"] = body

        at, r = (face["eyes"], face["r"]) if face else (None, None)
        if pose in eye_override:  # given by hand: positions, and the size kept from the face if found
            at = eye_override[pose]
            r = r or EYE_SIZE * 2.5 * abs(at[1][0] - at[0][0])
        if at is None:
            problems.append(f"{pose}: couldn't find the nose and blush to place the eyes; give them with --eyes")
            continue
        eyes = [[round(x + ox, 1), round(y + oy, 1)] for x, y in at]  # sheet px -> canvas px
        r = round(r, 1)
        faces[pose] = {"eyes": eyes, "r": r}
        if face:  # what the page draws in place of the erased blush, nose and mouth
            to_canvas = lambda b: [round(b[0] + ox, 1), round(b[1] + oy, 1), b[2], b[3]]
            faces[pose]["blush"] = [to_canvas(b) for b in face["blush"]]  # [x, y, w, h] each
            span = face["blush"][1][0] - face["blush"][0][0]
            nx, ny, _, nh = face["nose"]  # the mouth goes where the nose was: [x, y, w]
            faces[pose]["mouth"] = [round(nx + ox, 1), round(ny + oy + 0.6 * nh, 1), round(MOUTH_WIDTH * span, 1)]
        previews.append((body, eyes, r))
        print(f"{pose}: eyes at {[(round(x), round(y)) for x, y in at]} (sheet px)")

    # Replace what was there (frames and eye images of earlier sheets too); settings.json stays
    ours = re.compile(r"^[a-z_]+-\d+\.png$|^eyes-[a-z]+\.png$|^body\.png$")
    for pose in POSES:
        if (out / pose).is_dir():
            for f in (out / pose).iterdir():
                if ours.match(f.name):
                    f.unlink()
    for rel, c in outputs.items():
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.round(c).astype(np.uint8), "RGBA").save(dest, optimize=True)
    (out / "faces.json").write_text(json.dumps({"canvas": [cw, ch], "poses": faces}, indent=1))
    print(f"{sheet}: {len(bodies)} poses, canvas {cw} x {ch} px -> {len(outputs)} images + faces.json in {out}")
    if preview:
        _preview(previews, cw, ch, preview)
        print(f"preview: {preview}")
    return problems


def _preview(previews, cw, ch, path):
    """Every pose side by side, with a red ring where each eye goes."""
    from PIL import ImageDraw
    sheet = Image.new("RGBA", (cw * len(previews), ch), (58, 55, 47, 255))
    for i, (body, eyes, r) in enumerate(previews):
        sheet.alpha_composite(Image.fromarray(np.round(body).astype(np.uint8), "RGBA"), (i * cw, 0))
        d = ImageDraw.Draw(sheet)
        for x, y in eyes:
            d.ellipse([i * cw + x - r, y - r, i * cw + x + r, y + r], outline=(230, 40, 40, 255), width=3)
    sheet.convert("RGB").save(path)


def main() -> None:
    p = argparse.ArgumentParser(description="Cut the pose sheet into the pet's still images")
    p.add_argument("sheet", type=Path, nargs="?", default=Path("design.png"))
    p.add_argument("--out", type=Path, default=SPRITES_DIR)
    p.add_argument("--preview", type=Path, help="save every pose with a ring where each eye goes")
    p.add_argument("--eyes", type=json.loads, default={},
                   help='eye positions in sheet px for poses that come out wrong, e.g. '
                        '\'{"lie": [[790, 870], [900, 870]]}\'')
    args = p.parse_args()
    problems = build(args.sheet, args.out, args.preview, args.eyes)
    for line in problems:
        print("  !", line)
    sys.exit(1 if any(line.startswith("found ") for line in problems) else 0)


if __name__ == "__main__":
    main()
