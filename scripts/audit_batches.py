#!/usr/bin/env python3
"""Audit a YOLO-format dataset that is split into batches.

Usage:
    python audit_batches.py /path/to/dataset_root
    python audit_batches.py /path/to/dataset_root --names Unripe,Ripening,Ripe,Spoilt,Coffee_tree

Treats every first-level folder under the root as one batch. It counts files,
removes duplicates (same label text, or same image bytes fingerprint), checks
that images and labels pair up, counts boxes per class and estimates box size in
pixels. It only reads files and writes audit_summary.csv in the current folder.
"""
import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

try:
    from PIL import Image
except ImportError:  # image sizes are skipped without Pillow
    Image = None

IMG_EXT = {".jpg", ".jpeg", ".png"}
SKIP_TXT = {"classes.txt", "labels.txt", "readme.txt", "obj.names"}


def parse_label_file(path):
    """Return a list of (class_id, x, y, w, h), or None if this is not a YOLO label file."""
    boxes = []
    for line in path.read_text(errors="ignore").splitlines():
        parts = line.split()
        if not parts:
            continue
        if len(parts) != 5:
            return None
        try:
            boxes.append((int(parts[0]),) + tuple(float(v) for v in parts[1:]))
        except ValueError:
            return None
    return boxes


def fingerprint(path):
    """Fast duplicate check for big images: size + first and last 64 KB."""
    size = path.stat().st_size
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read(65536))
        if size > 131072:
            f.seek(-65536, 2)
            h.update(f.read(65536))
    return (size, h.hexdigest())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--names", default="", help="comma-separated class names in id order")
    ap.add_argument("--skip", default="", help="ignore files whose name contains any of these words, e.g. augmented")
    args = ap.parse_args()
    root = Path(args.root)
    names = [n.strip() for n in args.names.split(",") if n.strip()]
    skip = [w.strip().lower() for w in args.skip.split(",") if w.strip()]
    if not names:
        for cand in ("classes.txt", "labels.txt"):
            f = next(root.rglob(cand), None)
            if f:
                names = [l.strip() for l in f.read_text(errors="ignore").splitlines() if l.strip()]
                break

    batches = sorted(p for p in root.iterdir() if p.is_dir()) or [root]
    rows, all_box_px = [], defaultdict(list)
    seen_labels_global = Counter()
    class_total = Counter()

    for b in batches:
        print(f"Scanning {b.name} ...", flush=True)
        img_files = [p for p in b.rglob("*") if p.suffix.lower() in IMG_EXT]
        txt_files = [p for p in b.rglob("*.txt") if p.name.lower() not in SKIP_TXT]
        if skip:
            n_before = len(img_files) + len(txt_files)
            img_files = [p for p in img_files if not any(w in p.name.lower() for w in skip)]
            txt_files = [p for p in txt_files if not any(w in p.name.lower() for w in skip)]
            print(f"  skipped {n_before - len(img_files) - len(txt_files)} files matching {skip}", flush=True)
        print(f"  found {len(img_files)} images and {len(txt_files)} text files, checking them ...", flush=True)

        def norm(p):
            return p.stem.lower().replace("copy of ", "").replace("copy_of_", "")

        # unique images: same fingerprint = same picture, keep the shortest name
        by_fp = {}
        for p in img_files:
            fp = fingerprint(p)
            if fp not in by_fp or len(norm(p)) < len(norm(by_fp[fp])):
                by_fp[fp] = p
        imgs = {norm(p): p for p in by_fp.values()}

        # unique labels: same text = same label file, keep the shortest name
        by_text, non_yolo = {}, 0
        for p in txt_files:
            boxes = parse_label_file(p)
            if boxes is None:
                non_yolo += 1
                continue
            h = hashlib.md5(p.read_bytes()).hexdigest() if boxes else "empty-" + norm(p)
            if h not in by_text or len(norm(p)) < len(by_text[h][0]):
                by_text[h] = (norm(p), boxes)
        base = {stem: boxes for stem, boxes in by_text.values()}

        matched = [s for s in base if s in imgs]
        boxes_n, cls_count = 0, Counter()
        size_count = Counter()
        for s in base:
            size = None  # read the image size once per image, not once per box
            if s in imgs and Image is not None:
                try:
                    with Image.open(imgs[s]) as im:
                        size = im.size
                except Exception:
                    size = None
            if size:
                size_count[size] += 1
            for c, x, y, w, h in base[s]:
                cls_count[c] += 1
                boxes_n += 1
                if size:
                    all_box_px[c].append((w * size[0], h * size[1]))
        class_total.update(cls_count)
        for s in base:
            seen_labels_global[s] += 1

        rows.append({
            "batch": b.name, "image_files": len(img_files), "unique_images": len(imgs),
            "label_files": len(txt_files), "unique_labels": len(base), "paired": len(matched),
            "images_without_label": len(set(imgs) - set(base)),
            "labels_without_image": len(set(base) - set(imgs)),
            "non_yolo_txt": non_yolo, "boxes": boxes_n,
            "image_sizes": "; ".join(f"{w}x{h} ({n})" for (w, h), n in size_count.most_common(3)),
            **{f"class_{c}": cls_count[c] for c in sorted(class_total)},
        })

    print("\nImage sizes per batch (width x height, number of images, top 3):")
    for r in rows:
        print(f"  {r['batch']:10} {r['image_sizes'] or 'unknown (is Pillow installed?)'}")

    cross = sum(1 for v in seen_labels_global.values() if v > 1)
    print(f"\nDataset root: {root}   batches: {len(batches)}")
    keys = ["batch", "image_files", "unique_images", "label_files", "unique_labels", "paired",
            "images_without_label", "labels_without_image", "boxes"]
    print("\n" + " | ".join(k[:14].ljust(8) for k in keys))
    for r in rows:
        print(" | ".join(str(r[k])[:14].ljust(8) for k in keys))
    tot = {k: sum(r[k] for r in rows) for k in keys[1:]}
    print(" | ".join(["TOTAL".ljust(8)] + [str(tot[k]).ljust(8) for k in keys[1:]]))
    print(f"\nLabel stems that appear in more than one batch: {cross}  (if >0, batches overlap)")

    print("\nBoxes per class (unique labels only):")
    total_boxes = sum(class_total.values()) or 1
    for c in sorted(class_total):
        nm = names[c] if c < len(names) else "?"
        px = all_box_px.get(c, [])
        size = f"median {median(w for w, _ in px):.0f}x{median(h for _, h in px):.0f} px" if px else "size unknown"
        print(f"  class {c} {nm:12} {class_total[c]:7}  ({100 * class_total[c] / total_boxes:4.1f}%)  {size}")

    all_keys = sorted({k for r in rows for k in r})
    with open("audit_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=all_keys)
        w.writeheader()
        w.writerows(rows)
    print("\nWrote audit_summary.csv")


if __name__ == "__main__":
    main()
