#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

def main():
    # all actual image files from the folder
    images_dir = "../data/town04_leader_50_multimodal_dataset_20260618_102918/processed_camera/images"
    all_images = set([f.name for f in Path(images_dir).glob("*.png")])
    
    # the frames where YOLO successfully found a vehicle
    csv_path = "../data/town04_leader_50_multimodal_dataset_20260618_102918/processed_camera/detections_0.3_excl40.csv"
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