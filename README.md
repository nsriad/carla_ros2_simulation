# CARLA ROS 2 Simulation

A simulation environment bridging **CARLA 0.9.16** and **ROS 2 Humble** for multimodal data extraction (Camera, LiDAR, IMU, GNSS) and autonomous vehicle testing.

---

## Architecture Overview

### Ego Vehicle

- Tesla Model 3 (`role_name: tesla_ego`)

### Sensors

- IMU
- GNSS

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

## Running the Simulation

The pipeline is designed to run across **three terminals**.

### Terminal 1: Launch CARLA Server

Navigate to your CARLA installation directory and select the mode appropriate for your workflow.

#### Data Collection Mode (Maximum Performance)

```bash
./CarlaUE4.sh -RenderOffScreen
```

#### Testing Mode (Low Memory Usage)

```bash
./CarlaUE4.sh -quality-level=Low
```

#### Presentation Mode (Maximum Visual Quality)

```bash
./CarlaUE4.sh -quality-level=Epic
```

---

### Terminal 2: Launch CARLA ROS Bridge

Activate the Python virtual environment:

```bash
source ~/carla_env/bin/activate
```

#### Data Collection / Heavy Sensor Configuration (10 FPS)

Recommended for synchronized RGB and LiDAR data collection.

```bash
ros2 launch carla_ros_bridge carla_ros_bridge.launch.py \
town:=Town10HD_Opt \
timeout:=30 \
fixed_delta_seconds:=0.1
```

#### For Smooth Simulation (30 FPS)

Use only when heavy sensor streams are temporarily disabled.

```bash
ros2 launch carla_ros_bridge carla_ros_bridge.launch.py \
town:=Town10HD_Opt \
timeout:=30 \
fixed_delta_seconds:=0.033
```

---

### Terminal 3: Launch Vehicle Spawner

Activate the ROS 2 workspace and start the ego vehicle with sensors.

```bash
source install/setup.bash

ros2 run carla_ros_sim vehicle_spawner
```

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

