import os
import sys
import open3d as o3d

# define path to the extracted point clouds
if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv} <dataset_name>")
        sys.exit(1)
run_dir = '../data/' + sys.argv[1]

# define path to the extracted point clouds directly inside the run's folder
pcd_dir = os.path.join(run_dir, 'processed_lidar', 'pointclouds')
sample_file = 'scan_000300.pcd'
sample_path = os.path.join(pcd_dir, sample_file)

# check if file exists before loading
if not os.path.exists(sample_path):
    print(f"error: could not find {sample_file}")
else:
    # load the point cloud
    print(f"loading {sample_file}...")
    pcd = o3d.io.read_point_cloud(sample_path)
    
    # print basic stats
    print(f"point cloud has {len(pcd.points)} points.")
    
    # render interactive visualization
    print("press 'q' or 'esc' to close the window.")
    o3d.visualization.draw_geometries([pcd], 
                                      window_name="carla top_lidar preview", 
                                      width=1024, 
                                      height=768, 
                                      point_show_normal=False)
    
