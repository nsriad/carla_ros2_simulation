import os
import glob
import numpy as np
import open3d as o3d
import matplotlib.pyplot as plt
from PIL import Image

# define paths
pcd_dir = '../data/processed_lidar/pointclouds'
out_gif = '../data/processed_lidar/lidar_headway_timelapse.gif'

# grab first 100 pcd files
n_pcds = 1000
pcd_files = sorted(glob.glob(os.path.join(pcd_dir, '*.pcd')))[:n_pcds:4]  # downsample to 25fps from 100fps

if not pcd_files:
    print("error: no pcd files found")
    exit()

print(f"rendering {len(pcd_files)} frames...")

# setup visualizer
vis = o3d.visualization.Visualizer()
vis.create_window(window_name="carla distance rendering", width=800, height=600, visible=False)

# use plasma colormap (great for depth/distance representation)
cmap = plt.get_cmap('plasma')

def apply_distance_colors(pcd):
    points = np.asarray(pcd.points)
    if len(points) == 0:
        return
        
    # calc euclidean distance from origin
    distances = np.linalg.norm(points, axis=1)
    
    # normalize distances between 0 and 1
    d_min, d_max = distances.min(), distances.max()
    d_norm = (distances - d_min) / (d_max - d_min + 1e-6)
    
    # map to rgb
    colors = cmap(d_norm)[:, :3]
    pcd.colors = o3d.utility.Vector3dVector(colors)

# load base geometry
pcd = o3d.io.read_point_cloud(pcd_files[0])
apply_distance_colors(pcd)
vis.add_geometry(pcd)

frames = []

# render loop
for i, file in enumerate(pcd_files):
    # load new data
    new_pcd = o3d.io.read_point_cloud(file)
    
    # update geometry and colors
    pcd.points = new_pcd.points
    apply_distance_colors(pcd)
    
    # refresh visualizer
    vis.update_geometry(pcd)
    vis.poll_events()
    vis.update_renderer()
    
    # capture frame
    img_buffer = vis.capture_screen_float_buffer(do_render=True)
    img_array = (np.asarray(img_buffer) * 255).astype(np.uint8)
    frames.append(Image.fromarray(img_array))
    
    if (i + 1) % 10 == 0:
        print(f"processed {i + 1}/{n_pcds} frames")

vis.destroy_window()

# save gif
print("stitching gif...")
frames[0].save(out_gif, save_all=True, append_images=frames[1:], optimize=False, duration=40, loop=0)

print(f"animation complete: {out_gif}")
