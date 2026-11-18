#!/usr/bin/env bash
# runs carla, the ros bridge and the platoon node with one command
# usage: ./run_platoon.sh [--window] [--no-carla] [--map NAME] [--test]

cd "$(dirname "$0")"
CONFIG=configs/platoon_town04.py
mkdir -p logs

# options
WINDOW=false
NO_CARLA=false
TEST=false
MAP=""
while [ $# -gt 0 ]; do
    case "$1" in
        --window) WINDOW=true ;;
        --no-carla) NO_CARLA=true ;;
        --test) TEST=true ;;
        --map) MAP="$2"; shift ;;
        *) echo "unknown option $1"; exit 1 ;;
    esac
    shift
done

# carla and bridge paths, exported so the nodes can read CARLA_DIR
set -a
source run_simulation.env
set +a
source /opt/ros/humble/setup.bash
source "$CARLA_BRIDGE_DIR/install/setup.bash"
source install/setup.bash

# map and time step from the config, --map overrides the config map
if [ -z "$MAP" ]; then
    MAP=$(python3 -c "import runpy; print(runpy.run_path('$CONFIG')['MAP'])")
fi
DT=$(python3 -c "import runpy; print(runpy.run_path('$CONFIG')['DT'])")
# the bridge takes a town name or a path to an .xodr file
TOWN=${MAP#xodr:}
echo "map $MAP, dt $DT"

# fail early, before carla takes a minute to boot
if [ "$TEST" = false ] && ! ros2 pkg executables platoon_control | grep -q platoon_node; then
    echo "error: platoon_node is not built yet, use --test for now"
    exit 1
fi

# on exit or ctrl-c stop what we started, newest first (bridge before carla)
PIDS=""
stop_all() {
    for pid in $PIDS; do
        # the minus sign targets the whole process group, so child processes stop too
        kill -INT -- -$pid 2>/dev/null
        sleep 3
        kill -KILL -- -$pid 2>/dev/null
    done
    echo "stopped"
}
trap stop_all EXIT

# retries a check command every second, gives up after 60 s
wait_for() {
    name=$1
    shift
    SECONDS=0
    while [ $SECONDS -lt 60 ]; do
        if "$@" > /dev/null 2>&1; then
            echo "$name ready"
            return 0
        fi
        sleep 1
    done
    echo "error: $name not ready after 60 s, see logs/$name.log"
    exit 1
}

CARLA_CHECK="import carla; c = carla.Client('localhost', 2000); c.set_timeout(1.0); c.get_server_version()"

# carla server, headless unless --window
if [ "$NO_CARLA" = false ]; then
    if python3 -c "$CARLA_CHECK" > /dev/null 2>&1; then
        echo "error: carla is already running, stop it or use --no-carla"
        exit 1
    fi
    CARLA_ARGS="-RenderOffScreen"
    if [ "$WINDOW" = true ]; then
        CARLA_ARGS=""
    fi
    # setsid puts it in its own process group so stop_all can stop all of it
    setsid "$CARLA_DIR/CarlaUE4.sh" $CARLA_ARGS > logs/carla.log 2>&1 &
    PIDS="$! $PIDS"
    wait_for carla python3 -c "$CARLA_CHECK"
    # carla answers before it can load a new town, loading too early kills the bridge
    sleep 15
fi

# ros bridge, it loads the map and is the only one that calls world.tick()
# to add another background process later, copy this block
if [ "$NO_CARLA" = false ]; then
    setsid ros2 launch carla_ros_bridge carla_ros_bridge.launch.py \
        town:=$TOWN timeout:=30 fixed_delta_seconds:=$DT \
        synchronous_mode:=True use_sim_time:=True > logs/bridge.log 2>&1 &
    PIDS="$! $PIDS"
    # wait for a real /clock message, topic list can show stale topics from old runs
    wait_for bridge timeout 3 ros2 topic echo --once /clock
fi

# spawn check with --test, otherwise the platoon node
if [ "$TEST" = true ]; then
    echo "spawn check running, log in logs/spawn_check.log"
    python3 src/platoon_control/platoon_control/world_setup.py $CONFIG $MAP > logs/spawn_check.log 2>&1
    cat logs/spawn_check.log
else
    echo "platoon node running, log in logs/platoon_node.log"
    ros2 run platoon_control platoon_node --ros-args -p config:=$CONFIG > logs/platoon_node.log 2>&1
fi
echo "run finished"
