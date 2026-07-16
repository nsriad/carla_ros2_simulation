#!/usr/bin/env python3
import argparse
import glob
import os
import pandas as pd
from pathlib import Path

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--camera_dir", required=True, help="Path to .../processed_camera/")
    return p.parse_args()

def main():
    args = parse_args()

    images_dir = os.path.join(args.camera_dir, "images")
    all_images = set([f.name for f in Path(images_dir).glob("*.png")])

    detections_files = glob.glob(os.path.join(args.camera_dir, "detections_*.csv"))
    if not detections_files:
        print(f"ERROR: no detections_*.csv found in {args.camera_dir}. Run yolo_detection.py first.")
        return
    csv_path = max(detections_files, key=os.path.getmtime)
    print(f"Using detections file: {os.path.basename(csv_path)}")

    df = pd.read_csv(csv_path)
    yolo_frames = set(df['frame'].unique())
    
    # the exact frames that are missing
    missing_frames = sorted(list(all_images - yolo_frames))
    
    print("-" * 40)
    print("DATASET DIAGNOSTIC")
    print("-" * 40)
    print(f"Total images in folder: {len(all_images)}")
    print(f"Frames with detections: {len(yolo_frames)}")
    print(f"Total missing frames:   {len(missing_frames)}")
    
    if missing_frames:
        print("\nFirst 20 missing frames (to check for patterns):")
        for f in missing_frames[:20]:
            print(f" - {f}")

if __name__ == "__main__":
    main()