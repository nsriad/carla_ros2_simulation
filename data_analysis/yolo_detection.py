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

# coco vehicle class IDs
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--frames_dir", type=str, required=True)
    p.add_argument("--num_frames", type=int, default=None,
               help="Number of frames to sample. Omit this flag to run on ALL frames.")
    p.add_argument("--model", type=str, default="yolov8n.pt")
    p.add_argument("--conf_thresh", type=float, default=0.30)
    p.add_argument("--exclude_bottom_px", type=int, default=0,
               help="Mask out this many pixels from the bottom of the image before "
                    "running YOLO, to exclude the ego vehicle's own hood/bumper. "
                    "Check a few annotated images where a false 'second vehicle' was "
                    "detected and note the bbox's y1 (top edge, distance from bottom "
                    "of image) to pick this value. Default 0 = no masking.")
    return p.parse_args()

def main():
    args = parse_args()
    
    # find frames
    exts = ("*.png", "*.jpg", "*.jpeg")
    all_frames = []
    for ext in exts:
        all_frames.extend(sorted(Path(args.frames_dir).glob(ext)))
        
    if not all_frames:
        print(f"ERROR: No image files found in {args.frames_dir}")
        sys.exit(1)

    # selected frames
    if args.num_frames:
        step = max(1, len(all_frames) // args.num_frames)
        sampled = [str(all_frames[i]) for i in range(0, len(all_frames), step)][:args.num_frames]
        print(f"Sampling {len(sampled)} frames (stride={step}) out of {len(all_frames)} total.")
    else:
        sampled = [str(f) for f in all_frames]
        print(f"Running on all {len(sampled)} frames.")

    if args.exclude_bottom_px > 0:
        print(f"Excluding bottom {args.exclude_bottom_px}px of each frame from detection "
              f"(ego vehicle hood/bumper region).")
    
    # load yolo with cuda
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\nLoading YOLOv8 on {device}...")
    model = YOLO(args.model).to(device)

    # output directory
    base_dir = str(Path(args.frames_dir).parent)
    suffix = f"{args.conf_thresh}_excl{args.exclude_bottom_px}" if args.exclude_bottom_px > 0 else str(args.conf_thresh)
    annotated_dir = os.path.join(base_dir, "annotated_" + suffix)
    os.makedirs(annotated_dir, exist_ok=True)
    all_detections = []

    # run inference
    for fpath in tqdm(sampled, desc="Detecting vehicles"):
        fname = os.path.basename(fpath)
        img = cv2.imread(fpath)
        if img is None: continue

        # mask out the ego vehicle's hood/bumper region before inference, so YOLO
        # never sees it and can't produce a false "second vehicle" detection there
        if args.exclude_bottom_px > 0:
            img_infer = img.copy()
            img_infer[-args.exclude_bottom_px:, :] = 0
        else:
            img_infer = img

        # results = model(img_infer, conf=args.conf_thresh, verbose=False)[0]
        results = model(img_infer, conf=args.conf_thresh, agnostic_nms=True, verbose=False)[0]

        ann_img = img.copy()

        # draw the excluded region on the annotated image so it's visually obvious
        if args.exclude_bottom_px > 0:
            h = ann_img.shape[0]
            overlay = ann_img.copy()
            cv2.rectangle(overlay, (0, h - args.exclude_bottom_px), (ann_img.shape[1], h),
                          (0, 0, 255), -1)
            ann_img = cv2.addWeighted(overlay, 0.25, ann_img, 0.75, 0)

        for i, box in enumerate(results.boxes):
            cls_id = int(box.cls[0].item())
            if cls_id not in VEHICLE_CLASSES: continue
                
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            conf = float(box.conf[0].item())
            
            # save data
            all_detections.append({
                "frame": fname,
                "class": VEHICLE_CLASSES[cls_id],
                "confidence": round(conf, 3),
                "bbox_bottom_center_x": (x1 + x2) // 2,
                "bbox_bottom_center_y": y2
            })
            
            # draw box
            cv2.rectangle(ann_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(ann_img, f"{VEHICLE_CLASSES[cls_id]} {conf:.2f}", 
                        (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        
        cv2.imwrite(os.path.join(annotated_dir, fname), ann_img)

    # save results
    if all_detections:
        df = pd.DataFrame(all_detections)

        # report frames with multiple detections, for sanity checking
        multi = df.groupby("frame").size()
        n_multi = (multi > 1).sum()
        print(f"\nFrames with multiple vehicle detections: {n_multi}")

        out_csv = os.path.join(base_dir, f"detections_{suffix}.csv")
        df.to_csv(out_csv, index=False)
        print(f"Success! Found {len(df)} vehicles across {df['frame'].nunique()} frames.")
        print(f"Check {annotated_dir} to see the boxes (excluded region shaded red).")
        print(f"CSV saved to {out_csv}")
    else:
        print("\nNo vehicles found. Try lowering --conf_thresh.")

if __name__ == "__main__":
    main()
