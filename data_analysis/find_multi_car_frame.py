#!/usr/bin/env python3
import pandas as pd

def main():
    csv_path = "../data/town04_leader_50_multimodal_dataset_20260618_102918/processed_camera/detections_0.3_excl40.csv"
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
    