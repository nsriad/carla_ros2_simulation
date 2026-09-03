#!/usr/bin/env python3
import argparse
import glob
import os
import shutil
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
from ultralytics import YOLO
import torch

def parse_args():
    parser = argparse.ArgumentParser(description="Extract metric headway using YOLO26-depth.")
    parser.add_argument(
        "--camera_dir",
        type=str,
        required=True,
        help="Path to the processed_camera directory containing 'images' and 'detections_0.3_excl40.csv'"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Where to write results. Default: a sibling 'processed_camera_yolo26' directory"
    )
    parser.add_argument("--model", type=str, default="yolo26n-depth.pt")
    parser.add_argument("--imgsz", type=int, default=768, help="matches the released weights' training resolution")
    return parser.parse_args()

def main():
    args = parse_args()

    print("Loading detections...")

    base_dir = args.camera_dir
    images_dir = os.path.join(base_dir, "images")

    output_dir = args.output_dir or os.path.join(os.path.dirname(base_dir.rstrip('/')), "processed_camera_yolo26")
    os.makedirs(output_dir, exist_ok=True)

    detections_files = glob.glob(os.path.join(base_dir, "detections_*.csv"))
    if not detections_files:
        print(f"ERROR: no detections_*.csv found in {base_dir}. Run yolo_detection.py first")
        return
    detections_path = max(detections_files, key=os.path.getmtime)
    print(f"Using detections file: {os.path.basename(detections_path)}")

    suffix = os.path.basename(detections_path)[len("detections_"):-len(".csv")]

    df = pd.read_csv(detections_path)

    # bbox bottom lowest in frame as the closest one
    leader_idx = df.groupby('frame')['bbox_bottom_center_y'].idxmax()
    leaders = df.loc[leader_idx].copy()

    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"\nLoading {args.model} on {device}...")
    model = YOLO(args.model).to(device)
    results = []

    print(f"\nExtracting metric headway for {len(leaders)} frames...")
    for _, row in tqdm(leaders.iterrows(), total=len(leaders)):
        frame_name = row['frame']
        img_path = os.path.join(images_dir, frame_name)

        if not os.path.exists(img_path):
            continue

        img = cv2.imread(img_path)
        if img is None:
            continue

        # yolo26-depth takes bgr directly, no color conversion needed
        depth_result = model(img, imgsz=args.imgsz, verbose=False)[0]
        depth_map = depth_result.depth.data.cpu().numpy()

        x = int(row['bbox_bottom_center_x'])
        y = int(row['bbox_bottom_center_y'])

        y = min(y, depth_map.shape[0] - 1)
        x = min(x, depth_map.shape[1] - 1)

        headway_meters = depth_map[y, x]

        results.append({
            'frame': frame_name,
            'camera_headway_m': round(float(headway_meters), 3)
        })

    if results:
        out_df = pd.DataFrame(results)
        out_csv_path = os.path.join(output_dir, f"camera_headway_estimates_{suffix}.csv")
        out_df.to_csv(out_csv_path, index=False)

        # camera_calibrate.py needs camera_timestamps.csv alongside the estimates too
        ts_src = os.path.join(base_dir, "camera_timestamps.csv")
        if os.path.exists(ts_src):
            shutil.copy(ts_src, os.path.join(output_dir, "camera_timestamps.csv"))
        else:
            print(f"WARNING: {ts_src} not found. Copy it into {output_dir} manually before running camera_calibrate.py")

        print(f"\nSuccess! Extracted actual distances for {len(out_df)} frames.")
        print(f"Saved to: {out_csv_path}")
        print(f"Sample distance: {out_df['camera_headway_m'].iloc[0]} meters")
    else:
        print("\nFailed to extract any distances. Check your image paths.")

if __name__ == "__main__":
    main()
