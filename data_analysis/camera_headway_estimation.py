#!/usr/bin/env python3
import argparse
import os
import cv2
import torch
import numpy as np
import pandas as pd
from tqdm import tqdm

def parse_args():
    parser = argparse.ArgumentParser(description="Extract metric headway using ZoeDepth.")
    parser.add_argument(
        "--camera_dir", 
        type=str, 
        required=True,
        help="Path to the processed_camera directory containing 'images' and 'detections.csv'"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    print("Loading detections...")
    
    # directory location
    base_dir = args.camera_dir
    images_dir = os.path.join(base_dir, "images")
    detections_path = os.path.join(base_dir, "detections.csv")
    
    if not os.path.exists(detections_path):
        print(f"ERROR: Could not find {detections_path}. Did you run yolo_detection.py first?")
        return
        
    # load the boxes from yolo
    df = pd.read_csv(detections_path)
    
    # filter for the leader vehicle in each frame
    leader_idx = df.groupby('frame')['bbox_bottom_center_y'].idxmax()
    leaders = df.loc[leader_idx].copy()
    
    # load zoedepth model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\nLoading ZoeDepth model on {device} (this takes real-world distance)...")
    zoe = torch.hub.load("isl-org/ZoeDepth", "ZoeD_K", pretrained=True, trust_repo=True).to(device).eval()    
    results = []
    
    print(f"\nExtracting metric headway for {len(leaders)} frames...")
    for _, row in tqdm(leaders.iterrows(), total=len(leaders)):
        frame_name = row['frame']
        img_path = os.path.join(images_dir, frame_name)
        
        if not os.path.exists(img_path):
            continue
            
        # read image
        img = cv2.imread(img_path)
        if img is None:
            continue
            
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # depth map in meters
        with torch.no_grad():
            depth_map = zoe.infer_pil(img_rgb)
            
        # coordinates of the bottom-center of the bounding box
        x = int(row['bbox_bottom_center_x'])
        y = int(row['bbox_bottom_center_y'])
        
        # ensure coordinates are within the image boundaries
        y = min(y, depth_map.shape[0] - 1)
        x = min(x, depth_map.shape[1] - 1)
        
        # distance at exactly that pixel
        headway_meters = depth_map[y, x]
        
        results.append({
            'frame': frame_name,
            'camera_headway_m': round(float(headway_meters), 3)
        })

    # save data back to the same folder
    if results:
        out_df = pd.DataFrame(results)
        out_csv_path = os.path.join(base_dir, "camera_headway_estimates.csv")
        out_df.to_csv(out_csv_path, index=False)
        
        print(f"\nSuccess! Extracted actual distances for {len(out_df)} frames.")
        print(f"Saved to: {out_csv_path}")
        print(f"Sample distance: {out_df['camera_headway_m'].iloc[0]} meters")
    else:
        print("\nFailed to extract any distances. Check your image paths.")

if __name__ == "__main__":
    main()
