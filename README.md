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

## Development Notes and Troubleshooting

### NumPy 2.x and `cv_bridge` Compatibility

**Issue**

`cv_bridge` crashes due to incompatibilities with newer NumPy 2.x releases.

**Resolution**

Use a dedicated virtual environment (`carla_env`) with a NumPy 1.x version installed.

---

### CARLA 0.9.16 Version Rejection

**Issue**

The default `carla_ros_bridge` includes a version check that rejects CARLA releases newer than 0.9.13.

**Resolution**

Patch the bridge source code located at `~/carla_ros_bridge/src/ros-bridge/carla_ros_bridge/src/carla_ros_bridge/bridge.py` to bypass the version restriction and allow native support for CARLA 0.9.16. This code read the version from the file `CARLA_VERSION`, just edit the version here.

---

### Traffic Manager Port Conflicts

**Issue**

Previously terminated sessions may leave Traffic Manager processes attached to port `8000`, causing autopilot failures.

**Resolution**

Use a dedicated Traffic Manager port:

```python
client.get_trafficmanager(8051)
```

If conflicts remain:

```bash
killall -9 python3
```

or

```bash
sudo fuser -k 8051/tcp
```

---

### Spectator Camera Jitter and Desynchronization

**Issue**

ROS 2 timer callbacks may become unsynchronized from CARLA's physics engine, resulting in camera jitter.

**Resolution**

Bind spectator updates directly to the CARLA physics tick:

```python
self.world.on_tick(...)
```

This ensures smooth and physically synchronized camera tracking.

---

### Traffic Manager Route Divergence

**Issue**

When using autopilot for multiple vehicles in the same lane, the Traffic Manager may independently choose different routes at intersections, causing the ego vehicle to lose the leader.

**Resolution**

Predefine a specific route using waypoints and force both vehicles to follow it. Adjust the ego vehicle's `vehicle_percentage_speed_difference` to prevent it from overtaking the leader at traffic lights.

---

### <span style="color:#c0392b">Synchronous Mode Requirement for Custom Maps</span>

**Issue**

Running the ROS bridge in the default asynchronous mode caused sensor frame desynchronization when loading a custom OpenDRIVE map. The IMU sensor would wait indefinitely for a frame that was reset during map generation, hanging the entire pipeline.

**Resolution**

Add `synchronous_mode:=True` to the bridge launch command. This makes the bridge the single clock authority and ensures all sensors capture data on the same physics tick.

---

### <span style="color:#c0392b">Sensor Tick Conflict in Synchronous Mode</span>

**Issue**

Setting `sensor_tick` attributes (e.g. `sensor_tick='0.1'`) on sensors while running in synchronous mode caused sensors to desynchronize from the physics engine. The bridge already guarantees one sensor capture per tick at the rate set by `fixed_delta_seconds`, making manual tick attributes redundant and conflicting.

**Resolution**

Remove all `sensor_tick` attribute assignments from sensor configuration. In synchronous mode, sensor timing is governed entirely by `fixed_delta_seconds` in the bridge launch command.

---

### <span style="color:#c0392b">LiDAR ROI Filtering and Bag Recording</span>

**Issue**

Recording the full raw 360-degree LiDAR point cloud produced large bag files and included irrelevant environment returns (road surface, buildings, guardrails) that interfered with headway estimation analysis.

A ROS 2 plugin approach was evaluated but abandoned because the Python `pluginlib` framework does not support composable node plugins the way C++ does. A standalone filter node was considered but added unnecessary process overhead.

**Resolution**

The ROI bounding box filter is applied directly inside `lidar_headway_estimator.py`. After filtering, the node publishes the reduced point cloud to a separate topic `/carla/tesla_ego/top_lidar_roi`. The bag recorder subscribes to this filtered topic instead of the raw topic, reducing file size by approximately 50x while retaining all data relevant to headway estimation.

---

### <span style="color:#c0392b">Ego Vehicle Self-Occlusion in LiDAR</span>

**Issue**

With the LiDAR mounted at the vehicle center (`z=1.5m`) using default field of view and low point density (`100,000 pts/sec`), downward rays reflected off the ego vehicle's own hood and windshield, producing false close-range detections at approximately 1.49m consistently, overriding the true leader detection.

**Resolution**

Three changes applied together resolved the issue:

1. Raise the LiDAR mount to `z=2.5m` (above the Tesla Model 3 roof at 1.44m) so downward rays clear the ego body entirely before reaching the forward detection zone.
2. Narrow the vertical field of view to `upper_fov=2.0` and `lower_fov=-25.0` degrees to concentrate rays on the leader vehicle height range and avoid road surface returns at close range.
3. Increase `points_per_second` to `600,000` to compensate for the narrower FOV at 32 channels and 10Hz rotation this yields sufficient point density on the leader rear face at following distances of 3.5 to 80m.
4. Set `min_x=3.5m` in the ROI filter as an additional guard to exclude any remaining ego body returns within the vehicle footprint.

Final LiDAR configuration:

```python
lidar_bp.set_attribute('channels', '32')
lidar_bp.set_attribute('range', '80.0')
lidar_bp.set_attribute('points_per_second', '600000')
lidar_bp.set_attribute('rotation_frequency','10.0')
lidar_bp.set_attribute('upper_fov', '2.0')
lidar_bp.set_attribute('lower_fov', '-25.0')
lidar_transform = carla.Transform(carla.Location(x=0.0, z=2.5))
```

---
