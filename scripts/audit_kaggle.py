#!/usr/bin/env python3
"""
Audit a YOLO-format dataset split (built for Kaggle Coffee Cherry dataset).

Usage (WSL):
    python3 audit_kaggle.py "/mnt/c/Users/ahumu/Desktop/Coffee_kaggle" --out audit_kaggle_out

Needs only Pillow: pip install pillow
"""
import argparse
import csv
import hashlib
import os
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("Pillow is missing. Please run: pip install pillow")

# --- UPDATE: Kaggle dataset classes ---
CLASSES = {0: "Matang (Ripe)", 1: "Setengah Matang (Half)", 2: "Tidak Matang (Unripe)"}
COLORS = {0: (255, 0, 0), 1: (255, 215, 0), 2: (0, 200, 0)} # Red, Yellow, Green
IMG_EXT = {".jpg", ".jpeg", ".png"}
NOT_LABELS = {"classes.txt", "readme.txt", "requirements.txt", "notes.json"}
EDGE_TOL = 0.003

REPORT = []

def say(text=""):
    print(text)
    REPORT.append(text)

def resolve(p):
    """Turn C:\\... into /mnt/c/... when running under Linux/WSL."""
    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", str(p)):
        return Path("/mnt/" + str(p)[0].lower() + str(p)[2:].replace("\\", "/"))
    return Path(p)

def pctl(sorted_vals, q):
    if not sorted_vals:
        return float("nan")
    return sorted_vals[min(len(sorted_vals) - 1, int(q * (len(sorted_vals) - 1) + 0.5))]

