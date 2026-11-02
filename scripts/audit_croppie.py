#!/usr/bin/env python3
"""
Audit a YOLO-format dataset split (built for rgautroncgiar/croppie_coffee_ug).

Usage (Windows):   py audit_croppie.py
                   py audit_croppie.py "C:\\path\\to\\train" --out audit_val
Usage (WSL2):      python3 audit_croppie.py
                   (C:\\ paths are converted to /mnt/c/... automatically)

Optional, once you have seen the filenames:
    --group-regex "^(.*?)_tile\\d+$"   # capture group 1 = source photo id

Needs only Pillow:  pip install pillow   (WSL: sudo apt install python3-pil)
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
    sys.exit("Pillow is missing. Windows: pip install pillow | WSL: sudo apt install python3-pil")

DEFAULT_ROOT = r"C:\Users\ahumu\Downloads\Compressed\val"
CLASSES = {0: "dark_brown_cherry", 1: "green_cherry", 2: "low_visibility_unsure",
           3: "red_cherry", 4: "yellow_cherry"}
COLORS = {0: (139, 69, 19), 1: (0, 200, 0), 2: (255, 0, 255), 3: (255, 0, 0), 4: (255, 215, 0)}
IMG_EXT = {".jpg", ".jpeg", ".png"}
NOT_LABELS = {"classes.txt", "readme.txt", "requirements.txt"}
EDGE_TOL = 0.003  # normalised distance from image border that counts as "touching the edge"

REPORT = []


def say(text=""):
    print(text)
    REPORT.append(text)


def resolve(p):
    """Turn C:\\... into /mnt/c/... when running under Linux/WSL."""
    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", p):
        return Path("/mnt/" + p[0].lower() + p[2:].replace("\\", "/"))
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
    ap.add_argument("root", nargs="?", default=DEFAULT_ROOT)
    ap.add_argument("--out", default="audit_val", help="output folder for report, CSVs, samples")
    ap.add_argument("--group-regex", default=None,
                    help="regex; capture group 1 = source-photo id (for tile/leakage analysis)")
    ap.add_argument("--samples", type=int, default=24, help="annotated sample images to save")
    ap.add_argument("--no-hash", action="store_true", help="skip exact-duplicate hashing")
    args = ap.parse_args()

    root = resolve(args.root)
    if not root.exists():
        sys.exit(f"Path not found: {root}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    group_re = re.compile(args.group_regex) if args.group_regex else None

    # ---------- 1. inventory ----------
    all_files = [p for p in root.rglob("*") if p.is_file()]
    ext_count = Counter(p.suffix.lower() or "(none)" for p in all_files)
    say(f"ROOT: {root}")
    say(f"Total files: {len(all_files)}")
    say("By extension: " + ", ".join(f"{k}={v}" for k, v in ext_count.most_common()))
    folders = Counter(str(p.parent.relative_to(root)) for p in all_files)
    say("Files per folder (top 10): " + "; ".join(f"{k or '.'}={v}" for k, v in folders.most_common(10)))

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
    say(f"Stems used by >1 image file: {sum(1 for v in images.values() if len(v) > 1)}")
    say(f"Stems used by >1 label file: {sum(1 for v in labels.values() if len(v) > 1)}")
    sample_stems = sorted(img_stems)[:8]
    say("First stems (look at these to design --group-regex): " + ", ".join(sample_stems))
    say(f"Distinct first '_' tokens in stems: {len({s.split('_')[0] for s in img_stems})}")

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
        if i % 1000 == 0:
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

        group = stem
        if group_re:
            m = group_re.search(stem)
            if m:
                group = m.group(1)
        img_rows.append([stem, str(ipath.relative_to(root)), iw, ih, len(boxes), group])

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
    for c in corrupt[:5]:
        say("  " + c)
    say("Image sizes (w x h): " + ", ".join(f"{w}x{h}={n}" for (w, h), n in sizes.most_common(8)))
    say(f"Images with empty/no boxes (label exists but empty, or no label): "
        f"{empty_label_images + len(img_stems - lbl_stems)}")

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
        say(f"Boxes per image: min={bpi[0]} p25={pctl(bpi, .25)} median={pctl(bpi, .5)} "
            f"p75={pctl(bpi, .75)} p95={pctl(bpi, .95)} max={bpi[-1]}")
    say(f"{'class':<24}{'boxes':>8}{'%':>7}{'images':>8}{'edge%':>7}")
    for cls in sorted(per_class):
        c = per_class[cls]
        say(f"{CLASSES.get(cls, 'id ' + str(cls)):<24}{c['n']:>8}{100 * c['n'] / total_boxes:>7.1f}"
            f"{len(c['imgs']):>8}{100 * c['edge'] / c['n']:>7.1f}")

    say("\n=== BOX SIZE IN PIXELS (as stored in these files) ===")
    say("Compare these to what your robot camera gives you at working distance.")
    say(f"{'class':<24}{'medW':>7}{'medH':>7}{'minside p5':>12}{'p50':>7}{'p95':>7}{'<16px':>8}{'<32px':>8}")
    for cls in sorted(per_class):
        c = per_class[cls]
        m = sorted(c["min"])
        say(f"{CLASSES.get(cls, 'id ' + str(cls)):<24}{pctl(sorted(c['w']), .5):>7.0f}"
            f"{pctl(sorted(c['h']), .5):>7.0f}{pctl(m, .05):>12.0f}{pctl(m, .5):>7.0f}{pctl(m, .95):>7.0f}"
            f"{sum(v < 16 for v in m):>8}{sum(v < 32 for v in m):>8}")

    # ---------- 5. source-photo grouping (tile/leakage) ----------
    say("\n=== SOURCE-PHOTO GROUPS ===")
    groups = Counter(r[5] for r in img_rows)
    if group_re is None:
        say("No --group-regex given, so every image is its own group. Read the stems above,")
        say("write a regex that captures the source photo id, and re-run to measure tiling.")
    else:
        unmatched = sum(1 for r in img_rows if r[5] == r[0])
        say(f"Groups: {len(groups)} | images where regex did not match: {unmatched}")
        sz = Counter(groups.values())
        say("Images per group (size: count of groups): " +
            ", ".join(f"{k}:{v}" for k, v in sorted(sz.items())[:12]))
        say("Largest groups: " + ", ".join(f"{g}={n}" for g, n in groups.most_common(5)))

    # ---------- 6. exact duplicates ----------
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
        for v in dup_sets[:5]:
            say("  " + ", ".join(v[:4]))

    # ---------- 7. outputs ----------
    with open(out / "images.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stem", "path", "width", "height", "n_boxes", "group"])
        w.writerows(img_rows)
    with open(out / "boxes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stem", "class_id", "class", "cx", "cy", "w", "h", "w_px", "h_px", "touches_edge"])
        w.writerows(box_rows)

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
    print(f"\nSaved report, images.csv, boxes.csv and {len(picks)} annotated samples to: {out.resolve()}")


if __name__ == "__main__":
    main()
