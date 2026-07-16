import os
import glob
import sys
import numpy as np
import open3d as o3d
import matplotlib.pyplot as plt
from PIL import Image

import os

# dataset path
if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv} <dataset_name>")
        sys.exit(1)
run_dir = '../data/' + sys.argv[1]

# define paths inside the run's lidar folder
pcd_dir = os.path.join(run_dir, 'processed_lidar', 'pointclouds')
out_gif = os.path.join(run_dir, 'processed_lidar', 'lidar_headway_timelapse.gif')

# grab first 1000 pcd files
n_pcds = 1000
pcd_files = sorted(glob.glob(os.path.join(pcd_dir, '*.pcd')))[:n_pcds:4]  # skipping every 4 frames to get reduced gif file size

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

def make_ego_marker():
    """
    Creates a small white sphere at the sensor origin (0,0,0) representing
    the ego vehicle's LiDAR mount position. Gives spatial reference so the
    leader's back-and-forth motion makes sense relative to the ego.
    """
    sphere = o3d.geometry.TriangleMesh.create_sphere(radius=0.3)
    sphere.translate([0.0, 0.0, 0.0])
    sphere.paint_uniform_color([0.5, 0.0, 0.5])  # purple
    sphere.compute_vertex_normals()
    return sphere
 
def make_forward_axis():
    """
    Draws a short green line from origin pointing forward (+x) so the
    viewing direction is always clear in the GIF.
    """
    points = [[0, 0, 0], [3, 0, 0]]   # 3m forward arrow
    lines  = [[0, 1]]
    colors = [[0.0, 1.0, 0.0]]        # green
    line_set = o3d.geometry.LineSet()
    line_set.points = o3d.utility.Vector3dVector(points)
    line_set.lines  = o3d.utility.Vector2iVector(lines)
    line_set.colors = o3d.utility.Vector3dVector(colors)
    return line_set

# load base geometry
pcd = o3d.io.read_point_cloud(pcd_files[0])
apply_distance_colors(pcd)
vis.add_geometry(pcd)

# add ego marker and forward axis
ego_marker   = make_ego_marker()
forward_axis = make_forward_axis()
vis.add_geometry(ego_marker)
vis.add_geometry(forward_axis)

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
