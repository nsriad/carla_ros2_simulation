#!/bin/bash

# Define common paths to keep the script clean
BASE_DIR="../data/multimodal_dataset_20260713_191320"
CLEAN_CSV="$BASE_DIR/merged_cam_lid_gt_yolo26x_patch.csv"

echo "=========================================="
echo "1. GENERATING ABLATION DATASETS"
echo "=========================================="

# A. Camera Dropout Only
python3 fusion/inject_sensor_faults.py \
  --merged_csv $CLEAN_CSV \
  --output_csv $BASE_DIR/patch_cam_drop.csv \
  --dropout_prob_camera 0.4

# B. LiDAR Dropout Only
python3 fusion/inject_sensor_faults.py \
  --merged_csv $CLEAN_CSV \
  --output_csv $BASE_DIR/patch_lidar_drop.csv \
  --dropout_prob_lidar 0.4

# C. Both Sensors Dropout (Simultaneous)
python3 fusion/inject_sensor_faults.py \
  --merged_csv $CLEAN_CSV \
  --output_csv $BASE_DIR/patch_both_drop.csv \
  --dropout_prob_camera 0.4 --dropout_prob_lidar 0.4

# D. LiDAR Noise Only
python3 fusion/inject_sensor_faults.py \
  --merged_csv $CLEAN_CSV \
  --output_csv $BASE_DIR/patch_lidar_noise.csv \
  --noise_std_lidar 0.3


echo "=========================================="
echo "2. TRAINING MLP FUSION MODELS"
echo "=========================================="

# 0. Train Baseline (Clean)
python3 fusion/train_mlp_fusion.py \
  --merged_csv $CLEAN_CSV \
  --loss mse --no_diff \
  --output_dir $BASE_DIR/processed_fusion_clean

# A. Train Camera Dropout Model
python3 fusion/train_mlp_fusion.py \
  --merged_csv $BASE_DIR/patch_cam_drop.csv \
  --loss mse --no_diff \
  --output_dir $BASE_DIR/processed_fusion_cam_drop

# B. Train LiDAR Dropout Model
python3 fusion/train_mlp_fusion.py \
  --merged_csv $BASE_DIR/patch_lidar_drop.csv \
  --loss mse --no_diff \
  --output_dir $BASE_DIR/processed_fusion_lidar_drop

# C. Train Both Dropout Model
python3 fusion/train_mlp_fusion.py \
  --merged_csv $BASE_DIR/patch_both_drop.csv \
  --loss mse --no_diff \
  --output_dir $BASE_DIR/processed_fusion_both_drop

# D. Train LiDAR Noise Model
python3 fusion/train_mlp_fusion.py \
  --merged_csv $BASE_DIR/patch_lidar_noise.csv \
  --loss mse --no_diff \
  --output_dir $BASE_DIR/processed_fusion_lidar_noise

echo "=========================================="
echo "3. COMPILING RESULTS TO CSV"
echo "=========================================="
python3 fusion/extract_metrics.py --base_dir $BASE_DIR

echo "=========================================="
echo "All training runs complete!"
echo "=========================================="