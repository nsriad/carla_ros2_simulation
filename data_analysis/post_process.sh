#!/bin/bash

# check if the user provided the datetime argument
if [ -z "$1" ]; then
    echo "Error: No datetime provided."
    echo "Usage: ./post_process.sh 20260617_103550"
    exit 1
fi

DATETIME=$1
# DATASET_NAME="multimodal_dataset_${DATETIME}"
DATASET_NAME="${DATETIME}"

echo "====================================================="
echo " Starting Post-Processing for: $DATASET_NAME"
echo "====================================================="

echo "[1/3] Generating Camera GIF..."
python3 generate_cam_gif.py "$DATASET_NAME"

echo "[2/3] Generating LiDAR Animation..."
python3 lidar_animator.py "$DATASET_NAME"

echo "[3/3] Running LiDAR Visualizer..."
python3 lidar_visualizer.py "$DATASET_NAME"

# echo "[4/4] Running Headway Analysis..."
# python3 headway_analysis.py "$DATASET_NAME"

echo "====================================================="
echo " Post-Processing Complete!"
echo "====================================================="
