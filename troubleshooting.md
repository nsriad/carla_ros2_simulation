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
