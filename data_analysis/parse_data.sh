#!/bin/bash

# check if the user provided the datetime argument
if [ -z "$1" ]; then
    echo "Error: No datetime provided."
    echo "Usage: ./parse_data.sh 20260617_103550"
    exit 1
fi

DATETIME=$1
DATASET_NAME="multimodal_dataset_${DATETIME}"
# DATASET_NAME="${DATETIME}"

echo "====================================================="
echo " Starting Data Parsing for: $DATASET_NAME"
echo "====================================================="

echo "[1/4] Parsing Camera Data..."
python3 parsers/camera_parser.py "$DATASET_NAME"

echo "[2/4] Parsing LiDAR Data..."
python3 parsers/lidar_parser.py "$DATASET_NAME"

echo "[3/4] Parsing IMU & GNSS Data..."
python3 parsers/imu_gnss_parser.py "$DATASET_NAME"

echo "====================================================="
echo " Parsing Complete! Run ./post_process.sh $DATETIME to visualize."
echo "====================================================="
