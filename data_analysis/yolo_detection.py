#!/usr/bin/env python3
import argparse
import os
import sys
import random
from pathlib import Path

import cv2
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm
import torch
from ultralytics import YOLO

# COCO vehicle class IDs
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--frames_dir", type=str, required=True)
    p.add_argument("--output_dir", type=str, default="../data")
    p.add_argument("--num_frames", type=int, default=10) # Set default to 10 for a quick test
    p.add_argument("--model", type=str, default="yolov8n.pt")
    p.add_argument("--conf_thresh", type=float, default=0.5)
    return p.parse_args()

def main():
    args = parse_args()
    
    # 1. Find frames
    exts = ("*.png", "*.jpg", "*.jpeg")
    all_frames = []
    for ext in exts:
        all_frames.extend(sorted(Path(args.frames_dir).glob(ext)))
        
    if not all_frames:
        print(f"ERROR: No image files found in {args.frames_dir}")
        sys.exit(1)

    # Sample frames
    step = max(1, len(all_frames) // args.num_frames)
    sampled = [str(all_frames[i]) for i in range(0, len(all_frames), step)][:args.num_frames]
    
    # 2. Load YOLO with CUDA
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\nLoading YOLOv8 on {device}...")
    model = YOLO(args.model).to(device)

    # 3. Setup output
    base_dir = str(Path(args.frames_dir).parent)
    annotated_dir = os.path.join(base_dir, "annotated")
    os.makedirs(annotated_dir, exist_ok=True)
    all_detections = []

    # 4. Run inference
    for fpath in tqdm(sampled, desc="Detecting vehicles"):
        fname = os.path.basename(fpath)
        img = cv2.imread(fpath)
        if img is None: continue
        
        results = model(img, conf=args.conf_thresh, verbose=False)[0]
        ann_img = img.copy()
        
        for i, box in enumerate(results.boxes):
            cls_id = int(box.cls[0].item())
            if cls_id not in VEHICLE_CLASSES: continue
                
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            conf = float(box.conf[0].item())
            
            # Save data
            all_detections.append({
                "frame": fname,
                "class": VEHICLE_CLASSES[cls_id],
                "confidence": round(conf, 3),
                "bbox_bottom_center_x": (x1 + x2) // 2,
                "bbox_bottom_center_y": y2
            })
            
            # Draw box
            cv2.rectangle(ann_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(ann_img, f"{VEHICLE_CLASSES[cls_id]} {conf:.2f}", 
                        (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        
        cv2.imwrite(os.path.join(annotated_dir, fname), ann_img)

    # 5. Save results
    if all_detections:
        df = pd.DataFrame(all_detections)
        df.to_csv(os.path.join(base_dir, "detections.csv"), index=False)
        print(f"\nSuccess! Found {len(df)} vehicles.")
        print(f"Check {annotated_dir} to see the boxes.")
        print(f"CSV saved to {os.path.join(base_dir, 'detections.csv')}")
    else:
        print("\nNo vehicles found. Try lowering --conf_thresh.")

if __name__ == "__main__":
    main()

