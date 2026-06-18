# CARLA ROS 2 Simulation

A simulation environment bridging **CARLA 0.9.16** and **ROS 2 Humble** for multimodal data extraction (Camera, LiDAR, IMU, GNSS) and autonomous vehicle testing.

---

## Architecture Overview

### Ego Vehicle

- Tesla Model 3 (`role_name: tesla_ego`)

### Leader Vehicle

- Lincoln MKZ 2020 (`role_name: leader`)
- Predefined 1km route waypoint navigation

### Sensors

- IMU
- GNSS
- Front Camera (RGB)
- Top LiDAR (32-Channel)

---

## Tested Environment/Prerequisites

| Component | Version |
|-----------|---------|
| Ubuntu | 22.04 |
| ROS 2 | Humble |
| CARLA | 0.9.16 |
| Python | 3.10 |
| Unreal Engine | CARLA Built-in |
| NumPy | 1.x |

---

## Package Overview

The core ROS 2 package is `carla_ros_sim`. The source is organized into modular files under `src/carla_ros_sim/carla_ros_sim/`:

| File | Description |
|---|---|
| `vehicle_spawner.py` | Main ROS 2 node. Connects to CARLA, spawns vehicles, attaches sensors, runs the control loop, and manages simulation lifetime via a configurable duration timer |
| `carla_env.py` | Environment class handling CARLA client connection, vehicle spawning, ground truth calculation, spectator camera, and Traffic Manager configuration for both custom and default map modes |
| `sensors.py` | Sensor attachment manager. Configures and spawns IMU, GNSS, RGB camera, and 32-channel LiDAR onto the ego vehicle |
| `controllers.py` | PID longitudinal controller for ego vehicle gap tracking, and stop-and-go wave logic for the leader vehicle on the custom straight road |
| `lidar_headway_estimator.py` | ROS 2 node that subscribes to the raw LiDAR point cloud, applies a 3D bounding box ROI filter, estimates space headway via radial distance, publishes both the scalar headway and the filtered ROI point cloud, and logs results to a timestamped CSV |

---

## Installation & Workspace Setup

### 1. Setup the ROS 2 Workspace
Create a new workspace and clone the repository inside this directory:

```bash
mkdir -p ~/carla_simulation_ws
cd ~/carla_simulation_ws
git clone https://github.com/nsriad/carla_ros2_simulation.git
```

### 2. Install Python Dependencies
The post-processing and visualization scripts require specific Python libraries. You can install them globally or within your dedicated `carla_env` virtual environment:

```bash
pip install pandas numpy open3d rosbags matplotlib pillow
```

### 3. Build the Package
From the root of the cloned repository, build the package using `colcon`. Using the `--symlink-install` flag is recommended for Python packages so you do not have to rebuild every time you edit a script.

```
source /opt/ros/humble/setup.bash
colcon build --packages-select carla_ros_sim --symlink-install
```
Once built, source the local setup file so the ROS 2 CLI can find your package. You must do this in every new terminal before running the nodes:
```
source install/setup.bash
```

## Running the Simulation

The pipeline is designed to run across **5 terminals**.

### Terminal 1: Launch CARLA Server

Navigate to your CARLA installation directory and launch the simulation environment:

```bash
./CarlaUE4.sh
```
*Note: Append `-RenderOffScreen` for maximum performance during data collection, `-quality-level=Low` for testing with low memory usage, or `-quality-level=Epic` for maximum visual quality.*

---

### Terminal 2: Launch CARLA ROS Bridge

Navigate to your CARLA ROS bridge workspace and source its installation to make the launch files available. Then, launch with either a default CARLA town or a custom OpenDRIVE map. (defaulted to 10 FPS for synchronized RGB and LiDAR data collection):

**Default CARLA town (e.g. Town04):**

```bash
source ~/carla_ros_bridge/install/setup.bash

ros2 launch carla_ros_bridge carla_ros_bridge.launch.py \
  town:=Town04 \
  timeout:=30 \
  fixed_delta_seconds:=0.1 \
  synchronous_mode:=True
```

**Custom straight highway map:**

```bash
ros2 launch carla_ros_bridge carla_ros_bridge.launch.py \
  town:=/home/ruby/Nazmus_Shakib/Summer_26/carla_simulation_ws/custom_maps/straight_highway.xodr \
  timeout:=30 \
  fixed_delta_seconds:=0.1 \
  synchronous_mode:=True
```

*Note: `synchronous_mode:=True` is required. Running asynchronously causes sensor frame desynchronization and data loss. For smoother simulation when heavy sensor streams are disabled, adjust `fixed_delta_seconds` to `0.033` (30 FPS) or `0.016` (60 FPS).*

---

### Terminal 3: Launch Vehicle Spawner

First, activate the dedicated Python virtual environment. This environment isolates the CARLA Python API and specific package versions (like NumPy 1.x) required to prevent cv_bridge incompatibilities during image extraction. Then launch everything with a single command:

```bash
source ~/carla_simulation_ws/carla_env/bin/activate
```

*Note: The system is configured so that ROS 2 continues to utilize the global, OS-level Python installation for its core execution and hardware interfacing, while drawing only the simulation-specific dependencies from this active virtual environment.*

Next, navigate to the local ROS 2 workspace, source it, and start the ego vehicle with its sensors:

