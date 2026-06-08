import os
import struct
import numpy as np
import pandas as pd
import open3d as o3d
from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

# define paths
bag_dir = '../data/multimodal_dataset_20260608_125624'
out_dir = '../data/processed_lidar'
pcd_dir = os.path.join(out_dir, 'pointclouds')
lidar_topic = '/carla/tesla_ego/top_lidar'

# create output directories
os.makedirs(pcd_dir, exist_ok=True)

# init timestamp list
# initialize ros 2 humble typestore
typestore = get_typestore(Stores.ROS2_HUMBLE)
timestamps = []

# open rosbag reader
with Reader(bag_dir) as reader:
    # iterate through connections
    for connection, timestamp, rawdata in reader.messages():
        # filter for lidar topic
        if connection.topic == lidar_topic:
            # deserialize msg
            msg = typestore.deserialize_cdr(rawdata, connection.msgtype)
            
            # extract payload
            # carla 32-channel lidar typically packs x, y, z, intensity as float32
            point_step = msg.point_step
            num_points = msg.width * msg.height
            
            # parse byte array to numpy
            buffer = np.frombuffer(msg.data, dtype=np.uint8)
            buffer = buffer.reshape(-1, point_step)
            
            # slice xyz coordinates
            xyz_bytes = buffer[:, 0:12]
            xyz_floats = xyz_bytes.view(dtype=np.float32).reshape(-1, 3)
            
            # generate open3d pointcloud
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(xyz_floats)
            
            # normalize timestamp relative to t0
            t_sec = msg.header.stamp.sec + (msg.header.stamp.nanosec * 1e-9)
            if not timestamps:
                t0 = t_sec
            t_norm = t_sec - t0
            
            # save pcd file
            filename = f"scan_{len(timestamps):06d}.pcd"
            filepath = os.path.join(pcd_dir, filename)
            o3d.io.write_point_cloud(filepath, pcd)
            
            # append temporal data
            timestamps.append({
                'frame': len(timestamps),
                'normalized_timestamp': t_norm,
                'filename': filename
            })

# save sync data
df = pd.DataFrame(timestamps)
df.to_csv(os.path.join(out_dir, 'lidar_timestamps.csv'), index=False)

print("lidar processing complete")
