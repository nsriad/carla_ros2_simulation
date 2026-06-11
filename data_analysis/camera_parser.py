#!/usr/bin/env python3
import os
import numpy as np
import pandas as pd
import cv2
from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

def main():
    # dataset path
    bag_path = '../data/multimodal_dataset_20260611_121415'
    
    # output directly inside the run's folder
    output_dir = os.path.join(bag_path, 'processed_camera')
    images_dir = os.path.join(output_dir, 'images')
    
    # create output directories
    os.makedirs(images_dir, exist_ok=True)
    
    typestore = get_typestore(Stores.ROS2_HUMBLE)
    metadata = []
    
    print(f"Extracting camera frames from: {bag_path}")
    
    frame_count = 0
    with Reader(bag_path) as reader:
        for connection, timestamp, rawdata in reader.messages():
            if connection.topic == '/carla/tesla_ego/front_camera/image':
                msg = typestore.deserialize_cdr(rawdata, connection.msgtype)
                time_sec = timestamp / 1e9
                
                # reshape 1d array to 800x600x4
                img_bgra = np.array(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 4))
                
                # convert to bgr for opencv
                img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
                
                # filename with leading zeros
                filename = f"frame_{frame_count:04d}.png"
                filepath = os.path.join(images_dir, filename)
                
                # save image
                cv2.imwrite(filepath, img_bgr)
                
                # record timestamp for fusion
                metadata.append({
                    'frame_id': filename,
                    'timestamp': time_sec
                })
                
                frame_count += 1
                
                # print progress
                if frame_count % 500 == 0:
                    print(f"Extracted {frame_count} frames...")

    # save metadata
    df_meta = pd.DataFrame(metadata)
    
    # normalize time
    if not df_meta.empty:
        t0 = df_meta['timestamp'].min()
        df_meta['timestamp_normalized'] = df_meta['timestamp'] - t0
        
    csv_path = os.path.join(output_dir, 'camera_timestamps.csv')
    df_meta.to_csv(csv_path, index=False)
    
    print(f"\nSuccess! Saved {frame_count} images to {images_dir}")
    print(f"Saved synchronization metadata to {csv_path}")

if __name__ == '__main__':
    main()
    