def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def parse_label(path):
    """Return (boxes, problems). boxes = list of (cls, cx, cy, w, h)."""
    boxes, problems = [], Counter()
    seen = set()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            if len(parts) != 5:
                problems["not_5_columns"] += 1
                continue
            try:
                cls = int(float(parts[0]))
                cx, cy, w, h = (float(x) for x in parts[1:])
            except ValueError:
                problems["non_numeric"] += 1
                continue
            if cls not in CLASSES:
                problems["unknown_class_id"] += 1
            if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < w <= 1 and 0 < h <= 1):
                problems["coords_out_of_range_or_zero_size"] += 1
                continue
            key = (cls, round(cx, 5), round(cy, 5), round(w, 5), round(h, 5))
            if key in seen:
                problems["duplicate_box_in_file"] += 1
            seen.add(key)
            boxes.append((cls, cx, cy, w, h))
    return boxes, problems

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Path to the Kaggle dataset folder (containing images/ and labels/)")
    ap.add_argument("--out", default="audit_kaggle_out", help="output folder for report, CSVs, samples")
    ap.add_argument("--samples", type=int, default=24, help="annotated sample images to save")
    ap.add_argument("--no-hash", action="store_true", help="skip exact-duplicate hashing")
    args = ap.parse_args()

    root = resolve(args.root)
    if not root.exists():
        sys.exit(f"Path not found: {root}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # ---------- 1. inventory ----------
    all_files = [p for p in root.rglob("*") if p.is_file()]
    ext_count = Counter(p.suffix.lower() or "(none)" for p in all_files)
    say(f"ROOT: {root}")
    say(f"Total files: {len(all_files)}")
    say("By extension: " + ", ".join(f"{k}={v}" for k, v in ext_count.most_common()))
    
    images, labels = defaultdict(list), defaultdict(list)
    for p in all_files:
        ext = p.suffix.lower()
        if ext in IMG_EXT:
            images[p.stem].append(p)
        elif ext == ".txt" and p.name.lower() not in NOT_LABELS:
            labels[p.stem].append(p)

    img_stems, lbl_stems = set(images), set(labels)
    say("\n=== PAIRING ===")
    say(f"Images (unique stems): {len(img_stems)}")
    say(f"Label files (unique stems): {len(lbl_stems)}")
    say(f"Images without label: {len(img_stems - lbl_stems)}")
    say(f"Labels without image: {len(lbl_stems - img_stems)}")

    # ---------- 2. per-image / per-box pass ----------
    sizes = Counter()
    corrupt = []
    problems_total = Counter()
    img_rows, box_rows = [], []
    per_class = defaultdict(lambda: {"n": 0, "imgs": set(), "w": [], "h": [], "min": [], "edge": 0})
    boxes_per_image = []
    empty_label_images = 0
    labelled_for_samples = []

    for i, stem in enumerate(sorted(img_stems), 1):
        if i % 500 == 0:
            print(f"  processed {i}/{len(img_stems)} images...", file=sys.stderr)
        ipath = images[stem][0]
        try:
            with Image.open(ipath) as im:
                iw, ih = im.size
        except Exception:
            corrupt.append(str(ipath))
            continue
        sizes[(iw, ih)] += 1

        boxes = []
        if stem in labels:
            boxes, probs = parse_label(labels[stem][0])
            problems_total.update(probs)
            if not boxes:
                empty_label_images += 1
            else:
                labelled_for_samples.append((ipath, boxes))
        boxes_per_image.append(len(boxes))

        img_rows.append([stem, str(ipath.relative_to(root)), iw, ih, len(boxes), "single"])

        for cls, cx, cy, w, h in boxes:
            wpx, hpx = w * iw, h * ih
            edge = (cx - w / 2 <= EDGE_TOL or cx + w / 2 >= 1 - EDGE_TOL or
                    cy - h / 2 <= EDGE_TOL or cy + h / 2 >= 1 - EDGE_TOL)
            c = per_class[cls]
            c["n"] += 1
            c["imgs"].add(stem)
            c["w"].append(wpx)
            c["h"].append(hpx)
            c["min"].append(min(wpx, hpx))
            c["edge"] += edge
            box_rows.append([stem, cls, CLASSES.get(cls, "?"), round(cx, 5), round(cy, 5),
                             round(w, 5), round(h, 5), round(wpx, 1), round(hpx, 1), int(edge)])

    say("\n=== IMAGES ===")
    say(f"Corrupt/unreadable images: {len(corrupt)}")
    say("Image sizes (w x h): " + ", ".join(f"{w}x{h}={n}" for (w, h), n in sizes.most_common(5)))
    say(f"Images with empty/no boxes: {empty_label_images + len(img_stems - lbl_stems)}")

    # ---------- 3. label quality ----------
    say("\n=== LABEL PROBLEMS ===")
    if problems_total:
        for k, v in problems_total.items():
            say(f"  {k}: {v}")
    else:
        say("  none found")

    # ---------- 4. class balance and pixel sizes ----------
    total_boxes = sum(c["n"] for c in per_class.values())
    say("\n=== BOXES PER CLASS ===")
    say(f"Total boxes: {total_boxes}")
    bpi = sorted(boxes_per_image)
    if bpi:
        say(f"Boxes per image: min={bpi[0]} median={pctl(bpi, .5)} max={bpi[-1]}")
    say(f"{'class':<24}{'boxes':>8}{'%':>7}{'images':>8}{'edge%':>7}")
    for cls in sorted(per_class):
        c = per_class[cls]
        say(f"{CLASSES.get(cls, 'id ' + str(cls)):<24}{c['n']:>8}{100 * c['n'] / total_boxes:>7.1f}"
            f"{len(c['imgs']):>8}{100 * c['edge'] / c['n']:>7.1f}")

    say("\n=== BOX SIZE IN PIXELS ===")
    say(f"{'class':<24}{'medW':>7}{'medH':>7}{'minside p5':>12}{'p50':>7}{'p95':>7}{'<16px':>8}{'<32px':>8}")
    for cls in sorted(per_class):
        c = per_class[cls]
        m = sorted(c["min"])
        say(f"{CLASSES.get(cls, 'id ' + str(cls)):<24}{pctl(sorted(c['w']), .5):>7.0f}"
            f"{pctl(sorted(c['h']), .5):>7.0f}{pctl(m, .05):>12.0f}{pctl(m, .5):>7.0f}{pctl(m, .95):>7.0f}"
            f"{sum(v < 16 for v in m):>8}{sum(v < 32 for v in m):>8}")

    # ---------- 5. exact duplicates ----------
    if not args.no_hash:
        say("\n=== EXACT DUPLICATE IMAGES (md5) ===")
        by_hash = defaultdict(list)
        for stem in sorted(img_stems):
            try:
                by_hash[md5(images[stem][0])].append(stem)
            except OSError:
                pass
        dup_sets = [v for v in by_hash.values() if len(v) > 1]
        say(f"Duplicate sets: {len(dup_sets)} | redundant files: {sum(len(v) - 1 for v in dup_sets)}")

    # ---------- 6. outputs ----------
    random.seed(0)
    sdir = out / "samples"
    sdir.mkdir(exist_ok=True)
    picks = random.sample(labelled_for_samples, min(args.samples, len(labelled_for_samples)))
    for ipath, boxes in picks:
        with Image.open(ipath).convert("RGB") as im:
            d = ImageDraw.Draw(im)
            W, H = im.size
            for cls, cx, cy, w, h in boxes:
                d.rectangle([(cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H],
                            outline=COLORS.get(cls, (255, 255, 255)), width=2)
            im.save(sdir / f"{ipath.stem}.jpg", quality=90)

    (out / "audit_report.txt").write_text("\n".join(REPORT), encoding="utf-8")
    print(f"\nSaved report and {len(picks)} annotated samples to: {out.resolve()}")

if __name__ == "__main__":
    main()