```bash
cd ~/carla_simulation_ws
source install/setup.bash
ros2 launch carla_ros_sim sim_launch.py record:=true duration:=60
```

**Launch arguments:**

| Argument | Default | Description |
|---|---|---|
| `record` | `false` | Enable ROS bag recording |
| `duration` | `60` | Simulation duration in seconds. Set to `0` to run indefinitely |

The launch file starts three processes simultaneously: `vehicle_spawner`, `lidar_headway_estimator`, and the ROS bag recorder (when `record:=true`). The bag is saved to `data/multimodal_dataset_YYYYMMDD_HHMMSS/` automatically.

**To switch between custom map and default town mode**, change the following flag inside `vehicle_spawner.py` before building:

```python
self.env = CarlaEnvironment(use_custom_map=True)   # custom straight road
self.env = CarlaEnvironment(use_custom_map=False)  # default CARLA town
```

---

### Terminal 4: To plot rqt live plot

To plot linear acceleration in real-time:

```
ros2 run rqt_plot rqt_plot /carla/tesla_ego/imu_sensor/linear_acceleration/x
```
To plot your Latitude and Longitude moving in real-time:
```
ros2 run rqt_plot rqt_plot /carla/tesla_ego/gnss_sensor/latitude /carla/tesla_ego/gnss_sensor/longitude
```

---

## Data Post-Processing

Navigate to `data_analysis/` and run the pipeline shell scripts.

### Pipeline Scripts

| Script | Description |
|---|---|
| `parse_data.sh` | Extracts camera frames, LiDAR point clouds and IMU/GNSS data from the ROS bag into structured output directories |
| `post_process.sh` | Generates camera GIF, LiDAR timelapse animation, and headway plots from the parsed data |

**Usage:**

```bash
cd data_analysis/

# step 1: extract all sensor data from bag
./parse_data.sh 20260617_103550

# step 2: generate visualizations
./post_process.sh 20260617_103550
```

The datetime argument matches the folder name suffix: `multimodal_dataset_20260617_103550`.

### Parser Scripts

| Script | Description |
|---|---|
| `camera_parser.py` | Extracts camera frames as `.png` files |
| `lidar_parser.py` | Extracts point clouds as `.pcd` files from the filtered ROI topic |
| `imu_gnss_parser.py` | Extracts IMU and GNSS data as `.csv` and generates acceleration plot |
| `headway_analysis.py` | Reads the headway CSV log and generates LiDAR vs ground truth comparison plots |
| `generate_cam_gif.py` | Stitches camera frames into an animated GIF |
| `lidar_animator.py` | Renders LiDAR point cloud frames into an animated GIF with ego marker and forward axis |
| `lidar_visualizer.py` | Static single-frame LiDAR point cloud visualization |

### Output Structure

```text
data/
└── multimodal_dataset_YYYYMMDD_HHMMSS/
    ├── processed_camera/
    ├── processed_lidar/
    ├── processed_imu_gnss/
    └── processed_headway/
```
---


## Outputs & Data Visualization

The following visualizers demonstrate the synchronized multimodal data extracted from the ROS bag logs.

### Multimodal Sensor Grid

Demonstration of the ego vehicle navigating the cluttered town environment. The left column displays the front-facing RGB camera, and the right column displays the corresponding 32-channel LiDAR `PointCloud2` data (color-mapped for spatial distance).

| Scenario | Camera View | LiDAR Point Cloud |
| :---: | :---: | :---: |
| **Leader-FollowerTracking** | <img src="asset/simulation_preview.gif" height="250"> | <img src="asset/lidar_headway_timelapse.gif" height="250"> |
| **Baseline Navigation (No Leader)** | <img src="asset/no_leader_simulation_preview.gif" height="250"> | <img src="asset/no_leader_lidar_headway_timelapse.gif" height="250"> |

### ROI-Filtered LiDAR Point Cloud

After applying the 3D bounding box ROI filter, only points belonging to the leader vehicle's rear face are retained. The ego vehicle origin is marked as a fixed reference point (white sphere) with a green arrow indicating the forward direction. Point color encodes radial distance from the ego sensor origin using the plasma colormap (blue = close, yellow = far).

| Scenario | Camera View | ROI LiDAR Point Cloud |
| :---: | :---: | :---: |
| **Custom Straight Road** | <img src="asset/straight_cam_simulation_preview.gif" height="250"> | <img src="asset/straight_roi_lidar_headway_timelapse.gif" height="250"> |
| **Town04 Highway** | <img src="asset/town04_cam_simulation_preview.gif" height="250"> | <img src="asset/town04_roi_lidar_headway_timelapse.gif" height="250"> |

### Space Headway Validation

LiDAR-estimated space headway compared against CARLA ground truth for both environments.

| Scenario | Headway Plot |
| :---: | :---: |
| **Custom Straight Road** | <img src="asset/straight_space_headway.png" height="200"> |
| **Town04 Highway** | <img src="asset/town04_space_headway.png" height="200"> |

### IMU Sensor

Extracted linear acceleration data capturing the ego vehicle's longitudinal and lateral dynamics.

[View the IMU Acceleration Plot (PDF)](asset/acceleration_plot.pdf)

---

## Troubleshooting

For known issues and their resolutions, see [troubleshooting.md](troubleshooting.md).