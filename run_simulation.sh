#!/usr/bin/env bash
set -e

# copy run_simulation.env.example to run_simulation.env and fill in your own paths
ENV_FILE="$(dirname "$0")/run_simulation.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found."
    echo "Copy run_simulation.env.example to run_simulation.env and fill in your paths."
    exit 1
fi
# export so ros nodes can read CARLA_DIR
set -a
source "$ENV_FILE"
set +a

RECORD=${1:-false}     # ./run_simulation.sh true 60   -> record a bag
DURATION=${2:-60}      # ./run_simulation.sh false 0   -> debug run, no bag, indefinite

# kill every background process this script started, even on Ctrl+C or error
trap 'echo "=== shutting down ==="; \
      kill -9 $RQT_PID 2>/dev/null; \
      pkill -TERM -f "carla_ros_bridge" 2>/dev/null; \
      sleep 3; \
      pkill -TERM -f "CarlaUE4" 2>/dev/null; \
      sleep 3; \
      pkill -9 -f "CarlaUE4" 2>/dev/null; \
      true' EXIT

echo "1/4: starting CARLA server"
cd "$CARLA_DIR"
./CarlaUE4.sh &
CARLA_PID=$!
echo "waiting 15s for CARLA to finish booting.."
sleep 15

echo "2/4: starting CARLA ROS bridge"
source "$CARLA_BRIDGE_DIR/install/setup.bash"
ros2 launch carla_ros_bridge carla_ros_bridge.launch.py \
  town:=Town04 timeout:=30 fixed_delta_seconds:=0.1 \
  synchronous_mode:=True use_sim_time:=True &
BRIDGE_PID=$!

echo "waiting for bridge to come up (/clock topic)..."
until ros2 topic list 2>/dev/null | grep -q "/clock"; do
    sleep 1
done
echo "bridge is up."
sleep 3   # let the bridge finish its internal setup before spawning actors

echo "3/4: opening rqt_plot for all four headway sources"
ros2 run rqt_plot rqt_plot \
  /carla/tesla_ego/ground_truth_headway/data \
  /carla/tesla_ego/lidar_headway/data \
  /carla/tesla_ego/camera_headway/data \
  /carla/tesla_ego/ml_headway/data &
RQT_PID=$!

echo "4/4: launching simulation (record=${RECORD}, duration=${DURATION})"
cd "$WORKSPACE_DIR"
source install/setup.bash
ros2 launch carla_ros_sim sim_launch.py record:=${RECORD} duration:=${DURATION}

echo "=== simulation finished ==="
# trap above handles cleanup of rqt_plot, bridge, and CARLA automatically
