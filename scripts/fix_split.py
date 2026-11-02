import os
import shutil
from pathlib import Path
import re
from collections import defaultdict

# --- SETUP ---
# Change these paths to match your folders
SOURCE_ROOT = Path(r"C:\Users\ahumu\Downloads\Compressed")
TARGET_ROOT = Path(r"C:\Users\ahumu\Downloads\Croppie_Clean")

def extract_timestamp(filename):
    # Looks for the numbers at the start of the string (e.g., 1687438155343c2 -> 1687438155343)
    match = re.search(r'^(\d+)', filename)
    if match:
        return int(match.group(1))
    return 0 # Fallback for weird filenames

def main():
    print("Gathering all images and labels...")
    
    # 1. Gather all unique timestamps and their associated files
    timestamps_to_files = defaultdict(lambda: {"images": [], "labels": []})
    
    for split in ["train", "val"]:
        img_dir = SOURCE_ROOT / split / "images"
        lbl_dir = SOURCE_ROOT / split / "labels"
        
        if not img_dir.exists():
            continue
            
        for img_path in img_dir.glob("*.jpg"):
            timestamp = extract_timestamp(img_path.stem)
            timestamps_to_files[timestamp]["images"].append(img_path)
            
            # Find matching label
            lbl_path = lbl_dir / f"{img_path.stem}.txt"
            if lbl_path.exists():
                timestamps_to_files[timestamp]["labels"].append(lbl_path)

    # 2. Sort the timestamps chronologically
    sorted_timestamps = sorted(timestamps_to_files.keys())
    total_timestamps = len(sorted_timestamps)
    
    # 3. Calculate the 80/20 split point
    split_index = int(total_timestamps * 0.80)
    
    train_timestamps = sorted_timestamps[:split_index]
    val_timestamps = sorted_timestamps[split_index:]
    
    print(f"Found {total_timestamps} unique timestamps.")
    print(f"Assigning {len(train_timestamps)} to Train (First 80% of flight).")
    print(f"Assigning {len(val_timestamps)} to Val (Last 20% of flight).")

    # 4. Create the new folder structure and move files
    for split_name, ts_list in [("train", train_timestamps), ("val", val_timestamps)]:
        new_img_dir = TARGET_ROOT / "images" / split_name
        new_lbl_dir = TARGET_ROOT / "labels" / split_name
        new_img_dir.mkdir(parents=True, exist_ok=True)
        new_lbl_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Copying {split_name} files...")
        for ts in ts_list:
            for img in timestamps_to_files[ts]["images"]:
                shutil.copy(img, new_img_dir / img.name)
            for lbl in timestamps_to_files[ts]["labels"]:
                shutil.copy(lbl, new_lbl_dir / lbl.name)

    print(f"\nDone! Clean dataset created at: {TARGET_ROOT}")

if __name__ == "__main__":
    main()