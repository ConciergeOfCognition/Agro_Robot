#!/usr/bin/env python3
"""
Convert a YOLO-format dataset to the common class ids (issues #18 and #30).
The source folder is never modified. Output goes to a NEW folder.

Usage (WSL):
  python3 scripts/harmonise.py SRC OUT --map "0:3,1:4,2:1" \
      --names dark_brown,green,low_visibility,red,yellow

Writes OUT/images, OUT/labels, OUT/dataset.yaml, OUT/conversion_log.txt
and OUT/check_samples/ (random images with boxes drawn, for checking by eye).
Needs Pillow: pip install pillow
Do NOT commit OUT to git (image licences). Commit only conversion_log.txt.
"""
import argparse
import random
import shutil
import sys
from collections import Counter
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageOps
except ImportError:
    sys.exit("Pillow is missing. Run: pip install pillow")

IMG_EXT = {".jpg", ".jpeg", ".png"}
SKIP = {"classes.txt", "readme.txt", "requirements.txt", "notes.json"}
COLORS = [(139, 69, 19), (0, 200, 0), (128, 128, 128), (255, 0, 0), (255, 215, 0)]


def parse_map(s):
    m = {}
    for pair in s.split(","):
        a, b = pair.split(":")
        m[int(a)] = int(b)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--map", required=True, help='source:target ids, e.g. "0:3,1:4,2:1"')
    ap.add_argument("--names", required=True, help="target class names in id order")
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    src, out = Path(a.src).resolve(), Path(a.out).resolve()
    if out == src or src in out.parents or out in src.parents:
        sys.exit("OUT must be a separate folder, not inside or around SRC.")
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} already exists and is not empty. Pick a new folder.")

    imgs, lbls = {}, {}
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in IMG_EXT:
            imgs.setdefault(p.stem, []).append(p)
        elif p.suffix == ".txt" and p.name.lower() not in SKIP:
            lbls.setdefault(p.stem, []).append(p)
    dup = [s for d in (imgs, lbls) for s, v in d.items() if len(v) > 1]
    if dup:
        sys.exit(f"{len(dup)} duplicate file names, e.g. {dup[:3]}. Paste this message to Claude.")

    names = a.names.split(",")
    cmap = parse_map(a.map)
    (out / "images").mkdir(parents=True)
    (out / "labels").mkdir()

    before, after = Counter(), Counter()
    dropped = malformed = no_label = 0
    converted = []
    for stem, (ip,) in sorted(imgs.items()):
        if stem not in lbls:
            no_label += 1
            continue
        kept = []
        for line in lbls[stem][0].read_text().splitlines():
            parts = line.split()
            if not parts:
                continue
            try:
                c = int(parts[0])
                vals = [float(x) for x in parts[1:]]
            except ValueError:
                malformed += 1
                continue
            if len(parts) != 5 or not all(0 <= v <= 1 for v in vals):
                malformed += 1
                continue
            before[c] += 1
            if c not in cmap:
                dropped += 1
                continue
            after[cmap[c]] += 1
            kept.append(" ".join([str(cmap[c])] + parts[1:]))
        shutil.copy2(ip, out / "images" / ip.name)
        (out / "labels" / f"{stem}.txt").write_text("\n".join(kept) + ("\n" if kept else ""))
        converted.append((ip, kept))
    no_image = len(set(lbls) - set(imgs))

    rng = random.Random(a.seed)
    (out / "check_samples").mkdir()
    for ip, kept in rng.sample(converted, min(a.samples, len(converted))):
        im = ImageOps.exif_transpose(Image.open(ip)).convert("RGB")
        im.thumbnail((1000, 1000))
        w, h = im.size
        d = ImageDraw.Draw(im)
        for l in kept:
            c, x, y, bw, bh = l.split()
            c = int(c)
            x, y, bw, bh = float(x), float(y), float(bw), float(bh)
            box = [(x - bw / 2) * w, (y - bh / 2) * h, (x + bw / 2) * w, (y + bh / 2) * h]
            col = COLORS[c % len(COLORS)]
            d.rectangle(box, outline=col, width=3)
            d.text((box[0] + 3, box[1] + 3), names[c] if c < len(names) else str(c), fill=col)
        im.save(out / "check_samples" / f"{ip.stem}.jpg", quality=85)

    yaml = ["train: images", "val: images", "test: images", "names:"]
    yaml += [f"  {i}: {n}" for i, n in enumerate(names)]
    (out / "dataset.yaml").write_text("\n".join(yaml) + "\n")

    rep = [
        f"source: {src}",
        f"map (source:target): {a.map}",
        f"images converted: {len(converted)}",
        f"images without a label file (skipped): {no_label}",
        f"label files without an image: {no_image}",
        f"malformed label lines (skipped): {malformed}",
        f"boxes before, by source class: {dict(sorted(before.items()))}",
        f"boxes dropped (class not in map): {dropped}",
        "boxes after, by target class:",
    ]
    rep += [f"  {i} {n}: {after.get(i, 0)}" for i, n in enumerate(names)]
    ok = sum(after.values()) + dropped == sum(before.values())
    rep.append(f"check: after + dropped == before -> {ok}")
    text = "\n".join(rep)
    print(text)
    (out / "conversion_log.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
