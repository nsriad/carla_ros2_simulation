#!/usr/bin/env python3
import argparse
import glob
import os
import pandas as pd

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--camera_dir", required=True, help="Path to .../processed_camera/")
    return p.parse_args()

def main():
    args = parse_args()

    detections_files = glob.glob(os.path.join(args.camera_dir, "detections_*.csv"))
    if not detections_files:
        print(f"ERROR: no detections_*.csv found in {args.camera_dir}. Run yolo_detection.py first.")
        return
    csv_path = max(detections_files, key=os.path.getmtime)
    print(f"Using detections file: {os.path.basename(csv_path)}")

    df = pd.read_csv(csv_path)
    
    # Count how many times each frame appears in the CSV
    frame_counts = df['frame'].value_counts()
    
    # Filter for frames that appear more than once
    multi_car_frames = frame_counts[frame_counts > 1]
    
    print("-" * 40)
    print(f"FRAMES WITH MULTIPLE VEHICLES: {len(multi_car_frames)}")
    print("-" * 40)
    
    if multi_car_frames.empty:
        print("No frames have multiple vehicles.")
    else:
        for frame, count in multi_car_frames.items():
            print(f"{frame}: {count} vehicles detected")

if __name__ == "__main__":
    main()
    